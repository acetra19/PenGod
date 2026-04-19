"""Authorized engagement: probe in-scope URL + RAG pattern retrieval."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, HttpUrl

from pengod.api.deps import verify_optional_api_key
from pengod.config import get_settings
from pengod.recon.probe import build_rag_query_from_probe, probe_target_url
from pengod.rag.search import semantic_search

router = APIRouter(tags=["engagement"])


class EngagementRunBody(BaseModel):
    """Only use target_url values you are explicitly allowed to test."""

    target_url: HttpUrl = Field(..., description="In-scope http(s) URL")
    rag_query_hint: str | None = Field(None, max_length=2000, description="Override automatic RAG query")
    rag_limit: int = Field(8, ge=1, le=25)


@router.post("/engagement/run", dependencies=[Depends(verify_optional_api_key)])
async def engagement_run(request: Request, body: EngagementRunBody) -> dict[str, Any]:
    """
    1) HTTP probe of target (SSRF-guarded).
    2) Semantic search over ingested disclosure chunks related to the probe.
    """
    settings = getattr(request.app.state, "settings", get_settings())
    qdrant = getattr(request.app.state, "qdrant", None)
    embedder = getattr(request.app.state, "embedder", None)
    if qdrant is None or embedder is None:
        raise HTTPException(status_code=503, detail="Service not ready")
    try:
        qh = await qdrant.health()
    except Exception:
        raise HTTPException(status_code=503, detail="Qdrant unavailable") from None
    if not isinstance(qh, dict) or qh.get("ok") is not True:
        raise HTTPException(status_code=503, detail="Qdrant unavailable")

    url_str = str(body.target_url).strip()
    try:
        probe = await probe_target_url(
            url_str,
            timeout_seconds=settings.probe_timeout_seconds,
            max_redirects=settings.probe_max_redirects,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    qtext = build_rag_query_from_probe(probe, url_str, body.rag_query_hint)
    results = await semantic_search(
        qtext,
        limit=body.rag_limit,
        embedder=embedder,
        qdrant=qdrant,
    )
    return {
        "disclaimer": "For authorized testing only. Verify program scope before any further action.",
        "target_url": url_str,
        "probe": probe,
        "rag_query_used": qtext,
        "rag_hits": results,
    }
