"""Local embeddings via FastEmbed (runs in thread pool from async code)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from fastembed import TextEmbedding


class LocalEmbedder:
    """Lazy-loaded TextEmbedding model."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: TextEmbedding | None = None

    def _ensure(self) -> None:
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self._model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._ensure()
        assert self._model is not None
        vectors: list[list[float]] = []
        for emb in self._model.embed(texts):
            arr = np.asarray(emb, dtype=np.float32)
            vectors.append(arr.flatten().tolist())
        return vectors
