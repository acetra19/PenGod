"""LangGraph: probe → RAG → Ollama Strategist report (authorized targets only)."""

from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from pengod.config import Settings
from pengod.ingest.embeddings import LocalEmbedder
from pengod.llm.ollama_async import ollama_chat
from pengod.rag.qdrant_store import QdrantConnection
from pengod.rag.search import semantic_search
from pengod.recon.probe import build_rag_query_from_probe, probe_target_url

STRATEGIST_SYSTEM = """You are the Strategist agent in PenGod (authorized bug bounty research).
You receive HTTP probe data and short excerpts from similar past disclosures (reference only).
Produce a structured markdown report with:
1) Executive summary (2-4 sentences)
2) Observed surface (from probe) — stack hints, status, title
3) Pattern ideas from RAG excerpts — map to CWE-style classes where possible; do NOT claim vulnerabilities exist on the target
4) Suggested next checks (manual or tool-assisted) appropriate for an in-scope program — safe, non-destructive
5) Explicit reminder: only test what the program authorizes
6) If program_scope is provided, treat it as the authorized scope — align suggestions strictly with it

Do not output exploit code or step-by-step exploitation. Be factual and concise."""


class StrategistState(TypedDict, total=False):
    target_url: str
    program_scope: str | None
    probe: dict[str, Any]
    rag_query: str
    rag_hits: list[dict[str, Any]]
    strategist_report: str
    error: str | None


def build_strategist_graph(
    *,
    settings: Settings,
    qdrant: QdrantConnection,
    embedder: LocalEmbedder,
) -> Any:
    lim = settings.strategist_rag_limit

    async def node_probe(state: StrategistState) -> dict[str, Any]:
        try:
            p = await probe_target_url(
                state["target_url"],
                timeout_seconds=settings.probe_timeout_seconds,
                max_redirects=settings.probe_max_redirects,
            )
            return {"probe": p}
        except ValueError as exc:
            return {"probe": {"ok": False, "error": str(exc)}, "error": str(exc)}

    async def node_rag(state: StrategistState) -> dict[str, Any]:
        base_q = build_rag_query_from_probe(state.get("probe") or {}, state["target_url"], None)
        scope = (state.get("program_scope") or "").strip()
        if scope:
            q = f"{base_q} {scope[:600]}".strip()[:2000]
        else:
            q = base_q
        hits = await semantic_search(
            q,
            limit=lim,
            settings=settings,
            embedder=embedder,
            qdrant=qdrant,
        )
        return {"rag_query": q, "rag_hits": hits}

    async def node_strategist(state: StrategistState) -> dict[str, Any]:
        slim: list[dict[str, Any]] = []
        for h in (state.get("rag_hits") or [])[:lim]:
            pl = h.get("payload") or {}
            slim.append(
                {
                    "score": h.get("score"),
                    "title": pl.get("title"),
                    "weakness": pl.get("weakness"),
                    "severity": pl.get("severity"),
                    "text_preview": str(pl.get("text", ""))[:1200],
                }
            )
        payload = {
            "target_url": state.get("target_url"),
            "program_scope": state.get("program_scope"),
            "probe": state.get("probe"),
            "prior_error": state.get("error"),
            "similar_disclosures": slim,
        }
        user_text = json.dumps(payload, indent=2)[:28000]
        messages = [
            {"role": "system", "content": STRATEGIST_SYSTEM},
            {"role": "user", "content": user_text},
        ]
        report = await ollama_chat(
            settings.ollama_base_url,
            settings.strategist_model,
            messages,
        )
        return {"strategist_report": report}

    builder = StateGraph(StrategistState)
    # Node names must not collide with state keys (LangGraph reserves keys).
    builder.add_node("http_probe", node_probe)
    builder.add_node("retrieve_rag", node_rag)
    builder.add_node("strategist_llm", node_strategist)
    builder.add_edge(START, "http_probe")
    builder.add_edge("http_probe", "retrieve_rag")
    builder.add_edge("retrieve_rag", "strategist_llm")
    builder.add_edge("strategist_llm", END)
    return builder.compile()
