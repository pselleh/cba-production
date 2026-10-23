from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from cba_production.learning_credits.completion import missing_required_blocks


class RequiredBlockCompletionTests(TestCase):
    def setUp(self):
        self.learner = object()
        self.plan = SimpleNamespace(
            course_key="course-v1:CBA+TEST+2027",
            required_block_keys=["block-one", "block-two"],
        )

    def check(self, values):
        model = MagicMock()
        model.get_learning_context_completions.return_value = values
        with patch("django.apps.apps.get_model", return_value=model):
            result = missing_required_blocks(
                learner=self.learner, plan=self.plan
            )
        model.get_learning_context_completions.assert_called_once_with(
            self.learner, self.plan.course_key
        )
        return result

    def test_all_required_blocks_complete(self):
        self.assertEqual(self.check({
            "block-one": 1.0, "block-two": 1.0,
        }), [])

    def test_missing_and_partial_blocks_remain_required(self):
        self.assertEqual(self.check({
            "block-one": 0.5,
        }), ["block-one", "block-two"])

    def test_unrelated_completion_does_not_satisfy_requirement(self):
        self.assertEqual(self.check({
            "unrelated": 1.0, "block-two": 1.0,
        }), ["block-one"])

    def test_invalid_requirements_are_rejected(self):
        for required in ([], None, "block-one", [""], ["a", "a"]):
            with self.subTest(required=required):
                self.plan.required_block_keys = required
                with self.assertRaises(ValueError):
                    missing_required_blocks(
                        learner=self.learner, plan=self.plan
                    )
