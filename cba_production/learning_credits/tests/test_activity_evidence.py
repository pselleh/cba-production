from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError
from opaque_keys.edx.keys import UsageKey

from cba_production.learning_credits.activity_evidence import (
    collect_activity_evidence,
)


class ActivityEvidenceTests(TestCase):
    def setUp(self):
        self.learner = SimpleNamespace(pk=42)
        self.assignment = (
            "block-v1:CBA+TEST+2027+type@openassessment+block@assignment"
        )
        self.discussion = (
            "block-v1:CBA+TEST+2027+type@discussion+block@discussion"
        )
        self.plan = SimpleNamespace(
            course_key="course-v1:CBA+TEST+2027",
            required_block_keys=[],
            activity_requirements=[],
            activity_minutes={
                "instruction": 60,
                "assignments": 0,
                "assessments": 0,
                "discussions": 0,
                "other": 0,
            },
        )

    def assignment_rule(self):
        self.plan.required_block_keys = [self.assignment]
        self.plan.activity_minutes["assignments"] = 15
        self.plan.activity_requirements = [{
            "kind": "ora_score",
            "category": "assignments",
            "block_key": self.assignment,
            "minimum_fraction": "0.80",
        }]

    def discussion_rule(self):
        self.plan.required_block_keys = [self.discussion]
        self.plan.activity_minutes["discussions"] = 10
        self.plan.activity_requirements = [{
            "kind": "discussion_participation",
            "category": "discussions",
            "block_key": self.discussion,
            "minimum_posts": 1,
            "minimum_responses": 1,
        }]

    def block(self, value, user_id=42):
        return SimpleNamespace(scope_ids=SimpleNamespace(
            usage_id=UsageKey.from_string(value), user_id=user_id,
        ))

    def collect(self):
        return collect_activity_evidence(
            learner=self.learner, plan=self.plan,
        )

    def test_no_extra_requirements_produce_empty_evidence(self):
        self.assertEqual(self.collect(), [])

    def test_assignment_minutes_without_rules_are_rejected(self):
        self.plan.activity_minutes["assignments"] = 15
        with self.assertRaises(ValidationError):
            self.collect()

    def test_required_discussion_without_rule_is_rejected(self):
        self.plan.required_block_keys = [self.discussion]
        with self.assertRaises(ValidationError):
            self.collect()

    def test_other_activity_minutes_remain_blocked(self):
        self.plan.activity_minutes["other"] = 10
        with self.assertRaises(ValidationError):
            self.collect()

    def test_passing_assignment_evidence_is_collected(self):
        self.assignment_rule()
        expected = {"provider": "openassessment", "submission_id": 12}
        with patch(
            "cba_production.learning_credits.activity_evidence."
            "_load_learner_block",
            return_value=self.block(self.assignment),
        ), patch(
            "cba_production.learning_credits.activity_evidence."
            "passing_assignment_evidence",
            return_value=expected,
        ):
            self.assertEqual(self.collect(), [expected])

    def test_failed_assignment_evidence_blocks_award(self):
        self.assignment_rule()
        with patch(
            "cba_production.learning_credits.activity_evidence."
            "_load_learner_block",
            return_value=self.block(self.assignment),
        ), patch(
            "cba_production.learning_credits.activity_evidence."
            "passing_assignment_evidence",
            return_value=None,
        ):
            with self.assertRaises(ValidationError):
                self.collect()

    def test_wrong_learner_binding_is_rejected(self):
        self.assignment_rule()
        with patch(
            "cba_production.learning_credits.activity_evidence."
            "_load_learner_block",
            return_value=self.block(self.assignment, user_id=99),
        ):
            with self.assertRaises(ValidationError):
                self.collect()

    def test_unsupported_forum_backend_is_rejected_before_loading(self):
        self.discussion_rule()
        with patch(
            "cba_production.learning_credits.activity_evidence."
            "_native_forum_available",
            return_value=False,
        ), patch(
            "cba_production.learning_credits.activity_evidence."
            "_load_learner_block",
        ) as loader:
            with self.assertRaises(ValidationError):
                self.collect()
        loader.assert_not_called()
