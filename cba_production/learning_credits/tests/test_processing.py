from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from cba_production.learning_credits.models import (
    CourseCreditPlan,
    CourseCreditPlanBinding,
    CreditProcessingRequest,
)
from cba_production.learning_credits.processing import process_credit_request


class CreditProcessingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="processing-learner", password=None,
        )
        self.plan = CourseCreditPlan.objects.create(
            course_key="course-v1:CBA+TEST+2027",
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
        self.request = CreditProcessingRequest.objects.create(
            learner=self.user,
            plan=self.plan,
            course_key=self.plan.course_key,
            action="bind",
            source_event_id="processing-event",
        )

        for name, value in (
            ("_has_active_enrollment", True),
            ("bind_credit_plan", (None, True)),
            ("award_course_credits", (None, True)),
        ):
            patcher = patch(
                "cba_production.learning_credits.processing." + name,
                return_value=value,
            )
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

        patcher = patch(
            "cba_production.learning_credits.processing.logger"
        )
        self.logger = patcher.start()
        self.addCleanup(patcher.stop)

    def process(self):
        result = process_credit_request(self.request.pk)
        self.request.refresh_from_db()
        return result

    def make_due(self):
        self.request.next_attempt_at = timezone.now() - timedelta(seconds=1)
        self.request.save()

    def test_bind_request_binds_then_checks_award(self):
        self.assertEqual(self.process(), "done")
        self.bind_credit_plan.assert_called_once_with(
            learner=self.user,
            plan_id=self.plan.pk,
            source_event_id="processing-event",
        )
        self.award_course_credits.assert_called_once()
        self.assertEqual(self.request.attempts, 1)
        self.assertIsNotNone(self.request.processed_at)

    def test_check_request_does_not_rebind(self):
        self.request.action = "check"
        self.request.save()
        self.assertEqual(self.process(), "done")
        self.bind_credit_plan.assert_not_called()
        self.award_course_credits.assert_called_once()

    def test_incomplete_award_preserves_successful_binding(self):
        def create_binding(**kwargs):
            binding = CourseCreditPlanBinding.objects.create(
                learner=self.user,
                plan=self.plan,
                course_key=self.plan.course_key,
                plan_snapshot=self.plan.snapshot,
            )
            return binding, True

        self.bind_credit_plan.side_effect = create_binding
        self.award_course_credits.side_effect = ValidationError(
            "Required activity is incomplete."
        )
        self.assertEqual(self.process(), "pending")
        self.assertTrue(CourseCreditPlanBinding.objects.exists())
        self.assertGreater(self.request.next_attempt_at, timezone.now())
        self.assertIsNone(self.request.processed_at)

    def test_technical_failure_is_retained_for_retry(self):
        self.award_course_credits.side_effect = RuntimeError("Temporary error")
        self.assertEqual(self.process(), "pending")
        self.assertEqual(
            self.request.last_error, "Technical failure: RuntimeError"
        )
        self.assertGreater(self.request.next_attempt_at, timezone.now())
        self.logger.exception.assert_called_once()

    def test_completed_request_is_not_processed_twice(self):
        self.process()
        self.assertEqual(self.process(), "skipped")
        self.award_course_credits.assert_called_once()
        self.assertEqual(self.request.attempts, 1)

    def test_future_request_is_skipped(self):
        self.request.next_attempt_at = timezone.now() + timedelta(hours=1)
        self.request.save()
        self.assertEqual(self.process(), "skipped")
        self.bind_credit_plan.assert_not_called()
        self.award_course_credits.assert_not_called()

    def test_course_plan_mismatch_is_failed_without_award(self):
        self.request.course_key = "course-v1:CBA+OTHER+2027"
        self.request.save()
        self.assertEqual(self.process(), "failed")
        self.award_course_credits.assert_not_called()

    def test_unknown_action_is_failed_without_award(self):
        self.request.action = "unknown"
        self.request.save()
        self.assertEqual(self.process(), "failed")
        self.award_course_credits.assert_not_called()

    def test_later_success_finishes_pending_request(self):
        self.award_course_credits.side_effect = [
            ValidationError("Not complete yet."),
            (None, True),
        ]
        self.assertEqual(self.process(), "pending")
        self.make_due()
        self.assertEqual(self.process(), "done")
        self.assertEqual(self.request.attempts, 2)
        self.assertEqual(self.request.last_error, "")
