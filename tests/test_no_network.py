"""Proves the zero-network-calls claim with a test, not just a promise in
SECURITY.md.

Every outbound socket connection is blocked for the duration of these tests.
`MemoryStore`'s full read/write/search surface, plus JSONL import, must work
end to end against the deterministic, offline `StubEmbedder` used throughout
`test_store.py` — the same embedder stands in here for "after fastembed's
one-time model download has already happened", which is the one documented
exception to the no-network rule and is deliberately not exercised by this
module.
"""

from __future__ import annotations

import socket

import pytest
from test_store import StubEmbedder

from localmem_mcp.store import MemoryStore, import_records


class NetworkAccessBlocked(AssertionError):
    """Raised in place of a real connection attempt during this module's tests."""


@pytest.fixture(autouse=True)
def block_all_egress(monkeypatch):
    """Make any outbound connection attempt fail loudly instead of silently.

    `socket.socket.connect`/`connect_ex` are the primitive every higher-level
    HTTP client (urllib, requests, httpx, aiohttp) eventually calls through,
    so blocking here catches network access regardless of which library a
    dependency might use to attempt it.
    """

    def _blocked(self, address):
        raise NetworkAccessBlocked(f"blocked outbound connection attempt to {address!r}")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)


def test_full_store_lifecycle_never_touches_the_network(tmp_path):
    with MemoryStore(db_path=tmp_path / "offline.db", embedder=StubEmbedder()) as store:
        memory = store.add("We chose sqlite for storage", tags=["decision"])
        second = store.add("I drink coffee every morning")

        store.update(memory.id, tags=["decision", "confirmed"])
        store.search("what database did we pick?")
        store.list()
        store.recent()
        store.matching(tags=["decision"])
        store.get(memory.id)
        store.count()
        store.contains("I drink coffee every morning")
        list(store.export_records())
        store.delete(second.id)
        store.delete_many(tags=["decision"])
        store.stats()


def test_jsonl_import_never_touches_the_network(tmp_path):
    lines = [
        '{"content": "We chose sqlite for storage", "tags": ["decision"]}',
        '{"content": "I drink coffee every morning"}',
    ]
    with MemoryStore(db_path=tmp_path / "offline-import.db", embedder=StubEmbedder()) as store:
        report = import_records(store, lines)

    assert report.imported == 2
    assert report.errors == []
