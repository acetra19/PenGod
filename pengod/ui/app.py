"""
Streamlit front-end: agent run (probe + RAG + Strategist), search, engagement, LLM assistant.
Run: streamlit run pengod/ui/app.py
Set GROQ_API_KEY in the environment for Groq, or paste once per session (not persisted).
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
import streamlit as st

SYSTEM_PROMPT = (
    "You are a security research assistant for authorized bug bounty and coordinated disclosure. "
    "Refuse instructions that ask for attacks on systems without authorization. "
    "Be concise and technical. When RAG context is provided, use it as reference patterns only."
)

GROQ_BASE = "https://api.groq.com/openai/v1"
# Common Groq model ids (see https://console.groq.com/docs/models )
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]


def _ensure_absolute_http_url(raw: str) -> str:
    """Prepend https:// when user types host-only (API expects HttpUrl)."""
    u = raw.strip()
    if not u or "://" in u:
        return u
    return f"https://{u}"


def _parse_target_urls(raw: str) -> list[str]:
    """One URL per line or comma-separated; empty lines skipped."""
    out: list[str] = []
    for line in raw.replace(",", "\n").splitlines():
        u = line.strip()
        if u:
            out.append(_ensure_absolute_http_url(u))
    return out


def _api_get(base: str, path: str, *, params: dict[str, Any] | None = None, headers: dict[str, str]) -> Any:
    r = httpx.get(f"{base}{path}", params=params or {}, headers=headers, timeout=120.0)
    r.raise_for_status()
    return r.json()


def _api_post(
    base: str,
    path: str,
    *,
    json_body: dict[str, Any],
    headers: dict[str, str],
    timeout: float = 180.0,
) -> Any:
    h = {**headers, "Content-Type": "application/json"}
    r = httpx.post(f"{base}{path}", json=json_body, headers=h, timeout=timeout)
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


def _groq_chat(api_key: str, model: str, messages: list[dict[str, str]]) -> str:
    r = httpx.post(
        f"{GROQ_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 8192,
        },
        timeout=120.0,
    )
    r.raise_for_status()
    data = r.json()
    choices = data.get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("message") or {}).get("content") or ""


def main() -> None:
    st.set_page_config(page_title="PenGod", page_icon="🔍", layout="wide")
    st.title("PenGod")
    st.caption("Use only against targets you are authorized to test.")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [{"role": "assistant", "content": "Hello. Ask about patterns or your engagement."}]

    with st.sidebar:
        st.header("Connection")
        api_base = st.text_input("API base URL", value="http://127.0.0.1:8000").rstrip("/")
        api_key = st.text_input("PenGod X-API-Key (optional)", type="password")
        st.divider()
        st.subheader("Assistant LLM")
        llm_provider = st.radio("Provider", ("Groq (cloud)", "Ollama (local)"), index=0)
        use_groq = llm_provider.startswith("Groq")
        groq_key = ""
        groq_model = GROQ_MODELS[0]
        ollama_base = "http://127.0.0.1:11434"
        if use_groq:
            groq_key = st.text_input(
                "Groq API key",
                type="password",
                value=os.environ.get("GROQ_API_KEY") or "",
                help="Prefer: set GROQ_API_KEY in the environment. Never commit keys or paste them in chats.",
            )
            groq_model = st.selectbox("Groq model", GROQ_MODELS, index=0)
        else:
            ollama_base = st.text_input("Ollama URL", value="http://127.0.0.1:11434").rstrip("/")
        st.caption(
            "Strategist uses Ollama on the API server (`OLLAMA_BASE_URL`), not this sidebar URL."
        )

    def h() -> dict[str, str]:
        out: dict[str, str] = {}
        if api_key:
            out["X-API-Key"] = api_key
        return out

    t_agents, t_search, t_eng, t_llm = st.tabs(
        ["Agent run", "Semantic search", "Engagement run", "Assistant (LLM)"]
    )

    with t_agents:
        with st.expander("Where Ollama runs for Strategist"):
            st.markdown(
                "The **Agent run** tab calls your PenGod API, which uses **Ollama on the machine "
                "that runs the API** (`OLLAMA_BASE_URL` in the API environment). "
                "If the API is in Docker, point that variable at the host (e.g. `http://host.docker.internal:11434`) "
                "or run Ollama in the same network."
            )
        st.markdown(
            "Enter your **authorized program scope** and **in-scope page URLs** (one per line). "
            "The API runs probe → RAG → Ollama Strategist per URL. "
            "This is research assistance only — not automated exploitation."
        )
        scope_text = st.text_area(
            "Program scope",
            height=140,
            placeholder=(
                "e.g. In scope: *.example.com web app, API api.example.com. "
                "Out of scope: social engineering, DoS. Only test assets listed in the program."
            ),
            help="Agents use this to align suggestions with what you are allowed to test.",
        )
        urls_raw = st.text_area(
            "In-scope URLs",
            height=160,
            placeholder="https://app.example.com/\nhttps://api.example.com/v1/health",
            help="One URL per line (or comma-separated). Host-only entries get https://.",
        )
        if st.button("Run agents (Strategist)", type="primary"):
            urls = _parse_target_urls(urls_raw)
            if not urls:
                st.warning("Add at least one URL.")
            else:
                try:
                    body: dict[str, Any] = {"target_urls": urls}
                    sc = scope_text.strip()
                    if sc:
                        body["program_scope"] = sc
                    # Probe + RAG + Ollama per URL (sequential on server)
                    timeout_s = min(3600.0, max(300.0, 240.0 * len(urls)))
                    data = _api_post(
                        api_base,
                        "/v1/strategist/run",
                        json_body=body,
                        headers=h(),
                        timeout=timeout_s,
                    )
                    st.caption(data.get("disclaimer") or "")
                    if data.get("program_scope"):
                        st.subheader("Scope sent to agents")
                        st.text_area("Scope", value=data["program_scope"], height=120, disabled=True)
                    runs = data.get("runs") or []
                    st.subheader(f"Results ({len(runs)} URL(s))")
                    for i, run in enumerate(runs, start=1):
                        u = run.get("target_url", "")
                        with st.expander(f"#{i} {u}", expanded=(i == 1)):
                            if run.get("pipeline_error"):
                                st.error(run["pipeline_error"])
                            st.markdown("#### Strategist report")
                            st.markdown(run.get("strategist_report") or "(empty)")
                            st.markdown("#### Probe")
                            st.json(run.get("probe"))
                            st.markdown("#### RAG query")
                            st.code(run.get("rag_query") or "")
                            with st.expander("RAG hits (raw)"):
                                st.json(run.get("rag_hits"))
                except httpx.HTTPStatusError as exc:
                    st.error(f"HTTP {exc.response.status_code}: {exc.response.text[:4000]}")
                except Exception as exc:
                    st.error(f"Request failed: {exc}")

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
                body: dict[str, Any] = {
                    "target_url": _ensure_absolute_http_url(url),
                    "rag_limit": rlim,
                }
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
        if use_groq:
            st.info("Groq: fast cloud inference. Keys stay in memory / `GROQ_API_KEY` only.")
        else:
            if st.button("Refresh Ollama models"):
                st.session_state.ollama_models = _ollama_models(ollama_base)
            models = st.session_state.get("ollama_models") or _ollama_models(ollama_base)
            ollama_model = st.selectbox("Ollama model", models if models else ["llama3:latest"])
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
                if use_groq:
                    if not groq_key.strip():
                        reply = "Set `GROQ_API_KEY` or enter a Groq API key in the sidebar."
                    else:
                        reply = _groq_chat(groq_key.strip(), groq_model, msgs)
                else:
                    reply = _ollama_chat(ollama_base, ollama_model, msgs)
            except Exception as exc:
                reply = f"LLM error: {exc}"

            st.session_state.chat_messages.append({"role": "assistant", "content": reply})
            st.rerun()


if __name__ == "__main__":
    main()
