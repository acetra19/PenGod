"""Parse `Case N` + header + `Details:` exports (e.g. Casestudies.txt)."""

from __future__ import annotations

import re
from pathlib import Path

from pengod.ingest.models import ParsedCaseStudy

_CASE_START = re.compile(r"^Case\s+(\d+)\s*$", re.MULTILINE)
_HEADER_LINE = re.compile(
    r"^(Title|Scope|Weakness|Severity|Link|Date|By|CVE IDs):\s*(.*)$",
    re.MULTILINE,
)
_H1_REPORT_ID = re.compile(r"hackerone\.com/reports/(\d+)", re.I)


def split_case_blocks(raw: str) -> list[tuple[int, str]]:
    """Return (case_number, body) for each `Case N` section."""
    matches = list(_CASE_START.finditer(raw))
    if not matches:
        return []
    out: list[tuple[int, str]] = []
    for i, m in enumerate(matches):
        num = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        out.append((num, raw[start:end].strip()))
    return out


def _extract_details(block: str) -> tuple[str, str]:
    """Split header vs details after `Details:` marker."""
    m = re.search(r"(?ms)^Details:\s*\n", block)
    if not m:
        return block.strip(), ""
    header = block[: m.start()].strip()
    details = block[m.end() :].strip()
    return header, details


def _parse_header(header: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in header.splitlines():
        lm = _HEADER_LINE.match(line.strip())
        if lm:
            key = lm.group(1).lower().replace(" ", "_")
            fields[key] = lm.group(2).strip()
    return fields


def parse_case_block(case_index: int, block: str) -> ParsedCaseStudy:
    header, details_raw = _extract_details(block)
    fields = _parse_header(header)
    warnings: list[str] = []
    if not details_raw and "Details:" not in block:
        warnings.append("missing_details_marker")
    return ParsedCaseStudy(
        case_index=case_index,
        title=fields.get("title", ""),
        scope=fields.get("scope", ""),
        weakness=fields.get("weakness", ""),
        severity_label=fields.get("severity", ""),
        link=fields.get("link", ""),
        reported_at=fields.get("date", ""),
        reporter=fields.get("by", ""),
        cve_ids=fields.get("cve_ids", ""),
        details_raw=details_raw,
        parse_warnings=warnings,
    )


def report_id_from_link(link: str, *, fallback_case_index: int) -> str:
    m = _H1_REPORT_ID.search(link)
    if m:
        return m.group(1)
    return f"case-{fallback_case_index}"


def load_and_parse_cases(path: Path) -> list[ParsedCaseStudy]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if raw.startswith("\ufeff"):
        raw = raw[1:]
    blocks = split_case_blocks(raw)
    return [parse_case_block(num, body) for num, body in blocks]
