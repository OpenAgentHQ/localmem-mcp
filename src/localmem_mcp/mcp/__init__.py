"""MCP server implementation package.

The public surface is re-exported by :mod:`localmem_mcp.server`, the
backward-compatible facade. Importing this package registers the tools on
:data:`localmem_mcp.mcp.app.mcp`.
"""

from __future__ import annotations

from . import tools as _tools  # noqa: F401 - importing registers the tools on `mcp`
from .app import configure, get_store, main, mcp

__all__ = ["configure", "get_store", "main", "mcp"]
