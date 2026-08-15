# sqlite-vec evaluation

Findings for [issue #22](https://github.com/OpenAgentHQ/localmem-mcp/issues/22):
should a vector index sit behind `MemoryStore.search()`?

Produced by `benchmarks/sqlite_vec_eval.py`. Absolute numbers are only
comparable within one machine — re-run the harness locally rather than comparing
against these.

## Answer

**Yes, but not first, and never as a requirement.**

Vectorising the scoring loop ([#23](https://github.com/OpenAgentHQ/localmem-mcp/issues/23))
is the change that pays for itself at the sizes real users have. sqlite-vec is
worth adopting after it, as an *optional* accelerator for stores past ~50k
memories, because it is the only option measured here that gets 100k under
150 ms without holding the whole corpus in process memory.

Two assumptions in the issue turned out to be wrong, and both make sqlite-vec
look better than expected:

- **Recall loss is not a risk in the released version.** `vec0` is brute force.
  It has no ANN index, so its KNN is exact — measured 100% recall@5 and
  identical ranking against the exact scan at every size tested.
- **Install weight is not a risk either.** sqlite-vec is a 176 KB wheel that
  installs in under a second. The numpy that #23 wants is 45 MB.

The real cost is neither of those. It is that **the extension cannot be relied
on to load**, and that **candidate generation changes what a filtered search
can find**. Both are handled below, and both are why this must degrade rather
than depend.

## Machine

| | |
| --- | --- |
| OS / arch | Linux x86_64 (containerised CI-class VM) |
| Python | 3.11.15, CPython — `sqlite3` 3.45.1, extension loading available |
| sqlite-vec | 0.1.9 |
| numpy | 2.4.6 |
| Corpus | synthetic, seed `1234`, 10–50 words per memory, `hash-384` stub embedder |
| Search | `limit=5`, `oversample=8` |

20 queries per size at 1k and 10k; 5 at 100k, where one exact search is seconds.

## Strategies compared

| | what it does |
| --- | --- |
| `exact` | what ships today — fetch every row, score it in a Python loop |
| `numpy` | the same exact scan vectorised, reading blobs from SQLite per query |
| `numpy+` | the same, against a matrix cached in memory between queries |
| `vec0` | sqlite-vec KNN for candidates, then the existing hybrid scoring |

`numpy` is [#23](https://github.com/OpenAgentHQ/localmem-mcp/issues/23) as a
drop-in replacement for the loop. `numpy+` is what a cache would buy, and is not
a like-for-like comparison — it skips the row fetch the other two pay, and holds
the entire corpus resident.

## Latency

Unfiltered, `limit=5`:

| memories | `exact` p50 | `numpy` p50 | `numpy+` p50 | `vec0` p50 | `vec0` p95 |
| --- | --- | --- | --- | --- | --- |
| 1,000 | 43.9 ms | 6.5 ms | 1.9 ms | 5.6 ms | 6.2 ms |
| 10,000 | 466.0 ms | 69.3 ms | 17.4 ms | 20.8 ms | 24.2 ms |
| 100,000 | 4,815.3 ms | 1,313.0 ms | 149.2 ms | 134.6 ms | 191.9 ms |

With a tag filter (`--tag-filter ops`, matching ~17% of the corpus):

| memories | `exact` p50 | `numpy` p50 | `numpy+` p50 | `vec0` p50 |
| --- | --- | --- | --- | --- |
| 1,000 | 12.9 ms | 3.6 ms | 2.8 ms | 3.2 ms |
| 10,000 | 132.8 ms | 35.8 ms | 25.5 ms | 17.9 ms |
| 100,000 | 1,455.1 ms | 400.7 ms | 283.5 ms | 144.2 ms |

Index build, which is also the migration cost for an existing database:

| memories | `vec0` build | `vec0` index on disk | `numpy+` matrix in RAM |
| --- | --- | --- | --- |
| 1,000 | 23 ms | 1.5 MB | 1.5 MB |
| 10,000 | 214 ms | 15.2 MB | 14.6 MB |
| 100,000 | 3,502 ms | 149.6 MB | 146.5 MB |

## What the numbers say

**1. Below 10k, an index is not the answer — vectorising is.** At 10k the
Python loop is 466 ms and a plain vectorised scan is 69 ms, already inside the
budget where a tool call stops feeling sluggish. `vec0` gets to 21 ms, which is
better, but it is the difference between fast and faster, bought with a binary
extension. #23 alone moves the ~100 ms crossover from roughly 1,500 memories to
somewhere north of 15,000, and that covers essentially every personal store.

**2. At 100k, `numpy` alone is not enough, and the reason is I/O, not
arithmetic.** The vectorised scan still takes 1,313 ms at 100k, because it reads
150 MB of blobs out of SQLite on every query. Only the two strategies that avoid
that per-query read — a cached matrix, or the index — get under 200 ms.

**3. That is the actual case for sqlite-vec: it is the only way to be fast at
100k without a 146 MB resident cache.** `numpy+` and `vec0` land within 15 ms of
each other (149 ms vs 135 ms), but `numpy+` pays 146 MB of process memory and a
3.3 s warm-up, and has to be invalidated on every write. `vec0` keeps its index
in the same file, on disk, maintained by SQLite. For a tool whose whole premise
is a single local file, that is the better shape.

**4. With a filter, the index wins outright.** At 100k with a tag filter `vec0`
is 144 ms against `numpy+`'s 284 ms — the KNN prunes before scoring while a
cached matrix scores everything and filters after.

**5. Recall is exact, for now.** 100% recall@5 and identical ordering at every
size, filtered and unfiltered. This is not luck: `vec0` in 0.1.x is brute force
in C, with [ANN tracked as a pre-1.0 goal](https://github.com/asg017/sqlite-vec/issues/25).
So the speedup is a constant factor, not a change of complexity class — and the
day sqlite-vec ships an ANN index, recall becomes a knob this project would have
to measure and defend. Adopting it means pinning to exact KNN deliberately
rather than tracking whatever the extension does next.

## The three risks from the issue, re-examined

### Recall loss — not a risk today, a risk to pin against

Measured, not assumed: 100% at every size. But see finding 5 — this holds
because the released extension is exhaustive. A version bump could change it
silently, so the pin matters more than the current number.

### Install weight — the opposite of what we assumed

```
sqlite-vec   176 KB   0.9 s   cold install, no cache
numpy         45 MB   3.2 s   cold install, no cache
```

sqlite-vec is by far the cheaper of the two optimisations to install, and the
30-second install-to-working goal is untouched either way (the existing
onnxruntime dependency is 58 MB on its own). Wheels are published for macOS
x86_64 and arm64, manylinux x86_64 and aarch64, and Windows amd64 — the whole CI
matrix. There is no musllinux wheel, so Alpine has no binary.

### Complexity — the real cost, and it is not where the issue expected

Not index maintenance, which SQLite handles. Two other things:

**Extension loading is not guaranteed, and cannot be detected at install time.**
Python's `sqlite3` [is not built with loadable-extension support by
default](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.enable_load_extension) —
macOS's system SQLite is the well-known case, where `enable_load_extension`
raises `AttributeError` outright. A user can `pip install sqlite-vec`
successfully and still not be able to load it. So the fallback is not a nicety
for unusual setups; it is the main path on some platforms, and it has to catch
`ImportError`, `AttributeError`, *and* `sqlite3.OperationalError`. The FTS5
`try/except` in `_keyword_hits()` is the right pattern, one level up.

**Candidate generation is not scoring, and the hybrid bonus notices.** Two
memories can outrank the vector top-`limit`: a keyword hit that the FTS5 bonus
promotes, and any row a tag filter leaves behind. Both have to be pulled into
the candidate set explicitly or results silently change. Oversampling is the
lever, and its cost is negligible — but the factor it needs depends on filter
selectivity, which is data-dependent:

| oversample | recall@5 | identical order | queries returning short |
| --- | --- | --- | --- |
| 1 | 99.0% | 95.0% | 5.0% |
| 2 | 99.0% | 95.0% | 5.0% |
| 4 | 100.0% | 100.0% | 0.0% |
| 8 | 100.0% | 100.0% | 0.0% |

10k memories, `--tag-filter ops`. Latency is flat across all four (17–18 ms), so
oversampling is nearly free — but "nearly free and usually right" is exactly the
kind of knob that turns a missing memory into a bug nobody can reproduce. A
sufficiently selective tag will outrun any fixed factor.

## Recommended shape, if this is implemented

1. **Land [#23](https://github.com/OpenAgentHQ/localmem-mcp/issues/23) first.**
   It is most of the win, changes no schema, keeps search exact, and needs no
   binary extension. Re-measure after it lands — the case below is for what is
   left at 100k, not for what #23 already fixes.
2. **Optional dependency, runtime probe, silent fallback.** An extra
   (`pip install "localmem-mcp[vec]"`), loaded through one helper that returns
   `None` on `ImportError` / `AttributeError` / `OperationalError`. `search()`
   uses the index when it loaded and the exact scan when it did not, with no
   difference in results and no error either way.
3. **Index construction, not re-embedding.** The vectors are already in the
   `memories` rows as `float32` blobs, which is exactly what `vec0` stores —
   3.5 s for 100k, one time, no model involved. Build it lazily on first search,
   and drop it whenever `embedding_model` or `dim` changes.
4. **Oversample, and pull keyword hits in explicitly.** Candidates are
   `k = limit * oversample` KNN rows, unioned with the FTS5 hits, then scored by
   the existing hybrid scorer. Scoring semantics do not change; only which rows
   reach it.
5. **Keep the exact scan as the tag-filtered path** unless the filter is
   measured to be unselective, or push the filter into `vec0` metadata columns
   (equality only, which this project's comma-joined multi-valued tags do not
   fit as-is).
6. **Pin the extension version** and re-measure recall on every bump, per
   finding 5.

## Reproducing

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pip install sqlite-vec numpy       # both optional; missing ones skipped
.venv/bin/python benchmarks/sqlite_vec_eval.py --sizes 1000,10000 --queries 20
.venv/bin/python benchmarks/sqlite_vec_eval.py --sizes 100000 --queries 5
.venv/bin/python benchmarks/sqlite_vec_eval.py --sizes 10000 --tag-filter ops --oversample 1
```

The corpus is seeded, so the same `--seed` gives the same memories and queries on
any machine. Strategies whose dependency is missing are reported as unavailable
rather than skipped silently — which also makes the harness a check that the
fallback path is real.
