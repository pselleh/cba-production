import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.utils import timezone

from cba_production.learning_credits.catalog_import import catalog_plan_records
from cba_production.learning_credits.models import CourseCreditPlan


class DraftCreditImportTests(TestCase):
    key = "course-v1:CBA+TEST+2027"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "catalog.json"
        self.payload = {"microcourses": [{"course_key": self.key, "learning_outcomes": ["Assess risk."]}]}
        patcher = patch(
            "cba_production.learning_credits.management.commands.import_cba_credit_plans.course_exists",
            return_value=True,
        )
        self.exists = patcher.start()
        self.addCleanup(patcher.stop)

    def run_import(self, **options):
        self.path.write_text(json.dumps(self.payload))
        output = io.StringIO()
        call_command("import_cba_credit_plans", str(self.path), stdout=output, **options)
        return output.getvalue()

    def test_missing_credit_plan_preserves_unknown_time(self):
        self.run_import()
        plan = CourseCreditPlan.objects.get()
        self.assertIsNone(plan.instruction_minutes)
        self.assertIsNone(plan.credit_totals.pdu)
        self.assertEqual(plan.status, "draft")

    def test_validate_only_writes_nothing(self):
        self.run_import(validate_only=True)
        self.assertFalse(CourseCreditPlan.objects.exists())

    def test_approved_payload_is_imported_as_draft(self):
        self.payload["microcourses"][0]["credit_plan"] = {"status": "approved"}
        self.run_import()
        self.assertEqual(CourseCreditPlan.objects.get().status, "draft")

    def test_identical_reimport_is_idempotent(self):
        self.run_import()
        self.assertIn("unchanged=1", self.run_import())
        self.assertEqual(CourseCreditPlan.objects.count(), 1)

    def test_changes_require_explicit_draft_update(self):
        self.run_import()
        self.payload["microcourses"][0]["learning_outcomes"] = ["New outcome."]
        with self.assertRaises(CommandError):
            self.run_import()
        self.run_import(update_drafts=True)
        self.assertEqual(CourseCreditPlan.objects.get().learning_outcomes, ["New outcome."])

    def test_missing_course_blocks_the_whole_import(self):
        self.payload["microcourses"].append({"course_key": "course-v1:CBA+OTHER+2027"})
        self.exists.side_effect = [True, False]
        with self.assertRaises(CommandError):
            self.run_import()
        self.assertFalse(CourseCreditPlan.objects.exists())

    def test_locked_plan_is_never_overwritten(self):
        self.run_import()
        plan = CourseCreditPlan.objects.get()
        plan.instruction_minutes = 60
        plan.assignments_minutes = plan.assessments_minutes = plan.discussions_minutes = plan.other_minutes = 0
        plan.instructional_design_reference = "IDP-TEST"
        plan.required_block_keys = ["block-v1:CBA+TEST+2027+type@html+block@instruction"]
        plan.status = "approved"
        plan.approved_by = get_user_model().objects.create_user(username="import-approver")
        plan.approved_at = timezone.now()
        plan.save()
        self.assertIn("locked=1", self.run_import(update_drafts=True))
        plan.refresh_from_db()
        self.assertEqual(plan.status, "approved")
        self.assertEqual(plan.instruction_minutes, 60)

    def test_precalculated_credits_are_rejected(self):
        self.payload["microcourses"][0]["credit_plan"] = {"pdu": "999"}
        with self.assertRaises(CommandError):
            self.run_import()

    def test_studio_export_shape_is_supported(self):
        self.payload = {"course_key": self.key, "credit_plan": {"version": 2, "status": "draft"}}
        self.run_import()
        self.assertEqual(CourseCreditPlan.objects.get().version, 2)

    def test_conflicting_sidecar_plan_is_rejected(self):
        self.payload["microcourses"][0]["credit_plan"] = {"version": 1}
        self.payload["sidecar"] = {self.key: {"credit_plan": {"version": 2}}}
        with self.assertRaises(CommandError):
            self.run_import()

    def test_duplicate_keys_and_boolean_minutes_are_rejected(self):
        self.payload["microcourses"].append(self.payload["microcourses"][0].copy())
        with self.assertRaises(ValueError):
            catalog_plan_records(self.payload)
        self.payload["microcourses"].pop()
        self.payload["microcourses"][0]["credit_plan"] = {"activity_minutes": {
            "instruction": True, "assignments": 0, "assessments": 0, "discussions": 0, "other": 0,
        }}
        with self.assertRaises(ValueError):
            catalog_plan_records(self.payload)
