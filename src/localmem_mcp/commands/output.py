"""Output helpers shared by the CLI command handlers."""

from __future__ import annotations

import json
from collections.abc import Callable


def _print(payload: object, as_json: bool, render: Callable[[], None]) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        render()
