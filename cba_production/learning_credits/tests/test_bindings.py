from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from cba_production.learning_credits.bindings import bind_credit_plan
from cba_production.learning_credits.models import (
    CourseCreditPlan, CourseCreditPlanBinding,
)


class CreditPlanBindingTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.learner = users.objects.create_user(
            username="bound-learner", password=None,
        )
        self.approver = users.objects.create_user(
            username="binding-approver", password=None,
        )
        self.plan = CourseCreditPlan.objects.create(
            course_key="course-v1:CBA+TEST+2027",
            status=CourseCreditPlan.Status.APPROVED,
            instruction_minutes=60,
            assignments_minutes=0,
            assessments_minutes=0,
            discussions_minutes=0,
            other_minutes=0,
            instructional_design_reference="IDP-TEST-v1",
            learning_outcomes=["Assess risk."],
            required_block_keys=[
                "block-v1:CBA+TEST+2027+type@html+block@instruction",
            ],
            approved_by=self.approver,
            approved_at=timezone.now(),
        )
        enrollment = patch(
            "cba_production.learning_credits.bindings._has_active_enrollment",
            return_value=True,
        )
        self.enrollment = enrollment.start()
        self.addCleanup(enrollment.stop)

    def bind(self):
        return bind_credit_plan(
            learner=self.learner,
            plan_id=self.plan.pk,
            source_event_id="enrollment-event",
        )

    def test_binding_preserves_explicit_plan_and_snapshot(self):
        binding, created = self.bind()
        self.assertTrue(created)
        self.assertEqual(binding.plan_id, self.plan.pk)
        self.assertEqual(binding.plan_snapshot, self.plan.snapshot)
        self.assertEqual(binding.source_event_id, "enrollment-event")
        self.enrollment.assert_called_once_with(
            learner=self.learner, course_key=self.plan.course_key,
        )

    def test_repeated_binding_preserves_original_time(self):
        first, _ = self.bind()
        second, created = self.bind()
        self.assertFalse(created)
        self.assertEqual(second.pk, first.pk)
        self.assertEqual(second.bound_at, first.bound_at)

    def test_later_version_cannot_replace_binding(self):
        self.bind()
        replacement = CourseCreditPlan.objects.get(pk=self.plan.pk)
        replacement.pk = None
        replacement.version = 2
        replacement.save()
        with self.assertRaises(ValidationError):
            bind_credit_plan(
                learner=self.learner, plan_id=replacement.pk,
            )
        self.assertEqual(
            CourseCreditPlanBinding.objects.get().plan_id, self.plan.pk,
        )

    def test_draft_plan_cannot_be_bound(self):
        draft = CourseCreditPlan.objects.create(
            course_key="course-v1:CBA+DRAFT+2027",
        )
        with self.assertRaises(ValidationError):
            bind_credit_plan(learner=self.learner, plan_id=draft.pk)

    def test_enrollment_is_required(self):
        self.enrollment.return_value = False
        with self.assertRaises(ValidationError):
            self.bind()
        self.assertFalse(CourseCreditPlanBinding.objects.exists())

    def test_inactive_learner_cannot_be_bound(self):
        self.learner.is_active = False
        self.learner.save()
        with self.assertRaises(ValidationError):
            self.bind()

    def test_existing_binding_cannot_be_edited_through_save(self):
        binding, _ = self.bind()
        binding.source_event_id = "replacement"
        with self.assertRaises(ValidationError):
            binding.save()
