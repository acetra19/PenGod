"""FastAPI application with Qdrant lifecycle checks."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request

from pengod import __version__
from pengod.api.routes_search import router as search_router
from pengod.config import Settings, get_settings
from pengod.ingest.embeddings import LocalEmbedder
from pengod.rag.qdrant_store import QdrantConnection


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    qdrant = QdrantConnection(settings=settings)
    app.state.settings = settings
    app.state.qdrant = qdrant
    app.state.embedder = LocalEmbedder(settings.embedding_model)
    try:
        app.state.qdrant_health = await qdrant.health()
    except Exception as exc:  # noqa: BLE001 — surface connection errors to logs / health
        app.state.qdrant_health = {"ok": False, "error": str(exc)}
        if settings.qdrant_strict:
            await qdrant.close()
            raise
    yield
    await qdrant.close()


app = FastAPI(
    title="PenGod API",
    description="Authorized bug bounty research backend (RAG + agents).",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(search_router, prefix="/v1")


@app.get("/health")
async def health(request: Request) -> dict[str, Any]:
    qdrant = getattr(request.app.state, "qdrant", None)
    if qdrant is None:
        return {
            "status": "degraded",
            "qdrant": {"ok": False, "error": "not_initialized"},
            "version": __version__,
        }
    try:
        qh = await qdrant.health()
    except Exception as exc:  # noqa: BLE001
        qh = {"ok": False, "error": str(exc)}
    q_ok = bool(isinstance(qh, dict) and qh.get("ok") is True)
    return {
        "status": "ok" if q_ok else "degraded",
        "qdrant": qh,
        "version": __version__,
    }


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "pengod", "version": __version__, "docs": "/docs"}


def get_app_settings(request: Request) -> Settings:
    """Dependency helper for routes that need settings."""
    return getattr(request.app.state, "settings", get_settings())
