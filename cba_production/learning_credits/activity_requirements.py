"""Validate explicit activity evidence requirements."""

from decimal import Decimal, InvalidOperation

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import UsageKey


def validate_activity_requirements(rules, course_key, required_block_keys):
    if not isinstance(rules, list):
        raise ValueError("Activity requirements must be an array.")

    seen = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("Each activity requirement must be an object.")

        kind = rule.get("kind")
        if kind == "ora_score":
            fields = {"kind", "category", "block_key", "minimum_fraction"}
            categories = {"assignments", "assessments"}
            block_type = "openassessment"
        elif kind == "discussion_participation":
            fields = {
                "kind", "category", "block_key",
                "minimum_posts", "minimum_responses",
            }
            categories = {"discussions"}
            block_type = "discussion"
        else:
            raise ValueError("Unsupported activity evidence kind.")

        if set(rule) != fields:
            raise ValueError("Activity requirement fields do not match its kind.")
        if rule["category"] not in categories:
            raise ValueError("Activity category does not match its evidence kind.")

        value = rule["block_key"]
        if not isinstance(value, str):
            raise ValueError("A canonical activity block key is required.")
        try:
            key = UsageKey.from_string(value)
        except (InvalidKeyError, TypeError, ValueError) as exc:
            raise ValueError("A valid activity block key is required.") from exc

        if (
            str(key) != value
            or str(key.course_key) != course_key
            or key.block_type != block_type
            or value not in required_block_keys
        ):
            raise ValueError(
                "Activity must be a required block of the correct type "
                "from this course run."
            )
        if value in seen:
            raise ValueError("Duplicate activity evidence requirements.")
        seen.add(value)

        if kind == "ora_score":
            threshold = rule["minimum_fraction"]
            if not isinstance(threshold, str):
                raise ValueError("Store the passing fraction as a decimal string.")
            try:
                fraction = Decimal(threshold)
            except InvalidOperation as exc:
                raise ValueError("Invalid passing fraction.") from exc
            if not fraction.is_finite() or not 0 <= fraction <= 1:
                raise ValueError("Passing fraction must be between zero and one.")
        else:
            counts = (
                rule["minimum_posts"], rule["minimum_responses"],
            )
            if any(type(value) is not int or value < 0 for value in counts):
                raise ValueError("Discussion counts must be nonnegative integers.")
            if sum(counts) == 0:
                raise ValueError("Require at least one discussion contribution.")


def validate_evidence_coverage(plan):
    """Reject approval when required work has no supported verification rule."""
    validate_activity_requirements(
        plan.activity_requirements, plan.course_key, plan.required_block_keys,
    )
    if plan.activity_minutes["other"] not in (None, 0):
        raise ValueError("Other activities need a defined evidence verifier before approval.")
    categories = {rule["category"] for rule in plan.activity_requirements}
    for category in ("assignments", "discussions"):
        if plan.activity_minutes[category] not in (None, 0) and category not in categories:
            raise ValueError(f"Add passing requirements for {category} before approval.")
    covered = {rule["block_key"] for rule in plan.activity_requirements}
    for value in plan.required_block_keys:
        if UsageKey.from_string(value).block_type in {"openassessment", "discussion"} and value not in covered:
            raise ValueError("Add an evidence requirement for each required assignment and discussion.")
