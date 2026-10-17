def test_get_order_includes_items_and_prior_refunds(store):
    order = store.get_order("nw-2")
    assert order["order_id"] == "NW-2" and order["items"][0]["refunded"] == 20.0


def test_refund_within_window_is_eligible_for_full_price(store):
    check = store.check_refund_eligibility("NW-1", "IT-1", "changed_mind")
    assert check["eligible"] and check["max_amount"] == 90.0


def test_return_window_and_damage_exception(store):
    assert not store.check_refund_eligibility("NW-2", "IT-4", "changed_mind")["eligible"]   # 45 days > 30
    damaged = store.check_refund_eligibility("NW-2", "IT-4", "damaged")                       # 45 days < 60
    assert damaged["eligible"] and damaged["max_amount"] == 100.0                             # 120 - 20 already refunded


def test_gift_cards_final_sale_and_undelivered_are_not_refundable(store):
    assert not store.check_refund_eligibility("NW-1", "IT-2", "changed_mind")["eligible"]
    assert not store.check_refund_eligibility("NW-1", "IT-3", "changed_mind")["eligible"]
    assert store.check_refund_eligibility("NW-1", "IT-3", "damaged")["eligible"]             # damage overrides final sale
    assert not store.check_refund_eligibility("NW-3", "IT-5", "changed_mind")["eligible"]


def test_issue_refund_enforces_policy_even_if_asked_for_more(store):
    assert not store.issue_refund("NW-1", "IT-1", 500.0, "changed_mind")["ok"]      # prompt-injection style request
    assert store.issue_refund("NW-1", "IT-1", 90.0, "changed_mind")["ok"]
    assert not store.issue_refund("NW-1", "IT-1", 1.0, "changed_mind")["ok"]        # already fully refunded
    assert store.refunds_issued() == [{"item_id": "IT-1", "amount": 90.0, "reason": "changed_mind"}]


def test_issue_refund_rejects_bad_inputs(store):
    assert not store.issue_refund("NW-1", "IT-4", 10.0, "damaged")["ok"]      # item not in that order
    assert not store.issue_refund("NW-1", "IT-1", -5.0, "damaged")["ok"]
    assert not store.issue_refund("NW-1", "IT-1", 10.0, "because")["ok"]      # unknown reason


def test_only_in_transit_orders_can_be_cancelled(store):
    assert not store.update_order_status("NW-1", "cancelled")["ok"]
    assert store.update_order_status("NW-3", "cancelled")["ok"]
    assert store.get_order("NW-3")["status"] == "cancelled"
