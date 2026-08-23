"""CLI implementation package.

The public surface is re-exported by :mod:`localmem_mcp.cli`, the
backward-compatible facade that also hosts the console entry point
(``localmem_mcp.cli:main``).
"""

from __future__ import annotations

from .main import _shared, main
from .output import _print
from .parser import _build_parser, _days_arg

__all__ = ["_build_parser", "_days_arg", "_print", "_shared", "main"]
