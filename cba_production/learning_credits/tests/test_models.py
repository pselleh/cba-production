from copy import deepcopy
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from cba_production.learning_credits.models import (
    CourseCreditAward,
    CourseCreditPlan,
)


class CreditModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="credit-test", password=None,
        )

    def approved_plan(self):
        plan = CourseCreditPlan(
            course_key="course-v1:CBA+TEST+2027",
            instruction_minutes=60,
            assignments_minutes=15,
            assessments_minutes=10,
            discussions_minutes=5,
            other_minutes=0,
            instructional_design_reference="IDP-TEST-v1",
            required_block_keys=[
                "block-v1:CBA+TEST+2027+type@html+block@instruction",
            ],
            learning_outcomes=["Assess a documented risk scenario."],
            status=CourseCreditPlan.Status.APPROVED,
            approved_by=self.user,
            approved_at=timezone.now(),
        )
        plan.save()
        return plan

    def award(self, plan):
        totals = plan.credit_totals
        return CourseCreditAward(
            learner=self.user,
            plan=plan,
            course_key=plan.course_key,
            completed_at=timezone.now(),
            eligible_minutes=totals.eligible_minutes,
            pdu=totals.pdu,
            ceu=totals.ceu,
            policy_version=plan.policy_version,
            plan_snapshot=plan.snapshot,
        )

    def test_draft_can_have_unknown_minutes(self):
        plan = CourseCreditPlan.objects.create(
            course_key="course-v1:CBA+DRAFT+2027",
        )
        self.assertIsNone(plan.credit_totals.eligible_minutes)

    def test_incomplete_plan_cannot_be_approved(self):
        plan = CourseCreditPlan(
            course_key="course-v1:CBA+DRAFT+2027",
            status=CourseCreditPlan.Status.APPROVED,
        )
        with self.assertRaises(ValidationError):
            plan.save()
        self.assertEqual(CourseCreditPlan.objects.count(), 0)

    def test_approved_plan_cannot_be_edited_through_save(self):
        plan = self.approved_plan()
        plan.instruction_minutes = 120
        with self.assertRaises(ValidationError):
            plan.save()
        plan.refresh_from_db()
        self.assertEqual(plan.instruction_minutes, 60)

    def test_award_round_trip_preserves_credits_and_snapshot(self):
        plan = self.approved_plan()
        award = self.award(plan)
        award.save()
        award.refresh_from_db()
        self.assertEqual(award.eligible_minutes, 90)
        self.assertEqual(award.pdu, Decimal("1.5000"))
        self.assertEqual(award.ceu, Decimal("0.1500"))
        self.assertEqual(award.plan_snapshot, plan.snapshot)
        with self.assertRaises(ValidationError):
            award.save()

    def test_database_rejects_duplicate_learner_course_awards(self):
        plan = self.approved_plan()
        self.award(plan).save()
        duplicate = self.award(plan)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CourseCreditAward.objects.bulk_create([duplicate])
        self.assertEqual(CourseCreditAward.objects.count(), 1)

    def test_draft_plan_cannot_support_award(self):
        plan = CourseCreditPlan.objects.create(
            course_key="course-v1:CBA+DRAFT+2027",
        )
        award = CourseCreditAward(plan=plan)
        with self.assertRaises(ValidationError):
            award.clean()

    def test_altered_credit_values_are_rejected(self):
        award = self.award(self.approved_plan())
        award.pdu = Decimal("99.0000")
        with self.assertRaises(ValidationError):
            award.save()

    def test_altered_snapshot_is_rejected_and_copies_are_independent(self):
        plan = self.approved_plan()
        snapshot = plan.snapshot
        snapshot["learning_outcomes"].clear()
        self.assertTrue(plan.learning_outcomes)

        award = self.award(plan)
        award.plan_snapshot = deepcopy(award.plan_snapshot)
        award.plan_snapshot["version"] = 99
        with self.assertRaises(ValidationError):
            award.save()
