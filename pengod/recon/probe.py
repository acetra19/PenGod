"""Async HTTP GET probe for an in-scope URL (authorized testing only)."""

from __future__ import annotations

import re
from typing import Any

import httpx

from pengod.recon.ssrf import assert_public_http_url

_TITLE_RE = re.compile(r"<title[^>]*>([^<]{1,512})</title>", re.I | re.DOTALL)
_UA = "PenGod/0.1 (authorized security research; +https://github.com/acetra19/PenGod)"


async def probe_target_url(
    url: str,
    *,
    timeout_seconds: float = 12.0,
    max_redirects: int = 5,
) -> dict[str, Any]:
    """
    Fetch URL metadata (status, headers snippet, title). Caller must enforce scope.
    """
    assert_public_http_url(url)
    headers_out: dict[str, str] = {}
    try:
        async with httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=True,
            max_redirects=max_redirects,
        ) as client:
            resp = await client.get(url, headers={"User-Agent": _UA})
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "final_url": url,
        }

    for key in ("server", "content-type", "x-powered-by", "via"):
        val = resp.headers.get(key)
        if val:
            headers_out[key] = val[:500]

    title = ""
    ct = (resp.headers.get("content-type") or "").lower()
    if "html" in ct and resp.text:
        m = _TITLE_RE.search(resp.text[:200_000])
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()[:300]

    return {
        "ok": True,
        "final_url": str(resp.url),
        "status_code": resp.status_code,
        "headers": headers_out,
        "title": title,
    }


def build_rag_query_from_probe(probe: dict[str, Any], target_url: str, hint: str | None) -> str:
    """Turn probe facts into a short semantic query for disclosure RAG."""
    if hint and hint.strip():
        return hint.strip()[:2000]
    parts: list[str] = []
    if probe.get("title"):
        parts.append(probe["title"])
    if probe.get("headers", {}).get("x-powered-by"):
        parts.append(probe["headers"]["x-powered-by"])
    if probe.get("headers", {}).get("server"):
        parts.append(probe["headers"]["server"])
    parts.append(target_url)
    parts.append("web application security vulnerability patterns")
    return " ".join(parts)[:2000]
