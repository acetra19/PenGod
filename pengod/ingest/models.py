"""Ingest-specific data types (parsed case studies)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedCaseStudy:
    """One block from a `Casestudies.txt`-style export."""

    case_index: int
    title: str = ""
    scope: str = ""
    weakness: str = ""
    severity_label: str = ""
    link: str = ""
    reported_at: str = ""
    reporter: str = ""
    cve_ids: str = ""
    details_raw: str = ""
    parse_warnings: list[str] = field(default_factory=list)
