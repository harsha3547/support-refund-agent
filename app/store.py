"""SQLite-backed mock store: customers, orders, order items and refunds."""
import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    customer_email TEXT NOT NULL,
    status TEXT NOT NULL,            -- in_transit | delivered | cancelled
    delivered_on TEXT                -- ISO date, NULL if not delivered
);
CREATE TABLE IF NOT EXISTS items (
    item_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    name TEXT NOT NULL,
    category TEXT NOT NULL,          -- apparel | footwear | gear | gift_card
    price REAL NOT NULL,
    final_sale INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS refunds (
    refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL REFERENCES items(item_id),
    amount REAL NOT NULL,
    reason TEXT NOT NULL,
    created_on TEXT NOT NULL
);
"""


def connect(path: str | Path = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def seed(conn: sqlite3.Connection, store_json: str | Path) -> None:
    """Load orders, items and any prior refunds from the generated store file."""
    data = json.loads(Path(store_json).read_text())
    conn.executemany("INSERT INTO orders VALUES (:order_id, :customer_email, :status, :delivered_on)", data["orders"])
    conn.executemany("INSERT INTO items VALUES (:item_id, :order_id, :name, :category, :price, :final_sale)", data["items"])
    conn.executemany("INSERT INTO refunds (item_id, amount, reason, created_on) VALUES (:item_id, :amount, :reason, :created_on)",
                     data.get("refunds", []))
    conn.commit()
