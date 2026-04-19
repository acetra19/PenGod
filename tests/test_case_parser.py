"""Tests for case-study text parsing."""

from __future__ import annotations

from pathlib import Path

from pengod.ingest.case_parser import (
    load_and_parse_cases,
    parse_case_block,
    report_id_from_link,
    split_case_blocks,
)


SAMPLE = """
Case 1
Title:         Hello
Scope:         https://github.com/foo/bar
Weakness:      XSS
Severity:      High
Link:          https://hackerone.com/reports/12345
Date:          2026-01-01
By:            @user
CVE IDs:
Details:
## Summary
Body here.

Case 2
Title:         Other
Scope:         x
Weakness:      None
Severity:      Low
Link:          https://example.com
Date:
By:
CVE IDs:
Details:
More text.
"""


def test_split_and_parse(tmp_path: Path) -> None:
    p = tmp_path / "c.txt"
    p.write_text(SAMPLE.strip(), encoding="utf-8")
    cases = load_and_parse_cases(p)
    assert len(cases) == 2
    assert cases[0].title == "Hello"
    assert cases[0].case_index == 1
    assert "Body here" in cases[0].details_raw
    assert report_id_from_link(cases[0].link, fallback_case_index=1) == "12345"


def test_report_id_fallback() -> None:
    assert report_id_from_link("", fallback_case_index=7) == "case-7"


def test_parse_block_direct() -> None:
    blocks = split_case_blocks(SAMPLE)
    assert len(blocks) == 2
    c = parse_case_block(blocks[0][0], blocks[0][1])
    assert c.weakness == "XSS"
