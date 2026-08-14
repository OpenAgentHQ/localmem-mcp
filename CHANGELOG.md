# Changelog

All notable changes to localmem-mcp are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
See [RELEASE.md](RELEASE.md) for what counts as a breaking change here, and how
releases are cut.

## [Unreleased]

### Added

**MCP server**

- `list_memories` — enumerate memories with conjunctive tag filtering,
  pagination, and newest/oldest ordering. Uses database queries only and does
  not perform embedding or similarity scoring.

**Python library**

- `MemoryStore.list()` — list memories with SQL-side tag filtering,
  pagination, total counts, and newest/oldest ordering without loading the
  embedding model.

**CLI**

- `list` — browse memories by tag with pagination and newest/oldest ordering.
  Supports `--json` for machine-readable output.

- `offset` on `MemoryStore.search()` and the `search_memory` MCP tool, applied
  after ranking, so `limit=5, offset=5` returns results 6–10 without re-running
  a search and discarding the first page. Ranking is deterministic, so pages
  neither overlap nor skip. Negative offsets are clamped to `0`; an offset past
  the end returns no results rather than an error. `search_memory` now also
  echoes the `offset` it used.

## [0.1.1] — 2026-08-14
First release.

### Added

**MCP server**

- `store_memory` — embed and persist a memory, with optional tags and source.
  Returns the stored record including the id needed to recall it directly.
- `search_memory` — semantic search over stored memories, with `limit`,
  conjunctive tag filtering, and a `min_score` floor.
- `recall_memory` — read one memory by id, or the most recent N when no id is
  given. A missing id returns `found: false` rather than raising, so an agent
  can recover without a tool error.
- `memory_stats` — database path, memory count, and the active embedding model.
- Runs over stdio via FastMCP, so it works with Claude Code, Claude Desktop,
  Cursor, Zed, Windsurf, and any other MCP client.

**Storage**

- SQLite backend. Text, tags, JSON metadata, and the embedding live on one row —
  no separate vector store to keep in sync.
- Embeddings stored as `float32` blobs, with the model name and dimension
  recorded per row so a future migration can tell which rows are affected.
- FTS5 index over content and tags, kept current by insert/update/delete
  triggers.
- WAL journal mode, so a CLI command can read while a server holds the database
  open.

**Search**

- Hybrid ranking: cosine similarity across every row, plus a bounded additive
  bonus for FTS5 keyword hits. Additive rather than a weighted average, so
  scores stay on the 0–1 cosine scale and `min_score` means the same thing for
  every query.
- Query text is sanitized before reaching FTS5, so raw operators (`AND`, `"`,
  `*`, `:`) can't error or silently change the query's meaning.
- Falls back to pure vector search when SQLite is built without FTS5.

**Embeddings**

- On-device via [fastembed](https://github.com/qdrant/fastembed), defaulting to
  `BAAI/bge-small-en-v1.5` (384 dimensions).
- Model loads lazily on first use rather than at import, so clients that spawn
  the server eagerly don't stall on the initial download.
- `Embedder` protocol — any object with `.name` and `.embed(texts)` can be
  supplied via `MemoryStore(embedder=...)`.

**Python library**

- `MemoryStore` with `add`, `search`, `get`, `recent`, `delete`, `count`,
  `stats`, and `close`. Usable as a context manager.
- `Memory` and `SearchResult` dataclasses with `to_dict()`.

**Command line**

- `localmem-mcp` runs the MCP server; `add`, `search`, `recall`, and `stats`
  subcommands operate on the same database from a terminal.
- `--json` on every subcommand for scripting.
- `--db` and `--model` work either before or after the subcommand.

**Configuration**

- `LOCALMEM_DB_PATH`, then `LOCALMEM_HOME`, then `~/.localmem/memories.db`.
- `LOCALMEM_MODEL` selects any fastembed-supported model.

**Project**

- Documentation site at <https://openagenthq.github.io/localmem-mcp/>, with a
  generated API reference.
- CI across Python 3.10–3.13 on Linux, macOS, and Windows, including a job that
  runs against real fastembed embeddings.
- Release to PyPI via Trusted Publishing (OIDC), with no tokens or secrets.

### Privacy

- No network calls at runtime beyond fastembed's one-time model download, and no
  API keys anywhere in the project.

[Unreleased]: https://github.com/OpenAgentHQ/localmem-mcp/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/OpenAgentHQ/localmem-mcp/releases/tag/v0.1.1
[0.1.0]: https://github.com/OpenAgentHQ/localmem-mcp/releases/tag/v0.1.0
