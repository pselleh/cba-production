from copy import deepcopy
from unittest import TestCase

from cba_production.learning_credits.activity_requirements import (
    validate_activity_requirements,
)


class ActivityRequirementTests(TestCase):
    course = "course-v1:CBA+TEST+2027"
    assignment = (
        "block-v1:CBA+TEST+2027+type@openassessment+block@assignment"
    )
    discussion = (
        "block-v1:CBA+TEST+2027+type@discussion+block@discussion"
    )

    def ora(self):
        return {
            "kind": "ora_score",
            "category": "assignments",
            "block_key": self.assignment,
            "minimum_fraction": "0.80",
        }

    def forum(self):
        return {
            "kind": "discussion_participation",
            "category": "discussions",
            "block_key": self.discussion,
            "minimum_posts": 1,
            "minimum_responses": 2,
        }

    def validate(self, rules, required=None):
        return validate_activity_requirements(
            rules, self.course,
            required if required is not None else [
                self.assignment, self.discussion,
            ],
        )

    def test_valid_rules_are_preserved(self):
        rules = [self.ora(), self.forum()]
        before = deepcopy(rules)
        self.validate(rules)
        self.assertEqual(rules, before)

    def test_empty_rules_remain_valid_for_existing_plans(self):
        self.validate([])

    def test_wrong_course_run_is_rejected(self):
        rule = self.ora()
        rule["block_key"] = self.assignment.replace("+2027+", "+2028+")
        with self.assertRaises(ValueError):
            self.validate([rule], required=[rule["block_key"]])

    def test_activity_must_be_in_required_blocks(self):
        with self.assertRaises(ValueError):
            self.validate([self.ora()], required=[])

    def test_invalid_thresholds_are_rejected(self):
        for threshold in ("NaN", "Infinity", "-0.1", "1.1", True, 0.8):
            with self.subTest(threshold=threshold):
                rule = self.ora()
                rule["minimum_fraction"] = threshold
                with self.assertRaises(ValueError):
                    self.validate([rule])

    def test_invalid_discussion_counts_are_rejected(self):
        for posts, responses in ((0, 0), (-1, 1), (True, 1), (1, "2")):
            with self.subTest(posts=posts, responses=responses):
                rule = self.forum()
                rule.update(
                    minimum_posts=posts, minimum_responses=responses,
                )
                with self.assertRaises(ValueError):
                    self.validate([rule])

    def test_duplicates_are_rejected(self):
        with self.assertRaises(ValueError):
            self.validate([self.ora(), self.ora()])

    def test_unknown_fields_and_wrong_categories_are_rejected(self):
        for change in (
            {"unrecognized": True},
            {"category": "discussions"},
            {"kind": "unsupported"},
            {"block_key": self.discussion},
        ):
            with self.subTest(change=change):
                rule = self.ora()
                rule.update(change)
                with self.assertRaises(ValueError):
                    self.validate([rule])
