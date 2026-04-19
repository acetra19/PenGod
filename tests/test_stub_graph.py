"""Smoke test for the LangGraph skeleton."""

from __future__ import annotations

import pytest

from pengod.agents.stub_graph import build_research_stub_graph


@pytest.mark.asyncio
async def test_research_stub_graph_linear_run() -> None:
    graph = build_research_stub_graph()
    out = await graph.ainvoke(
        {
            "task": "authorized recon",
            "rag_notes": "",
            "strategy": "",
            "payload_hints": "",
        }
    )
    assert "placeholder" in out["rag_notes"].lower()
    assert "placeholder" in out["strategy"].lower()
    assert "placeholder" in out["payload_hints"].lower()
