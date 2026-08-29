import json
import os
import time
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, HTTPException
from pydantic import BaseModel

from api_v10 import app
from api_v06 import remove_route
from api import search, SearchRequest
from rag import ask_nemotron


ASK_STATE_DIR = Path.home() / "research-knowledge" / "ask_states"
ASK_STATE_DIR.mkdir(parents=True, exist_ok=True)


class AskRequest(BaseModel):
    query: str
    limit: int = 5


def _state_path(token: str) -> Path:
    return ASK_STATE_DIR / f"{token}.json"


def _write_state(token: str, data: dict):
    path = _state_path(token)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _read_state(token: str) -> dict:
    path = _state_path(token)
    if not path.exists():
        raise FileNotFoundError(token)
    return json.loads(path.read_text(encoding="utf-8"))


def _run_ask(token: str, query: str, limit: int):
    started = time.time()

    try:
        _write_state(token, {
            "ok": True,
            "ask_token": token,
            "status": "retrieving",
            "query": query,
        })

        search_result = search(
            SearchRequest(
                query=query,
                limit=limit,
                deduplicate=True,
            )
        )

        results = search_result.get("results", [])

        if not results:
            _write_state(token, {
                "ok": True,
                "ask_token": token,
                "status": "completed",
                "query": query,
                "answer": (
                    "No encontré evidencia suficiente "
                    "en la base de conocimiento."
                ),
                "source_package_ids": [],
                "insufficient_evidence": True,
                "retrieved": 0,
                "sources": [],
                "seconds": round(time.time() - started, 2),
            })
            return

        _write_state(token, {
            "ok": True,
            "ask_token": token,
            "status": "generating",
            "query": query,
            "retrieved": len(results),
        })

        rag_result = ask_nemotron(query, results)

        _write_state(token, {
            "ok": True,
            "ask_token": token,
            "status": "completed",
            "query": query,
            "answer": rag_result.get("answer", ""),
            "source_package_ids": rag_result.get(
                "source_package_ids", []
            ),
            "insufficient_evidence": rag_result.get(
                "insufficient_evidence", False
            ),
            "retrieved": len(results),
            "sources": [
                {
                    "package_id": item["package_id"],
                    "title": item["title"],
                    "hybrid_score": item["hybrid_score"],
                    "semantic_score": item["semantic_score"],
                    "lexical_score": item["lexical_score"],
                }
                for item in results
            ],
            "seconds": round(time.time() - started, 2),
        })

    except Exception as exc:
        _write_state(token, {
            "ok": False,
            "ask_token": token,
            "status": "failed",
            "query": query,
            "error": str(exc),
            "seconds": round(time.time() - started, 2),
        })


# Replace legacy synchronous /ask inherited through api_v03.
remove_route("/ask", "POST")


@app.post("/ask", status_code=202)
def ask_async(req: AskRequest, background_tasks: BackgroundTasks):
    query = req.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty",
        )

    limit = max(1, min(int(req.limit), 8))
    token = uuid.uuid4().hex[:12]

    _write_state(token, {
        "ok": True,
        "ask_token": token,
        "status": "queued",
        "query": query,
    })

    background_tasks.add_task(
        _run_ask,
        token,
        query,
        limit,
    )

    return {
        "ok": True,
        "ask_token": token,
        "status": "queued",
        "status_endpoint": f"/ask-status/{token}",
    }


@app.get("/ask-status/{ask_token}")
def ask_status(ask_token: str):
    try:
        return _read_state(ask_token)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Ask state not found",
        )


@app.get("/v11/status")
def v11_status():
    return {
        "ok": True,
        "version": "0.11.0",
        "pipeline": "persistent-resumable-async",
        "upload_behavior": "202-accepted-background-processing",
        "ask_behavior": "202-accepted-background-inference",
        "rag_num_ctx": 16384,
        "rag_num_predict": 768,
        "ask_status_endpoint": "/ask-status/{ask_token}",
    }
