"""The :class:`MemoryStore` — SQLite-backed memory with hybrid search.

Everything here runs on the user's machine: SQLite for storage, fastembed for
embeddings. No network calls are made except the one-time model download that
fastembed performs on first use.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .embedders import DEFAULT_MODEL, Embedder, FastEmbedEmbedder
from .models import Memory, SearchResult
from .schema import _SCHEMA
from .search import KEYWORD_WEIGHT, _cosine, _fts_query
from .utils import (
    _bulk_filters,
    _has_tags,
    _normalize_tags,
    _now,
    _pack,
    _row_to_memory,
    _unpack,
    default_db_path,
)


class MemoryStore:
    """Local memory store backed by SQLite and on-device embeddings."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        embedder: Embedder | None = None,
        model_name: str = DEFAULT_MODEL,
    ):
        self.db_path = Path(db_path).expanduser() if db_path else default_db_path()
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedder: Embedder = embedder or FastEmbedEmbedder(model_name)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._lock = threading.Lock()
        with self._conn:
            self._conn.executescript(_SCHEMA)

    # -- writes ---------------------------------------------------------

    def add(
        self,
        content: str,
        tags: Iterable[str] | str | None = None,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Memory:
        """Embed and persist a memory. Returns the stored record."""
        content = (content or "").strip()
        if not content:
            raise ValueError("content must not be empty")

        tag_list = _normalize_tags(tags)
        vector = self.embedder.embed([content])[0]
        timestamp = _now()

        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO memories
                    (content, tags, source, metadata, created_at, updated_at,
                     embedding, embedding_model, dim)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    content,
                    ",".join(tag_list),
                    source,
                    json.dumps(metadata or {}),
                    timestamp,
                    timestamp,
                    _pack(vector),
                    self.embedder.name,
                    len(vector),
                ),
            )
        return Memory(
            id=int(cursor.lastrowid),
            content=content,
            tags=tag_list,
            source=source,
            metadata=metadata or {},
            created_at=timestamp,
            updated_at=timestamp,
        )

    def update(
        self,
        memory_id: int,
        content: str | None = None,
        tags: Iterable[str] | str | None = None,
        source: str | None = None,
    ) -> Memory | None:
        """Correct an existing memory in place. Returns None if there's no such memory.

        Only the fields you pass are changed. Changing ``content`` re-embeds the
        memory so search finds the correction; a tag- or source-only update
        leaves the vector alone. ``created_at`` is preserved and ``updated_at``
        refreshed. The FTS5 index stays in sync via the AFTER UPDATE trigger.
        """
        sets: list[str] = []
        params: list[Any] = []

        if content is not None:
            content = content.strip()
            if not content:
                raise ValueError("content must not be empty")
            vector = self.embedder.embed([content])[0]
            sets += ["content = ?", "embedding = ?", "embedding_model = ?", "dim = ?"]
            params += [content, _pack(vector), self.embedder.name, len(vector)]

        if tags is not None:
            tag_list = _normalize_tags(tags)
            sets.append("tags = ?")
            params.append(",".join(tag_list))

        if source is not None:
            sets.append("source = ?")
            params.append(source)

        if not sets:
            raise ValueError("nothing to update: pass content, tags, or source")

        sets.append("updated_at = ?")
        params.append(_now())
        params.append(memory_id)

        with self._lock, self._conn:
            cursor = self._conn.execute(
                f"UPDATE memories SET {', '.join(sets)} WHERE id = ?", params
            )
            if cursor.rowcount == 0:
                return None
            row = self._conn.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()
        return _row_to_memory(row)

    def delete(self, memory_id: int) -> bool:
        """Delete a memory. Returns True if it existed, False if it didn't."""
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "DELETE FROM memories WHERE id = ?", (memory_id,)
            )
        return cursor.rowcount > 0

    def matching(
        self,
        tags: Iterable[str] | str | None = None,
        older_than_days: int | None = None,
    ) -> list[Memory]:
        """Memories a bulk delete would remove, newest first.

        Same filters as :meth:`delete_many`, without deleting — the CLI uses
        this to show what ``forget --tag stale`` would remove before asking.
        """
        where, params = _bulk_filters(tags, older_than_days)
        rows = self._conn.execute(
            f"SELECT * FROM memories WHERE {where} ORDER BY id DESC", params
        ).fetchall()
        return [_row_to_memory(row) for row in rows]

    def delete_many(
        self,
        tags: Iterable[str] | str | None = None,
        older_than_days: int | None = None,
    ) -> int:
        """Bulk-delete memories matching all given tags and/or age.

        Requires at least one of ``tags`` or ``older_than_days``; an unfiltered
        call raises :class:`ValueError` so the store can't be wiped by accident.
        Deletion is hard — rows are gone, not hidden — and the FTS5 index stays
        in sync via the AFTER DELETE trigger. Returns the number removed.
        """
        where, params = _bulk_filters(tags, older_than_days)
        with self._lock, self._conn:
            cursor = self._conn.execute(
                f"DELETE FROM memories WHERE {where}", params
            )
        return cursor.rowcount

    # -- reads ----------------------------------------------------------

    def get(self, memory_id: int) -> Memory | None:
        """Fetch one memory by id, or None if there's no such memory."""
        row = self._conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        return _row_to_memory(row) if row else None

    def recent(
        self, limit: int = 10, tags: Iterable[str] | str | None = None
    ) -> list[Memory]:
        """Most recently stored memories, newest first."""
        tag_list = _normalize_tags(tags)
        rows = self._conn.execute(
            "SELECT * FROM memories ORDER BY id DESC LIMIT ?",
            (max(1, limit) * (10 if tag_list else 1),),
        ).fetchall()
        memories = [_row_to_memory(row) for row in rows]
        if tag_list:
            memories = [m for m in memories if _has_tags(m, tag_list)]
        return memories[:limit]

    def search(
        self,
        query: str,
        limit: int = 5,
        tags: Iterable[str] | str | None = None,
        min_score: float = 0.0,
        offset: int = 0,
    ) -> list[SearchResult]:
        """Semantic search, nudged by exact keyword matches.

        Every stored memory is scored by cosine similarity against the query
        embedding; memories that also match the FTS5 index get a bounded
        keyword bonus so literal terms are not lost to paraphrase.

        ``offset`` skips that many ranked results before ``limit`` is applied,
        so ``limit=5, offset=5`` is the second page. Ranking is deterministic
        (score descending, ties broken by id descending), so pages neither
        overlap nor skip. Negative offsets are clamped to 0, and an offset past
        the end returns an empty list rather than raising.
        """
        query = (query or "").strip()
        if not query:
            return []

        tag_list = _normalize_tags(tags)
        rows = self._conn.execute("SELECT * FROM memories").fetchall()
        if not rows:
            return []

        query_vector = self.embedder.embed([query])[0]
        keyword_hits = self._keyword_hits(query)

        results: list[SearchResult] = []
        for row in rows:
            memory = _row_to_memory(row)
            if tag_list and not _has_tags(memory, tag_list):
                continue
            similarity = (
                _cosine(query_vector, _unpack(row["embedding"]))
                if row["embedding"]
                else 0.0
            )
            # Keyword matching is additive on top of cosine so scores stay on
            # the familiar 0-1 similarity scale that `min_score` filters on.
            score = min(1.0, similarity + KEYWORD_WEIGHT * keyword_hits.get(memory.id, 0.0))
            if score >= min_score:
                results.append(SearchResult(memory=memory, score=score))

        results.sort(key=lambda r: (-r.score, -r.memory.id))
        start = max(0, offset)
        return results[start : start + max(1, limit)]

    def _keyword_hits(self, query: str) -> dict[int, float]:
        """Map memory id -> keyword score in [0, 1] using FTS5 bm25 ranking."""
        match = _fts_query(query)
        if not match:
            return {}
        try:
            rows = self._conn.execute(
                """
                SELECT rowid AS id, bm25(memories_fts) AS rank
                FROM memories_fts WHERE memories_fts MATCH ? ORDER BY rank LIMIT 50
                """,
                (match,),
            ).fetchall()
        except sqlite3.OperationalError:
            # FTS5 unavailable in this SQLite build — vector search still works.
            return {}
        if not rows:
            return {}
        # bm25() returns negative numbers, better matches more negative.
        best = min(row["rank"] for row in rows)
        if best == 0:
            return {int(row["id"]): 1.0 for row in rows}
        return {int(row["id"]): max(0.0, min(1.0, row["rank"] / best)) for row in rows}

    def count(self) -> int:
        """Total number of stored memories."""
        return int(self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0])

    def stats(self) -> dict[str, Any]:
        """Database location, memory count, and the embedding model in use."""
        return {
            "db_path": str(self.db_path),
            "memories": self.count(),
            "embedding_model": self.embedder.name,
        }

    # -- lifecycle ------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    def __enter__(self) -> MemoryStore:  # noqa: PYI034 - typing.Self needs 3.11
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()