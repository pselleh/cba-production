"""Permission-controlled learning-credit operations."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from .models import CourseCreditPlan


APPROVAL_PERMISSION = "cba_learning_credits.approve_course_credit_plan"


def approve_credit_plan(*, plan_id, approver):
    if not (
        approver
        and approver.is_authenticated
        and approver.is_active
        and approver.has_perm(APPROVAL_PERMISSION)
    ):
        raise PermissionDenied("Credit-plan approval permission is required.")

    with transaction.atomic():
        plan = CourseCreditPlan.objects.select_for_update().get(pk=plan_id)

        try:
            key = CourseKey.from_string(plan.course_key)
        except (InvalidKeyError, TypeError, ValueError) as exc:
            raise ValidationError("A valid course key is required.") from exc
        if str(key) != plan.course_key:
            raise ValidationError("Use the canonical course key.")

        if plan.status == CourseCreditPlan.Status.APPROVED:
            return plan

        plan.status = CourseCreditPlan.Status.APPROVED
        plan.approved_by = approver
        plan.approved_at = timezone.now()
        plan.save()
        return plan
