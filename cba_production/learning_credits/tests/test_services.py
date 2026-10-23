from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from cba_production.learning_credits.models import CourseCreditPlan
from cba_production.learning_credits.services import approve_credit_plan


class CreditApprovalTests(TestCase):
    def setUp(self):
        self.approver = get_user_model().objects.create_user(
            username="approver", password=None,
        )
        permission = Permission.objects.get(
            content_type__app_label="cba_learning_credits",
            codename="approve_course_credit_plan",
        )
        self.approver.user_permissions.add(permission)
        self.plan = CourseCreditPlan.objects.create(
            course_key="course-v1:CBA+TEST+2027",
            instruction_minutes=60,
            assignments_minutes=15,
            assessments_minutes=10,
            discussions_minutes=5,
            other_minutes=0,
            instructional_design_reference="IDP-TEST-v1",
            required_block_keys=[
                "block-v1:CBA+TEST+2027+type@html+block@instruction",
                "block-v1:CBA+TEST+2027+type@openassessment+block@assignment",
                "block-v1:CBA+TEST+2027+type@discussion+block@discussion",
            ],
            activity_requirements=[
                {
                    "kind": "ora_score", "category": "assignments",
                    "block_key": "block-v1:CBA+TEST+2027+type@openassessment+block@assignment",
                    "minimum_fraction": "0.80",
                },
                {
                    "kind": "discussion_participation", "category": "discussions",
                    "block_key": "block-v1:CBA+TEST+2027+type@discussion+block@discussion",
                    "minimum_posts": 1, "minimum_responses": 1,
                },
            ],
            learning_outcomes=["Assess a risk scenario."],
        )

    def test_authorized_approval_records_actor_and_time(self):
        approved = approve_credit_plan(
            plan_id=self.plan.pk, approver=self.approver,
        )
        self.assertEqual(approved.status, CourseCreditPlan.Status.APPROVED)
        self.assertEqual(approved.approved_by_id, self.approver.pk)
        self.assertIsNotNone(approved.approved_at)
        self.assertEqual(approved.credit_totals.eligible_minutes, 90)

    def test_staff_without_approval_permission_is_denied(self):
        staff = get_user_model().objects.create_user(
            username="ordinary-staff", password=None, is_staff=True,
        )
        with self.assertRaises(PermissionDenied):
            approve_credit_plan(plan_id=self.plan.pk, approver=staff)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, CourseCreditPlan.Status.DRAFT)

    def test_inactive_approver_is_denied(self):
        self.approver.is_active = False
        with self.assertRaises(PermissionDenied):
            approve_credit_plan(
                plan_id=self.plan.pk, approver=self.approver,
            )

    def test_incomplete_plan_remains_draft_after_failed_approval(self):
        self.plan.assessments_minutes = None
        self.plan.save()
        with self.assertRaises(ValidationError):
            approve_credit_plan(
                plan_id=self.plan.pk, approver=self.approver,
            )
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, CourseCreditPlan.Status.DRAFT)
        self.assertIsNone(self.plan.approved_at)

    def test_repeated_approval_preserves_original_approval(self):
        first = approve_credit_plan(
            plan_id=self.plan.pk, approver=self.approver,
        )
        second = approve_credit_plan(
            plan_id=self.plan.pk, approver=self.approver,
        )
        self.assertEqual(first.approved_at, second.approved_at)
        self.assertEqual(first.approved_by_id, second.approved_by_id)

    def test_invalid_course_key_cannot_be_approved(self):
        self.plan.course_key = "not-a-course-key"
        self.plan.activity_requirements = []
        self.plan.save()
        with self.assertRaises(ValidationError):
            approve_credit_plan(
                plan_id=self.plan.pk, approver=self.approver,
            )
