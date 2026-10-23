"""Read scored ORA evidence from a trusted, server-loaded LMS block."""

from decimal import Decimal, InvalidOperation


def _fraction(value):
    if isinstance(value, bool):
        raise ValueError("Use a numeric passing fraction.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Use a numeric passing fraction.") from exc
    if not result.is_finite() or not Decimal("0") <= result <= Decimal("1"):
        raise ValueError("Passing fraction must be between zero and one.")
    return result


def _get_ora_score(student_item):
    from submissions.api import get_score
    return get_score(student_item)


def passing_assignment_evidence(*, block, learner, minimum_fraction):
    """Return scored evidence or None; this does not create an award.

    block must be loaded by the server for the required course activity.
    minimum_fraction must come from the approved activity requirement.
    """
    threshold = _fraction(minimum_fraction)
    usage_key = block.scope_ids.usage_id

    if usage_key.block_type != "openassessment":
        raise ValueError("An Open Response Assessment block is required.")
    if str(usage_key.course_key) != str(block.course_id):
        raise ValueError("The assignment must belong to the expected course.")

    student_item = block.get_student_item_dict_from_username_or_email(
        learner.username
    )
    if (
        not isinstance(student_item, dict)
        or student_item.get("item_type") != "openassessment"
        or str(student_item.get("course_id")) != str(block.course_id)
        or str(student_item.get("item_id")) != str(usage_key)
        or not isinstance(student_item.get("student_id"), str)
        or not student_item["student_id"].strip()
    ):
        raise ValueError("ORA did not resolve a valid learner activity.")

    score = _get_ora_score(student_item)
    if not isinstance(score, dict):
        return None

    earned = score.get("points_earned")
    possible = score.get("points_possible")
    # The installed submissions models store these as integers.
    if (
        type(earned) is not int
        or type(possible) is not int
        or possible <= 0
        or earned < 0
        or earned > possible
    ):
        return None
    if Decimal(earned) < Decimal(possible) * threshold:
        return None

    return {
        "provider": "openassessment",
        "course_key": str(block.course_id),
        "block_key": str(usage_key),
        "points_earned": earned,
        "points_possible": possible,
        "minimum_fraction": str(threshold),
        "submission_id": score.get("submission"),
    }
