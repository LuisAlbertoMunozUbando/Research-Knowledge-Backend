import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path.home() / "knowledge-agent" / "data" / "knowledge.db"


def now():
    return datetime.now(timezone.utc).isoformat()


def create_package(title: str, expected_slides: int, user_note: str = "") -> int:
    if not title or not title.strip():
        raise ValueError("Package title cannot be empty")
    if expected_slides < 1:
        raise ValueError("expected_slides must be at least 1")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        """
        INSERT INTO packages (
            title,
            user_note,
            expected_slides,
            received_slides,
            status,
            created_at
        ) VALUES (?, ?, ?, 0, 'collecting', ?)
        """,
        (title.strip(), user_note or "", int(expected_slides), now()),
    )
    package_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return package_id


def get_package(package_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM packages WHERE id = ?",
        (int(package_id),),
    ).fetchone()
    conn.close()
    return dict(row) if row else None
