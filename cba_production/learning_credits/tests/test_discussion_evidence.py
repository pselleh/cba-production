from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from opaque_keys.edx.keys import UsageKey

from cba_production.learning_credits.discussion_evidence import (
    _read_native_posts,
    native_discussion_evidence,
)


class DiscussionEvidenceTests(TestCase):
    def setUp(self):
        self.key = UsageKey.from_string(
            "block-v1:CBA+TEST+2027+type@discussion+block@topic"
        )
        self.learner = SimpleNamespace(pk=42)
        self.block = SimpleNamespace(
            scope_ids=SimpleNamespace(usage_id=self.key),
            discussion_id="required-topic",
        )
        self.rule = {
            "kind": "discussion_participation",
            "category": "discussions",
            "block_key": str(self.key),
            "minimum_posts": 1,
            "minimum_responses": 1,
        }

    def read(self, posts, responses):
        with patch(
            "cba_production.learning_credits.discussion_evidence."
            "_read_native_posts",
            return_value=(posts, responses),
        ):
            return native_discussion_evidence(
                block=self.block,
                learner=self.learner,
                requirement=self.rule,
            )

    def test_required_participation_returns_evidence_ids(self):
        result = self.read(
            [{"id": 10, "body": "My analysis"}],
            [{"id": 20, "body": "My response"}],
        )
        self.assertEqual(result["post_ids"], [10])
        self.assertEqual(result["response_ids"], [20])
        self.assertEqual(result["topic_id"], "required-topic")

    def test_missing_post_is_rejected(self):
        self.assertIsNone(self.read(
            [], [{"id": 20, "body": "Response"}],
        ))

    def test_missing_response_is_rejected(self):
        self.assertIsNone(self.read(
            [{"id": 10, "body": "Analysis"}], [],
        ))

    def test_blank_html_does_not_count(self):
        self.assertIsNone(self.read(
            [{"id": 10, "body": "<p>&nbsp;</p>"}],
            [{"id": 20, "body": "Response"}],
        ))

    def test_wrong_activity_requirement_is_rejected(self):
        self.rule["block_key"] = str(self.key).replace(
            "block@topic", "block@different"
        )
        with self.assertRaises(ValueError):
            self.read([], [])

    def test_missing_topic_is_rejected(self):
        self.block.discussion_id = ""
        with self.assertRaises(ValueError):
            self.read([], [])

    def test_zero_contribution_requirement_is_rejected(self):
        self.rule.update(minimum_posts=0, minimum_responses=0)
        with self.assertRaises(ValueError):
            self.read([], [])

    def test_database_lookup_is_scoped_and_excludes_self_responses(self):
        threads = MagicMock()
        comments = MagicMock()
        with patch(
            "django.apps.apps.get_model",
            side_effect=[threads, comments],
        ):
            _read_native_posts(
                learner=self.learner,
                course_key=str(self.key.course_key),
                topic_id="required-topic",
            )

        threads.objects.filter.assert_called_once_with(
            author_id=42,
            course_id=str(self.key.course_key),
            commentable_id="required-topic",
            visible=True,
        )
        comments.objects.filter.assert_called_once_with(
            author_id=42,
            course_id=str(self.key.course_key),
            visible=True,
            parent__isnull=True,
            comment_thread__course_id=str(self.key.course_key),
            comment_thread__commentable_id="required-topic",
            comment_thread__visible=True,
        )
        comments.objects.filter.return_value.exclude.assert_called_once_with(
            comment_thread__author_id=42,
        )
