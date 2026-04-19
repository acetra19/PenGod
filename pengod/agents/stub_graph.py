"""Minimal LangGraph skeleton: Archivist → Strategist → Payload Lab (placeholders)."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class AgentPipelineState(TypedDict):
    """Shared state for the research pipeline (extend as agents grow)."""

    task: str
    rag_notes: str
    strategy: str
    payload_hints: str


def _archivist(state: AgentPipelineState) -> AgentPipelineState:
    return {
        **state,
        "rag_notes": "RAG: retrieve disclosure patterns for task (placeholder).",
    }


def _strategist(state: AgentPipelineState) -> AgentPipelineState:
    return {
        **state,
        "strategy": "Strategy: map recon to RAG_notes (placeholder).",
    }


def _payload_lab(state: AgentPipelineState) -> AgentPipelineState:
    return {
        **state,
        "payload_hints": "Local LLM: craft safe test payloads per scope (placeholder).",
    }


def build_research_stub_graph():
    """
    Linear stub graph. Replace node bodies with real RAG / LLM calls.
    Invoke with: `await graph.ainvoke({...})`
    """
    builder = StateGraph(AgentPipelineState)
    builder.add_node("archivist", _archivist)
    builder.add_node("strategist", _strategist)
    builder.add_node("payload_lab", _payload_lab)
    builder.add_edge(START, "archivist")
    builder.add_edge("archivist", "strategist")
    builder.add_edge("strategist", "payload_lab")
    builder.add_edge("payload_lab", END)
    return builder.compile()
