"""
Streamlit front-end: semantic search, engagement run, Ollama chat with optional RAG grounding.
Run: streamlit run pengod/ui/app.py
Requires: FastAPI backend and (for Assistant) Ollama if you use local LLM.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import streamlit as st

SYSTEM_PROMPT = (
    "You are a security research assistant for authorized bug bounty and coordinated disclosure. "
    "Refuse instructions that ask for attacks on systems without authorization. "
    "Be concise and technical. When RAG context is provided, use it as reference patterns only."
)


def _api_get(base: str, path: str, *, params: dict[str, Any] | None = None, headers: dict[str, str]) -> Any:
    r = httpx.get(f"{base}{path}", params=params or {}, headers=headers, timeout=120.0)
    r.raise_for_status()
    return r.json()


def _api_post(base: str, path: str, *, json_body: dict[str, Any], headers: dict[str, str]) -> Any:
    h = {**headers, "Content-Type": "application/json"}
    r = httpx.post(f"{base}{path}", json=json_body, headers=h, timeout=180.0)
    r.raise_for_status()
    return r.json()


def _ollama_models(base: str) -> list[str]:
    try:
        r = httpx.get(f"{base}/api/tags", timeout=8.0)
        r.raise_for_status()
        data = r.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def _ollama_chat(base: str, model: str, messages: list[dict[str, str]]) -> str:
    r = httpx.post(
        f"{base}/api/chat",
        json={"model": model, "messages": messages, "stream": False},
        timeout=300.0,
    )
    r.raise_for_status()
    data = r.json()
    return (data.get("message") or {}).get("content") or ""


def main() -> None:
    st.set_page_config(page_title="PenGod", page_icon="🔍", layout="wide")
    st.title("PenGod")
    st.caption("Use only against targets you are authorized to test.")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [{"role": "assistant", "content": "Hello. Ask about patterns or your engagement."}]

    with st.sidebar:
        st.header("Connection")
        api_base = st.text_input("API base URL", value="http://127.0.0.1:8000").rstrip("/")
        api_key = st.text_input("X-API-Key (optional)", type="password")
        ollama_base = st.text_input("Ollama URL", value="http://127.0.0.1:11434").rstrip("/")

    def h() -> dict[str, str]:
        out: dict[str, str] = {}
        if api_key:
            out["X-API-Key"] = api_key
        return out

    t_search, t_eng, t_llm = st.tabs(["Semantic search", "Engagement run", "Assistant (Ollama)"])

    with t_search:
        q = st.text_input("Search query", placeholder="e.g. stored XSS attachment flow")
        lim = st.slider("Result limit", 1, 25, 8)
        if st.button("Search", type="primary"):
            try:
                data = _api_get(api_base, "/v1/search", params={"q": q, "limit": lim}, headers=h())
                st.subheader("Results")
                for i, row in enumerate(data.get("results") or [], start=1):
                    with st.expander(f"#{i} score={row.get('score', 0):.4f}"):
                        st.markdown(f"**ID:** `{row.get('id')}`")
                        payload = row.get("payload") or {}
                        st.text_area("Text", value=str(payload.get("text", ""))[:8000], height=200, key=f"t{i}")
                        st.json({k: v for k, v in payload.items() if k != "text"})
            except Exception as exc:
                st.error(f"Request failed: {exc}")

    with t_eng:
        url = st.text_input("In-scope target URL", placeholder="https://example.com/")
        hint = st.text_area("Optional RAG query override", height=100)
        rlim = st.slider("RAG hits", 1, 25, 8)
        if st.button("Run engagement", type="primary"):
            try:
                body: dict[str, Any] = {"target_url": url.strip(), "rag_limit": rlim}
                if hint.strip():
                    body["rag_query_hint"] = hint.strip()
                data = _api_post(api_base, "/v1/engagement/run", json_body=body, headers=h())
                st.subheader("Probe")
                st.json(data.get("probe"))
                st.subheader("RAG query used")
                st.code(data.get("rag_query_used") or "")
                st.subheader("RAG hits")
                st.json(data.get("rag_hits"))
            except httpx.HTTPStatusError as exc:
                st.error(f"HTTP {exc.response.status_code}: {exc.response.text[:2000]}")
            except Exception as exc:
                st.error(f"Request failed: {exc}")

    with t_llm:
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Refresh Ollama models"):
                st.session_state.ollama_models = _ollama_models(ollama_base)
        models = st.session_state.get("ollama_models") or _ollama_models(ollama_base)
        model = st.selectbox("Model", models if models else ["llama3:latest"])
        use_rag = st.checkbox("Ground answer with RAG (uses Search API)", value=True)

        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("Your message"):
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            rag_block = ""
            if use_rag:
                try:
                    sdata = _api_get(
                        api_base,
                        "/v1/search",
                        params={"q": prompt, "limit": 5},
                        headers=h(),
                    )
                    rag_block = json.dumps(sdata.get("results") or [], indent=2)[:12000]
                except Exception as rag_exc:
                    rag_block = f"(RAG fetch failed: {rag_exc})"

            msgs: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
            if rag_block:
                msgs.append(
                    {
                        "role": "system",
                        "content": f"RAG retrieval (reference patterns only):\n```json\n{rag_block}\n```",
                    }
                )
            for m in st.session_state.chat_messages:
                msgs.append({"role": m["role"], "content": m["content"]})

            try:
                reply = _ollama_chat(ollama_base, model, msgs)
            except Exception as exc:
                reply = f"Ollama error: {exc}"

            st.session_state.chat_messages.append({"role": "assistant", "content": reply})
            st.rerun()


if __name__ == "__main__":
    main()
