# Roadmap

Where localmem-mcp is going, and why. This is a statement of direction, not a
set of promises with dates — a weekend project shipped 0.1.0, and everything
below is open for contribution.

**The constraint that shapes all of it:** nothing on this roadmap may introduce
a runtime network call, an API key, or a hosted dependency. Features that would
need one are out of scope no matter how useful. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## Where we are — 0.1.1

Storing, searching, recalling, editing, and deleting memories works end to end.
Memories live in one SQLite file, embeddings are computed on-device, and search
is hybrid (cosine + FTS5 keyword). It ships as an MCP server, a Python library,
and a CLI.

What's missing is everything that turns a working tool into one an organisation
can commit to: you can't get your data back out, there's no evidence it holds up
past a few thousand rows, and nothing proves the privacy claim automatically.

That's the shape of the roadmap.

---

## 0.2 — Own your memories

*Lifecycle and portability. The gap most likely to make someone abandon the
tool.*

Memories can now be created, read, corrected, and pruned. What's left is
portability: if you want your data elsewhere, there's no supported path.

- **`list_memories`** — enumerate and filter without a search query, with
  pagination.
- **JSONL export and import** — the portability guarantee. Your memories should
  be as easy to take somewhere else as they are to delete.
- **Pagination on `search_memory`** — an `offset`, so an agent can page rather
  than re-query.

## 0.3 — Hold up under weight

*Make the scaling story real instead of assumed.*

Search currently scans every row and scores it in Python. That's exact and
genuinely fine at personal scale — but "fine" is an assumption nobody has
measured, and a team sharing a memory store will find its ceiling.

- **A benchmark harness** — store/search latency at 1k, 10k, and 100k memories,
  runnable by anyone. This comes first: it decides whether the rest is needed.
- **A vector index** (likely [sqlite-vec](https://github.com/asg017/sqlite-vec)),
  behind the existing `MemoryStore.search()` signature. The API must not change
  to accommodate the storage strategy.
- **Batch embedding** — `add_many`, so bulk import doesn't pay per-item model
  overhead.
- **Cheaper scoring** — the cosine loop is pure Python; vectorising it may
  remove the need for an index entirely at the scales that matter.

## 0.4 — Many contexts, one tool

*Today every memory lands in one undifferentiated pile.*

Separate databases per project work, but they're a blunt instrument — you lose
cross-project recall entirely. And over months, a memory store accumulates
duplicates and stale facts that quietly degrade search.

- **Namespaces** — partition memories within one database, searchable
  individually or together.
- **Near-duplicate detection** — warn or merge when a new memory closely
  restates an existing one.
- **Importance and decay** — let recency and access frequency influence ranking,
  so a fact stated once two years ago doesn't outrank yesterday's decision.
- **Compaction** — collapse a cluster of related memories into a summary,
  keeping the originals recoverable.

## 0.5 — Trust and operations

*What an organisation asks before it adopts anything.*

The privacy claim is currently a promise backed by readable code. That's a good
start and not enough — it should be enforced by tests and verifiable from the
outside.

- **An automated no-network test** — run the suite with egress blocked and prove
  nothing reaches out. The core claim of the project deserves a test, not just a
  paragraph.
- **Optional encryption at rest** — via SQLCipher or an equivalent, off by
  default. Only worth doing if key handling stays honest; see the
  [privacy model](docs/guide/privacy.md#memories-are-stored-unencrypted).
- **An audit log** — an append-only record of which tool did what, for anyone
  who needs to answer "what did the agent remember, and when".
- **Read-only and append-only modes** — so a shared or archived store can be
  consulted without being mutated.
- **Signed releases** — build provenance attestation and an SBOM, so the
  artifact on PyPI can be traced back to the commit that produced it.
- **`mypy --strict` and a coverage gate** in CI.

## 1.0 — Stability worth depending on

*The point at which breaking things stops being acceptable.*

- **A schema migration framework**, and a guarantee: a release must always open
  a database written by the previous one.
- **A published compatibility policy** covering all four surfaces — MCP tools,
  schema, CLI, and Python API. The definitions already live in
  [RELEASE.md](RELEASE.md).
- **A frozen public API**, with deprecations carried for at least one minor
  release.

---

## Ongoing, not milestone-bound

- **Client recipes** — every MCP client someone actually uses, documented in
  [Connect your client](docs/getting-started/clients.md).
- **Multilingual embeddings** — the default model is English-only. Model choice
  is already configurable; what's missing is guidance and testing.
- **Better agent ergonomics** — the tool docstrings are the real interface for a
  model. Evidence that a rewording improves tool selection is a valuable
  contribution.

## Explicit non-goals

These are settled, and a PR implementing one will be declined regardless of
quality:

- **Cloud sync or a hosted backend.** It would negate the entire premise.
- **Anything requiring an API key.**
- **Becoming an agent framework.** This is a memory tool. Not RAG-over-documents,
  not a chat UI, not an orchestrator.
- **A second datastore.** One SQLite file, one row per memory.

## How to help

Issues tagged [`good first issue`](https://github.com/OpenAgentHQ/localmem-mcp/labels/good%20first%20issue)
are scoped to be completable without deep context.
[`help wanted`](https://github.com/OpenAgentHQ/localmem-mcp/labels/help%20wanted)
marks work that's ready for someone to pick up.

Milestone order reflects priority, not a schedule. If a later item matters more
to you, say so on the issue — that's real signal about what to pull forward.

For anything larger than a bug fix, open an issue before building. It's much
nicer than having a finished PR turned down for scope.
