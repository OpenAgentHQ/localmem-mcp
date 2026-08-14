# Changelog

All notable changes to localmem-mcp are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
See [RELEASE.md](RELEASE.md) for what counts as a breaking change here, and how
releases are cut.

## [Unreleased]

### Added

**CLI**

- `export` — write memories to stdout as JSONL, one object per line, oldest
  first. `--tag` filters conjunctively. Embeddings are excluded by default,
  since a vector only means something on a machine running the same model;
  `--with-embeddings` includes them along with `embedding_model` and `dim`.
- `import` — read JSONL from a file or stdin and store each memory. Memories are
  re-embedded rather than trusting vectors in the file, because a vector from
  the wrong model isn't detectably wrong — search just stops matching. Original
  `created_at` is preserved. Malformed lines are reported on stderr with their
  line number and skipped, so a large import doesn't die on one bad record; the
  exit status is `1` if any line failed. Records whose content already exists
  are skipped unless `--allow-duplicates` is passed, so importing the same file
  twice doesn't double the store, and `--dry-run` reports what would be stored
  without writing.

**Python library**

- `MemoryStore.export_records()` — stream every memory as a plain dict, with the
  same tag filter and optional embeddings as the CLI.
- `import_records()` — read an iterable of JSONL lines into a store, returning
  an `ImportReport` with the counts and per-line errors. Supports `dry_run` and
  `allow_duplicates`.
- `MemoryStore.contains()` — whether a memory with exactly this content is
  already stored; the duplicate check the import path uses.
- `MemoryStore.add()` takes an optional `created_at`, so a restored memory keeps
  the day it was first recorded.

**Search**

- `offset` on `MemoryStore.search()` and the `search_memory` MCP tool, applied
  after ranking, so `limit=5, offset=5` returns results 6–10 without re-running
  a search and discarding the first page. Ranking is deterministic, so pages
  neither overlap nor skip. Negative offsets are clamped to `0`; an offset past
  the end returns no results rather than an error. `search_memory` now also
  echoes the `offset` it used.

## [0.1.1] — 2026-08-14

### Added

**MCP server**

- `update_memory` — correct an existing memory in place. Changing `content`
  re-embeds the memory so search finds the correction; a tag- or source-only
  update leaves the vector alone. `created_at` is preserved, `updated_at`
  refreshed, and a missing id returns `found: false` rather than raising.
- `forget_memory` — permanently delete one memory by id. A missing id returns
  `found: false` rather than raising.
- `forget_memories` — permanently delete memories by tag and/or age, returning
  the count removed. Requires at least one filter; an unfiltered call is
  rejected so the store can't be wiped by accident.

**Python library**

- `MemoryStore.update()` — edit `content`, `tags`, or `source` on an existing
  memory, re-embedding only when the content changes. Returns the corrected
  `Memory`, or `None` for a missing id.
- `MemoryStore.delete_many()` — bulk-delete memories by tag and/or age,
  returning the number removed. Requires at least one filter so an unfiltered
  call can't wipe the store. `MemoryStore.matching()` previews what a bulk
  delete would remove without deleting.

**CLI**

- `forget` — delete a memory by id (`forget 7`), or bulk-delete by tag and/or
  age (`forget --tag stale`, `forget --older-than 90d`). Bulk deletes preview
  what will be removed and prompt for confirmation, with `--yes` to skip.

## [0.1.0] — 2026-08-14

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
