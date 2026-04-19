"""Semantic search over the Qdrant disclosure collection."""

from __future__ import annotations

import asyncio
from typing import Any

from pengod.config import Settings, get_settings
from pengod.ingest.embeddings import LocalEmbedder
from pengod.rag.qdrant_store import QdrantConnection


async def semantic_search(
    query: str,
    *,
    limit: int = 8,
    settings: Settings | None = None,
    embedder: LocalEmbedder | None = None,
    qdrant: QdrantConnection | None = None,
) -> list[dict[str, Any]]:
    """
    Embed the query and run vector search. Caller must pass embedder/qdrant or defaults are created.
    """
    settings = settings or get_settings()
    own_q = qdrant is None
    own_e = embedder is None
    if qdrant is None:
        qdrant = QdrantConnection(settings=settings)
    if embedder is None:
        embedder = LocalEmbedder(settings.embedding_model)

    try:
        vectors = await asyncio.to_thread(embedder.embed, [query])
        if not vectors:
            return []
        # qdrant-client 1.17+: use query_points (search() removed from AsyncQdrantClient)
        resp = await qdrant.client.query_points(
            collection_name=qdrant.default_collection,
            query=vectors[0],
            limit=limit,
            with_payload=True,
        )
        out: list[dict[str, Any]] = []
        for hit in resp.points:
            out.append(
                {
                    "score": hit.score,
                    "payload": hit.payload or {},
                    "id": str(hit.id),
                }
            )
        return out
    finally:
        if own_q:
            await qdrant.close()
