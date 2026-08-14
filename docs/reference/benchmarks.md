# Benchmarks

How fast are `add()` and `search()`, and where does the time actually go? These
numbers come from `benchmarks/run.py` in the repository, which anyone can re-run.

!!! info "Absolute numbers are machine-specific"

    The shape — what dominates, and how it grows — holds anywhere. The
    milliseconds don't. Run the harness on your own machine before drawing
    conclusions about your setup.

## Results

Measured on Linux x86_64, CPython 3.11.15, with a stub embedder producing
384-dimension vectors (the same width as the default `BAAI/bge-small-en-v1.5`),
a seeded synthetic corpus of 10–50 word memories, and `limit=5`. 50 queries per
size at 1k and 10k; 10 at 100k, where a single search takes seconds.

| memories | add p50 | add p95 | search p50 | search p95 | db size |
| --- | --- | --- | --- | --- | --- |
| 1,000 | 0.144 ms | 0.379 ms | 65.4 ms | 72.8 ms | 2.2 MB |
| 10,000 | 0.150 ms | 0.386 ms | 683.6 ms | 750.9 ms | 21.1 MB |
| 100,000 | 0.152 ms | 0.399 ms | 7,269.5 ms | 10,330.2 ms | 210.0 MB |

Where each search spends its time:

| memories | embedding | SQLite | scoring | scoring share |
| --- | --- | --- | --- | --- |
| 1,000 | 0.02 ms | 4.4 ms | 60.9 ms | 93% |
| 10,000 | 0.03 ms | 59.7 ms | 623.2 ms | 91% |
| 100,000 | 0.03 ms | 526.3 ms | 6,741.9 ms | 93% |

Search latency is linear in corpus size — roughly 70 ms per 1,000 memories on
this machine. Around the point where a tool call starts to feel sluggish:

| memories | search p50 | search p95 |
| --- | --- | --- |
| 1,500 | 103.8 ms | 110.8 ms |
| 2,000 | 135.1 ms | 141.9 ms |
| 3,000 | 203.5 ms | 242.3 ms |

## What this means for you

**Search stays comfortable to about 1,500 memories** and crosses 100 ms there.
Most personal stores live well inside that. At 10k a search is roughly two
thirds of a second, which an agent tool call will feel; at 100k it is seconds,
which is too slow to use interactively.

**Writes are free and stay free.** `add()` is ~0.15 ms whether the store holds
a thousand memories or a hundred thousand — the insert and its FTS5 trigger cost
the same either way. Storing memories liberally costs you nothing.

**Disk is about 2.2 KB per memory**, mostly the 1,536-byte `float32` embedding
plus the FTS5 index. A hundred thousand memories is 210 MB.

**If your store is large and search feels slow, split it.** Per-project
databases via `LOCALMEM_DB_PATH` keep each one small, and they keep unrelated
projects from interfering in results either way. See
[Configuration](../guide/configuration.md).

## What this means for the project

Two findings decide where optimisation effort goes.

**Embedding is not the bottleneck.** A query embed is a rounding error next to
scoring — 0.03 ms of a 683 ms search with the stub. Even the real model, at
roughly 5–20 ms per query, would be under 3% of search time at 10k.

**The pure-Python cosine loop is**, at 91–93% of search time at every size.
[`_cosine()`](https://github.com/OpenAgentHQ/localmem-mcp/blob/main/src/localmem_mcp/core/search.py)
makes three Python-level passes over 384 floats per row, and every stored blob
is materialised into a Python list before that. SQLite — fetching all rows plus
the FTS5 lookup — is the remaining 7–9%.

So the first optimisation worth making is vectorising the scoring loop, which
targets ~92% of the cost while keeping
[`MemoryStore.search()`](api.md#localmem_mcp.store.MemoryStore.search) exact and
its signature unchanged. An approximate-nearest-neighbour index attacks a
different term — the *number* of rows scored — and only starts to pay once
per-row scoring is cheap. See
[Why a full table scan](../guide/how-search-works.md#why-a-full-table-scan).

## Running it yourself

```bash
git clone https://github.com/OpenAgentHQ/localmem-mcp
cd localmem-mcp
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python benchmarks/run.py --sizes 1000,10000,100000
```

The corpus is seeded, so the same `--seed` produces the same memories and
queries on any machine. Useful flags:

| Flag | What it does |
| --- | --- |
| `--sizes 1000,10000` | corpus sizes to measure |
| `--queries 50` | searches timed per size |
| `--real` | use the real fastembed model instead of the stub |
| `--format markdown` | emit a table to paste into an issue (`text`, `markdown`, `json`) |
| `--db-dir DIR` | keep the benchmark databases instead of using a temp dir |
| `--seed 1234` | corpus seed |

The stub embedder is the default so the numbers isolate localmem's own work —
SQLite and the scoring loop — rather than ONNX inference. `--real` adds the
model back for end-to-end figures.

The committed results, including the machine they came from and the caveats
behind each number, live in
[`benchmarks/RESULTS.md`](https://github.com/OpenAgentHQ/localmem-mcp/blob/main/benchmarks/RESULTS.md).
