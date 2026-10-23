from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from opaque_keys.edx.keys import UsageKey

from cba_production.learning_credits.assignment_evidence import (
    passing_assignment_evidence,
)


class AssignmentEvidenceTests(TestCase):
    def setUp(self):
        self.key = UsageKey.from_string(
            "block-v1:CBA+TEST+2027+type@openassessment+block@assignment"
        )
        self.item = {
            "student_id": "course-specific-anonymous-id",
            "course_id": str(self.key.course_key),
            "item_id": str(self.key),
            "item_type": "openassessment",
        }
        self.block = SimpleNamespace(
            course_id=self.key.course_key,
            scope_ids=SimpleNamespace(usage_id=self.key),
            get_student_item_dict_from_username_or_email=Mock(
                return_value=self.item
            ),
        )
        self.learner = SimpleNamespace(username="learner")

    def read(self, score, threshold="0.80"):
        with patch(
            "cba_production.learning_credits.assignment_evidence."
            "_get_ora_score",
            return_value=score,
        ) as reader:
            result = passing_assignment_evidence(
                block=self.block,
                learner=self.learner,
                minimum_fraction=threshold,
            )
        return result, reader

    def test_passing_score_uses_ora_learner_mapping(self):
        result, reader = self.read({
            "points_earned": 8, "points_possible": 10, "submission": 12,
        })
        self.assertEqual(result["submission_id"], 12)
        self.assertEqual(result["block_key"], str(self.key))
        reader.assert_called_once_with(self.item)
        self.block.get_student_item_dict_from_username_or_email.assert_called_once_with(
            "learner"
        )

    def test_below_threshold_is_rejected(self):
        result, _ = self.read({
            "points_earned": 7, "points_possible": 10,
        })
        self.assertIsNone(result)

    def test_missing_or_reset_score_is_rejected(self):
        result, _ = self.read(None)
        self.assertIsNone(result)

    def test_invalid_score_values_are_rejected(self):
        for earned, possible in (
            (0, 0), (-1, 10), (11, 10), (True, 10), ("8", 10),
        ):
            with self.subTest(earned=earned, possible=possible):
                result, _ = self.read({
                    "points_earned": earned,
                    "points_possible": possible,
                })
                self.assertIsNone(result)

    def test_invalid_threshold_is_rejected(self):
        for threshold in (True, "-0.1", "1.1", "NaN", None):
            with self.subTest(threshold=threshold):
                with self.assertRaises(ValueError):
                    self.read(None, threshold)

    def test_wrong_course_mapping_is_rejected(self):
        self.item["course_id"] = "course-v1:CBA+OTHER+2027"
        with self.assertRaises(ValueError):
            self.read(None)

    def test_wrong_assignment_mapping_is_rejected(self):
        self.item["item_id"] = "different-assignment"
        with self.assertRaises(ValueError):
            self.read(None)

    def test_missing_anonymous_learner_mapping_is_rejected(self):
        self.item["student_id"] = ""
        with self.assertRaises(ValueError):
            self.read(None)
