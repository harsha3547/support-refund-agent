"""Builds a Store backed by a SQLite file, creating and seeding it on first use."""
import json
import os
from datetime import date
from pathlib import Path

from app.actions import Store
from app.store import connect, seed

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def as_of_date(store_json: Path = DATA / "store.json") -> date:
    """The store's 'today', fixed in the data so policy decisions are reproducible."""
    return date.fromisoformat(json.loads(store_json.read_text())["as_of"])


def create_db(db_path: str | Path, store_json: Path = DATA / "store.json") -> Path:
    db_path = Path(db_path)
    db_path.unlink(missing_ok=True)
    conn = connect(db_path)
    seed(conn, store_json)
    conn.close()
    return db_path


def open_store(db_path: str | Path | None = None, store_json: Path = DATA / "store.json") -> Store:
    db_path = Path(db_path or os.getenv("STORE_DB", DATA / "store.db"))
    if not db_path.exists():
        create_db(db_path, store_json)
    return Store(connect(db_path), as_of_date(store_json), DATA / "refund_policy.md")
