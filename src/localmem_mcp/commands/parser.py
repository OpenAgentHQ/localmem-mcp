"""Argument parsing for the localmem-mcp CLI."""

from __future__ import annotations

import argparse
import re

from .. import __version__
from ..core import DEFAULT_MODEL, default_db_path


def _days_arg(value: str) -> int:
    """Parse a duration like ``30``, ``90d``, or ``8w`` into days."""
    text = str(value).strip().lower()
    match = re.fullmatch(r"(\d+)([dw]?)", text)
    if not match:
        raise argparse.ArgumentTypeError(
            f"invalid duration {value!r} (use e.g. 90, 90d, or 8w)"
        )
    days = int(match.group(1))
    if match.group(2) == "w":
        days *= 7
    return days


def _build_parser() -> argparse.ArgumentParser:
    # Shared flags live on a parent parser so they work either before or after
    # the subcommand: `localmem-mcp --db x search q` and `search q --db x`.
    #
    # They default to SUPPRESS rather than a real value. A subparser writes into
    # the same namespace as the main parser, so an ordinary default would
    # overwrite a value already parsed from before the subcommand — silently
    # sending `--db x stats` to the default database. With SUPPRESS an unset
    # option writes nothing, and `_shared()` supplies the default instead.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--db",
        metavar="PATH",
        default=argparse.SUPPRESS,
        help=f"SQLite database to use (default: {default_db_path()})",
    )
    common.add_argument(
        "--model",
        default=argparse.SUPPRESS,
        help=f"fastembed model name (default: {DEFAULT_MODEL})",
    )
    common.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Emit JSON instead of text",
    )

    parser = argparse.ArgumentParser(
        prog="localmem-mcp",
        description="Local-first, zero-API memory for AI agents.",
        parents=[common],
    )
    parser.add_argument("--version", action="version", version=f"localmem-mcp {__version__}")

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", parents=[common], help="Run the MCP server over stdio (default)")

    add = sub.add_parser("add", parents=[common], help="Store a memory")
    add.add_argument("content", help="The memory text")
    add.add_argument("--tag", action="append", dest="tags", default=[], help="Tag (repeatable)")
    add.add_argument("--source", help="Where this memory came from")

    search = sub.add_parser("search", parents=[common], help="Search memories by meaning")
    search.add_argument("query")
    search.add_argument("-n", "--limit", type=int, default=5)
    search.add_argument("--tag", action="append", dest="tags", default=[])
    search.add_argument("--min-score", type=float, default=0.0)

    recall = sub.add_parser(
        "recall", parents=[common], help="Read a memory by id, or the most recent ones"
    )
    recall.add_argument("memory_id", nargs="?", type=int)
    recall.add_argument("-n", "--limit", type=int, default=5)

    forget = sub.add_parser(
        "forget",
        parents=[common],
        help="Delete a memory by id, or bulk-delete by tag and/or age",
    )
    forget.add_argument(
        "memory_id",
        nargs="?",
        type=int,
        help="Delete the single memory with this id",
    )
    forget.add_argument(
        "--tag",
        action="append",
        dest="tags",
        default=[],
        help="Bulk-delete memories with this tag (repeatable)",
    )
    forget.add_argument(
        "--older-than",
        dest="older_than",
        type=_days_arg,
        default=None,
        metavar="DURATION",
        help="Bulk-delete memories older than this (e.g. 90, 90d, or 8w)",
    )
    forget.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt for bulk deletes",
    )
    list_memories = sub.add_parser(
        "list",
        parents=[common],
        help="List stored memories without semantic search",
    )
    list_memories.add_argument(
        "--tag",
        action="append",
        dest="tags",
        default=[],
        help="Filter by tag (repeatable; all tags must match)",
    )
    list_memories.add_argument(
        "-n",
        "--limit",
        type=int,
        default=20,
        help="Maximum number of memories to return",
    )
    list_memories.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Number of matching memories to skip",
    )
    list_memories.add_argument(
        "--order",
        choices=["newest", "oldest"],
        default="newest",
        help="Ordering direction",
    )

    sub.add_parser("stats", parents=[common], help="Show database location and memory count")
    return parser