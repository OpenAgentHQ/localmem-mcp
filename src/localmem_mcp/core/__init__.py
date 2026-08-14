"""Data layer: SQLite storage, embeddings, and hybrid search.

The public names are re-exported here and at :mod:`localmem_mcp.store`, which
is the backward-compatible facade the rest of the codebase imports.
"""

from __future__ import annotations

from .embedders import DEFAULT_MODEL, Embedder, FastEmbedEmbedder
from .models import Memory, SearchResult
from .schema import _SCHEMA
from .search import KEYWORD_WEIGHT, _cosine, _fts_query
from .store import MemoryStore
from .utils import (
    _bulk_filters,
    _days_ago,
    _has_tags,
    _normalize_tags,
    _now,
    _pack,
    _row_to_memory,
    _unpack,
    default_db_path,
)

__all__ = [
    "DEFAULT_MODEL",
    "KEYWORD_WEIGHT",
    "_SCHEMA",
    "Embedder",
    "FastEmbedEmbedder",
    "Memory",
    "MemoryStore",
    "SearchResult",
    "_bulk_filters",
    "_cosine",
    "_days_ago",
    "_fts_query",
    "_has_tags",
    "_normalize_tags",
    "_now",
    "_pack",
    "_row_to_memory",
    "_unpack",
    "default_db_path",
]
