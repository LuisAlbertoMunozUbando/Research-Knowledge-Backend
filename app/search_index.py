import json
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / "knowledge-agent" / "data" / "knowledge.db"


def text_list(values):
    if not values:
        return ""
    return "\n".join(str(v).strip() for v in values if str(v).strip())


def relation_text(values):
    parts = []
    for value in values or []:
        if isinstance(value, dict):
            parts.append(" | ".join(f"{k}: {v}" for k, v in value.items()))
        else:
            text = str(value).strip()
            if text:
                parts.append(text)
    return "\n".join(parts)


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT id, title, package_final
        FROM packages
        WHERE package_final IS NOT NULL
          AND trim(package_final) <> ''
        ORDER BY id
        """
    ).fetchall()

    conn.execute("DELETE FROM package_search")

    indexed = 0
    for row in rows:
        try:
            final = json.loads(row["package_final"])
        except Exception:
            continue

        summary = str(final.get("summary") or "").strip()
        title = str(final.get("title") or row["title"] or "").strip()

        conn.execute(
            """
            INSERT INTO package_search (
                package_id,
                title,
                summary,
                topics,
                people,
                organizations,
                projects,
                concepts,
                key_points,
                relationships,
                metrics
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(row["id"]),
                title,
                summary,
                text_list(final.get("detected_topics", [])),
                text_list(final.get("people", [])),
                text_list(final.get("organizations", [])),
                text_list(final.get("projects", [])),
                text_list(final.get("concepts", [])),
                text_list(final.get("key_points", [])),
                relation_text(final.get("relationships", [])),
                text_list(final.get("metrics", [])),
            ),
        )
        indexed += 1

    conn.commit()
    conn.close()
    print(json.dumps({"ok": True, "indexed": indexed}))


if __name__ == "__main__":
    main()
