"""Capture credit processing requests without awarding inside LMS events."""

from uuid import uuid4

from django.conf import settings

from .models import (
    CourseCreditPlan,
    CourseCreditPlanBinding,
    CreditProcessingRequest,
)


def _event_id(metadata):
    return str(getattr(metadata, "id", None) or uuid4())


def _captured_plan_id(learner_id, course_key):
    binding = CourseCreditPlanBinding.objects.filter(
        learner_id=learner_id, course_key=course_key,
    ).first()
    if binding is not None:
        return binding.plan_id

    request = CreditProcessingRequest.objects.filter(
        learner_id=learner_id,
        course_key=course_key,
        action=CreditProcessingRequest.Action.BIND,
    ).order_by("created_at", "pk").first()
    return request.plan_id if request is not None else None


def _enqueue(*, learner_id, course_key, plan_id, action, metadata):
    return CreditProcessingRequest.objects.get_or_create(
        learner_id=learner_id,
        course_key=course_key,
        action=action,
        source_event_id=_event_id(metadata),
        defaults={"plan_id": plan_id},
    )


def handle_enrollment(sender=None, enrollment=None, metadata=None, **kwargs):
    if not getattr(settings, "CBA_LEARNING_CREDITS_EVENTS_ENABLED", False):
        return
    if (
        enrollment is None
        or not enrollment.is_active
        or not enrollment.user.is_active
    ):
        return

    learner_id = enrollment.user.id
    course_key = str(enrollment.course.course_key)
    plan_id = _captured_plan_id(learner_id, course_key)

    if plan_id is None:
        versions = getattr(
            settings, "CBA_LEARNING_CREDIT_PLAN_VERSIONS", {},
        )
        version = versions.get(course_key)
        if type(version) is not int or version < 1:
            return

        # Select an explicit version, never the latest approved plan.
        # Do not retroactively bind a plan approved after enrollment.
        plan = CourseCreditPlan.objects.filter(
            course_key=course_key,
            version=version,
            status=CourseCreditPlan.Status.APPROVED,
            approved_at__lte=enrollment.creation_date,
        ).first()
        if plan is None:
            return
        plan_id = plan.pk

    _enqueue(
        learner_id=learner_id,
        course_key=course_key,
        plan_id=plan_id,
        action=CreditProcessingRequest.Action.BIND,
        metadata=metadata,
    )


def handle_grade(sender=None, grade=None, metadata=None, **kwargs):
    if not getattr(settings, "CBA_LEARNING_CREDITS_EVENTS_ENABLED", False):
        return
    if grade is None:
        return

    course_key = str(grade.course.course_key)
    plan_id = _captured_plan_id(grade.user_id, course_key)
    if plan_id is None:
        return

    _enqueue(
        learner_id=grade.user_id,
        course_key=course_key,
        plan_id=plan_id,
        action=CreditProcessingRequest.Action.CHECK,
        metadata=metadata,
    )


def register_handlers():
    from openedx_events.learning.signals import (
        COURSE_ENROLLMENT_CHANGED,
        COURSE_ENROLLMENT_CREATED,
        PERSISTENT_GRADE_SUMMARY_CHANGED,
    )

    for signal in (COURSE_ENROLLMENT_CREATED, COURSE_ENROLLMENT_CHANGED):
        signal.connect(
            handle_enrollment,
            dispatch_uid="cba.learning_credits.enrollment",
            weak=False,
        )
    PERSISTENT_GRADE_SUMMARY_CHANGED.connect(
        handle_grade,
        dispatch_uid="cba.learning_credits.grade",
        weak=False,
    )
