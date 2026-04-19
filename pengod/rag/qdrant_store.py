"""Async Qdrant client helper for collections and health checks."""

from __future__ import annotations

from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from pengod.config import Settings, get_settings


class QdrantConnection:
    """
    Thin wrapper around AsyncQdrantClient with project defaults.
    Does not store secrets in code — use Settings / environment.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = AsyncQdrantClient(
            url=self._settings.qdrant_url,
            api_key=self._settings.qdrant_api_key,
        )

    @property
    def client(self) -> AsyncQdrantClient:
        return self._client

    @property
    def default_collection(self) -> str:
        return self._settings.qdrant_collection

    async def close(self) -> None:
        await self._client.close()

    async def health(self) -> dict[str, Any]:
        """Return collection names for startup checks (Qdrant reachable)."""
        result = await self._client.get_collections()
        names = [c.name for c in result.collections]
        return {"ok": True, "collections": names}

    async def ensure_collection(
        self,
        name: str | None = None,
        *,
        vector_size: int,
        distance: Distance = Distance.COSINE,
    ) -> None:
        """Create collection if missing (idempotent for same params)."""
        collection = name or self.default_collection
        existing = await self._client.get_collections()
        if any(c.name == collection for c in existing.collections):
            return
        await self._client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=vector_size, distance=distance),
        )

    async def upsert_points(
        self,
        points: list[PointStruct],
        *,
        collection: str | None = None,
    ) -> None:
        if not points:
            return
        await self._client.upsert(
            collection_name=collection or self.default_collection,
            points=points,
        )
