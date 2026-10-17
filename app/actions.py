"""Store operations. These plain functions back both the MCP server and the rule-based baseline.

Read actions run freely. Write actions (issue_refund, update_order_status) re-check the policy
themselves, so even an approved request cannot pay out more than the policy allows.
"""
import sqlite3
from datetime import date
from pathlib import Path

from app import policy

REASONS = ["damaged", "defective", "wrong_item", "changed_mind", "too_small", "too_large", "other"]
WRITE_TOOLS = {"issue_refund", "update_order_status"}   # require human approval in the agent


class Store:
    def __init__(self, conn: sqlite3.Connection, today: date, policy_path: str | Path = "data/refund_policy.md"):
        self.conn, self.today, self.policy_path = conn, today, Path(policy_path)

    # ---------- reads ----------
    def get_order(self, order_id: str) -> dict:
        order = self.conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id.strip().upper(),)).fetchone()
        if not order:
            return {"error": f"No order {order_id}."}
        items = []
        for it in self.conn.execute("SELECT * FROM items WHERE order_id = ?", (order["order_id"],)):
            items.append(dict(it) | {"final_sale": bool(it["final_sale"]), "refunded": self._refunded(it["item_id"])})
        return dict(order) | {"items": items}

    def list_orders(self, customer_email: str) -> list[dict]:
        rows = self.conn.execute("SELECT order_id, status, delivered_on FROM orders WHERE lower(customer_email) = lower(?)",
                                 (customer_email.strip(),))
        return [dict(r) for r in rows]

    def get_refund_policy(self) -> str:
        return self.policy_path.read_text()

    def check_refund_eligibility(self, order_id: str, item_id: str, reason: str) -> dict:
        item_id = item_id.strip().upper()
        found = self._item_and_order(order_id, item_id)
        if "error" in found:
            return found
        item, order = found["item"], found["order"]
        e = policy.check(item, order, self._refunded(item_id), reason, self.today)
        return {"eligible": e.eligible, "max_amount": e.max_amount, "reasons": e.reasons}

    # ---------- writes (approval required in the agent) ----------
    def issue_refund(self, order_id: str, item_id: str, amount: float, reason: str) -> dict:
        item_id = item_id.strip().upper()
        if reason not in REASONS:
            return {"ok": False, "error": f"Unknown reason '{reason}'. Use one of {REASONS}."}
        if amount <= 0:
            return {"ok": False, "error": "Refund amount must be positive."}
        check = self.check_refund_eligibility(order_id, item_id, reason)
        if "error" in check:
            return {"ok": False, "error": check["error"]}
        if not check["eligible"]:
            return {"ok": False, "error": "Not eligible: " + " ".join(check["reasons"])}
        if amount > check["max_amount"] + 1e-9:
            return {"ok": False, "error": f"Amount ${amount:.2f} exceeds the maximum refundable ${check['max_amount']:.2f}."}
        self.conn.execute("INSERT INTO refunds (item_id, amount, reason, created_on) VALUES (?, ?, ?, ?)",
                          (item_id, round(amount, 2), reason, self.today.isoformat()))
        self.conn.commit()
        return {"ok": True, "refunded": round(amount, 2), "item_id": item_id}

    def update_order_status(self, order_id: str, status: str) -> dict:
        if status not in {"cancelled"}:
            return {"ok": False, "error": "Only cancelling an order is supported."}
        order = self.conn.execute("SELECT status FROM orders WHERE order_id = ?", (order_id.strip().upper(),)).fetchone()
        if not order:
            return {"ok": False, "error": f"No order {order_id}."}
        if order["status"] != "in_transit":
            return {"ok": False, "error": f"Only in-transit orders can be cancelled (this one is {order['status']})."}
        self.conn.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id.strip().upper()))
        self.conn.commit()
        return {"ok": True, "order_id": order_id.strip().upper(), "status": status}

    # ---------- helpers ----------
    def refunds_issued(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT item_id, amount, reason FROM refunds WHERE created_on = ?",
                                                   (self.today.isoformat(),))]

    def _refunded(self, item_id: str) -> float:
        row = self.conn.execute("SELECT COALESCE(SUM(amount), 0) AS s FROM refunds WHERE item_id = ?", (item_id,)).fetchone()
        return round(row["s"], 2)

    def _item_and_order(self, order_id: str, item_id: str) -> dict:
        item = self.conn.execute("SELECT * FROM items WHERE item_id = ?", (item_id.strip().upper(),)).fetchone()
        if not item or item["order_id"] != order_id.strip().upper():
            return {"error": f"Item {item_id} is not part of order {order_id}."}
        order = self.conn.execute("SELECT * FROM orders WHERE order_id = ?", (item["order_id"],)).fetchone()
        return {"item": dict(item), "order": dict(order)}
