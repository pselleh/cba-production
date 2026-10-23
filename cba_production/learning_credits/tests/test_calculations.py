from decimal import Decimal
from unittest import TestCase

from cba_production.learning_credits.calculations import (
    ACTIVITY_CATEGORIES,
    CREDIT_POLICY_VERSION,
    calculate_credits,
)


class CreditCalculationTests(TestCase):
    def minutes(self, **changes):
        values = dict.fromkeys(ACTIVITY_CATEGORIES, 0)
        values.update(changes)
        return values

    def test_sixty_minutes_earns_one_pdu_and_point_one_ceu(self):
        result = calculate_credits(self.minutes(instruction=60))
        self.assertEqual(result.eligible_minutes, 60)
        self.assertEqual(result.pdu, Decimal("1.0000"))
        self.assertEqual(result.ceu, Decimal("0.1000"))
        self.assertEqual(result.policy_version, CREDIT_POLICY_VERSION)

    def test_required_activity_minutes_are_included(self):
        result = calculate_credits(self.minutes(
            instruction=60, assignments=15, assessments=10, discussions=5,
        ))
        self.assertEqual(result.eligible_minutes, 90)
        self.assertEqual(result.pdu, Decimal("1.5000"))
        self.assertEqual(result.ceu, Decimal("0.1500"))

    def test_fractional_hour_credits(self):
        result = calculate_credits(self.minutes(instruction=30))
        self.assertEqual(result.pdu, Decimal("0.5000"))
        self.assertEqual(result.ceu, Decimal("0.0500"))

    def test_unknown_time_does_not_become_zero_credit(self):
        result = calculate_credits(self.minutes(assignments=None))
        self.assertIsNone(result.eligible_minutes)
        self.assertIsNone(result.pdu)
        self.assertIsNone(result.ceu)

    def test_explicit_zero_is_preserved(self):
        result = calculate_credits(self.minutes())
        self.assertEqual(result.eligible_minutes, 0)
        self.assertEqual(result.pdu, Decimal("0.0000"))
        self.assertEqual(result.ceu, Decimal("0.0000"))

    def test_invalid_minute_values_are_rejected(self):
        for value in (True, -1, 1.5, "60"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    calculate_credits(self.minutes(instruction=value))

    def test_missing_or_unknown_categories_are_rejected(self):
        missing = self.minutes()
        del missing["assessments"]
        extra = self.minutes(unrecognized=10)
        for values in (missing, extra, []):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    calculate_credits(values)

    def test_rounding_occurs_after_totaling_minutes(self):
        result = calculate_credits(self.minutes(
            instruction=1, assignments=1, assessments=1,
        ))
        self.assertEqual(result.pdu, Decimal("0.0500"))
        self.assertEqual(result.ceu, Decimal("0.0050"))
