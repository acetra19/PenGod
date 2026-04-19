"""Remove low-value boilerplate from disclosure-style text to save tokens."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ContextRefiner:
    """
    Heuristic refiner for HackerOne-like reports (no LLM required).
    Keeps technical sentences; drops acknowledgements and noisy timelines.
    """

    max_chars: int | None = 20000
    drop_line_patterns: tuple[re.Pattern[str], ...] = field(
        default_factory=lambda: (
            re.compile(r"^\s*(thanks|thank you|cheers)\b", re.I),
            re.compile(r"^\s*best regards\b", re.I),
            re.compile(r"^\s*I hope this (helps|finds you well)\b", re.I),
            re.compile(r"^\s*Please let me know if\b", re.I),
            re.compile(r"^\s*Timeline\s*$", re.I),
            re.compile(r"^\s*Acknowledgements?\s*$", re.I),
        )
    )
    fluff_only_lines: tuple[re.Pattern[str], ...] = field(
        default_factory=lambda: (
            re.compile(r"^\s*#\s*Timeline\s*$", re.I),
            re.compile(r"^\s*##\s*References\s*$", re.I),
        )
    )

    def refine(self, raw: str) -> str:
        if not raw:
            return ""
        lines = raw.splitlines()
        kept: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if kept and kept[-1] != "":
                    kept.append("")
                continue
            if any(p.search(stripped) for p in self.drop_line_patterns):
                continue
            if any(p.match(stripped) for p in self.fluff_only_lines):
                continue
            kept.append(line.rstrip())

        text = "\n".join(kept)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        text = re.sub(r"[ \t]{2,}", " ", text)
        if self.max_chars is not None and len(text) > self.max_chars:
            text = text[: self.max_chars].rsplit("\n", 1)[0] + "\n[…truncated]"
        return text


_default_refiner = ContextRefiner()


def refine_h1_report_text(raw: str, *, max_chars: int | None = None) -> str:
    """Strip fluff from a HackerOne-style report body."""
    refiner = _default_refiner if max_chars is None else ContextRefiner(max_chars=max_chars)
    return refiner.refine(raw)
