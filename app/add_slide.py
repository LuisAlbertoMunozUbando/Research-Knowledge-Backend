import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path.home() / "knowledge-agent" / "data" / "knowledge.db"


def now():
    return datetime.now(timezone.utc).isoformat()


def load_verified(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(data.get("visual_verified"), dict):
        visual_verified = data["visual_verified"]
        visual_raw = data.get("visual_raw", {})
    else:
        visual_verified = data
        visual_raw = {}

    return {
        "visual_raw": visual_raw,
        "visual_verified": visual_verified,
    }


def add_slide(package_id: int, sequence: int, verified_path: Path):
    verified_path = Path(verified_path).expanduser().resolve()
    if not verified_path.exists():
        raise FileNotFoundError(verified_path)

    data = load_verified(verified_path)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    package = conn.execute(
        "SELECT * FROM packages WHERE id = ?",
        (int(package_id),),
    ).fetchone()

    if not package:
        conn.close()
        raise ValueError(f"Package {package_id} not found")

    cur = conn.execute(
        """
        INSERT INTO slides (
            package_id,
            sequence,
            image_path,
            visual_raw,
            visual_verified,
            knowledge_normalized,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(package_id, sequence) DO UPDATE SET
            image_path=excluded.image_path,
            visual_raw=excluded.visual_raw,
            visual_verified=excluded.visual_verified,
            knowledge_normalized=excluded.knowledge_normalized
        """,
        (
            int(package_id),
            int(sequence),
            str(verified_path),
            json.dumps(data["visual_raw"], ensure_ascii=False),
            json.dumps(data["visual_verified"], ensure_ascii=False),
            json.dumps(data["visual_verified"], ensure_ascii=False),
            now(),
        ),
    )

    received = conn.execute(
        "SELECT COUNT(*) FROM slides WHERE package_id = ?",
        (int(package_id),),
    ).fetchone()[0]

    expected = int(package["expected_slides"])
    status = "complete" if received >= expected else "collecting"
    completed_at = now() if status == "complete" else None

    conn.execute(
        """
        UPDATE packages
        SET received_slides = ?, status = ?, completed_at = ?
        WHERE id = ?
        """,
        (received, status, completed_at, int(package_id)),
    )

    conn.commit()
    slide = conn.execute(
        "SELECT id FROM slides WHERE package_id = ? AND sequence = ?",
        (int(package_id), int(sequence)),
    ).fetchone()
    conn.close()

    return {
        "slide_id": int(slide["id"]),
        "package_id": int(package_id),
        "sequence": int(sequence),
        "received_slides": int(received),
        "expected_slides": expected,
        "status": status,
    }


def main():
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: add_slide.py <package_id> <sequence> <verified_json>"
        )

    result = add_slide(
        package_id=int(sys.argv[1]),
        sequence=int(sys.argv[2]),
        verified_path=Path(sys.argv[3]),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
