"""SQLite + local-embedding memory backend.

Everything here runs on the user's machine: SQLite for storage, fastembed for
embeddings. No network calls are made except the one-time model download that
fastembed performs on first use.
"""

from __future__ import annotations

import array
import json
import math
import os
import sqlite3
import threading
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"

#: Weight given to the keyword (FTS5) signal when blending with cosine
#: similarity. Vector similarity carries the rest.
KEYWORD_WEIGHT = 0.25

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    content         TEXT    NOT NULL,
    tags            TEXT    NOT NULL DEFAULT '',
    source          TEXT,
    metadata        TEXT    NOT NULL DEFAULT '{}',
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    embedding       BLOB,
    embedding_model TEXT,
    dim             INTEGER
);

CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at DESC);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
USING fts5(content, tags, content='memories', content_rowid='id');

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, tags) VALUES (new.id, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags)
    VALUES ('delete', old.id, old.content, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags)
    VALUES ('delete', old.id, old.content, old.tags);
    INSERT INTO memories_fts(rowid, content, tags) VALUES (new.id, new.content, new.tags);
END;
"""


class Embedder(Protocol):
    """Anything that can turn text into a fixed-length vector."""

    name: str

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        ...


class FastEmbedEmbedder:
    """Local ONNX embeddings via `fastembed`.

    The model is loaded lazily so importing this module (and starting the MCP
    server) stays fast — the first `store_memory`/`search_memory` call pays the
    load cost, not process startup.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, cache_dir: str | None = None):
        self.name = model_name
        self._cache_dir = cache_dir
        self._model: Any = None
        self._lock = threading.Lock()

    def _ensure_model(self) -> Any:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from fastembed import TextEmbedding

                    self._model = TextEmbedding(
                        model_name=self.name, cache_dir=self._cache_dir
                    )
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        model = self._ensure_model()
        return [list(map(float, vec)) for vec in model.embed(list(texts))]


@dataclass
class Memory:
    id: int
    content: str
    tags: list[str] = field(default_factory=list)
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResult:
    memory: Memory
    score: float

    def to_dict(self) -> dict[str, Any]:
        payload = self.memory.to_dict()
        payload["score"] = round(self.score, 4)
        return payload


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


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _fts_query(text: str) -> str:
    """Turn free text into a safe FTS5 OR-query.

    User text can contain FTS operators (``AND``, ``"``, ``*``, ``:``) that
    would either error or change the query's meaning, so each word is quoted
    and joined explicitly.
    """
    words = [w for w in "".join(c if c.isalnum() else " " for c in text).split() if w]
    return " OR ".join(f'"{w}"' for w in words)


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

    def delete(self, memory_id: int) -> bool:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "DELETE FROM memories WHERE id = ?", (memory_id,)
            )
        return cursor.rowcount > 0

    # -- reads ----------------------------------------------------------

    def get(self, memory_id: int) -> Memory | None:
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
    ) -> list[SearchResult]:
        """Semantic search, nudged by exact keyword matches.

        Every stored memory is scored by cosine similarity against the query
        embedding; memories that also match the FTS5 index get a bounded
        keyword bonus so literal terms are not lost to paraphrase.
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
        return results[: max(1, limit)]

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
        return int(self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0])

    def stats(self) -> dict[str, Any]:
        return {
            "db_path": str(self.db_path),
            "memories": self.count(),
            "embedding_model": self.embedder.name,
        }

    # -- lifecycle ------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> MemoryStore:  # noqa: PYI034 - typing.Self needs 3.11
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


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
