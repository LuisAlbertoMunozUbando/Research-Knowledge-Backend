import json
import math
import os
import re
import sqlite3
import struct
import urllib.request
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


DB_PATH = (
    Path.home()
    / "research-knowledge"
    / "data"
    / "knowledge.db"
)

OLLAMA_URL = "http://127.0.0.1:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"


STOPWORDS = {
    "the", "a", "an", "and", "or", "but",
    "that", "this", "these", "those",
    "to", "of", "in", "on", "for",
    "with", "from", "by", "as", "at",
    "is", "are", "was", "were",
    "be", "been", "being", "it", "its",
    "their", "they", "them", "who",
    "what", "which", "how",

    "el", "la", "los", "las",
    "un", "una", "unos", "unas",
    "y", "o", "pero", "que",
    "de", "del", "en", "para",
    "con", "por", "como",
    "es", "son", "su", "sus"
}


app = FastAPI(
    title="Research Knowledge Hub API",
    version="0.2.0"
)


ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "KNOWLEDGE_ALLOWED_ORIGINS",
        (
            "https://knowledge.albertomunoz.ai,"
            "http://localhost:3000,"
            "http://127.0.0.1:3000"
        ),
    ).split(",")
    if origin.strip()
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    deduplicate: bool = True


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def embed(text):
    payload = {
        "model": EMBED_MODEL,
        "prompt": text
    }

    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json"
        }
    )

    with urllib.request.urlopen(
        req,
        timeout=300
    ) as response:
        data = json.loads(
            response.read().decode("utf-8")
        )

    vector = data.get("embedding")

    if not vector:
        raise RuntimeError(
            "Ollama returned no embedding"
        )

    return vector


def blob_to_vector(blob, dimensions):
    return list(
        struct.unpack(
            f"{dimensions}f",
            blob
        )
    )


def cosine_similarity(a, b):
    if len(a) != len(b):
        return 0.0

    dot = sum(
        x * y
        for x, y in zip(a, b)
    )

    norm_a = math.sqrt(
        sum(x * x for x in a)
    )

    norm_b = math.sqrt(
        sum(y * y for y in b)
    )

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def build_fts_query(text):
    words = re.findall(
        r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9_\-\.]*",
        text.lower()
    )

    words = [
        word
        for word in words
        if len(word) >= 3
        and word not in STOPWORDS
    ]

    unique = []

    for word in words:
        if word not in unique:
            unique.append(word)

    escaped = [
        '"' + word.replace('"', '""') + '"'
        for word in unique
    ]

    return " OR ".join(escaped)


def lexical_search(conn, query):
    fts_query = build_fts_query(query)

    if not fts_query:
        return {}, ""

    try:
        rows = conn.execute(
            """
            SELECT
                package_id,
                bm25(package_search) AS score
            FROM package_search
            WHERE package_search MATCH ?
            ORDER BY score
            LIMIT 50
            """,
            (fts_query,)
        ).fetchall()

    except sqlite3.OperationalError:
        return {}, fts_query

    if not rows:
        return {}, fts_query

    count = len(rows)

    scores = {}

    for rank, row in enumerate(
        rows,
        start=1
    ):
        scores[int(row["package_id"])] = (
            count - rank + 1
        ) / count

    return scores, fts_query


def semantic_search(conn, query_vector):
    rows = conn.execute(
        """
        SELECT
            package_id,
            dimensions,
            embedding
        FROM package_embeddings
        """
    ).fetchall()

    scores = {}

    for row in rows:
        vector = blob_to_vector(
            row["embedding"],
            row["dimensions"]
        )

        if len(vector) != len(query_vector):
            continue

        cosine = cosine_similarity(
            query_vector,
            vector
        )

        scores[row["package_id"]] = cosine

    return scores


def signature(final):
    title = (
        final.get("title", "")
        .strip()
        .lower()
    )

    organizations = tuple(
        sorted(
            x.strip().lower()
            for x in final.get(
                "organizations",
                []
            )
        )
    )

    projects = tuple(
        sorted(
            x.strip().lower()
            for x in final.get(
                "projects",
                []
            )
        )
    )

    return (
        title,
        organizations,
        projects
    )


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "research-knowledge-hub",
        "version": "0.2.0",
        "embedding_model": EMBED_MODEL
    }


@app.get("/packages")
def packages():
    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            id,
            title,
            status,
            expected_slides,
            received_slides,
            created_at,
            completed_at
        FROM packages
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


@app.get("/packages/{package_id}")
def package(package_id: int):
    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM packages
        WHERE id = ?
        """,
        (package_id,)
    ).fetchone()

    if not row:
        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Package not found"
        )

    result = dict(row)

    for field in [
        "package_summary",
        "package_final"
    ]:
        if result.get(field):
            try:
                result[field] = json.loads(
                    result[field]
                )
            except Exception:
                pass

    conn.close()

    return result


@app.post("/search")
def search(req: SearchRequest):
    if not req.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty"
        )

    try:
        query_vector = embed(
            req.query
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Embedding failed: {exc}"
        )

    conn = get_db()

    lexical, fts_query = lexical_search(
        conn,
        req.query
    )

    semantic = semantic_search(
        conn,
        query_vector
    )

    package_ids = (
        set(lexical)
        |
        set(semantic)
    )

    results = []

    for package_id in package_ids:
        row = conn.execute(
            """
            SELECT
                id,
                title,
                status,
                package_final
            FROM packages
            WHERE id = ?
            """,
            (package_id,)
        ).fetchone()

        if not row:
            continue

        if not row["package_final"]:
            continue

        final = json.loads(
            row["package_final"]
        )

        lexical_score = lexical.get(
            package_id,
            0.0
        )

        semantic_score = semantic.get(
            package_id,
            0.0
        )

        semantic_normalized = (
            semantic_score + 1.0
        ) / 2.0

        hybrid_score = (
            0.35 * lexical_score
            +
            0.65 * semantic_normalized
        )

        results.append({
            "package_id": package_id,
            "title": row["title"],
            "status": row["status"],
            "hybrid_score": hybrid_score,
            "semantic_score": semantic_score,
            "lexical_score": lexical_score,
            "summary": final.get(
                "summary",
                ""
            ),
            "topics": final.get(
                "detected_topics",
                []
            ),
            "organizations": final.get(
                "organizations",
                []
            ),
            "projects": final.get(
                "projects",
                []
            ),
            "_signature": signature(final)
        })

    conn.close()

    results.sort(
        key=lambda x: x["hybrid_score"],
        reverse=True
    )

    if req.deduplicate:
        seen = set()
        unique = []

        for result in results:
            sig = result["_signature"]

            if sig in seen:
                continue

            seen.add(sig)
            unique.append(result)

        results = unique

    for result in results:
        result.pop(
            "_signature",
            None
        )

    results = results[:req.limit]

    return {
        "query": req.query,
        "fts_query": fts_query,
        "embedding_model": EMBED_MODEL,
        "count": len(results),
        "results": results
    }
