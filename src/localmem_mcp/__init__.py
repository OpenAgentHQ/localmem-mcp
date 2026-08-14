"""localmem-mcp — local-first, zero-API memory for AI agents.

Use it as an MCP server::

    localmem-mcp

or as a plain Python library::

    from localmem_mcp import MemoryStore

    store = MemoryStore()
    store.add("We chose SQLite for storage", tags=["decision"])
    store.search("what database are we using?")
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

from .store import (
    DEFAULT_MODEL,
    Embedder,
    FastEmbedEmbedder,
    ImportReport,
    Memory,
    MemoryStore,
    SearchResult,
    default_db_path,
    import_records,
)

try:
    __version__ = _version("localmem-mcp")
except PackageNotFoundError:  # running from a source checkout
    __version__ = "0.0.0.dev0"

__all__ = [
    "DEFAULT_MODEL",
    "Embedder",
    "FastEmbedEmbedder",
    "ImportReport",
    "Memory",
    "MemoryStore",
    "SearchResult",
    "__version__",
    "default_db_path",
    "import_records",
]
