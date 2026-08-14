"""Per-command handlers for the localmem-mcp CLI.

Each handler takes the store, parsed args, and the JSON flag, and returns the
process exit code. Handlers are wired to subcommands in
:mod:`localmem_mcp.commands.main`.
"""

from __future__ import annotations

import argparse
import sys
from typing import TextIO

from ..core import MemoryStore
from .output import _print


def handle_add(store: MemoryStore, args: argparse.Namespace, as_json: bool) -> int:
    """Store a memory."""
    memory = store.add(content=args.content, tags=args.tags, source=args.source)
    _print(
        memory.to_dict(),
        as_json,
        lambda: print(f"stored #{memory.id}: {memory.content}"),
    )
    return 0


def handle_search(store: MemoryStore, args: argparse.Namespace, as_json: bool) -> int:
    """Search memories by meaning."""
    results = store.search(
        query=args.query, limit=args.limit, tags=args.tags, min_score=args.min_score
    )
    payload = [result.to_dict() for result in results]

    def render() -> None:
        if not results:
            print("no matches")
            return
        for result in results:
            print(f"[{result.score:.3f}] #{result.memory.id} {result.memory.content}")

    _print(payload, as_json, render)
    return 0


def handle_recall(store: MemoryStore, args: argparse.Namespace, as_json: bool) -> int:
    """Read a memory by id, or the most recent ones."""
    if args.memory_id is not None:
        memory = store.get(args.memory_id)
        if memory is None:
            print(f"no memory with id {args.memory_id}", file=sys.stderr)
            return 1
        memories = [memory]
    else:
        memories = store.recent(limit=args.limit)

    def render() -> None:
        if not memories:
            print("no memories yet")
            return
        for memory in memories:
            tags = f" [{', '.join(memory.tags)}]" if memory.tags else ""
            print(f"#{memory.id} ({memory.created_at}){tags} {memory.content}")

    _print([m.to_dict() for m in memories], as_json, render)
    return 0


def handle_forget(store: MemoryStore, args: argparse.Namespace, as_json: bool) -> int:
    """Delete a memory by id, or bulk-delete by tag and/or age."""
    if args.memory_id is not None:
        deleted = store.delete(args.memory_id)
        if not deleted:
            print(f"no memory with id {args.memory_id}", file=sys.stderr)
            return 1
        _print(
            {"deleted": True, "memory_id": args.memory_id},
            as_json,
            lambda: print(f"forgot #{args.memory_id}"),
        )
        return 0

    # Bulk delete: preview what matches, then confirm before deleting.
    try:
        matches = store.matching(tags=args.tags, older_than_days=args.older_than)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not matches:
        print("nothing matches those filters", file=sys.stderr)
        return 0

    def render_preview(stream: TextIO) -> None:
        for memory in matches:
            tags = f" [{', '.join(memory.tags)}]" if memory.tags else ""
            print(f"#{memory.id} ({memory.created_at}){tags} {memory.content}", file=stream)

    if as_json:
        # Keep stdout machine-readable: the human-readable preview and the
        # confirmation prompt go to stderr, so the result on stdout stays a
        # single JSON document a script can parse.
        render_preview(sys.stderr)
    else:
        render_preview(sys.stdout)

    if not args.yes:
        print(f"Delete {len(matches)} memories? [y/N] ", file=sys.stderr, end="", flush=True)
        answer = input().strip().lower()
        if answer not in ("y", "yes"):
            print("aborted", file=sys.stderr)
            return 1

    count = store.delete_many(tags=args.tags, older_than_days=args.older_than)
    _print(
        {"deleted": True, "count": count},
        as_json,
        lambda: print(f"forgot {count} memories"),
    )
    return 0


def handle_stats(store: MemoryStore, args: argparse.Namespace, as_json: bool) -> int:
    """Report database location and memory count."""
    stats = store.stats()
    _print(
        stats,
        as_json,
        lambda: print(
            f"db: {stats['db_path']}\n"
            f"memories: {stats['memories']}\n"
            f"model: {stats['embedding_model']}"
        ),
    )
    return 0