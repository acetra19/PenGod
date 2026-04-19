"""End-to-end ingest: parse → refine → chunk → embed → Qdrant."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qdrant_client.models import PointStruct

from pengod.config import Settings, get_settings
from pengod.ingest.case_parser import load_and_parse_cases, report_id_from_link
from pengod.ingest.chunking import chunk_text
from pengod.ingest.embeddings import LocalEmbedder
from pengod.rag.context_refiner import refine_h1_report_text
from pengod.rag.qdrant_store import QdrantConnection


@dataclass
class IngestStats:
    cases: int = 0
    chunks: int = 0
    points_upserted: int = 0
    errors: list[str] = field(default_factory=list)


def _severity_token(label: str) -> str | None:
    s = label.strip().lower()
    for token in ("critical", "high", "medium", "low", "none"):
        if s.startswith(token):
            return token
    return None


def _tech_from_scope(scope: str) -> list[str]:
    import re

    m = re.search(r"github\.com/([^/\s]+/[^/\s]+)", scope)
    if m:
        return [m.group(1)]
    s = scope.strip()
    return [s[:160]] if s else []


async def ingest_case_file(path: Path, settings: Settings | None = None) -> IngestStats:
    """Parse a case-study export file and upsert chunks into Qdrant."""
    settings = settings or get_settings()
    stats = IngestStats()
    try:
        cases = load_and_parse_cases(path)
    except OSError as exc:
        stats.errors.append(str(exc))
        return stats

    stats.cases = len(cases)
    if not cases:
        stats.errors.append("no_cases_found")
        return stats

    embedder = LocalEmbedder(settings.embedding_model)
    qdrant = QdrantConnection(settings=settings)

    await qdrant.ensure_collection(vector_size=settings.embedding_vector_size)

    batch_texts: list[str] = []
    batch_payloads: list[dict[str, Any]] = []
    batch_ids: list[str] = []

    async def flush() -> None:
        nonlocal batch_texts, batch_payloads, batch_ids
        if not batch_texts:
            return
        vectors = await asyncio.to_thread(embedder.embed, batch_texts)
        if len(vectors) != len(batch_texts):
            stats.errors.append("embedding_count_mismatch")
            batch_texts, batch_payloads, batch_ids = [], [], []
            return
        points = [
            PointStruct(id=pid, vector=vec, payload=pay)
            for pid, vec, pay in zip(batch_ids, vectors, batch_payloads, strict=True)
        ]
        await qdrant.upsert_points(points)
        stats.points_upserted += len(points)
        stats.chunks += len(points)
        batch_texts, batch_payloads, batch_ids = [], [], []

    try:
        for case in cases:
            report_id = report_id_from_link(case.link, fallback_case_index=case.case_index)
            body = refine_h1_report_text(case.details_raw)
            if not body.strip() and case.title:
                body = case.title
            pieces = chunk_text(
                body,
                max_chars=settings.chunk_size,
                overlap=settings.chunk_overlap,
            )
            if not pieces:
                continue
            weakness = case.weakness.strip()
            if weakness.lower() in ("", "none"):
                weakness = ""
            sev = _severity_token(case.severity_label) or ""
            tech = _tech_from_scope(case.scope)
            for idx, text in enumerate(pieces):
                pid = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"pengod://chunk/{report_id}/{idx}",
                    )
                )
                payload: dict[str, Any] = {
                    "text": text,
                    "title": case.title,
                    "report_id": report_id,
                    "case_index": case.case_index,
                    "chunk_index": idx,
                    "weakness": weakness,
                    "severity": sev,
                    "scope": case.scope,
                    "tech_stack": tech,
                    "source_link": case.link,
                    "reporter": case.reporter,
                }
                batch_ids.append(pid)
                batch_texts.append(text)
                batch_payloads.append(payload)
                if len(batch_texts) >= 32:
                    await flush()
        await flush()
    finally:
        await qdrant.close()

    return stats
