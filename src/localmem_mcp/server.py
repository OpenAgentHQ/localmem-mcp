"""FastMCP server exposing localmem's four memory tools over stdio."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from .store import DEFAULT_MODEL, MemoryStore

mcp = FastMCP(
    "localmem",
    instructions=(
        "Local-first, private long-term memory. Use store_memory to save durable "
        "facts, decisions, and preferences worth remembering across sessions; "
        "search_memory to find them by meaning; recall_memory to re-read a "
        "specific memory or the most recent ones; update_memory to correct a "
        "stored memory. Everything stays on this machine."
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


@mcp.tool
def store_memory(
    content: str,
    tags: list[str] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Save something worth remembering across sessions.

    Store durable facts, decisions, preferences, and project context — not
    transient chatter. The text is embedded locally so it can be found later by
    meaning, not just exact words.

    Args:
        content: The memory itself, written so it makes sense on its own later.
        tags: Optional labels for filtering, e.g. ["project-x", "preference"].
        source: Optional origin of the memory, e.g. "conversation" or a file path.

    Returns:
        The stored memory, including the id needed to recall it directly.
    """
    memory = get_store().add(content=content, tags=tags, source=source)
    return memory.to_dict()


@mcp.tool
def search_memory(
    query: str,
    limit: int = 5,
    tags: list[str] | None = None,
    min_score: float = 0.0,
) -> dict[str, Any]:
    """Find memories by meaning.

    Semantic search over everything stored, so "what database did we pick?"
    finds a memory that says "we went with SQLite". Results are ranked by
    similarity, highest first.

    Args:
        query: What you are trying to remember, in natural language.
        limit: Maximum number of memories to return.
        tags: Only consider memories carrying all of these tags.
        min_score: Drop results scoring below this (0.0-1.0).

    Returns:
        Matching memories with their similarity scores.
    """
    results = get_store().search(
        query=query, limit=limit, tags=tags, min_score=min_score
    )
    return {
        "query": query,
        "count": len(results),
        "results": [result.to_dict() for result in results],
    }


@mcp.tool
def recall_memory(memory_id: int | None = None, limit: int = 5) -> dict[str, Any]:
    """Re-read a specific memory by id, or the most recent memories.

    Use this when you already know which memory you want (from a previous
    store_memory or search_memory call), or to catch up on what was recorded
    most recently. To find memories by meaning, use search_memory instead.

    Args:
        memory_id: The id of a single memory to read back. Omit for recent ones.
        limit: How many recent memories to return when memory_id is omitted.

    Returns:
        The requested memory, or the most recently stored memories, newest first.
    """
    store = get_store()
    if memory_id is not None:
        memory = store.get(memory_id)
        if memory is None:
            return {"found": False, "memory_id": memory_id, "memories": []}
        return {"found": True, "memory_id": memory_id, "memories": [memory.to_dict()]}

    memories = store.recent(limit=limit)
    return {
        "found": bool(memories),
        "count": len(memories),
        "memories": [memory.to_dict() for memory in memories],
    }


@mcp.tool
def update_memory(
    memory_id: int,
    content: str | None = None,
    tags: list[str] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Correct an existing memory in place.

    Use this when a stored memory is wrong — a misremembered decision, a
    misspelled name, a fact that has since changed. It edits the original record
    rather than adding a related one, and re-embeds the text so search finds the
    correction. Only the fields you pass are changed.

    Args:
        memory_id: The id of the memory to correct, from a previous
            store_memory or search_memory call.
        content: The corrected memory text. Re-embeds the memory when changed.
        tags: Replacement tags. Omit to keep the current tags.
        source: Replacement source. Omit to keep the current source.

    Returns:
        The corrected memory, or {"found": false} if the id doesn't exist.
    """
    memory = get_store().update(
        memory_id=memory_id, content=content, tags=tags, source=source
    )
    if memory is None:
        return {"found": False, "memory_id": memory_id, "memory": None}
    return {"found": True, "memory_id": memory_id, "memory": memory.to_dict()}


@mcp.tool
def memory_stats() -> dict[str, Any]:
    """Report where memories are stored, how many there are, and which model is used."""
    return get_store().stats()


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
