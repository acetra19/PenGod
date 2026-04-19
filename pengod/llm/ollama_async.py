"""Async Ollama /api/chat helper."""

from __future__ import annotations

import httpx


async def ollama_chat(
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    timeout_seconds: float = 300.0,
    options: dict[str, int | float] | None = None,
) -> str:
    base = base_url.rstrip("/")
    body: dict[str, object] = {"model": model, "messages": messages, "stream": False}
    if options:
        body["options"] = options
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        r = await client.post(
            f"{base}/api/chat",
            json=body,
        )
        if r.status_code >= 400:
            body = (r.text or "")[:2000]
            raise RuntimeError(f"Ollama HTTP {r.status_code}: {body}")
        data = r.json()
        return (data.get("message") or {}).get("content") or ""
