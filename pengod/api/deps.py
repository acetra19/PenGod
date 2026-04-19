"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Header, HTTPException, Request

from pengod.config import get_settings


async def verify_optional_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    settings = getattr(request.app.state, "settings", None) or get_settings()
    expected = settings.pengod_api_key
    if expected and (not x_api_key or x_api_key != expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
