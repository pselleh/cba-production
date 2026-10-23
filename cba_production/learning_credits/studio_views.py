"""Studio controls scoped to course authors and authorized approvers."""

from copy import deepcopy

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from .models import CourseCreditPlan
from .services import APPROVAL_PERMISSION, approve_credit_plan
from .studio_forms import CreditPlanForm, RequirementFormSet, requirement_initial


def _can_author_course(user, key):
    if user.is_superuser:
        return True
    from common.djangoapps.student.roles import CourseInstructorRole, CourseStaffRole
    return CourseInstructorRole(key).has_user(user) or CourseStaffRole(key).has_user(user)


def _course_activities(key):
    from xmodule.modulestore.django import modulestore
    store = modulestore()
    course = store.get_course(key)
    if course is None:
        raise Http404("Course not found.")
    activities = []
    for block in store.get_items(key):
        if block.category in {"course", "chapter", "sequential", "vertical"}:
            continue
        activities.append({
            "key": str(block.location), "type": block.category,
            "label": f"{block.display_name_with_default} ({block.category})",
        })
    return str(course.display_name_with_default), sorted(activities, key=lambda item: (item["label"], item["key"]))


def _authorize(request, course_key):
    try:
        key = CourseKey.from_string(course_key)
    except (InvalidKeyError, ValueError, TypeError) as exc:
        raise Http404("Invalid course identifier.") from exc
    if str(key) != course_key:
        raise Http404("Use the canonical course identifier.")
    if not request.user.is_active or not _can_author_course(request.user, key):
        raise PermissionDenied("Course author access is required.")
    return _course_activities(key)


def _page_url(course_key):
    return reverse("cba_learning_credits_studio:course", kwargs={"course_key": course_key})


def _courses_for_author(user):
    from xmodule.modulestore.django import modulestore
    result = []
    for course in modulestore().get_courses():
        key = course.id
        if _can_author_course(user, key):
            result.append({"key": str(key), "title": str(course.display_name_with_default)})
    return sorted(result, key=lambda item: (item["title"], item["key"]))


@never_cache
@require_GET
@login_required
def credit_courses(request):
    if not request.user.is_active:
        raise PermissionDenied("An active account is required.")
    return render(request, "cba_learning_credits/studio_courses.html", {
        "courses": _courses_for_author(request.user),
    })


@never_cache
@require_http_methods(["GET", "POST"])
@login_required
@csrf_protect
@transaction.atomic
def course_credit_plans(request, course_key):
    title, activities = _authorize(request, course_key)
    plans = CourseCreditPlan.objects.filter(course_key=course_key).order_by("-version")
    next_version = (plans.aggregate(value=Max("version"))["value"] or 0) + 1
    selected = request.POST.get("plan_id") if request.method == "POST" else request.GET.get("edit")
    instance = CourseCreditPlan(course_key=course_key, version=next_version)
    if selected:
        try:
            instance = get_object_or_404(plans.select_for_update(), pk=int(selected))
        except (ValueError, TypeError) as exc:
            raise Http404("Plan not found.") from exc
    elif request.method == "GET" and request.GET.get("copy"):
        try:
            original = get_object_or_404(plans, pk=int(request.GET["copy"]))
        except (ValueError, TypeError) as exc:
            raise Http404("Plan not found.") from exc
        for name in CreditPlanForm.Meta.fields:
            if name != "version":
                setattr(instance, name, deepcopy(getattr(original, name)))
        instance.activity_requirements = deepcopy(original.activity_requirements)

    readonly = instance.status == CourseCreditPlan.Status.APPROVED
    if request.method == "POST" and readonly:
        raise PermissionDenied("Approved plans are locked. Create a new version.")
    data = request.POST if request.method == "POST" else None
    formset = RequirementFormSet(
        data, prefix="requirements", initial=requirement_initial(instance.activity_requirements),
        form_kwargs={"activities": activities},
    )
    if data is not None:
        rules_valid = formset.is_valid()
        if rules_valid:
            instance.activity_requirements = [
                row.rule() for row in formset.forms
                if row.cleaned_data and not row.cleaned_data.get("DELETE")
            ]
    else:
        rules_valid = True
    form = CreditPlanForm(data, instance=instance, activities=activities)
    totals = instance.credit_totals if data is None else None
    if data is not None:
        valid = form.is_valid()
        action = request.POST.get("action")
        if action not in {"save", "preview"}:
            form.add_error(None, "Choose Save draft or Preview credits.")
            valid = False
        if valid and rules_valid:
            totals = form.instance.credit_totals
            if action == "save":
                plan = form.save()
                return redirect(_page_url(course_key) + f"?edit={plan.pk}")
    return render(request, "cba_learning_credits/studio.html", {
        "course_key": course_key, "course_title": title, "form": form,
        "requirements": formset, "plans": plans, "selected_plan": instance,
        "totals": totals, "readonly": readonly,
        "can_approve": request.user.has_perm(APPROVAL_PERMISSION),
    })


@never_cache
@require_POST
@login_required
@csrf_protect
def approve_plan(request, course_key, plan_id):
    title, activities = _authorize(request, course_key)
    plan = get_object_or_404(CourseCreditPlan, course_key=course_key, pk=plan_id)
    if not request.user.has_perm(APPROVAL_PERMISSION):
        raise PermissionDenied("Credit-plan approval permission is required.")
    try:
        available = {item["key"] for item in activities}
        if not set(plan.required_block_keys) <= available:
            raise ValidationError("A required activity no longer exists in this course. Update the draft first.")
        approve_credit_plan(plan_id=plan.pk, approver=request.user)
    except ValidationError as exc:
        return render(request, "cba_learning_credits/approval_error.html", {
            "messages": exc.messages, "back_url": _page_url(course_key) + f"?edit={plan.pk}",
        }, status=400)
    return redirect(_page_url(course_key) + f"?edit={plan.pk}")


@never_cache
@require_GET
@login_required
def export_plan(request, course_key, plan_id):
    _authorize(request, course_key)
    plan = get_object_or_404(CourseCreditPlan, course_key=course_key, pk=plan_id)
    totals = plan.credit_totals
    response = JsonResponse({
        "schema_version": "cba-credit-plan-v1", "course_key": course_key,
        "approval": {
            "approved_by_id": plan.approved_by_id,
            "approved_at": plan.approved_at.isoformat() if plan.approved_at else None,
        },
        "credit_plan": {
            "version": plan.version, "status": plan.status,
            "activity_minutes": plan.activity_minutes,
            "instructional_design_reference": plan.instructional_design_reference,
            "learning_outcomes": plan.learning_outcomes,
            "required_block_keys": plan.required_block_keys,
            "activity_requirements": plan.activity_requirements,
        },
        "credit_preview": {
            "eligible_minutes": totals.eligible_minutes,
            "pdu": str(totals.pdu) if totals.pdu is not None else None,
            "ceu": str(totals.ceu) if totals.ceu is not None else None,
            "policy_version": totals.policy_version,
        },
    })
    response["Content-Disposition"] = f'attachment; filename="credit-plan-{plan.pk}-v{plan.version}.json"'
    return response
