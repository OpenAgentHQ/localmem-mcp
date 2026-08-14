# MCP tools

localmem-mcp exposes five tools. Four are the core loop — store, search,
recall, update — and one reports on the database itself.

Tool descriptions are written for the model, not for you: each docstring says
when to reach for the tool *and when not to*. That's why `recall_memory`
explicitly points at `search_memory` for meaning-based lookup.

---

## `store_memory`

Save something worth remembering across sessions.

```python
store_memory(
    content: str,
    tags: list[str] | None = None,
    source: str | None = None,
) -> dict
```

| Argument | Type | Default | Description |
| --- | --- | --- | --- |
| `content` | `str` | *required* | The memory itself, written so it makes sense on its own later. |
| `tags` | `list[str]` | `None` | Labels for filtering, e.g. `["project-x", "preference"]`. |
| `source` | `str` | `None` | Where it came from — `"conversation"`, a file path, a URL. |

**Returns** the stored memory, including the `id` needed to recall it directly:

```json
{
  "id": 1,
  "content": "We chose SQLite over Postgres because it ships in a single file",
  "tags": ["decision", "architecture"],
  "source": "conversation",
  "metadata": {},
  "created_at": "2026-08-14T11:31:00+00:00",
  "updated_at": "2026-08-14T11:31:00+00:00"
}
```

!!! note "Tags are normalized"

    Tags are lowercased, trimmed, and de-duplicated while preserving order, so
    `["Decision", " decision ", "Architecture"]` is stored as
    `["decision", "architecture"]`.

Empty or whitespace-only content raises an error — that's a caller bug, not a
recoverable state.

---

## `search_memory`

Find memories by meaning.

```python
search_memory(
    query: str,
    limit: int = 5,
    tags: list[str] | None = None,
    min_score: float = 0.0,
) -> dict
```

| Argument | Type | Default | Description |
| --- | --- | --- | --- |
| `query` | `str` | *required* | What you're trying to remember, in natural language. |
| `limit` | `int` | `5` | Maximum memories to return. |
| `tags` | `list[str]` | `None` | Only consider memories carrying **all** of these tags. |
| `min_score` | `float` | `0.0` | Drop results scoring below this, on a 0–1 scale. |

**Returns** matches ranked by similarity, highest first:

```json
{
  "query": "what database are we using?",
  "count": 1,
  "results": [
    {
      "id": 1,
      "content": "We chose SQLite over Postgres because it ships in a single file",
      "tags": ["decision", "architecture"],
      "source": "conversation",
      "metadata": {},
      "created_at": "2026-08-14T11:31:00+00:00",
      "updated_at": "2026-08-14T11:31:00+00:00",
      "score": 0.8213
    }
  ]
}
```

Scores are cosine similarity with a bounded keyword bonus, so they stay on a
0–1 scale — see [How search works](how-search-works.md). A blank query returns
no results rather than everything.

!!! tip "Choosing a `min_score`"

    Don't filter at all to start. If you get noise, `0.3`–`0.5` is a reasonable
    floor for "actually related". Thresholds are model-dependent, so tune
    against your own data rather than trusting a number from a doc.

Tag filtering is **conjunctive** — `tags=["work", "urgent"]` matches only
memories carrying both.

---

## `recall_memory`

Re-read a specific memory by id, or catch up on the most recent ones.

```python
recall_memory(
    memory_id: int | None = None,
    limit: int = 5,
) -> dict
```

| Argument | Type | Default | Description |
| --- | --- | --- | --- |
| `memory_id` | `int` | `None` | The id of a single memory to read back. Omit for recent ones. |
| `limit` | `int` | `5` | How many recent memories to return when `memory_id` is omitted. |

Two modes:

=== "By id"

    ```json
    { "found": true, "memory_id": 1, "memories": [ { "id": 1, "…": "…" } ] }
    ```

    A missing id returns `found: false` with an empty list rather than raising,
    so the agent can recover without a tool error.

    ```json
    { "found": false, "memory_id": 9999, "memories": [] }
    ```

=== "Most recent"

    ```json
    { "found": true, "count": 2, "memories": [ { "…": "…" }, { "…": "…" } ] }
    ```

    Newest first.

!!! info "This is not a search tool"

    `recall_memory` is for when you already know which memory you want — from a
    previous `store_memory` or `search_memory` call — or when you want a
    chronological catch-up. To find memories by meaning, use
    [`search_memory`](#search_memory).

---

## `update_memory`

Correct an existing memory in place.

```python
update_memory(
    memory_id: int,
    content: str | None = None,
    tags: list[str] | None = None,
    source: str | None = None,
) -> dict
```

| Argument | Type | Default | Description |
| --- | --- | --- | --- |
| `memory_id` | `int` | *required* | The id of the memory to correct. |
| `content` | `str` | `None` | The corrected text. When provided, the memory is re-embedded so search finds the correction. |
| `tags` | `list[str]` | `None` | Replacement tags. Omit to keep the current ones. |
| `source` | `str` | `None` | Replacement source. Omit to keep the current one. |

Only the arguments you pass are changed — a tag- or source-only call never
re-embeds, so it's instant. `created_at` is preserved; `updated_at` is
refreshed.

**Returns** the corrected memory, or `found: false` if the id doesn't exist:

```json
{ "found": true, "memory_id": 1, "memory": { "id": 1, "content": "…", "…": "…" } }
```

```json
{ "found": false, "memory_id": 9999, "memory": null }
```

!!! warning "This corrects, it doesn't add"

    Use `update_memory` when a stored memory is *wrong* — a misremembered fact,
    a misspelled name, a decision that has since changed. Editing the original
    record keeps one authoritative version instead of leaving the wrong one in
    search results. For something genuinely new, use
    [`store_memory`](#store_memory).

---

## `memory_stats`

Report where memories are stored, how many there are, and which model is in use.

```python
memory_stats() -> dict
```

```json
{
  "db_path": "/Users/you/.localmem/memories.db",
  "memories": 42,
  "embedding_model": "BAAI/bge-small-en-v1.5"
}
```

Useful for the agent to orient itself, and the first thing to check when
memories seem to be missing — usually the answer is that a different database is
configured than the one you expected.

---

## Typical flow

```mermaid
flowchart LR
    A[User says something<br/>worth keeping] --> B[store_memory]
    B --> C[(SQLite)]
    D[New session,<br/>related question] --> E[search_memory]
    E --> C
    C --> F{Good match?}
    F -->|Yes| G[Answer with context]
    F -->|Need the full record| H[recall_memory by id]
    H --> C
    F -->|Wrong or stale| I[update_memory]
    I --> C
```

## Writing memories that stay useful

The tools work regardless, but a memory is only as good as its content:

- **Self-contained beats terse.** "Use the staging bucket" means nothing in six
  months. "Deploy artifacts go to the `acme-staging` S3 bucket, not `acme-prod`"
  still works.
- **Store decisions with their reasoning.** The *why* is what stops the same
  debate happening twice.
- **Durable, not transient.** Preferences, architecture choices, constraints,
  people's names — not "the build is running".
- **Tag by context**, so unrelated projects don't pollute each other's results.
