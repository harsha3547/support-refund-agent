"""Rule-based support bot: the offline baseline the agent is compared against.

It handles tickets with keyword rules: find the order id, guess the intent and reason from
keywords, take any dollar amount the customer mentions at face value, and act. It has no
judgment, so it is easily misled, but the store's own policy checks still stop it from
paying out more than allowed.
"""
import re

from app.actions import Store

DAMAGE_WORDS = ("damaged", "broken", "defective", "arrived torn", "wrong item")


def resolve_ticket(store: Store, message: str) -> list[str]:
    """Handle one ticket. Returns a log of what the bot did."""
    log = []
    m = re.search(r"\bNW-\d+\b", message, re.I)
    if not m:
        return ["No order id found; asked the customer for it."]
    order = store.get_order(m.group(0))
    if "error" in order:
        return [order["error"]]
    text = message.lower()

    if "cancel" in text:
        result = store.update_order_status(order["order_id"], "cancelled")
        return [f"cancel -> {result}"]

    if not any(w in text for w in ("refund", "return", "money back")):
        return [f"Status reply: order is {order['status']}."]

    item = next((it for it in order["items"] if it["name"].lower() in text), order["items"][0])
    reason = "damaged" if any(w in text for w in DAMAGE_WORDS) else "changed_mind"
    asked = re.search(r"\$\s?(\d+(?:\.\d{1,2})?)", message)
    amount = float(asked.group(1)) if asked else item["price"]     # trusts the customer's number
    result = store.issue_refund(order["order_id"], item["item_id"], amount, reason)
    log.append(f"refund {item['item_id']} ${amount:.2f} ({reason}) -> {result}")
    return log
