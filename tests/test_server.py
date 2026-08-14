"""End-to-end tests for the MCP tools, driven through an in-memory client.

These exercise the same path a real MCP client (Claude Code, Cursor, …) takes:
tool discovery, argument validation, and JSON results.
"""

from __future__ import annotations

import pytest
from fastmcp import Client
from test_store import StubEmbedder

from localmem_mcp import server
from localmem_mcp.store import MemoryStore


@pytest.fixture
def mcp_server(tmp_path, monkeypatch):
    store = MemoryStore(db_path=tmp_path / "mcp.db", embedder=StubEmbedder())
    monkeypatch.setattr(server, "_store", store)
    yield server.mcp
    store.close()


async def test_tools_are_exposed(mcp_server):
    async with Client(mcp_server) as client:
        names = {tool.name for tool in await client.list_tools()}

    assert {"store_memory", "search_memory", "recall_memory", "update_memory"} <= names


async def test_store_search_recall_roundtrip(mcp_server):
    async with Client(mcp_server) as client:
        stored = await client.call_tool(
            "store_memory",
            {"content": "We chose sqlite as the database", "tags": ["decision"]},
        )
        memory_id = stored.data["id"]
        assert stored.data["tags"] == ["decision"]

        await client.call_tool("store_memory", {"content": "I drink coffee each morning"})

        found = await client.call_tool(
            "search_memory", {"query": "which database did we pick?", "limit": 2}
        )
        assert found.data["count"] >= 1
        assert "sqlite" in found.data["results"][0]["content"]

        recalled = await client.call_tool("recall_memory", {"memory_id": memory_id})
        assert recalled.data["found"] is True
        assert recalled.data["memories"][0]["content"] == "We chose sqlite as the database"


async def test_recall_without_id_returns_recent(mcp_server):
    async with Client(mcp_server) as client:
        await client.call_tool("store_memory", {"content": "older note about python"})
        await client.call_tool("store_memory", {"content": "newer note about rust"})

        result = await client.call_tool("recall_memory", {"limit": 2})

    contents = [m["content"] for m in result.data["memories"]]
    assert contents == ["newer note about rust", "older note about python"]


async def test_recall_missing_id_reports_not_found(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("recall_memory", {"memory_id": 9999})

    assert result.data["found"] is False
    assert result.data["memories"] == []


async def test_update_memory_corrects_in_place(mcp_server):
    async with Client(mcp_server) as client:
        stored = await client.call_tool(
            "store_memory", {"content": "We chose postgres as the database"}
        )
        memory_id = stored.data["id"]
        created_at = stored.data["created_at"]

        updated = await client.call_tool(
            "update_memory",
            {"memory_id": memory_id, "content": "We chose sqlite as the database"},
        )

        assert updated.data["found"] is True
        assert updated.data["memory"]["content"] == "We chose sqlite as the database"
        assert updated.data["memory"]["created_at"] == created_at

        found = await client.call_tool(
            "search_memory", {"query": "which database did we pick?"}
        )
        assert found.data["results"][0]["id"] == memory_id


async def test_update_memory_tag_only_leaves_content(mcp_server):
    async with Client(mcp_server) as client:
        stored = await client.call_tool(
            "store_memory", {"content": "python typing note", "tags": ["old"]}
        )
        memory_id = stored.data["id"]

        updated = await client.call_tool(
            "update_memory", {"memory_id": memory_id, "tags": ["new"]}
        )

        assert updated.data["found"] is True
        assert updated.data["memory"]["content"] == "python typing note"
        assert updated.data["memory"]["tags"] == ["new"]


async def test_update_memory_missing_id_reports_not_found(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "update_memory", {"memory_id": 9999, "content": "anything"}
        )

    assert result.data["found"] is False
    assert result.data["memory_id"] == 9999
    assert result.data["memory"] is None


async def test_search_with_tag_filter(mcp_server):
    async with Client(mcp_server) as client:
        await client.call_tool(
            "store_memory", {"content": "sqlite database note", "tags": ["work"]}
        )
        await client.call_tool(
            "store_memory", {"content": "sqlite database note", "tags": ["personal"]}
        )

        result = await client.call_tool(
            "search_memory", {"query": "database", "tags": ["personal"]}
        )

    assert result.data["count"] == 1
    assert result.data["results"][0]["tags"] == ["personal"]


async def test_memory_stats_reports_db(mcp_server, tmp_path):
    async with Client(mcp_server) as client:
        await client.call_tool("store_memory", {"content": "a note"})
        stats = await client.call_tool("memory_stats", {})

    assert stats.data["memories"] == 1
    assert stats.data["db_path"] == str(tmp_path / "mcp.db")
