import json
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / "knowledge-agent" / "data" / "knowledge.db"
OUT_DIR = Path.home() / "knowledge-agent" / "data" / "embedding_jobs"


def as_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return "; ".join(f"{k}: {v}" for k, v in value.items())
    return str(value).strip()


def join_values(values):
    if not isinstance(values, list):
        return ""
    parts = [as_text(v) for v in values]
    return "; ".join(x for x in parts if x)


def build_search_document(final):
    sections = [
        ("Title", as_text(final.get("title"))),
        ("Summary", as_text(final.get("summary"))),
        ("Topics", join_values(final.get("detected_topics", []))),
        ("People", join_values(final.get("people", []))),
        ("Organizations", join_values(final.get("organizations", []))),
        ("Projects", join_values(final.get("projects", []))),
        ("Concepts", join_values(final.get("concepts", []))),
        ("Key points", join_values(final.get("key_points", []))),
        ("Relationships", join_values(final.get("relationships", []))),
        ("Metrics", join_values(final.get("metrics", []))),
        ("Visible links", join_values(final.get("links_visible", []))),
        ("Mentioned links", join_values(final.get("links_mentioned", []))),
        ("Uncertainties", join_values(final.get("uncertainties", []))),
    ]
    text = "\n".join(f"{name}: {value}" for name, value in sections if value).strip()
    if not text:
        raise ValueError("Canonical package contains no searchable text")
    return text


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, package_final FROM packages WHERE package_final IS NOT NULL ORDER BY id"
    ).fetchall()
    conn.close()

    written = 0
    skipped = 0
    for package_id, package_final in rows:
        try:
            final = json.loads(package_final)
            document = build_search_document(final)
        except Exception as exc:
            skipped += 1
            print(f"SKIP package {package_id}: {exc}")
            continue

        output = OUT_DIR / f"package_{package_id}.embedding_job.json"
        output.write_text(
            json.dumps(
                {"package_id": package_id, "search_document": document},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        written += 1
        print(output)

    print(f"EMBEDDING JOBS WRITTEN: {written}")
    print(f"EMBEDDING JOBS SKIPPED: {skipped}")


if __name__ == "__main__":
    main()
