"""Calculate learning credits from approved eligible activity minutes."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, localcontext


CREDIT_POLICY_VERSION = "cba-eligible-minutes-v1"
ACTIVITY_CATEGORIES = (
    "instruction",
    "assignments",
    "assessments",
    "discussions",
    "other",
)
CREDIT_QUANTUM = Decimal("0.0001")


@dataclass(frozen=True)
class CreditTotals:
    eligible_minutes: int | None
    pdu: Decimal | None
    ceu: Decimal | None
    policy_version: str = CREDIT_POLICY_VERSION


def calculate_credits(activity_minutes):
    """All categories must be supplied; null means time is not yet known."""
    if not isinstance(activity_minutes, dict):
        raise ValueError("Activity minutes must be an object.")

    if set(activity_minutes) != set(ACTIVITY_CATEGORIES):
        raise ValueError(
            "Supply exactly these activity categories: "
            + ", ".join(ACTIVITY_CATEGORIES)
        )

    values = []
    for category in ACTIVITY_CATEGORIES:
        minutes = activity_minutes[category]
        if minutes is not None and (
            type(minutes) is not int or minutes < 0
        ):
            raise ValueError(
                f"{category} must be nonnegative whole minutes or null."
            )
        values.append(minutes)

    if any(value is None for value in values):
        return CreditTotals(None, None, None)

    total = sum(values)
    with localcontext() as context:
        context.prec = max(28, len(str(total)) + 12)
        pdu = (Decimal(total) / Decimal(60)).quantize(
            CREDIT_QUANTUM, rounding=ROUND_HALF_UP
        )
        ceu = (Decimal(total) / Decimal(600)).quantize(
            CREDIT_QUANTUM, rounding=ROUND_HALF_UP
        )
    return CreditTotals(total, pdu, ceu)
