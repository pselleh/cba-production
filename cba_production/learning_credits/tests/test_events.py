from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from cba_production.learning_credits.events import (
    handle_enrollment, handle_grade,
)
from cba_production.learning_credits.models import (
    CourseCreditPlan, CreditProcessingRequest,
)


@override_settings(CBA_LEARNING_CREDITS_EVENTS_ENABLED=True)
class CreditEventTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="event-learner", password=None,
        )
        self.course_key = "course-v1:CBA+TEST+2027"
        self.plan = CourseCreditPlan.objects.create(
            course_key=self.course_key,
            status=CourseCreditPlan.Status.APPROVED,
            instruction_minutes=60,
            assignments_minutes=0,
            assessments_minutes=0,
            discussions_minutes=0,
            other_minutes=0,
            instructional_design_reference="IDP-TEST",
            learning_outcomes=["Assess risk."],
            required_block_keys=[
                "block-v1:CBA+TEST+2027+type@html+block@instruction",
            ],
            approved_by=self.user,
            approved_at=timezone.now(),
        )
        self.enrollment = SimpleNamespace(
            user=SimpleNamespace(id=self.user.pk, is_active=True),
            course=SimpleNamespace(course_key=self.course_key),
            is_active=True,
            creation_date=timezone.now(),
        )
        self.metadata = SimpleNamespace(id="enrollment-event-123")
        self.mapping = override_settings(
            CBA_LEARNING_CREDIT_PLAN_VERSIONS={self.course_key: 1},
        )
        self.mapping.enable()
        self.addCleanup(self.mapping.disable)

    def enqueue(self):
        handle_enrollment(
            enrollment=self.enrollment, metadata=self.metadata,
        )

    def test_enrollment_captures_explicit_plan(self):
        self.enqueue()
        request = CreditProcessingRequest.objects.get()
        self.assertEqual(request.plan_id, self.plan.pk)
        self.assertEqual(request.learner_id, self.user.pk)
        self.assertEqual(request.action, "bind")
        self.assertEqual(request.status, "pending")

    def test_duplicate_event_does_not_duplicate_request(self):
        self.enqueue()
        self.enqueue()
        self.assertEqual(CreditProcessingRequest.objects.count(), 1)

    @override_settings(CBA_LEARNING_CREDITS_EVENTS_ENABLED=False)
    def test_disabled_handlers_create_no_requests(self):
        self.enqueue()
        self.assertFalse(CreditProcessingRequest.objects.exists())

    def test_inactive_enrollment_is_ignored(self):
        self.enrollment.is_active = False
        self.enqueue()
        self.assertFalse(CreditProcessingRequest.objects.exists())

    @override_settings(CBA_LEARNING_CREDIT_PLAN_VERSIONS={})
    def test_unconfigured_course_is_not_bound(self):
        self.enqueue()
        self.assertFalse(CreditProcessingRequest.objects.exists())

    def test_plan_approved_after_enrollment_is_not_selected(self):
        self.enrollment.creation_date = self.plan.approved_at - timedelta(
            days=1,
        )
        self.enqueue()
        self.assertFalse(CreditProcessingRequest.objects.exists())

    def test_grade_uses_previously_captured_plan(self):
        self.enqueue()
        grade = SimpleNamespace(
            user_id=self.user.pk,
            course=SimpleNamespace(course_key=self.course_key),
        )
        with override_settings(
            CBA_LEARNING_CREDIT_PLAN_VERSIONS={self.course_key: 99},
        ):
            handle_grade(
                grade=grade,
                metadata=SimpleNamespace(id="grade-event-123"),
            )
        request = CreditProcessingRequest.objects.get(action="check")
        self.assertEqual(request.plan_id, self.plan.pk)

    def test_rolled_back_enrollment_does_not_leave_request(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.enqueue()
                raise RuntimeError("Rollback test")
        self.assertFalse(CreditProcessingRequest.objects.exists())
