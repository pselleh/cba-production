import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from cba_production.learning_credits import studio_views
from cba_production.learning_credits.models import CourseCreditPlan
from cba_production.learning_credits.services import approve_credit_plan


@override_settings(
    ROOT_URLCONF="cba_production.learning_credits.tests.studio_test_urls",
    ALLOWED_HOSTS=["testserver"], LOGIN_URL="/login/",
    STATIC_URL="/static/",
    TEMPLATES=[{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}],
)
class StudioCreditControlsTests(TestCase):
    course = "course-v1:CBA+TEST+2027"
    html = "block-v1:CBA+TEST+2027+type@html+block@instruction"
    ora = "block-v1:CBA+TEST+2027+type@openassessment+block@assignment"
    discussion = "block-v1:CBA+TEST+2027+type@discussion+block@topic"

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="course-author")
        self.factory = RequestFactory()
        self.activities = [
            {"key": self.html, "type": "html", "label": "Instruction"},
            {"key": self.ora, "type": "openassessment", "label": "Risk assignment"},
            {"key": self.discussion, "type": "discussion", "label": "Risk discussion"},
        ]
        for name, value in (("_can_author_course", True), ("_course_activities", ("Test course", self.activities))):
            patcher = patch.object(studio_views, name, return_value=value)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def payload(self, **changes):
        values = {
            "version": "1", "instruction_minutes": "60", "assignments_minutes": "0",
            "assessments_minutes": "0", "discussions_minutes": "0", "other_minutes": "0",
            "instructional_design_reference": "IDP-TEST", "learning_outcomes": "Assess risk.\nExplain a control.",
            "required_block_keys": [self.html], "action": "save",
            "requirements-TOTAL_FORMS": "1", "requirements-INITIAL_FORMS": "0",
            "requirements-MIN_NUM_FORMS": "0", "requirements-MAX_NUM_FORMS": "200",
        }
        values.update(changes)
        return values

    def request(self, data=None, query=None, csrf=False):
        request = self.factory.post("/credits/", data=data) if data is not None else self.factory.get("/credits/", data=query or {})
        request.user = self.user
        request._dont_enforce_csrf_checks = not csrf
        return request

    def save_draft(self, **changes):
        response = studio_views.course_credit_plans(self.request(self.payload(**changes)), self.course)
        self.assertEqual(response.status_code, 302)
        return CourseCreditPlan.objects.get(course_key=self.course)

    def allow_approval(self):
        self.user.user_permissions.add(Permission.objects.get(
            content_type__app_label="cba_learning_credits", codename="approve_course_credit_plan",
        ))
        self.user = get_user_model().objects.get(pk=self.user.pk)

    def test_page_lists_real_course_activities(self):
        response = studio_views.course_credit_plans(self.request(), self.course)
        self.assertContains(response, "Risk assignment")
        self.assertContains(response, "Calculated preview")

    def test_author_course_picker_uses_author_scoped_courses(self):
        with patch.object(studio_views, "_courses_for_author", return_value=[
            {"key": self.course, "title": "My course"},
        ]) as selector:
            response = studio_views.credit_courses(self.request())
        self.assertContains(response, "My course")
        selector.assert_called_once_with(self.user)

    def test_empty_course_picker_explains_draft_import(self):
        with patch.object(studio_views, "_courses_for_author", return_value=[]):
            response = studio_views.credit_courses(self.request())
        self.assertContains(response, "Import a draft course first")

    def test_preview_calculates_without_saving(self):
        response = studio_views.course_credit_plans(self.request(self.payload(action="preview", assessments_minutes="30")), self.course)
        self.assertContains(response, "1.5000")
        self.assertContains(response, "0.1500")
        self.assertFalse(CourseCreditPlan.objects.exists())

    def test_unknown_time_stays_pending(self):
        response = studio_views.course_credit_plans(self.request(self.payload(action="preview", assignments_minutes="")), self.course)
        self.assertContains(response, "Pending")
        self.assertFalse(CourseCreditPlan.objects.exists())

    def test_saves_draft_and_ignores_forged_approval_and_credits(self):
        plan = self.save_draft(status="approved", pdu="999", ceu="999", approved_by=self.user.pk)
        self.assertEqual(plan.status, "draft")
        self.assertIsNone(plan.approved_at)
        self.assertEqual(str(plan.credit_totals.pdu), "1.0000")
        self.assertEqual(plan.learning_outcomes, ["Assess risk.", "Explain a control."])

    def test_other_course_activity_cannot_be_submitted(self):
        response = studio_views.course_credit_plans(self.request(self.payload(required_block_keys=[self.html.replace("TEST", "OTHER")])), self.course)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CourseCreditPlan.objects.exists())

    def test_assignment_passing_percentage_is_normalized(self):
        plan = self.save_draft(**{
            "assignments_minutes": "15", "required_block_keys": [self.html, self.ora],
            "requirements-0-activity": self.ora, "requirements-0-category": "assignments",
            "requirements-0-minimum_percent": "80",
        })
        self.assertEqual(plan.activity_requirements[0]["minimum_fraction"], "0.8")

    def test_assignment_cannot_omit_passing_percentage(self):
        response = studio_views.course_credit_plans(self.request(self.payload(**{
            "required_block_keys": [self.ora], "requirements-0-activity": self.ora,
            "requirements-0-category": "assignments",
        })), self.course)
        self.assertContains(response, "Enter the approved passing percentage")
        self.assertFalse(CourseCreditPlan.objects.exists())

    def test_discussion_requires_explicit_contribution_counts(self):
        plan = self.save_draft(**{
            "discussions_minutes": "15", "required_block_keys": [self.html, self.discussion],
            "requirements-0-activity": self.discussion, "requirements-0-category": "discussions",
            "requirements-0-minimum_posts": "1", "requirements-0-minimum_responses": "2",
        })
        self.assertEqual(plan.activity_requirements[0]["minimum_responses"], 2)

    def test_approved_plan_is_locked_and_copies_to_new_draft(self):
        plan = self.save_draft()
        self.allow_approval()
        response = studio_views.approve_plan(self.request({}), self.course, plan.pk)
        self.assertEqual(response.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.status, "approved")
        with self.assertRaises(PermissionDenied):
            studio_views.course_credit_plans(self.request(self.payload(plan_id=plan.pk)), self.course)
        response = studio_views.course_credit_plans(self.request(query={"copy": plan.pk}), self.course)
        self.assertContains(response, 'name="version" value="2"')
        self.assertEqual(CourseCreditPlan.objects.count(), 1)

    def test_course_author_without_approval_permission_cannot_approve(self):
        plan = self.save_draft()
        with self.assertRaises(PermissionDenied):
            studio_views.approve_plan(self.request({}), self.course, plan.pk)

    def test_approval_rejects_missing_evidence_rules_even_through_service(self):
        plan = self.save_draft(assignments_minutes="15")
        self.allow_approval()
        with self.assertRaises(ValidationError):
            approve_credit_plan(plan_id=plan.pk, approver=self.user)
        plan.refresh_from_db()
        self.assertEqual(plan.status, "draft")

    def test_approval_rejects_deleted_activities(self):
        plan = self.save_draft()
        self.allow_approval()
        self._course_activities.return_value = ("Test course", [])
        response = studio_views.approve_plan(self.request({}), self.course, plan.pk)
        self.assertEqual(response.status_code, 400)
        plan.refresh_from_db()
        self.assertEqual(plan.status, "draft")

    def test_approval_cannot_target_another_course_plan(self):
        plan = self.save_draft()
        self.allow_approval()
        from django.http import Http404
        with self.assertRaises(Http404):
            studio_views.approve_plan(self.request({}), "course-v1:CBA+OTHER+2027", plan.pk)

    def test_non_author_is_denied(self):
        self._can_author_course.return_value = False
        with self.assertRaises(PermissionDenied):
            studio_views.course_credit_plans(self.request(), self.course)

    def test_anonymous_user_is_redirected_to_login(self):
        request = self.request()
        request.user = AnonymousUser()
        self.assertEqual(studio_views.course_credit_plans(request, self.course).status_code, 302)

    def test_mutations_require_csrf(self):
        response = studio_views.course_credit_plans(self.request(self.payload(), csrf=True), self.course)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(CourseCreditPlan.objects.exists())

    def test_plan_export_matches_authoring_fields(self):
        plan = self.save_draft()
        payload = json.loads(studio_views.export_plan(self.request(), self.course, plan.pk).content)
        self.assertEqual(payload["credit_plan"]["status"], "draft")
        self.assertEqual(payload["credit_plan"]["activity_minutes"]["instruction"], 60)
        self.assertEqual(payload["credit_preview"]["ceu"], "0.1000")

    def test_preview_can_show_zero_without_calling_it_unknown(self):
        response = studio_views.course_credit_plans(self.request(self.payload(action="preview", instruction_minutes="0")), self.course)
        self.assertContains(response, "0.0000")

    def test_approval_rejects_unverifiable_other_time(self):
        plan = self.save_draft(other_minutes="15")
        self.allow_approval()
        response = studio_views.approve_plan(self.request({}), self.course, plan.pk)
        self.assertEqual(response.status_code, 400)
