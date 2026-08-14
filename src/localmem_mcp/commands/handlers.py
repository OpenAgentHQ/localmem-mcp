"""Per-command handlers for the localmem-mcp CLI.

Each handler takes the store, parsed args, and the JSON flag, and returns the
process exit code. Handlers are wired to subcommands in
:mod:`localmem_mcp.commands.main`.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import TextIO

from ..core import MemoryStore, import_records
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


def handle_export(store: MemoryStore, args: argparse.Namespace, as_json: bool) -> int:
    """Write memories to stdout as JSONL, one object per line.

    Output is always JSONL — `--json` has nothing to add, since the format is
    already machine-readable, and a single JSON array would defeat the point of
    a format you can stream and append to.
    """
    for record in store.export_records(
        tags=args.tags, with_embeddings=args.with_embeddings
    ):
        # No indent, no sorting: one compact line per memory is what makes the
        # file streamable and diff-friendly.
        print(json.dumps(record, ensure_ascii=False))
    return 0


def handle_import(store: MemoryStore, args: argparse.Namespace, as_json: bool) -> int:
    """Read JSONL and store each memory, skipping malformed lines."""
    try:
        if args.path == "-":
            report = import_records(
                store,
                sys.stdin,
                dry_run=args.dry_run,
                allow_duplicates=args.allow_duplicates,
            )
        else:
            with open(args.path, encoding="utf-8") as handle:
                report = import_records(
                    store,
                    handle,
                    dry_run=args.dry_run,
                    allow_duplicates=args.allow_duplicates,
                )
    except OSError as exc:
        print(f"cannot read {args.path}: {exc.strerror or exc}", file=sys.stderr)
        return 2

    # Per-line failures go to stderr in both modes, so a --json stdout stays a
    # single parseable document and a text run can be piped past the noise.
    for error in report.errors:
        print(error, file=sys.stderr)

    def render() -> None:
        verb = "would import" if report.dry_run else "imported"
        summary = f"{verb} {report.imported} memories"
        if report.skipped_duplicates:
            summary += f", skipped {report.skipped_duplicates} duplicates"
        if report.failed:
            summary += f", {report.failed} malformed lines"
        print(summary)

    _print(report.to_dict(), as_json, render)
    # Nonzero when something didn't make it in, so a script can tell a clean
    # import from one that quietly dropped lines.
    return 1 if report.errors else 0


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