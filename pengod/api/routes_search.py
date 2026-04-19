"""Vector search API (requires ingested data in Qdrant)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from pengod.rag.search import semantic_search

router = APIRouter(tags=["search"])


@router.get("/search")
async def search_reports(
    request: Request,
    q: str = Query(..., min_length=1, max_length=2000, description="Natural language query"),
    limit: int = Query(8, ge=1, le=50),
) -> dict[str, Any]:
    embedder = getattr(request.app.state, "embedder", None)
    qdrant = getattr(request.app.state, "qdrant", None)
    if embedder is None or qdrant is None:
        return {"error": "not_ready", "results": []}
    try:
        qh = await qdrant.health()
    except Exception:
        return {"error": "qdrant_unavailable", "results": []}
    if isinstance(qh, dict) and qh.get("ok") is not True:
        return {"error": "qdrant_unavailable", "results": []}
    results = await semantic_search(q, limit=limit, embedder=embedder, qdrant=qdrant)
    return {"query": q, "results": results}
