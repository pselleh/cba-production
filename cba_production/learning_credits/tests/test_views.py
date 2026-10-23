import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from cba_production.learning_credits.models import (
    CourseCreditAward, CourseCreditPlan,
)
from cba_production.learning_credits.views import (
    learner_credit_page, learner_credit_record,
)


@override_settings(
    ALLOWED_HOSTS=["testserver"],
    TEMPLATES=[{
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
    }],
)
class LearnerCreditViewTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.user = users.objects.create_user(
            username="record-owner", password=None,
        )
        self.other = users.objects.create_user(
            username="other-owner", password=None,
        )
        self.plan = CourseCreditPlan.objects.create(
            course_key="course-v1:CBA+TEST+2027",
            status=CourseCreditPlan.Status.APPROVED,
            instruction_minutes=60,
            assignments_minutes=0,
            assessments_minutes=0,
            discussions_minutes=0,
            other_minutes=0,
            instructional_design_reference="PRIVATE-IDP",
            learning_outcomes=["Assess risk."],
            required_block_keys=[
                "block-v1:CBA+TEST+2027+type@html+block@instruction",
            ],
            approved_by=self.user,
            approved_at=timezone.now(),
        )
        totals = self.plan.credit_totals
        for user in (self.user, self.other):
            CourseCreditAward.objects.create(
                learner=user,
                plan=self.plan,
                course_key=self.plan.course_key,
                completed_at=timezone.now(),
                eligible_minutes=totals.eligible_minutes,
                pdu=totals.pdu,
                ceu=totals.ceu,
                policy_version=self.plan.policy_version,
                plan_snapshot=self.plan.snapshot,
                source_event_id="private-event-reference",
            )
        self.factory = RequestFactory()

    def request(self, user=None, query=None):
        request = self.factory.get(
            "/cba/learning-credits/api/", data=query or {},
        )
        request.user = user if user is not None else self.user
        return request

    def test_anonymous_request_is_denied(self):
        response = learner_credit_record(self.request(AnonymousUser()))
        self.assertEqual(response.status_code, 401)

    def test_inactive_account_is_denied(self):
        self.user.is_active = False
        response = learner_credit_record(self.request())
        self.assertEqual(response.status_code, 401)

    def test_record_is_scoped_to_signed_in_user(self):
        response = learner_credit_record(self.request(
            query={"user_id": self.other.pk},
        ))
        payload = json.loads(response.content)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(
            payload["results"][0]["id"],
            CourseCreditAward.objects.get(learner=self.user).pk,
        )

    def test_credit_values_preserve_decimal_precision(self):
        response = learner_credit_record(self.request())
        row = json.loads(response.content)["results"][0]
        self.assertEqual(row["pdu"], "1.0000")
        self.assertEqual(row["ceu"], "0.1000")

    def test_private_evidence_and_plan_details_are_not_exposed(self):
        response = learner_credit_record(self.request())
        row = json.loads(response.content)["results"][0]
        self.assertNotIn("plan_snapshot", row)
        self.assertNotIn("activity_evidence", row)
        self.assertNotIn("source_event_id", row)
        self.assertNotIn("PRIVATE-IDP", response.content.decode())
        self.assertIn("no-store", response["Cache-Control"])

    def test_post_is_not_allowed(self):
        request = self.factory.post("/cba/learning-credits/api/")
        request.user = self.user
        self.assertEqual(learner_credit_record(request).status_code, 405)

    def test_invalid_page_is_rejected(self):
        response = learner_credit_record(self.request(
            query={"page": "-1"},
        ))
        self.assertEqual(response.status_code, 400)

    def test_authenticated_record_page_renders_awarded_credits(self):
        response = learner_credit_page(self.request())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My learning credits")
        self.assertContains(response, "1.0000")
        self.assertContains(response, "0.1000")
