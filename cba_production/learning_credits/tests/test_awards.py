from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from cba_production.learning_credits.awards import award_course_credits
from cba_production.learning_credits.models import (
    CourseCreditAward, CourseCreditPlan,
)


class CreditAwardServiceTests(TestCase):
    def setUp(self):
        self.learner = get_user_model().objects.create_user(
            username="credit-learner", password=None,
        )
        self.approver = get_user_model().objects.create_user(
            username="credit-approver", password=None,
        )
        self.plan = CourseCreditPlan.objects.create(
            course_key="course-v1:CBA+TEST+2027",
            status=CourseCreditPlan.Status.APPROVED,
            instruction_minutes=60,
            assignments_minutes=0,
            assessments_minutes=30,
            discussions_minutes=0,
            other_minutes=0,
            instructional_design_reference="IDP-TEST-v1",
            learning_outcomes=["Assess a risk scenario."],
            required_block_keys=[
                "block-v1:CBA+TEST+2027+type@problem+block@assessment",
            ],
            approved_by=self.approver,
            approved_at=timezone.now(),
        )
        self.grade = patch(
            "cba_production.learning_credits.awards.currently_passing",
            return_value=True,
        )
        self.blocks = patch(
            "cba_production.learning_credits.awards.missing_required_blocks",
            return_value=[],
        )
        self.grade_mock = self.grade.start()
        self.blocks_mock = self.blocks.start()
        self.addCleanup(self.grade.stop)
        self.addCleanup(self.blocks.stop)

    def award(self, **kwargs):
        return award_course_credits(
            learner=self.learner, plan_id=self.plan.pk, **kwargs
        )

    def test_award_preserves_approved_values_and_snapshot(self):
        award, created = self.award(source_event_id="event-123")
        self.assertTrue(created)
        self.assertEqual(award.eligible_minutes, 90)
        self.assertEqual(award.pdu, Decimal("1.5000"))
        self.assertEqual(award.ceu, Decimal("0.1500"))
        self.assertEqual(award.plan_snapshot, self.plan.snapshot)
        self.assertEqual(award.source_event_id, "event-123")
        self.assertIsNotNone(award.completed_at)
        self.grade_mock.assert_called_once()
        self.blocks_mock.assert_called_once()

    def test_repeated_event_does_not_create_or_modify_award(self):
        first, _ = self.award(source_event_id="first")
        self.grade_mock.return_value = False
        second, created = self.award(source_event_id="retry")
        self.assertFalse(created)
        self.assertEqual(second.pk, first.pk)
        self.assertEqual(second.source_event_id, "first")
        self.assertEqual(second.completed_at, first.completed_at)
        self.assertEqual(CourseCreditAward.objects.count(), 1)

    def test_failing_grade_creates_no_award(self):
        self.grade_mock.return_value = False
        with self.assertRaises(ValidationError):
            self.award()
        self.assertFalse(CourseCreditAward.objects.exists())

    def test_incomplete_required_block_creates_no_award(self):
        self.blocks_mock.return_value = self.plan.required_block_keys
        with self.assertRaises(ValidationError):
            self.award()
        self.assertFalse(CourseCreditAward.objects.exists())

    def test_draft_plan_creates_no_award(self):
        draft = CourseCreditPlan.objects.create(
            course_key="course-v1:CBA+DRAFT+2027",
        )
        with self.assertRaises(ValidationError):
            award_course_credits(
                learner=self.learner, plan_id=draft.pk,
            )
        self.assertFalse(CourseCreditAward.objects.exists())

    def test_inactive_learner_creates_no_award(self):
        self.learner.is_active = False
        self.learner.save()
        with self.assertRaises(ValidationError):
            self.award()
        self.assertFalse(CourseCreditAward.objects.exists())

    def test_activity_evidence_cannot_be_replaced_by_block_views(self):
        for index, category in enumerate(
            ("assignments", "discussions", "other"), start=2
        ):
            with self.subTest(category=category):
                plan = CourseCreditPlan.objects.create(
                    course_key=self.plan.course_key,
                    version=index,
                    status=CourseCreditPlan.Status.APPROVED,
                    instruction_minutes=60,
                    assignments_minutes=5 if category == "assignments" else 0,
                    assessments_minutes=0,
                    discussions_minutes=5 if category == "discussions" else 0,
                    other_minutes=5 if category == "other" else 0,
                    instructional_design_reference="IDP-TEST",
                    learning_outcomes=["Assess risk."],
                    required_block_keys=self.plan.required_block_keys,
                    approved_by=self.approver,
                    approved_at=timezone.now(),
                )
                with self.assertRaises(ValidationError):
                    award_course_credits(
                        learner=self.learner, plan_id=plan.pk,
                    )
        self.assertFalse(CourseCreditAward.objects.exists())

    def test_activity_evidence_is_saved_with_award(self):
        evidence = [{
            "provider": "openassessment",
            "block_key": self.plan.required_block_keys[0],
            "submission_id": 12,
            "points_earned": 8,
            "points_possible": 10,
        }]
        with patch(
            "cba_production.learning_credits.awards.collect_activity_evidence",
            return_value=evidence,
        ):
            award, created = self.award()
        self.assertTrue(created)
        award.refresh_from_db()
        self.assertEqual(award.activity_evidence, evidence)
