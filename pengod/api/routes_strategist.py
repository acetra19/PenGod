"""Full Strategist pipeline: probe → RAG → Ollama."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, HttpUrl, model_validator

from pengod.agents.strategist_pipeline import build_strategist_graph
from pengod.api.deps import verify_optional_api_key
from pengod.config import get_settings

router = APIRouter(tags=["strategist"])

_MAX_URLS = 25


class StrategistRunBody(BaseModel):
    """Authorized targets. Ollama must reach settings.ollama_base_url from the API process."""

    target_url: HttpUrl | None = Field(None, description="Single URL (legacy; use target_urls for multiple)")
    target_urls: list[HttpUrl] | None = Field(None, description="One or more in-scope URLs")
    program_scope: str | None = Field(
        None,
        max_length=8000,
        description="Bug bounty / program scope — agents align suggestions to this text",
    )

    @model_validator(mode="after")
    def normalize_urls(self) -> StrategistRunBody:
        urls = self.target_urls
        if urls:
            if len(urls) > _MAX_URLS:
                raise ValueError(f"At most {_MAX_URLS} URLs per request")
            return self
        if self.target_url is not None:
            self.target_urls = [self.target_url]
            return self
        raise ValueError("Provide target_url or target_urls")


@router.post("/strategist/run", dependencies=[Depends(verify_optional_api_key)])
async def strategist_run(request: Request, body: StrategistRunBody) -> dict[str, Any]:
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

    scope = (body.program_scope or "").strip() or None
    graph = build_strategist_graph(settings=settings, qdrant=qdrant, embedder=embedder)
    runs: list[dict[str, Any]] = []
    assert body.target_urls is not None
    for tu in body.target_urls:
        url_str = str(tu).strip()
        try:
            out = await graph.ainvoke(
                {
                    "target_url": url_str,
                    "program_scope": scope,
                }
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Strategist pipeline failed for {url_str} "
                    f"(is Ollama running at {settings.ollama_base_url}?): {exc}"
                ),
            ) from exc
        runs.append(
            {
                "target_url": url_str,
                "probe": out.get("probe"),
                "rag_query": out.get("rag_query"),
                "rag_hits": out.get("rag_hits"),
                "strategist_report": out.get("strategist_report"),
                "pipeline_error": out.get("error"),
            }
        )

    return {
        "disclaimer": "Authorized testing only. This is research assistance, not a pentest certificate.",
        "program_scope": scope,
        "runs": runs,
    }
