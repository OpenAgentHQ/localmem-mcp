#!/usr/bin/env python
"""Evaluate sqlite-vec as a vector index behind ``MemoryStore.search`` (issue #22).

    python benchmarks/sqlite_vec_eval.py --sizes 1000,10000,100000

The question this answers is not "is sqlite-vec fast" — it is "is an index the
right way to spend this project's complexity budget". So it measures three
strategies for the vector stage of search against the same corpus and the same
queries:

* ``exact``  — what ships today: fetch every row, score it in a Python loop.
* ``numpy``  — the same exact scan, vectorised into one matrix multiply, reading
  the blobs out of SQLite on every query exactly as ``search`` does now. This is
  issue #23, and it is the alternative an index has to beat.
* ``numpy+`` — the same, but against a matrix held in memory between queries. It
  is the ceiling a cache would buy, not a like-for-like comparison, since it
  skips the row fetch the other two pay.
* ``vec0``   — sqlite-vec KNN for candidate generation, then the existing hybrid
  scoring over the returned candidates.

For each it reports p50/p95 query latency, and for the alternatives how often
their top-5 differs from ``exact``. Recall is measured, never assumed: a memory
tool that silently drops a result is worse than a slow one. ``--tag-filter``
repeats the queries with a tag filter, which is where candidate generation is
most likely to come up short — a global KNN can return ``k`` neighbours that the
tag filter then throws away.

The index is built from the embeddings already stored in the ``memories``
table, so index build time here is also the migration cost for an existing
database — no re-embedding is involved.

Everything runs against the deterministic hashing embedder from ``run.py``, so
the numbers isolate scoring and candidate generation rather than ONNX inference.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from run import (  # noqa: E402
    DEFAULT_DIM,
    HashEmbedder,
    _db_bytes,
    _fmt_bytes,
    _percentile,
    machine_spec,
    make_corpus,
)

from localmem_mcp.core.search import KEYWORD_WEIGHT, _cosine  # noqa: E402
from localmem_mcp.core.utils import _row_to_memory, _unpack  # noqa: E402
from localmem_mcp.store import MemoryStore  # noqa: E402

DEFAULT_SIZES = (1_000, 10_000)
DEFAULT_QUERIES = 20
DEFAULT_LIMIT = 5

#: How many candidates the vec0 strategy asks for per requested result. The
#: keyword bonus can promote a memory that vector distance alone would not have
#: put in the top ``limit``, so a KNN of exactly ``limit`` cannot reproduce the
#: current ranking even with a perfectly exact index. Oversampling is the lever
#: that buys agreement back, and measuring what it costs is half the point.
DEFAULT_OVERSAMPLE = 8


def load_sqlite_vec(conn: sqlite3.Connection) -> str | None:
    """Load the sqlite-vec extension into ``conn``. Returns its version, or None.

    Mirrors the fallback the store would need: every way this can fail — package
    missing, ``enable_load_extension`` compiled out of the Python build, no
    binary for this platform — has to degrade to the exact scan rather than
    raise, exactly as FTS5 already degrades to pure vector search.
    """
    try:
        import sqlite_vec
    except ImportError:
        return None
    try:
        conn.enable_load_extension(True)
    except AttributeError:
        # Python built without extension-loading support (some distro and
        # vendor builds compile it out). Nothing to do but fall back.
        return None
    try:
        sqlite_vec.load(conn)
    except sqlite3.OperationalError:
        return None
    finally:
        try:
            conn.enable_load_extension(False)
        except AttributeError:  # pragma: no cover - unreachable if enable worked
            pass
    return str(conn.execute("SELECT vec_version()").fetchone()[0])


def load_numpy() -> Any | None:
    try:
        import numpy
    except ImportError:
        return None
    return numpy


@dataclass
class Strategy:
    """One way of producing the vector stage of a search."""

    name: str
    available: bool
    note: str = ""
    build_seconds: float = 0.0
    index_bytes: int = 0


def build_corpus_db(size: int, queries: int, seed: int, path: Path) -> Any:
    """Populate a store with ``size`` synthetic memories. Returns the corpus."""
    corpus = make_corpus(size, queries, seed)
    store = MemoryStore(db_path=path, embedder=HashEmbedder(DEFAULT_DIM))
    for content, tags in zip(corpus.contents, corpus.tags):
        store.add(content, tags=tags)
    store._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return corpus, store


def build_vec_index(store: MemoryStore, dim: int) -> float:
    """Build a vec0 index from the embeddings already in ``memories``.

    Returns build time in seconds. This is the migration path: vectors are read
    out of the rows that already hold them, so an existing database is indexed,
    not re-embedded.
    """
    conn = store._conn
    start = time.perf_counter()
    conn.execute(
        f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_memories USING vec0(
            memory_id integer primary key,
            embedding float[{dim}] distance_metric=cosine
        )
        """
    )
    rows = conn.execute("SELECT id, embedding FROM memories").fetchall()
    with conn:
        conn.executemany(
            "INSERT INTO vec_memories(memory_id, embedding) VALUES (?, ?)",
            [(row["id"], row["embedding"]) for row in rows],
        )
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return time.perf_counter() - start


def search_exact(store: MemoryStore, query: str, limit: int,
                 tag: str | None) -> list[int]:
    """Today's implementation, straight through the public API."""
    return [r.memory.id for r in store.search(query, limit=limit, tags=tag)]


def _normalized_matrix(np: Any, rows: list[Any]) -> tuple[Any, list[int]]:
    """Stack stored blobs into one unit-normalised (n, dim) float32 matrix."""
    ids = [int(row["id"]) for row in rows]
    matrix = (
        np.frombuffer(b"".join(row["embedding"] for row in rows), dtype="float32")
        .reshape(len(ids), DEFAULT_DIM)
        .copy()
    )
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    matrix /= norms
    return matrix, ids


def search_numpy(store: MemoryStore, np: Any, query: str, limit: int,
                 tag: str | None, matrix: Any = None,
                 ids: list[int] | None = None) -> list[int]:
    """Exact scan, vectorised: one matrix multiply instead of N Python loops.

    With ``matrix``/``ids`` supplied the caller is reusing a cached matrix; with
    them omitted the blobs are read and stacked per query, which is what a
    drop-in replacement for the current loop would actually do.
    """
    allowed: set[int] | None = None
    if matrix is None:
        rows = store._conn.execute("SELECT id, tags, embedding FROM memories").fetchall()
        rows = [row for row in rows if row["embedding"]]
        if tag:
            rows = [row for row in rows if tag in (row["tags"] or "").split(",")]
        if not rows:
            return []
        matrix, ids = _normalized_matrix(np, rows)
    elif tag:
        # A cached matrix covers every row, so the tag filter has to be applied
        # while scoring rather than by narrowing what gets scanned.
        allowed = set(_tag_ids(store, tag))

    query_vector = np.asarray(store.embedder.embed([query])[0], dtype="float32")
    norm = float(np.linalg.norm(query_vector))
    if norm == 0.0:
        return []
    similarities = matrix @ (query_vector / norm)
    keyword_hits = store._keyword_hits(query)

    scored = []
    for memory_id, similarity in zip(ids, similarities.tolist()):
        if allowed is not None and memory_id not in allowed:
            continue
        score = min(1.0, similarity + KEYWORD_WEIGHT * keyword_hits.get(memory_id, 0.0))
        scored.append((score, memory_id))
    scored.sort(key=lambda pair: (-pair[0], -pair[1]))
    return [memory_id for _, memory_id in scored[:limit]]


def search_vec0(store: MemoryStore, query: str, limit: int, oversample: int,
                tag: str | None) -> list[int]:
    """KNN candidate generation, then the existing hybrid scoring over candidates.

    Scoring semantics are untouched — cosine plus the bounded keyword bonus, on
    the same 0-1 scale. What changes is only *which* rows get scored.
    """
    conn = store._conn
    query_vector = store.embedder.embed([query])[0]
    keyword_hits = store._keyword_hits(query)

    k = max(limit, limit * oversample)
    candidates = conn.execute(
        """
        SELECT memory_id FROM vec_memories
        WHERE embedding MATCH ? AND k = ?
        ORDER BY distance
        """,
        (_as_blob(query_vector), k),
    ).fetchall()
    candidate_ids = {int(row[0]) for row in candidates}
    # A keyword-only hit is not in the KNN result but can still outrank one, so
    # it has to be pulled in explicitly or the bonus stops meaning anything.
    candidate_ids |= set(keyword_hits)
    if not candidate_ids:
        return []

    placeholders = ",".join("?" * len(candidate_ids))
    rows = conn.execute(
        f"SELECT * FROM memories WHERE id IN ({placeholders})", tuple(candidate_ids)
    ).fetchall()

    scored = []
    for row in rows:
        memory = _row_to_memory(row)
        # The tag filter can only be applied after candidate generation: vec0
        # metadata columns accept equality, and this project's tags are a
        # multi-valued comma-joined string. So the filter shrinks an already
        # truncated candidate set — the under-fill this harness counts.
        if tag and tag not in memory.tags:
            continue
        similarity = _cosine(query_vector, _unpack(row["embedding"])) if row["embedding"] else 0.0
        score = min(1.0, similarity + KEYWORD_WEIGHT * keyword_hits.get(memory.id, 0.0))
        scored.append((score, memory.id))
    scored.sort(key=lambda pair: (-pair[0], -pair[1]))
    return [memory_id for _, memory_id in scored[:limit]]


def _as_blob(vector: list[float]) -> bytes:
    import struct

    return struct.pack(f"{len(vector)}f", *vector)


def _agreement(baseline: list[list[int]], candidate: list[list[int]]) -> dict[str, float]:
    """How closely ``candidate``'s rankings match the exact scan's."""
    exact_matches = 0
    recalled = 0
    total = 0
    underfilled = 0
    for want, got in zip(baseline, candidate):
        if want == got:
            exact_matches += 1
        recalled += len(set(want) & set(got))
        total += len(want)
        if len(got) < len(want):
            underfilled += 1
    queries = max(1, len(baseline))
    return {
        "identical_order_pct": 100.0 * exact_matches / queries,
        "recall_pct": 100.0 * recalled / max(1, total),
        "underfilled_pct": 100.0 * underfilled / queries,
    }


def evaluate_size(size: int, queries: int, seed: int, limit: int,
                  oversample: int, tag: str | None) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "eval.db"
        corpus, store = build_corpus_db(size, queries, seed, path)
        base_bytes = _db_bytes(path)

        np = load_numpy()
        vec_version = load_sqlite_vec(store._conn)

        strategies: dict[str, Strategy] = {
            "exact": Strategy("exact", True),
            "numpy": Strategy("numpy", np is not None,
                              "" if np else "numpy not installed"),
            "numpy+": Strategy("numpy+", np is not None,
                               "cached matrix" if np else "numpy not installed"),
            "vec0": Strategy("vec0", vec_version is not None,
                             f"sqlite-vec {vec_version}" if vec_version
                             else "sqlite-vec unavailable"),
        }

        matrix = ids = None
        if strategies["numpy+"].available:
            start = time.perf_counter()
            rows = store._conn.execute("SELECT id, embedding FROM memories").fetchall()
            matrix, ids = _normalized_matrix(np, rows)
            strategies["numpy+"].build_seconds = time.perf_counter() - start
            strategies["numpy+"].index_bytes = matrix.nbytes

        if strategies["vec0"].available:
            strategies["vec0"].build_seconds = build_vec_index(store, DEFAULT_DIM)
            strategies["vec0"].index_bytes = _db_bytes(path) - base_bytes

        timings: dict[str, list[float]] = {name: [] for name in strategies}
        rankings: dict[str, list[list[int]]] = {name: [] for name in strategies}

        for query in corpus.queries:
            for name, strategy in strategies.items():
                if not strategy.available:
                    continue
                start = time.perf_counter()
                if name == "exact":
                    result = search_exact(store, query, limit, tag)
                elif name == "numpy":
                    result = search_numpy(store, np, query, limit, tag)
                elif name == "numpy+":
                    result = search_numpy(store, np, query, limit, tag,
                                          matrix=matrix, ids=ids)
                else:
                    result = search_vec0(store, query, limit, oversample, tag)
                timings[name].append(time.perf_counter() - start)
                rankings[name].append(result)

        report: dict[str, Any] = {"size": size, "db_bytes": base_bytes, "strategies": {}}
        for name, strategy in strategies.items():
            if not strategy.available:
                report["strategies"][name] = {"available": False, "note": strategy.note}
                continue
            entry = {
                "available": True,
                "note": strategy.note,
                "p50_ms": _percentile(timings[name], 50) * 1000,
                "p95_ms": _percentile(timings[name], 95) * 1000,
                "mean_ms": statistics.fmean(timings[name]) * 1000,
                "build_ms": strategy.build_seconds * 1000,
                "index_bytes": strategy.index_bytes,
            }
            if name != "exact":
                entry.update(_agreement(rankings["exact"], rankings[name]))
            report["strategies"][name] = entry
        return report


def _tag_ids(store: MemoryStore, tag: str) -> list[int]:
    """Ids carrying ``tag``, matched on the comma-joined tag string."""
    rows = store._conn.execute("SELECT id, tags FROM memories").fetchall()
    return [int(row["id"]) for row in rows if tag in (row["tags"] or "").split(",")]


def render_text(reports: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    lines = [
        "sqlite-vec evaluation (issue #22)",
        f"  machine:   {meta['machine']}",
        f"  python:    {meta['python']}",
        f"  sqlite:    {meta['sqlite']}",
        f"  queries:   {meta['queries']} per size, limit={meta['limit']}, "
        f"oversample={meta['oversample']}",
        f"  tag filter: {meta['tag_filter'] or 'none'}",
        "",
    ]
    for report in reports:
        lines.append(f"{report['size']:,} memories  (db {_fmt_bytes(report['db_bytes'])})")
        header = (
            f"  {'strategy':<8} {'p50':>10} {'p95':>10} {'build':>10} "
            f"{'index':>10} {'recall@5':>9} {'same order':>11} {'short':>7}"
        )
        lines.append(header)
        for name, entry in report["strategies"].items():
            if not entry["available"]:
                lines.append(f"  {name:<8} unavailable — {entry['note']}")
                continue
            recall = entry.get("recall_pct")
            order = entry.get("identical_order_pct")
            short = entry.get("underfilled_pct")
            recall_cell = "—" if recall is None else f"{recall:.1f}%"
            order_cell = "—" if order is None else f"{order:.1f}%"
            short_cell = "—" if short is None else f"{short:.1f}%"
            lines.append(
                f"  {name:<8} {entry['p50_ms']:>9.2f}ms {entry['p95_ms']:>9.2f}ms "
                f"{entry['build_ms']:>9.0f}ms {_fmt_bytes(entry['index_bytes']):>10} "
                f"{recall_cell:>9} {order_cell:>11} {short_cell:>7}"
            )
        lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate sqlite-vec against the exact scan and a vectorised scan."
    )
    parser.add_argument(
        "--sizes",
        default=",".join(str(size) for size in DEFAULT_SIZES),
        help="comma-separated corpus sizes (default: 1000,10000)",
    )
    parser.add_argument("--queries", type=int, default=DEFAULT_QUERIES,
                        help="queries per size (default: 20)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help="results per query (default: 5)")
    parser.add_argument("--oversample", type=int, default=DEFAULT_OVERSAMPLE,
                        help="KNN candidates per requested result (default: 8)")
    parser.add_argument(
        "--tag-filter",
        metavar="TAG",
        default=None,
        help="repeat every query with this tag filter (corpus tags: decision, "
        "bug, meeting, idea, todo, ops)",
    )
    parser.add_argument("--seed", type=int, default=1234, help="corpus seed")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sizes = [int(part) for part in args.sizes.split(",") if part.strip()]

    reports = [
        evaluate_size(size, args.queries, args.seed, args.limit, args.oversample,
                      args.tag_filter)
        for size in sizes
    ]
    meta = {
        "machine": machine_spec(),
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "queries": args.queries,
        "limit": args.limit,
        "oversample": args.oversample,
        "tag_filter": args.tag_filter,
        "seed": args.seed,
    }
    if args.format == "json":
        print(json.dumps({"meta": meta, "results": reports}, indent=2))
    else:
        print(render_text(reports, meta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
