from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.utils import timezone

from cba_production.learning_credits.models import CourseCreditPlan


class CreditRequirementTests(SimpleTestCase):
    def plan(self, blocks):
        return CourseCreditPlan(
            course_key="course-v1:CBA+TEST+2027",
            instruction_minutes=60,
            assignments_minutes=0,
            assessments_minutes=0,
            discussions_minutes=0,
            other_minutes=0,
            instructional_design_reference="IDP-TEST-v1",
            learning_outcomes=["Apply a documented procedure."],
            required_block_keys=blocks,
            status=CourseCreditPlan.Status.APPROVED,
            approved_by_id=1,
            approved_at=timezone.now(),
        )

    def test_valid_required_block_is_accepted(self):
        plan = self.plan([
            "block-v1:CBA+TEST+2027+type@html+block@instruction",
        ])
        plan.clean()
        self.assertEqual(plan.snapshot["required_block_keys"], plan.required_block_keys)

    def test_approval_requires_completion_requirements(self):
        with self.assertRaises(ValidationError):
            self.plan([]).clean()

    def test_block_from_another_run_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.plan([
                "block-v1:CBA+TEST+2028+type@html+block@instruction",
            ]).clean()

    def test_duplicate_required_blocks_are_rejected(self):
        key = "block-v1:CBA+TEST+2027+type@html+block@instruction"
        with self.assertRaises(ValidationError):
            self.plan([key, key]).clean()
