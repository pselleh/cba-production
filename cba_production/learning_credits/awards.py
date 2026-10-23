"""Internal award operations using approved plans and LMS evidence."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .activity_evidence import collect_activity_evidence
from .completion import missing_required_blocks
from .grades import currently_passing
from .models import (
    CourseCreditAward, CourseCreditPlan, CourseCreditPlanBinding,
)


def award_course_credits(*, learner, plan_id, source_event_id=""):
    """Return (award, created); completed_at is the verification time.

    Internal service only. Plan selection and activity-specific evidence
    must be established before exposing an automatic award workflow.
    """
    if learner.pk is None:
        raise ValidationError("A saved learner is required.")

    with transaction.atomic():
        # Serialize award attempts even when callers supply different
        # plan versions for the same learner and course.
        stored_learner = get_user_model().objects.select_for_update().get(
            pk=learner.pk
        )
        plan = CourseCreditPlan.objects.get(pk=plan_id)

        existing = CourseCreditAward.objects.filter(
            learner=stored_learner, course_key=plan.course_key
        ).first()
        if existing is not None:
            return existing, False

        if not stored_learner.is_active:
            raise ValidationError("The learner must be active.")
        if plan.status != CourseCreditPlan.Status.APPROVED:
            raise ValidationError("Credits require an approved plan.")

        snapshot = plan.snapshot
        binding = CourseCreditPlanBinding.objects.filter(
            learner=stored_learner, course_key=plan.course_key,
        ).first()
        if binding is None or binding.plan_id != plan.pk:
            raise ValidationError(
                "The learner must be bound to this approved plan version."
            )
        if binding.plan_snapshot != snapshot:
            raise ValidationError(
                "The approved plan differs from the learner's bound snapshot."
            )

        if not currently_passing(
            learner=stored_learner, course_key=plan.course_key
        ):
            raise ValidationError("A current passing course grade is required.")

        missing = missing_required_blocks(
            learner=stored_learner, plan=plan
        )
        if missing:
            raise ValidationError({
                "required_block_keys": [
                    "Required activity is incomplete: " + key
                    for key in missing
                ],
            })

        activity_evidence = collect_activity_evidence(
            learner=stored_learner, plan=plan,
        )
        totals = plan.credit_totals
        award = CourseCreditAward.objects.create(
            learner=stored_learner,
            plan=plan,
            course_key=plan.course_key,
            completed_at=timezone.now(),
            eligible_minutes=totals.eligible_minutes,
            pdu=totals.pdu,
            ceu=totals.ceu,
            policy_version=plan.policy_version,
            plan_snapshot=snapshot,
            activity_evidence=activity_evidence,
            source_event_id=source_event_id,
        )
        return award, True
