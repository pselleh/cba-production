from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from cba_production.learning_credits.grades import currently_passing


class CurrentGradeTests(TestCase):
    def check(self, grade):
        learner = SimpleNamespace(pk=42)
        key = "course-v1:CBA+TEST+2027"
        with patch(
            "cba_production.learning_credits.grades._load_current_grade",
            return_value=grade,
        ) as loader:
            result = currently_passing(
                learner=learner, course_key=key
            )
        loader.assert_called_once_with(
            learner=learner, course_key=key
        )
        return result

    def test_current_passing_grade_is_eligible(self):
        self.assertTrue(self.check(SimpleNamespace(passed=True)))

    def test_missing_grade_is_not_eligible(self):
        self.assertFalse(self.check(None))

    def test_historical_pass_does_not_override_current_failure(self):
        self.assertFalse(self.check(SimpleNamespace(
            passed=False, passed_timestamp="previously passed",
        )))

    def test_unknown_passing_decision_is_not_eligible(self):
        self.assertFalse(self.check(SimpleNamespace(passed=None)))
