"""Embedding providers — the injectable ``Embedder`` interface."""

from __future__ import annotations

import threading
from collections.abc import Sequence
from typing import Any, Protocol

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class Embedder(Protocol):
    """Anything that can turn text into a fixed-length vector."""

    name: str

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per input text, all of the same length."""
        ...


class FastEmbedEmbedder:
    """Local ONNX embeddings via `fastembed`.

    The model is loaded lazily so importing this module (and starting the MCP
    server) stays fast — the first `store_memory`/`search_memory` call pays the
    load cost, not process startup.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, cache_dir: str | None = None):
        self.name = model_name
        self._cache_dir = cache_dir
        self._model: Any = None
        self._lock = threading.Lock()

    def _ensure_model(self) -> Any:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from fastembed import TextEmbedding

                    self._model = TextEmbedding(
                        model_name=self.name, cache_dir=self._cache_dir
                    )
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed texts locally, loading the model on the first call."""
        model = self._ensure_model()
        return [list(map(float, vec)) for vec in model.embed(list(texts))]