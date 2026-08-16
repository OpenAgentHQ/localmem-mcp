"""Backward-compatible facade over :mod:`localmem_mcp.mcp`.

The FastMCP server now lives in the :mod:`localmem_mcp.mcp` package; this
module re-exports the names that previously lived here so existing imports
(docs, tests, and library users) keep working unchanged.
"""

from __future__ import annotations

from .mcp import configure, get_store, main, mcp

__all__ = ["configure", "get_store", "main", "mcp"]


if __name__ == "__main__":
    main()
