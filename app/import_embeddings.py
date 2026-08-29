import json
import sqlite3
import struct
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path.home() / "knowledge-agent" / "data" / "knowledge.db"
JOBS_DIR = Path.home() / "knowledge-agent" / "data" / "embedding_jobs"


def vector_to_blob(vector):
    if not isinstance(vector, list) or not vector:
        raise ValueError("embedding must be a non-empty list")
    values = [float(x) for x in vector]
    return struct.pack(f"{len(values)}f", *values)


def main():
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(JOBS_DIR.glob("package_*.embedding_result.json"))

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    imported = 0
    skipped = 0

    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            package_id = int(data["package_id"])
            model = str(data["model"]).strip()
            dimensions = int(data["dimensions"])
            document = str(data["search_document"]).strip()
            vector = data["embedding"]

            if not model:
                raise ValueError("model is empty")
            if not document:
                raise ValueError("search_document is empty")
            if dimensions <= 0:
                raise ValueError("dimensions must be positive")
            if len(vector) != dimensions:
                raise ValueError(
                    f"dimension mismatch: declared {dimensions}, got {len(vector)}"
                )

            exists = conn.execute(
                "SELECT 1 FROM packages WHERE id=?",
                (package_id,),
            ).fetchone()
            if not exists:
                raise ValueError(f"package {package_id} does not exist")

            blob = vector_to_blob(vector)
            now = datetime.now(timezone.utc).isoformat()

            conn.execute(
                """
                INSERT INTO package_embeddings (
                    package_id, model, dimensions,
                    search_document, embedding, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(package_id) DO UPDATE SET
                    model=excluded.model,
                    dimensions=excluded.dimensions,
                    search_document=excluded.search_document,
                    embedding=excluded.embedding,
                    created_at=excluded.created_at
                """,
                (package_id, model, dimensions, document, blob, now),
            )
            imported += 1
            print(f"IMPORTED package {package_id}: {dimensions} dimensions")
        except Exception as exc:
            skipped += 1
            print(f"SKIP {path.name}: {exc}")

    conn.commit()
    conn.close()

    print(f"EMBEDDINGS IMPORTED: {imported}")
    print(f"EMBEDDINGS SKIPPED: {skipped}")


if __name__ == "__main__":
    main()
