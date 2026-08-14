"""The MCP tools — thin wrappers over :class:`~localmem_mcp.core.store.MemoryStore`.

Each tool's docstring is the agent-facing UX: it says when to use the tool and
when not to, because that text is what an MCP client shows the model.
"""

from __future__ import annotations

from typing import Any

from .app import get_store, mcp


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
    offset: int = 0,
) -> dict[str, Any]:
    """Find memories by meaning.

    Semantic search over everything stored, so "what database did we pick?"
    finds a memory that says "we went with SQLite". Results are ranked by
    similarity, highest first.

    To page through more matches, keep the same query and advance `offset` by
    `limit` — ranking is stable, so pages don't overlap or skip. An offset past
    the last match returns no results.

    Args:
        query: What you are trying to remember, in natural language.
        limit: Maximum number of memories to return.
        tags: Only consider memories carrying all of these tags.
        min_score: Drop results scoring below this (0.0-1.0).
        offset: Skip this many ranked results before returning `limit` of them.

    Returns:
        Matching memories with their similarity scores.
    """
    results = get_store().search(
        query=query, limit=limit, tags=tags, min_score=min_score, offset=offset
    )
    return {
        "query": query,
        "count": len(results),
        "offset": max(0, offset),
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
def list_memories(
    tags: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
    order: str = "newest",
) -> dict[str, Any]:
    """List stored memories without semantic search.

    Use this to browse or audit memories, especially when you need all
    memories carrying specific tags. Unlike search_memory, this performs
    database filtering and ordering only — no embeddings or similarity
    scoring are used.

    Args:
        tags: Only return memories carrying all of these tags.
        limit: Maximum number of memories to return.
        offset: Number of matching memories to skip for pagination.
        order: Ordering direction: "newest" or "oldest".

    Returns:
        The matching memories, total number of matches, and pagination details.
    """
    memories, total = get_store().list(
        tags=tags,
        limit=limit,
        offset=offset,
        order=order,
    )

    return {
        "count": len(memories),
        "total": total,
        "offset": offset,
        "limit": limit,
        "order": order,
        "tags": tags or [],
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
def forget_memory(memory_id: int) -> dict[str, Any]:
    """Permanently delete one memory by id.

    Use this when a stored memory is wrong beyond correction, sensitive, or
    simply no longer wanted — prune it so stale facts stop outranking current
    ones. To fix a memory instead of deleting it, use update_memory. The delete
    is hard: the row is gone, not hidden.

    Args:
        memory_id: The id of the memory to delete, from a previous
            store_memory or search_memory call.

    Returns:
        {"found": true, "memory_id": id} if it was deleted, or
        {"found": false} if no such id exists.
    """
    deleted = get_store().delete(memory_id)
    return {"found": deleted, "memory_id": memory_id}


@mcp.tool
def forget_memories(
    tags: list[str] | None = None,
    older_than_days: int | None = None,
) -> dict[str, Any]:
    """Permanently delete memories by tag and/or age.

    Use this to prune stale facts en masse — drop every memory tagged
    "scratch", or everything older than 90 days. At least one filter is
    required; an unfiltered call is rejected so the store can't be wiped by
    accident. Deletion is hard: matching rows are gone, not hidden.

    Args:
        tags: Only delete memories carrying all of these tags.
        older_than_days: Only delete memories created more than this many days ago.

    Returns:
        The number of memories removed, along with the filters that matched them.
    """
    count = get_store().delete_many(tags=tags, older_than_days=older_than_days)
    return {
        "count": count,
        "tags": list(tags) if tags else [],
        "older_than_days": older_than_days,
    }


@mcp.tool
def memory_stats() -> dict[str, Any]:
    """Report where memories are stored, how many there are, and which model is used."""
    return get_store().stats()
