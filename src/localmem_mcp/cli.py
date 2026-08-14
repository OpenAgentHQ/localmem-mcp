"""Command-line entry point for localmem-mcp.

Running `localmem-mcp` with no arguments starts the MCP stdio server, which is
what MCP clients spawn. The other subcommands are for humans poking at the
store from a terminal.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .store import DEFAULT_MODEL, MemoryStore, default_db_path


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

    sub.add_parser("stats", parents=[common], help="Show database location and memory count")
    return parser


def _print(payload: object, as_json: bool, render) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        render()


def _shared(args: argparse.Namespace) -> tuple[str | None, str, bool]:
    """Read the shared flags, supplying the defaults SUPPRESS leaves out."""
    return (
        getattr(args, "db", None),
        getattr(args, "model", DEFAULT_MODEL),
        getattr(args, "json", False),
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    db_path, model_name, as_json = _shared(args)
    command = args.command or "serve"

    if command == "serve":
        from .server import configure, mcp

        configure(db_path=db_path, model_name=model_name)
        mcp.run()
        return 0

    store = MemoryStore(db_path=db_path, model_name=model_name)

    if command == "add":
        memory = store.add(content=args.content, tags=args.tags, source=args.source)
        _print(
            memory.to_dict(),
            as_json,
            lambda: print(f"stored #{memory.id}: {memory.content}"),
        )

    elif command == "search":
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

    elif command == "recall":
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

    elif command == "stats":
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

    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
