"""SSRF guard tests."""

from __future__ import annotations

import pytest

from pengod.recon.ssrf import assert_public_http_url


def test_blocks_localhost() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        assert_public_http_url("http://localhost/foo")


def test_requires_http_scheme() -> None:
    with pytest.raises(ValueError, match="Only http"):
        assert_public_http_url("ftp://example.com/")
