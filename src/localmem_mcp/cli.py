"""Backward-compatible facade over :mod:`localmem_mcp.commands`.

The CLI now lives in the :mod:`localmem_mcp.commands` package; this module
re-exports the names that previously lived here so existing imports keep
working. The console entry point is ``localmem_mcp.cli:main`` (see
``pyproject.toml``).
"""

from __future__ import annotations

from .commands import _build_parser, _days_arg, _print, _shared, main

__all__ = ["_build_parser", "_days_arg", "_print", "_shared", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
