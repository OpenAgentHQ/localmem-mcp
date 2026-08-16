"""Small helpers shared across the data layer."""

from __future__ import annotations

import array
import json
import os
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .models import Memory


def default_db_path() -> Path:
    """Where memories live unless told otherwise.

    Honours ``LOCALMEM_DB_PATH``, then ``LOCALMEM_HOME``, then ``~/.localmem``.
    """
    env_path = os.environ.get("LOCALMEM_DB_PATH")
    if env_path:
        return Path(env_path).expanduser()
    home = Path(os.environ.get("LOCALMEM_HOME", "~/.localmem")).expanduser()
    return home / "memories.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _days_ago(days: int) -> str:
    """ISO timestamp for ``days`` before now, for age-based filtering."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")


def _normalize_tags(tags: Iterable[str] | str | None) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        raw: Iterable[str] = tags.split(",")
    else:
        raw = tags
    seen: list[str] = []
    for tag in raw:
        cleaned = tag.strip().lower()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _pack(vector: Sequence[float]) -> bytes:
    return array.array("f", vector).tobytes()


def _unpack(blob: bytes) -> list[float]:
    vec = array.array("f")
    vec.frombytes(blob)
    return list(vec)


def _escape_like(s: str) -> str:
    """Escape SQL LIKE wildcards (%, _, \\) for literal matching."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _bulk_filters(
    tags: Iterable[str] | str | None, older_than_days: int | None
) -> tuple[str, list[Any]]:
    """Validate bulk-delete filters and return ``(where_sql, params)``.

    Bulk deletion must be scoped: at least one of ``tags`` or
    ``older_than_days`` is required, otherwise a typo could wipe the whole
    store. Tags are matched conjunctively against the CSV ``tags`` column with
    padded commas so ``ops`` can't match ``operations``.
    """
    tag_list = _normalize_tags(tags)
    if not tag_list and older_than_days is None:
        raise ValueError("at least one of tags or older_than_days is required")
    if older_than_days is not None and older_than_days < 0:
        raise ValueError("older_than_days must be non-negative")

    clauses: list[str] = []
    params: list[Any] = []
    for tag in tag_list:
        clauses.append("(',' || tags || ',') LIKE ? ESCAPE '\\'")
        params.append(f"%,{_escape_like(tag)},%")
    if older_than_days is not None:
        clauses.append("created_at < ?")
        params.append(_days_ago(older_than_days))
    return " AND ".join(clauses), params


def _row_to_memory(row: sqlite3.Row) -> Memory:
    try:
        metadata = json.loads(row["metadata"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return Memory(
        id=int(row["id"]),
        content=row["content"],
        tags=[t for t in (row["tags"] or "").split(",") if t],
        source=row["source"],
        metadata=metadata,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _has_tags(memory: Memory, wanted: Sequence[str]) -> bool:
    return all(tag in memory.tags for tag in wanted)
