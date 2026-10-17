import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.actions import Store  # noqa: E402
from app.store import connect  # noqa: E402

TODAY = date(2026, 10, 15)


@pytest.fixture()
def store():
    conn = connect(":memory:")
    conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", [
        ("NW-1", "a@example.com", "delivered", "2026-10-05"),    # 10 days ago
        ("NW-2", "a@example.com", "delivered", "2026-08-31"),    # 45 days ago
        ("NW-3", "b@example.com", "in_transit", None),
    ])
    conn.executemany("INSERT INTO items VALUES (?, ?, ?, ?, ?, ?)", [
        ("IT-1", "NW-1", "Rain Jacket", "apparel", 90.0, 0),
        ("IT-2", "NW-1", "Gift Card", "gift_card", 50.0, 0),
        ("IT-3", "NW-1", "Beanie", "apparel", 20.0, 1),          # final sale
        ("IT-4", "NW-2", "Trail Shoes", "footwear", 120.0, 0),
        ("IT-5", "NW-3", "Camp Stove", "gear", 55.0, 0),
    ])
    conn.execute("INSERT INTO refunds (item_id, amount, reason, created_on) VALUES ('IT-4', 20.0, 'other', '2026-09-10')")
    conn.commit()
    return Store(conn, TODAY, ROOT / "data" / "refund_policy.md")
