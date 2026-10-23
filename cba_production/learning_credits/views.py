"""Private, read-only learner credit records."""

from django.contrib.auth.decorators import login_required
from django.core.paginator import InvalidPage, Paginator
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .models import CourseCreditAward


def _credit_record(user, page_number):
    number = int(page_number)
    if number < 1:
        raise ValueError("Page must be positive.")

    queryset = CourseCreditAward.objects.filter(
        learner=user,
    ).order_by("-awarded_at", "-pk")
    paginator = Paginator(queryset, 50)
    page = paginator.page(number)

    return {
        "count": paginator.count,
        "page": page.number,
        "pages": paginator.num_pages,
        "previous_page": (
            page.previous_page_number() if page.has_previous() else None
        ),
        "next_page": page.next_page_number() if page.has_next() else None,
        "results": [
            {
                "id": award.pk,
                "course_key": award.course_key,
                "eligible_minutes": award.eligible_minutes,
                "pdu": format(award.pdu, ".4f"),
                "ceu": format(award.ceu, ".4f"),
                "verified_at": award.completed_at.isoformat(),
                "awarded_at": award.awarded_at.isoformat(),
                "plan_version": award.plan_snapshot["version"],
                "policy_version": award.policy_version,
            }
            for award in page.object_list
        ],
    }


@never_cache
@require_GET
def learner_credit_record(request):
    if not (
        request.user.is_authenticated and request.user.is_active
    ):
        return JsonResponse({"detail": "Authentication required."}, status=401)
    try:
        record = _credit_record(
            request.user, request.GET.get("page", "1"),
        )
    except (ValueError, TypeError):
        return JsonResponse({"detail": "Invalid page."}, status=400)
    except InvalidPage:
        return JsonResponse({"detail": "Page not found."}, status=404)
    return JsonResponse(record)


@never_cache
@require_GET
@login_required
def learner_credit_page(request):
    if not request.user.is_active:
        return HttpResponseForbidden("An active account is required.")
    try:
        record = _credit_record(
            request.user, request.GET.get("page", "1"),
        )
    except (ValueError, TypeError, InvalidPage) as exc:
        raise Http404("Credit record page not found.") from exc
    return render(
        request,
        "cba_learning_credits/record.html",
        {"record": record},
    )
