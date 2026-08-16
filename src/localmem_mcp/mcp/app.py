"""FastMCP app instance and store lifecycle.

The FastMCP instance and the process-wide :class:`MemoryStore` live here so the
tool functions in :mod:`localmem_mcp.mcp.tools` stay thin wrappers.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastmcp import FastMCP

from ..core import DEFAULT_MODEL, MemoryStore

mcp = FastMCP(
    "localmem",
    instructions=(
        "Local-first, private long-term memory. Use store_memory to save durable "
        "facts, decisions, and preferences worth remembering across sessions; "
        "search_memory to find them by meaning; recall_memory to re-read a "
        "specific memory or the most recent ones; list_memories to browse memories "
        "with tag filtering, ordering, and pagination; update_memory to correct a "
        "stored memory; forget_memory or forget_memories to prune memories that "
        "are stale, sensitive, or no longer wanted. Everything stays on this "
        "machine."
    ),
)

_store: MemoryStore | None = None


def get_store() -> MemoryStore:
    """Return the process-wide store, opening it on first use."""
    global _store
    if _store is None:
        _store = MemoryStore(
            db_path=os.environ.get("LOCALMEM_DB_PATH"),
            model_name=os.environ.get("LOCALMEM_MODEL", DEFAULT_MODEL),
        )
    return _store


def configure(db_path: str | Path | None = None, model_name: str | None = None) -> MemoryStore:
    """Point the server at a specific database/model before serving."""
    global _store
    if _store is not None:
        _store.close()
    _store = MemoryStore(db_path=db_path, model_name=model_name or DEFAULT_MODEL)
    return _store


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()
