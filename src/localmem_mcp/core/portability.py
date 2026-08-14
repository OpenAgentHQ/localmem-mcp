"""JSONL import — reading an export back into a store.

The matching export lives on :meth:`MemoryStore.export_records`; this module
handles the other direction, where the input is a file someone may have hand
edited and the failure modes are more interesting.

Two rules shape it. **Vectors in the file are never trusted** — every imported
memory is re-embedded by the importing store, because a vector produced by a
different model is not wrong in any way search can detect; it just quietly stops
matching. And **a bad line is not fatal**: a 10,000-line import that dies on
line 3 is worse than useless, so malformed records are collected with their line
numbers and reported at the end.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - import cycle at runtime, fine for typing
    from .store import MemoryStore


@dataclass
class ImportReport:
    """What an import did, or — with ``dry_run`` — what it would have done."""

    imported: int = 0
    skipped_duplicates: int = 0
    dry_run: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def failed(self) -> int:
        """Number of lines that could not be read as a memory."""
        return len(self.errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "imported": self.imported,
            "skipped_duplicates": self.skipped_duplicates,
            "failed": self.failed,
            "dry_run": self.dry_run,
            "errors": list(self.errors),
        }


def _parse_record(raw: str) -> dict[str, Any]:
    """Turn one JSONL line into add() keyword arguments.

    Raises :class:`ValueError` with a human-readable reason for anything the
    store couldn't accept — the caller turns that into a numbered error.
    """
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"not valid JSON ({exc.msg})") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object, got {type(payload).__name__}")

    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("missing or empty 'content'")

    tags = payload.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    elif not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise ValueError("'tags' must be a list of strings")

    source = payload.get("source")
    if source is not None and not isinstance(source, str):
        raise ValueError("'source' must be a string or null")

    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError("'metadata' must be an object")

    created_at = payload.get("created_at")
    if created_at is not None and not isinstance(created_at, str):
        raise ValueError("'created_at' must be a string")

    # `id`, `embedding`, `embedding_model`, and `dim` are deliberately dropped:
    # ids are reassigned by the importing database, and vectors are recomputed.
    return {
        "content": content,
        "tags": tags,
        "source": source,
        "metadata": metadata,
        "created_at": created_at or None,
    }


def import_records(
    store: MemoryStore,
    lines: Iterable[str],
    dry_run: bool = False,
    allow_duplicates: bool = False,
) -> ImportReport:
    """Store one memory per JSONL line, skipping (and reporting) bad ones.

    ``lines`` is any iterable of strings — an open file, so a large import
    streams rather than loading the whole thing. Blank lines are ignored.

    Each memory is re-embedded by ``store``; embeddings present in the file are
    ignored. ``created_at`` is preserved when the record has one. By default a
    record whose content already exists in the store is skipped, so importing
    the same file twice doesn't double the store — pass ``allow_duplicates`` to
    store it anyway. With ``dry_run`` nothing is written and nothing is
    embedded; the report says what would have happened.
    """
    report = ImportReport(dry_run=dry_run)
    # Dry runs write nothing, so duplicates within the file have to be tracked
    # here — the store can't tell us about a memory it never saw.
    seen: set[str] = set()

    for number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            record = _parse_record(raw)
        except ValueError as exc:
            report.errors.append(f"line {number}: {exc}")
            continue

        if not allow_duplicates:
            content = record["content"].strip()
            if content in seen or store.contains(content):
                report.skipped_duplicates += 1
                continue
            seen.add(content)

        if not dry_run:
            store.add(**record)
        report.imported += 1

    return report
