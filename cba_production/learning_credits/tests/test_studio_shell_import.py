import io
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey

from cba_production.learning_credits.models import CourseCreditPlan


class StudioShellImportTests(TestCase):
    key = "course-v1:ERPI+TEST+2027"

    def setUp(self):
        self.author = get_user_model().objects.create_user(username="shell-author", is_staff=True)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "catalog.json"
        self.payload = {"microcourses": [{"course_key": self.key, "title": "Test course", "learning_outcomes": ["Assess risk."]}]}
        self.courses, self.created = {}, []

        def create_course(*, org, course, run, fields, user_id):
            key = str(CourseKey.from_string(f"course-v1:{org}+{course}+{run}"))
            self.created.append({"key": key, "fields": fields, "user_id": user_id})
            self.courses[key] = SimpleNamespace(id=key)
            return self.courses[key]

        self.store = SimpleNamespace(get_course=lambda key: self.courses.get(str(key)), create_course=create_course)
        self.role = Mock()
        self.role.add_users = Mock()
        self.environment = patch(
            "cba_production.learning_credits.management.commands.import_cba_studio_courses.native_environment",
            return_value=(self.store, {"display_name", "catalog_visibility", "invitation_only"}, Mock(return_value=self.role)),
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def run_command(self, **options):
        self.path.write_text(json.dumps(self.payload))
        output = io.StringIO()
        call_command("import_cba_studio_courses", str(self.path), author=self.author.username, course_key=self.key, stdout=output, **options)
        return output.getvalue()

    def test_default_is_validation_only(self):
        self.assertIn("no writes", self.run_command())
        self.assertFalse(self.created)
        self.assertFalse(CourseCreditPlan.objects.exists())

    def test_apply_creates_private_shell_and_pending_draft_plan(self):
        self.run_command(apply=True)
        self.assertEqual(self.created[0]["fields"]["catalog_visibility"], "none")
        self.assertTrue(self.created[0]["fields"]["invitation_only"])
        self.role.add_users.assert_called_once_with(self.author)
        plan = CourseCreditPlan.objects.get()
        self.assertEqual(plan.status, "draft")
        self.assertIsNone(plan.credit_totals.pdu)

    def test_repeat_does_not_replace_existing_content(self):
        self.run_command(apply=True)
        self.run_command(apply=True)
        self.assertEqual(len(self.created), 1)
        self.assertEqual(CourseCreditPlan.objects.count(), 1)

    def test_non_staff_author_cannot_create_shells(self):
        self.author.is_staff = False
        self.author.save()
        with self.assertRaises(CommandError):
            self.run_command(apply=True)
        self.assertFalse(self.created)

    def test_invalid_title_is_caught_before_writes(self):
        self.payload["microcourses"][0]["title"] = ""
        with self.assertRaises(CommandError):
            self.run_command(apply=True)
        self.assertFalse(self.created)

    def test_wrong_native_api_stops_before_writes(self):
        self.store.create_course = lambda unexpected: None
        with self.assertRaises(CommandError):
            self.run_command(apply=True)
        self.assertFalse(self.created)
