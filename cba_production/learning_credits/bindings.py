"""Bind enrolled learners to explicit approved credit-plan versions."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import CourseCreditPlan, CourseCreditPlanBinding


def _has_active_enrollment(*, learner, course_key):
    from django.apps import apps

    enrollment = apps.get_model("student", "CourseEnrollment")
    return enrollment.objects.filter(
        user_id=learner.pk,
        course_id=course_key,
        is_active=True,
    ).exists()


def bind_credit_plan(*, learner, plan_id, source_event_id=""):
    """Internal operation; never silently select or replace a plan version."""
    with transaction.atomic():
        stored_learner = get_user_model().objects.select_for_update().get(
            pk=learner.pk,
        )
        plan = CourseCreditPlan.objects.get(pk=plan_id)

        existing = CourseCreditPlanBinding.objects.filter(
            learner=stored_learner, course_key=plan.course_key,
        ).first()
        if existing is not None:
            if existing.plan_id != plan.pk:
                raise ValidationError(
                    "The learner is already bound to another plan version."
                )
            return existing, False

        if not stored_learner.is_active:
            raise ValidationError("The learner must be active.")
        if plan.status != CourseCreditPlan.Status.APPROVED:
            raise ValidationError("Binding requires an approved plan.")
        if not _has_active_enrollment(
            learner=stored_learner, course_key=plan.course_key,
        ):
            raise ValidationError("An active course enrollment is required.")

        binding = CourseCreditPlanBinding.objects.create(
            learner=stored_learner,
            plan=plan,
            course_key=plan.course_key,
            plan_snapshot=plan.snapshot,
            source_event_id=source_event_id,
        )
        return binding, True
