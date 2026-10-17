"""The refund policy as code. Every refund is checked here, no matter who (or what) asked for it."""
from dataclasses import dataclass, field
from datetime import date

RETURN_WINDOW_DAYS = 30
DAMAGED_WINDOW_DAYS = 60
DAMAGE_REASONS = {"damaged", "defective", "wrong_item"}


@dataclass
class Eligibility:
    eligible: bool
    max_amount: float
    reasons: list[str] = field(default_factory=list)


def check(item: dict, order: dict, already_refunded: float, reason: str, today: date) -> Eligibility:
    """Decide whether an item can be refunded and for how much.

    item:  {price, category, final_sale}
    order: {status, delivered_on}
    reason: one of damaged, defective, wrong_item, changed_mind, too_small, too_large, other
    """
    remaining = round(item["price"] - already_refunded, 2)
    damage = reason in DAMAGE_REASONS

    if order["status"] != "delivered" or not order["delivered_on"]:
        return Eligibility(False, 0.0, ["Order has not been delivered yet; offer tracking instead."])
    if remaining <= 0:
        return Eligibility(False, 0.0, ["Item has already been fully refunded."])

    age = (today - date.fromisoformat(order["delivered_on"])).days
    if damage and age > DAMAGED_WINDOW_DAYS:
        return Eligibility(False, 0.0, [f"Delivered {age} days ago; damaged/wrong items are refundable within {DAMAGED_WINDOW_DAYS} days."])
    if not damage:
        if item["category"] == "gift_card":
            return Eligibility(False, 0.0, ["Gift cards are not refundable."])
        if item["final_sale"]:
            return Eligibility(False, 0.0, ["Final sale items are not refundable."])
        if age > RETURN_WINDOW_DAYS:
            return Eligibility(False, 0.0, [f"Delivered {age} days ago; the return window is {RETURN_WINDOW_DAYS} days."])

    return Eligibility(True, remaining, [f"Eligible for up to ${remaining:.2f} ({'damage/wrong item' if damage else 'within return window'})."])
