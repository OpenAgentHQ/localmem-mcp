# Python library

The MCP server is a thin shell over `MemoryStore`, which you can import and use
directly. Same database, same behaviour, no MCP involved.

```bash
pip install localmem-mcp
```

## Basics

```python
from localmem_mcp import MemoryStore

store = MemoryStore()  # ~/.localmem/memories.db

store.add(
    "We chose SQLite over Postgres because it ships in a single file",
    tags=["decision", "architecture"],
    source="design-review",
)

for hit in store.search("what database are we using?"):
    print(f"{hit.score:.3f}  {hit.memory.content}")
```

```
0.821  We chose SQLite over Postgres because it ships in a single file
```

The store is a context manager, which is the tidiest way to use it:

```python
with MemoryStore(db_path="./project.db") as store:
    store.add("Deploys go out on Thursdays", tags=["ops"])
    print(store.count())
```

## Storing

```python
memory = store.add(
    content="Priya prefers async updates over standups",
    tags=["team", "preference"],
    source="1:1 notes",
    metadata={"confidence": 0.9, "person": "Priya"},
)

memory.id          # 7
memory.tags        # ["team", "preference"] — normalized
memory.created_at  # "2026-08-14T11:31:00+00:00"
```

`metadata` is an arbitrary JSON-serializable dict, stored alongside the memory
and returned intact. It isn't searched — use tags for anything you want to
filter on.

Tags are lowercased, trimmed, and de-duplicated in order. A string is accepted
too and split on commas, so `tags="work,urgent"` and `tags=["work", "urgent"]`
are equivalent.

Empty content raises `ValueError`.

## Searching

```python
results = store.search(
    query="deployment schedule",
    limit=10,
    tags=["ops"],       # must carry ALL of these
    min_score=0.3,
    offset=0,           # skip this many ranked results
)

for result in results:
    print(result.score, result.memory.id, result.memory.content)
```

| Argument | Type | Default | Description |
| --- | --- | --- | --- |
| `query` | `str` | *required* | What you're trying to remember, in natural language. |
| `limit` | `int` | `5` | Maximum memories to return. |
| `tags` | `Iterable[str] \| str` | `None` | Only consider memories carrying **all** of these tags. |
| `min_score` | `float` | `0.0` | Drop results scoring below this, on a 0–1 scale. |
| `offset` | `int` | `0` | Skip this many ranked results before applying `limit`. |

Each result is a `SearchResult` wrapping a `Memory` and a `score` — cosine
similarity plus a bounded keyword bonus, on a 0–1 scale. See
[How search works](how-search-works.md).

`offset` is applied after ranking, so `search(q, limit=5, offset=5)` is the
second page of `search(q, limit=5)`. Ranking is deterministic (score
descending, ties broken by id), so pages neither overlap nor skip. Negative
offsets are clamped to `0`, and an offset past the end returns `[]`.

## Reading, updating, and deleting

```python
memory = store.get(7)              # Memory | None
recent = store.recent(limit=10)    # newest first
recent = store.recent(limit=10, tags=["ops"])

updated = store.update(7, content="Priya prefers written updates over standups")
store.update(7, tags=["team", "preference"])  # omit content to skip re-embedding
store.delete(7)                    # True if it existed
removed = store.delete_many(tags=["scratch"])        # int — count removed
removed = store.delete_many(older_than_days=90)
preview = store.matching(tags=["stale"])             # list[Memory] — what a bulk delete would remove
store.count()                      # int
store.stats()                      # {"db_path": …, "memories": …, "embedding_model": …}
```

`update()` corrects a memory in place. Only the fields you pass are changed —
omitting `content` leaves the embedding alone, so retagging is instant. Changing
`content` re-embeds the memory so search finds the correction. `created_at` is
preserved, `updated_at` is refreshed, and a missing id returns `None` rather
than raising.

`delete_many()` bulk-deletes by tag and/or age and requires at least one filter
— an unfiltered call raises `ValueError` so the store can't be wiped by
accident. `matching()` applies the same filters without deleting, so you can
preview what `delete_many()` would remove first.

## Serializing

`Memory` and `SearchResult` are dataclasses with `to_dict()` — the same shape
the MCP tools return:

```python
import json

memories = [m.to_dict() for m in store.recent(limit=100)]
print(json.dumps(memories, indent=2))
```

## Choosing a database and model

```python
store = MemoryStore(
    db_path="./project.db",
    model_name="BAAI/bge-base-en-v1.5",
)
```

With no `db_path`, the same resolution order as everything else applies:
`LOCALMEM_DB_PATH`, then `LOCALMEM_HOME`, then `~/.localmem/memories.db`. See
[Configuration](configuration.md).

## Custom embedders

`MemoryStore` accepts any object with a `name` attribute and an
`embed(texts) -> list[list[float]]` method. That's the `Embedder` protocol:

```python
from localmem_mcp import MemoryStore

class MyEmbedder:
    name = "my-embedder"

    def embed(self, texts):
        return [my_model.encode(t) for t in texts]

store = MemoryStore(db_path="./custom.db", embedder=MyEmbedder())
```

This exists mainly so tests can run offline — the project's own suite uses a
deterministic bag-of-words stub instead of downloading a model. It's also the
extension point if you want a different embedding backend.

!!! warning "Embedders aren't interchangeable mid-database"

    Vectors from different models can't be compared. localmem records the model
    name and dimension per row and scores mismatched dimensions as `0.0`, so
    results degrade rather than mislead — but a database should stick to one
    embedder.

## Threading and processes

The connection is opened with `check_same_thread=False` and writes are guarded
by a lock, so a single `MemoryStore` is safe to share across threads.

Across *processes*, SQLite's WAL mode handles concurrent readers alongside one
writer — a CLI command can read while an MCP server holds the file open. Heavy
concurrent writing from many processes isn't a workload this is built for.

## Performance notes

- **The first embed call is slow** — that's the model loading (and downloading,
  the very first time). It's lazy, so constructing a `MemoryStore` is cheap.
- **Search scans every row.** Exact, no index to maintain, and imperceptible at
  personal scale. See [why](how-search-works.md#why-a-full-table-scan).
- **Embedding dominates.** Both `add()` and `search()` embed one string; the
  SQLite work either side of that is negligible.

## Full API

Every public class and method is documented in the
[Python API reference](../reference/api.md).
