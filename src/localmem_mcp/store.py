"""Backward-compatible facade over :mod:`localmem_mcp.core`.

The data layer now lives in the :mod:`localmem_mcp.core` package; this module
re-exports the names that previously lived here so existing imports (docs,
tests, and library users) keep working unchanged.
"""

from __future__ import annotations

from .core import (
    _SCHEMA,
    DEFAULT_MODEL,
    KEYWORD_WEIGHT,
    Embedder,
    FastEmbedEmbedder,
    ImportReport,
    Memory,
    MemoryStore,
    SearchResult,
    _bulk_filters,
    _cosine,
    _days_ago,
    _fts_query,
    _has_tags,
    _normalize_tags,
    _now,
    _pack,
    _row_to_memory,
    _unpack,
    default_db_path,
    import_records,
)

__all__ = [
    "DEFAULT_MODEL",
    "KEYWORD_WEIGHT",
    "_SCHEMA",
    "Embedder",
    "FastEmbedEmbedder",
    "ImportReport",
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
    "import_records",
]
