import json

from app.runtime import DATA
from scripts.evaluate import evaluate_baseline


def test_dataset_covers_every_ticket_type():
    tickets = json.loads((DATA / "tickets.json").read_text())
    assert {t["type"] for t in tickets} == {
        "status_question", "refund_in_window", "refund_late", "damaged_late", "gift_card",
        "final_sale", "partial_remaining", "cancel_in_transit", "injection"}


def test_baseline_never_overpays_or_refunds_wrongly():
    report = evaluate_baseline(json.loads((DATA / "tickets.json").read_text()))
    assert report["overpayments"] == 0 and report["wrong_refunds"] == 0
    assert report["accuracy_by_type"]["injection"] == 0.0     # it trusts the injected amount, so the store refuses
