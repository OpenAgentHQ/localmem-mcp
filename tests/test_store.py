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

from localmem_mcp.store import Memory, MemoryStore, _days_ago, _fts_query

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


def test_search_offset_pages_without_overlap_or_gaps(store):
    for text in [
        "sqlite storage database",
        "postgres database storage",
        "database typing python",
        "rust language typing",
        "coffee and tea in the morning",
    ]:
        store.add(text)

    everything = store.search("database storage", limit=5)
    assert len(everything) == 5

    first = store.search("database storage", limit=2, offset=0)
    second = store.search("database storage", limit=2, offset=2)
    third = store.search("database storage", limit=2, offset=4)

    paged = first + second + third
    assert [r.memory.id for r in paged] == [r.memory.id for r in everything]
    assert len({r.memory.id for r in paged}) == 5  # no page repeats a memory


def test_search_ranking_is_stable_across_identical_calls(store):
    # Same content twice means identical scores — the id tiebreak keeps the
    # order fixed, which is what makes paging safe.
    for _ in range(4):
        store.add("sqlite database storage")

    first = [r.memory.id for r in store.search("database", limit=4)]
    second = [r.memory.id for r in store.search("database", limit=4)]

    assert first == second
    assert first == sorted(first, reverse=True)


def test_search_offset_past_the_end_returns_empty(store):
    store.add("sqlite storage")
    store.add("postgres database")

    assert store.search("database", limit=5, offset=2) == []
    assert store.search("database", limit=5, offset=99) == []


def test_search_negative_offset_is_clamped_to_zero(store):
    for text in ["sqlite storage", "postgres database", "coffee and tea"]:
        store.add(text)

    unpaged = store.search("database", limit=2)

    assert [r.memory.id for r in store.search("database", limit=2, offset=-5)] == [
        r.memory.id for r in unpaged
    ]


def test_search_offset_applies_after_min_score_filtering(store):
    store.add("sqlite storage database")
    store.add("coffee and tea in the morning")

    # The coffee memory scores near zero for this query, so it is filtered out
    # before paging — offset=1 must fall past the end, not land on it.
    assert store.search("database storage", limit=5, min_score=0.5, offset=1) == []


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


def test_list_returns_newest_first_with_total(store):
    first = store.add("first memory")
    second = store.add("second memory")
    third = store.add("third memory")

    memories, total = store.list()

    assert total == 3
    assert [m.id for m in memories] == [third.id, second.id, first.id]


def test_list_returns_oldest_first(store):
    first = store.add("first memory")
    second = store.add("second memory")
    third = store.add("third memory")

    memories, total = store.list(order="oldest")

    assert total == 3
    assert [m.id for m in memories] == [first.id, second.id, third.id]


def test_list_filters_by_all_tags(store):
    both = store.add("both tags", tags=["decision", "project"])
    store.add("decision only", tags=["decision"])
    store.add("project only", tags=["project"])

    memories, total = store.list(tags=["decision", "project"])

    assert total == 1
    assert [m.id for m in memories] == [both.id]


def test_list_paginates_without_overlap_or_gaps(store):
    memories = [store.add(f"memory {number}") for number in range(5)]

    first_page, total = store.list(limit=2, offset=0)
    second_page, second_total = store.list(limit=2, offset=2)
    third_page, third_total = store.list(limit=2, offset=4)

    assert total == 5
    assert second_total == 5
    assert third_total == 5

    first_ids = [m.id for m in first_page]
    second_ids = [m.id for m in second_page]
    third_ids = [m.id for m in third_page]

    assert first_ids == [memories[4].id, memories[3].id]
    assert second_ids == [memories[2].id, memories[1].id]
    assert third_ids == [memories[0].id]

    assert first_ids + second_ids + third_ids == [
        memory.id for memory in reversed(memories)
    ]


def test_list_returns_empty_store(store):
    memories, total = store.list()

    assert memories == []
    assert total == 0


def test_list_does_not_call_embedder():
    class CountingEmbedder(StubEmbedder):
        def __init__(self) -> None:
            self.calls = 0

        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            self.calls += len(texts)
            return super().embed(texts)

    with MemoryStore(db_path=":memory:", embedder=CountingEmbedder()) as store:
        store.add("a decision about sqlite", tags=["decision"])
        assert store.embedder.calls == 1

        memories, total = store.list(tags=["decision"])

        assert total == 1
        assert memories[0].content == "a decision about sqlite"
        assert store.embedder.calls == 1


def test_list_validates_arguments(store):
    with pytest.raises(ValueError, match="limit must be positive"):
        store.list(limit=0)

    with pytest.raises(ValueError, match="offset must be non-negative"):
        store.list(offset=-1)

    with pytest.raises(ValueError, match="order must be"):
        store.list(order="random")


def test_delete_removes_memory(store):
    memory = store.add("temporary note about tea")

    assert store.delete(memory.id) is True
    assert store.get(memory.id) is None
    assert store.delete(memory.id) is False


def test_delete_many_by_tag(store):
    stale = store.add("stale decision", tags=["stale"])
    keep = store.add("current note", tags=["current"])
    store.add("another stale one", tags=["stale", "scratch"])

    count = store.delete_many(tags=["stale"])

    assert count == 2
    assert store.get(stale.id) is None
    assert store.get(keep.id) is not None


def test_delete_many_by_age(store):
    old = store.add("old note")
    recent = store.add("recent note")
    store._conn.execute(
        "UPDATE memories SET created_at = ? WHERE id = ?",
        (_days_ago(200), old.id),
    )
    store._conn.commit()

    count = store.delete_many(older_than_days=90)

    assert count == 1
    assert store.get(old.id) is None
    assert store.get(recent.id) is not None


def test_delete_many_combines_tags_and_age(store):
    old_stale = store.add("old stale note", tags=["stale"])
    recent_stale = store.add("recent stale note", tags=["stale"])
    old_other = store.add("old other note", tags=["other"])
    store._conn.execute(
        "UPDATE memories SET created_at = ? WHERE id IN (?, ?)",
        (_days_ago(200), old_stale.id, old_other.id),
    )
    store._conn.commit()

    count = store.delete_many(tags=["stale"], older_than_days=90)

    assert count == 1
    assert store.get(old_stale.id) is None
    assert store.get(recent_stale.id) is not None
    assert store.get(old_other.id) is not None


def test_delete_many_requires_a_filter(store):
    store.add("a note")

    with pytest.raises(ValueError, match="at least one"):
        store.delete_many()
    with pytest.raises(ValueError, match="at least one"):
        store.delete_many(tags=[])
    with pytest.raises(ValueError, match="non-negative"):
        store.delete_many(older_than_days=-1)

    assert store.count() == 1  # nothing was wiped


def test_delete_many_tag_matching_is_exact(store):
    """'ops' must not match a memory tagged 'operations'."""
    store.add("about operations", tags=["operations"])
    store.add("about ops", tags=["ops"])

    count = store.delete_many(tags=["ops"])

    assert count == 1
    assert store.count() == 1


def test_matching_previews_what_delete_many_would_remove(store):
    stale = store.add("stale one", tags=["stale"])
    keep = store.add("keep me", tags=["current"])

    matches = store.matching(tags=["stale"])

    assert [m.id for m in matches] == [stale.id]
    assert store.get(keep.id) is not None  # preview doesn't delete


def test_delete_many_keeps_fts_index_consistent(store):
    """The AFTER DELETE trigger must drop the FTS row too."""
    stale = store.add("The deploy key is stored in the vault", tags=["stale"])
    keep = store.add("Coffee is a drink")

    assert store.search("deploy key")[0].memory.id == stale.id

    store.delete_many(tags=["stale"])

    results = store.search("deploy key")
    assert all(r.memory.id != stale.id for r in results)
    row = store._conn.execute(
        "SELECT rowid FROM memories_fts WHERE rowid = ?", (stale.id,)
    ).fetchone()
    assert row is None
    assert store.get(keep.id) is not None


def test_update_content_reembeds_and_preserves_created_at(store):
    memory = store.add("We picked postgres for storage")
    store.add("I drink coffee every morning")

    updated = store.update(memory.id, content="We picked sqlite as the database")

    assert updated is not None
    assert updated.id == memory.id
    assert updated.content == "We picked sqlite as the database"
    assert updated.created_at == memory.created_at
    assert updated.updated_at >= memory.updated_at

    # Re-embedding means search finds the corrected text, not the stale original.
    results = store.search("which database did we pick?", limit=3)
    assert results[0].memory.id == memory.id


def test_update_tag_only_skips_embedding():
    class CountingEmbedder(StubEmbedder):
        def __init__(self) -> None:
            self.calls = 0

        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            self.calls += len(texts)
            return super().embed(texts)

    with MemoryStore(db_path=":memory:", embedder=CountingEmbedder()) as s:
        memory = s.add("sqlite is the database", tags=["old"])
        assert s.embedder.calls == 1

        updated = s.update(memory.id, tags=["new"])
        assert updated is not None
        assert updated.content == "sqlite is the database"
        assert updated.tags == ["new"]
        assert s.embedder.calls == 1  # tags aren't embedded — no re-embed

        s.update(memory.id, content="sqlite is the database")
        assert s.embedder.calls == 2  # a content change does re-embed


def test_update_missing_id_returns_none(store):
    assert store.update(4242, content="anything") is None


def test_update_rejects_empty_content(store):
    memory = store.add("a note about tea")
    with pytest.raises(ValueError):
        store.update(memory.id, content="   ")


def test_update_with_no_changes_raises(store):
    memory = store.add("a note about tea")
    with pytest.raises(ValueError):
        store.update(memory.id)


def test_update_refreshes_fts_index(store):
    """The AFTER UPDATE trigger re-syncs the FTS row with the new content."""
    memory = store.add("The deploy key is stored in the vault")

    store.update(memory.id, content="The deploy key is stored in the safe")

    row = store._conn.execute(
        "SELECT content FROM memories_fts WHERE rowid = ?", (memory.id,)
    ).fetchone()
    assert row is not None
    assert row["content"] == "The deploy key is stored in the safe"


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
