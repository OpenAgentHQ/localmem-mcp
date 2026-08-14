# Benchmark results

Produced by `benchmarks/run.py`. Absolute numbers are only comparable within one
machine — re-run the harness locally rather than comparing against these.

## Machine

| | |
| --- | --- |
| OS / arch | Linux x86_64 (containerised CI-class VM) |
| Python | 3.11.15, CPython |
| localmem-mcp | `main` @ the commit that added this file |
| Embedder | `hash-384` stub — 384-dim vectors, same width as `BAAI/bge-small-en-v1.5` |
| Corpus | synthetic, seed `1234`, 10–50 words per memory |
| Search | `limit=5`, no tag filter |

The stub embedder is the default so the numbers isolate this project's own code
— SQLite and the scoring loop — instead of ONNX inference. See
[Real-model figures](#real-model-figures) below.

## Headline

```bash
python benchmarks/run.py --sizes 1000,10000 --queries 50
python benchmarks/run.py --sizes 100000 --queries 10
```

| memories | add p50 | add p95 | add embed p50 | add sqlite p50 | search p50 | search p95 | search embed p50 | search sqlite p50 | search score p50 | db size |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1,000 | 0.144 ms | 0.379 ms | 0.020 ms | 0.122 ms | 65.4 ms | 72.8 ms | 0.022 ms | 4.4 ms | 60.9 ms | 2.2 MB |
| 10,000 | 0.150 ms | 0.386 ms | 0.020 ms | 0.128 ms | 683.6 ms | 750.9 ms | 0.033 ms | 59.7 ms | 623.2 ms | 21.1 MB |
| 100,000 | 0.152 ms | 0.399 ms | 0.020 ms | 0.130 ms | 7,269.5 ms | 10,330.2 ms | 0.032 ms | 526.3 ms | 6,741.9 ms | 210.0 MB |

50 queries per size at 1k and 10k; 10 at 100k, where a single search is seconds.
`add` columns are per memory, `search` columns per query.

Around the 100 ms mark, at 20 queries per size:

| memories | search p50 | search p95 | search sqlite p50 | search score p50 |
| --- | --- | --- | --- | --- |
| 1,500 | 103.8 ms | 110.8 ms | 8.3 ms | 95.5 ms |
| 2,000 | 135.1 ms | 141.9 ms | 10.7 ms | 124.6 ms |
| 3,000 | 203.5 ms | 242.3 ms | 17.1 ms | 186.4 ms |

## What the numbers say

**1. Search crosses ~100 ms at roughly 1,500 memories.** Not 10k, not 100k —
1,500. Latency is linear in corpus size at about 70 ms per 1,000 memories on this
machine, so 10k is already two thirds of a second and 100k is over seven seconds
per query, with a p95 of ten. The "fast enough at personal scale" claim holds
only for stores of a few hundred memories.

**2. Embedding does not dominate — it is a rounding error.** The stub embed is
0.03 ms of a 683 ms search at 10k. Even the real model, at roughly 5–20 ms per
query embed, would be under 3% of search time at 10k and under 0.3% at 100k.
Query embedding is not the problem at any size worth optimising for.

**3. The pure-Python cosine loop is the bottleneck, by an order of magnitude.**
Scoring is 91–93% of search time at every tier (60.9 of 65.4 ms at 1k; 623 of
684 ms at 10k; 6,742 of 7,270 ms at 100k). SQLite — fetching every row plus the
FTS5 lookup — is the other 7–9%. `_cosine()` runs three Python-level passes over
384 floats per row (dot, and a norm for each side), and `_unpack()` materialises
every stored blob into a Python list first.

Two consequences for the 0.3 work:

- **Vectorising the scoring loop (#23) is the highest-value change and should
  come first.** It targets ~92% of the cost, keeps `MemoryStore.search`'s
  signature and exactness, and adds nothing to the schema. Pre-computing and
  storing each vector's norm is a cheaper sub-step in the same direction, since
  the stored norm never changes.
- **A vector index (#22) is not what the data asks for yet.** An index attacks
  the *number of rows scored*, which only becomes the dominant term once
  per-row scoring is cheap. Measure again after #23: if vectorised scoring puts
  10k comfortably under 100 ms, an index is a 100k-and-beyond feature rather
  than a 0.3 requirement.

**Writes are fine and flat.** `add()` sits at ~0.15 ms p50 / ~0.4 ms p95 with no
growth from 1k to 100k — the insert plus FTS5 trigger cost is constant, as
expected. p95 is ~2.6× p50 across every tier, which is WAL commit jitter, not
size-dependent.

**Disk is ~2.2 KB per memory**, dominated by the 1,536-byte `float32` embedding
plus the FTS5 index. 100k memories is 210 MB — large but unremarkable for a
local file; storage is not a reason to change anything.

## Real-model figures

Not collected here: this environment blocks fastembed's model download, so the
`--real` run could not be made. It costs one extra query embed per search and one
per `add`, so from the breakdown above the expected shape is `add` p50 rising to
roughly the model's per-text embed cost (the SQLite 0.13 ms becomes noise), and
`search` gaining a flat few-to-tens of milliseconds independent of corpus size.
Anyone with the model cached locally can fill this in:

```bash
python benchmarks/run.py --sizes 1000,10000 --queries 50 --real --format markdown
```

## Reproducing

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python benchmarks/run.py --sizes 1000,10000,100000 --format markdown
```

The corpus is seeded, so the same `--seed` gives the same memories and queries
on any machine. See the Benchmarks section of
[CONTRIBUTING.md](../CONTRIBUTING.md) for the full flag list.
