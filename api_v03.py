from fastapi import HTTPException
from pydantic import BaseModel

from api import app, search, SearchRequest
from rag import ask_nemotron


class AskRequest(BaseModel):
    query: str
    limit: int = 5


@app.post("/ask")
def ask(req: AskRequest):
    if not req.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty"
        )

    # 1. Reuse the existing hybrid search endpoint internally.
    search_result = search(
        SearchRequest(
            query=req.query,
            limit=req.limit,
            deduplicate=True
        )
    )

    results = search_result.get(
        "results",
        []
    )

    if not results:
        return {
            "query": req.query,
            "answer": (
                "No encontré evidencia suficiente "
                "en la base de conocimiento."
            ),
            "source_package_ids": [],
            "insufficient_evidence": True,
            "retrieved": 0
        }

    # 2. Send retrieved evidence to Nemotron.
    try:
        rag_result = ask_nemotron(
            req.query,
            results
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"RAG generation failed: {exc}"
        )

    return {
        "query": req.query,
        "answer": rag_result.get(
            "answer",
            ""
        ),
        "source_package_ids":
            rag_result.get(
                "source_package_ids",
                []
            ),
        "insufficient_evidence":
            rag_result.get(
                "insufficient_evidence",
                False
            ),
        "retrieved": len(results),
        "sources": [
            {
                "package_id":
                    item["package_id"],
                "title":
                    item["title"],
                "hybrid_score":
                    item["hybrid_score"],
                "semantic_score":
                    item["semantic_score"],
                "lexical_score":
                    item["lexical_score"]
            }
            for item in results
        ]
    }
