"""Split long report text into overlapping chunks for embedding."""

from __future__ import annotations


def chunk_text(text: str, *, max_chars: int, overlap: int) -> list[str]:
    """
    Greedy char-based chunking with overlap. Respects paragraph breaks when possible.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        piece = text[start:end]
        if end < len(text):
            cut = piece.rfind("\n\n")
            if cut > max_chars // 4:
                piece = piece[:cut]
                end = start + cut
        chunks.append(piece.strip())
        if end >= len(text):
            break
        start = max(0, end - overlap)
        if start >= len(text):
            break
    return [c for c in chunks if c]
