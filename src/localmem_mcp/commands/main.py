"""CLI entry point: parse arguments and dispatch to the command handlers.

Running `localmem-mcp` with no arguments starts the MCP stdio server, which is
what MCP clients spawn. The other subcommands are for humans poking at the
store from a terminal.
"""

from __future__ import annotations

import argparse

from ..core import DEFAULT_MODEL, MemoryStore
from .handlers import (
    handle_add,
    handle_forget,
    handle_list,
    handle_recall,
    handle_search,
    handle_stats,
)
from .parser import _build_parser


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
        from ..server import configure, mcp

        configure(db_path=db_path, model_name=model_name)
        mcp.run()
        return 0

    store = MemoryStore(db_path=db_path, model_name=model_name)
    handlers = {
        "add": handle_add,
        "search": handle_search,
        "recall": handle_recall,
        "list": handle_list,
        "forget": handle_forget,
        "stats": handle_stats,
    }
    exit_code = handlers[command](store, args, as_json)
    store.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())