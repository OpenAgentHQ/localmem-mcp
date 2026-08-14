"""Tests for the SQLite memory store.

These run against a deterministic stub embedder so the suite stays fast and
offline. The real fastembed path is covered by `test_fastembed_roundtrip`,
which is skipped unless the model is already available locally (set
LOCALMEM_TEST_FASTEMBED=1 to require it).
"""

from __future__ import annotations

import math
import os
from collections.abc import Sequence

import pytest

from localmem_mcp.store import Memory, MemoryStore, _fts_query

VOCAB = [
    "sqlite", "database", "storage", "postgres",
    "python", "rust", "language", "typing",
    "coffee", "tea", "morning", "drink",
]


class StubEmbedder:
    """Bag-of-words vectors — deterministic, offline, and good enough to make
    'sqlite' look more like 'database' than like 'coffee'."""

    name = "stub-bow"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            words = text.lower().split()
            vector = [float(sum(1 for w in words if term in w)) for term in VOCAB]
            if not any(vector):
                vector[0] = 1e-6  # avoid a zero vector
            vectors.append(vector)
        return vectors


@pytest.fixture
def store(tmp_path):
    with MemoryStore(db_path=tmp_path / "memories.db", embedder=StubEmbedder()) as s:
        yield s


def test_add_returns_stored_memory(store):
    memory = store.add("We chose sqlite for storage", tags=["Decision", " decision "])

    assert isinstance(memory, Memory)
    assert memory.id > 0
    assert memory.content == "We chose sqlite for storage"
    assert memory.tags == ["decision"]  # normalized and de-duplicated
    assert memory.created_at


def test_add_rejects_empty_content(store):
    with pytest.raises(ValueError):
        store.add("   ")


def test_get_roundtrips_metadata(store):
    stored = store.add("python is the language", metadata={"confidence": 0.9})

    fetched = store.get(stored.id)

    assert fetched is not None
    assert fetched.content == stored.content
    assert fetched.metadata == {"confidence": 0.9}


def test_get_missing_returns_none(store):
    assert store.get(4242) is None


def test_search_ranks_semantically_closest_first(store):
    store.add("I drink coffee every morning")
    store.add("We picked sqlite as the database")
    store.add("The project is written in python")

    results = store.search("which database did we use?", limit=3)

    assert results
    assert "sqlite" in results[0].memory.content
    assert results[0].score >= results[-1].score


def test_search_respects_limit_and_min_score(store):
    for text in ["sqlite storage", "postgres database", "coffee and tea"]:
        store.add(text)

    assert len(store.search("database", limit=1)) == 1
    assert store.search("database", min_score=1.5) == []


def test_search_filters_by_tags(store):
    store.add("sqlite is the database", tags=["work"])
    store.add("sqlite is the database", tags=["personal"])

    results = store.search("database", tags=["work"])

    assert len(results) == 1
    assert results[0].memory.tags == ["work"]


def test_search_on_empty_store_returns_nothing(store):
    assert store.search("anything") == []
    assert store.search("   ") == []


def test_keyword_match_boosts_exact_terms(store):
    store.add("The deploy key is stored in the vault")
    store.add("Coffee is a drink")

    results = store.search("deploy key")

    assert results[0].memory.content.startswith("The deploy key")


def test_recent_returns_newest_first(store):
    first = store.add("first memory about python")
    second = store.add("second memory about rust")

    recent = store.recent(limit=2)

    assert [m.id for m in recent] == [second.id, first.id]


def test_recent_filters_by_tags(store):
    store.add("tagged memory", tags=["keep"])
    store.add("untagged memory")

    recent = store.recent(limit=5, tags=["keep"])

    assert len(recent) == 1
    assert recent[0].content == "tagged memory"


def test_delete_removes_memory(store):
    memory = store.add("temporary note about tea")

    assert store.delete(memory.id) is True
    assert store.get(memory.id) is None
    assert store.delete(memory.id) is False


def test_count_and_stats(store):
    store.add("one")
    store.add("two")

    stats = store.stats()

    assert store.count() == 2
    assert stats["memories"] == 2
    assert stats["embedding_model"] == "stub-bow"
    assert stats["db_path"].endswith("memories.db")


def test_persists_across_reopen(tmp_path):
    db = tmp_path / "memories.db"
    with MemoryStore(db_path=db, embedder=StubEmbedder()) as first:
        first.add("sqlite keeps this on disk")

    with MemoryStore(db_path=db, embedder=StubEmbedder()) as second:
        assert second.count() == 1
        assert second.search("database")[0].memory.content.startswith("sqlite")


@pytest.mark.parametrize(
    "text, expected",
    [
        ("hello world", '"hello" OR "world"'),
        ('drop "table" AND *', '"drop" OR "table" OR "AND"'),
        ("!!!", ""),
    ],
)
def test_fts_query_sanitizes_user_input(text, expected):
    assert _fts_query(text) == expected


def test_search_survives_fts_operators_in_query(store):
    store.add("a memory about python typing")

    # Raw FTS5 syntax must not blow up the query.
    assert store.search('python AND "typing" OR *') is not None


@pytest.mark.skipif(
    not os.environ.get("LOCALMEM_TEST_FASTEMBED"),
    reason="set LOCALMEM_TEST_FASTEMBED=1 to run against real fastembed embeddings",
)
def test_fastembed_roundtrip(tmp_path):
    with MemoryStore(db_path=tmp_path / "real.db") as real_store:
        real_store.add("We decided to store everything in SQLite", tags=["decision"])
        real_store.add("My favourite drink is oat milk latte")

        results = real_store.search("what database are we using?")

        assert "SQLite" in results[0].memory.content
        assert 0.0 < results[0].score <= 1.0
        assert not math.isnan(results[0].score)
