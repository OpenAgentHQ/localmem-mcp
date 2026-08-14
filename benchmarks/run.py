#!/usr/bin/env python
"""Benchmark harness for :meth:`MemoryStore.add` and :meth:`MemoryStore.search`.

    python benchmarks/run.py --sizes 1000,10000,100000

Search scans every row and scores it in a Python loop. This measures what that
actually costs, and — more importantly — *where* the time goes: embedding,
SQLite, or scoring. Those differ by orders of magnitude, and which one dominates
decides whether an index would buy anything.

By default the harness runs against a deterministic hashing embedder so the
numbers isolate this project's own code (SQLite + the scoring loop) rather than
ONNX inference. Pass ``--real`` for end-to-end figures with the shipped model.

How the breakdown is derived:

* **embed** is measured directly, by a wrapper around the embedder that
  accumulates the time spent inside ``embed()``.
* **sqlite** for ``add()`` is the remainder of the call once embedding is
  subtracted — insert, FTS5 trigger, commit.
* **sqlite** for ``search()`` is measured by a separate probe pass that repeats
  just the row fetch and the FTS5 keyword lookup, so it is an estimate of that
  component rather than a slice of the timed call.
* **score** for ``search()`` is what is left: unpacking vectors, cosine, and the
  sort. Clamped at zero, since the two measured parts come from different passes.
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import shutil
import statistics
import sys
import tempfile
import time
import zlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from localmem_mcp.store import DEFAULT_MODEL, Embedder, MemoryStore  # noqa: E402

DEFAULT_SIZES = (1_000, 10_000, 100_000)
DEFAULT_QUERIES = 50
DEFAULT_DIM = 384  # bge-small-en-v1.5, so the cosine loop does realistic work

#: Word pool for the synthetic corpus. Deliberately mundane engineering prose —
#: the point is realistic length and vocabulary overlap, not meaning.
WORDS = """
sqlite database storage postgres duckdb schema migration index query rows
python rust typescript go typing async runtime dependency package version
embedding vector cosine similarity search ranking hybrid keyword semantic
server client protocol tool docstring endpoint handler parser command flag
decided chose because instead avoided prefer tradeoff simpler faster smaller
review release tag branch merge revert regression benchmark latency memory
user agent session context prompt model local offline privacy machine disk
morning coffee standup notes meeting decision followup owner deadline scope
""".split()

SUBJECTS = [
    "We decided to",
    "The team agreed to",
    "Noted during review:",
    "Reminder:",
    "After the outage we",
    "For the 0.3 release we",
]


def _percentile(values: Sequence[float], pct: float) -> float:
    """Nearest-rank percentile, in milliseconds-friendly plain floats."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, min(len(ordered), int(round(pct / 100.0 * len(ordered)))))
    return ordered[rank - 1]


class HashEmbedder:
    """Deterministic offline embedder with realistic dimensionality.

    Token hashes pick the non-zero positions, so the same text always gets the
    same vector and texts sharing words end up nearer each other. It exists to
    make ``add``/``search`` do the same amount of *our* work as the real model
    would — same vector width, same blob size, same cosine loop — without the
    inference cost getting in the way of the measurement.
    """

    def __init__(self, dim: int = DEFAULT_DIM):
        self.name = f"hash-{dim}"
        self.dim = dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * self.dim
            for token in text.lower().split():
                h = zlib.crc32(token.encode())
                vector[h % self.dim] += 1.0
                vector[(h >> 8) % self.dim] += 0.5
                vector[(h >> 16) % self.dim] += 0.25
            if not any(vector):
                vector[0] = 1e-6
            vectors.append(vector)
        return vectors


class TimedEmbedder:
    """Wraps an embedder and accumulates the time spent inside ``embed()``."""

    def __init__(self, inner: Embedder):
        self._inner = inner
        self.name = inner.name
        self.elapsed = 0.0

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        start = time.perf_counter()
        try:
            return self._inner.embed(texts)
        finally:
            self.elapsed += time.perf_counter() - start

    def take(self) -> float:
        """Return the time accumulated since the last call, and reset."""
        elapsed, self.elapsed = self.elapsed, 0.0
        return elapsed


@dataclass
class Corpus:
    """A deterministically generated set of memories and queries."""

    contents: list[str]
    tags: list[list[str]]
    queries: list[str]


def make_corpus(size: int, queries: int, seed: int) -> Corpus:
    """Build ``size`` memories of 10–50 words plus ``queries`` search phrases."""
    rng = random.Random(seed)
    contents: list[str] = []
    tags: list[list[str]] = []
    tag_pool = ["decision", "bug", "meeting", "idea", "todo", "ops"]

    for _ in range(size):
        length = rng.randint(10, 50)
        body = " ".join(rng.choice(WORDS) for _ in range(length))
        contents.append(f"{rng.choice(SUBJECTS)} {body}")
        tags.append(rng.sample(tag_pool, rng.randint(0, 2)))

    # Queries reuse the corpus vocabulary so keyword hits and cosine both fire —
    # a query that matches nothing would skip work a real query does.
    query_list = [
        " ".join(rng.choice(WORDS) for _ in range(rng.randint(3, 8)))
        for _ in range(queries)
    ]
    return Corpus(contents=contents, tags=tags, queries=query_list)


@dataclass
class Measurement:
    """Per-operation totals plus the embedding slice of each one, in seconds."""

    total: list[float] = field(default_factory=list)
    embed: list[float] = field(default_factory=list)
    sqlite: list[float] = field(default_factory=list)

    def summary(self) -> dict[str, float]:
        rest = [
            max(0.0, t - e - s)
            for t, e, s in zip(self.total, self.embed, self.sqlite or [0.0] * len(self.total))
        ]
        return {
            "p50_ms": _percentile(self.total, 50) * 1000,
            "p95_ms": _percentile(self.total, 95) * 1000,
            "embed_p50_ms": _percentile(self.embed, 50) * 1000,
            "embed_p95_ms": _percentile(self.embed, 95) * 1000,
            "sqlite_p50_ms": _percentile(self.sqlite, 50) * 1000,
            "score_p50_ms": _percentile(rest, 50) * 1000,
            "mean_ms": (statistics.fmean(self.total) if self.total else 0.0) * 1000,
        }


def _db_bytes(db_path: Path) -> int:
    """Size of the database including its WAL sidecars."""
    total = 0
    for path in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        if path.exists():
            total += path.stat().st_size
    return total


def benchmark_size(
    size: int,
    corpus: Corpus,
    db_path: Path,
    embedder: Embedder,
    limit: int,
) -> dict[str, Any]:
    """Fill a fresh store with ``size`` memories, then time searches against it."""
    timed = TimedEmbedder(embedder)
    timed.embed(["warmup"])  # pay any lazy model-load cost before the clock starts
    timed.take()

    adds = Measurement()
    with MemoryStore(db_path=db_path, embedder=timed) as store:
        for content, tags in zip(corpus.contents, corpus.tags):
            start = time.perf_counter()
            store.add(content, tags=tags)
            elapsed = time.perf_counter() - start
            embed_time = timed.take()
            adds.total.append(elapsed)
            adds.embed.append(embed_time)
            adds.sqlite.append(max(0.0, elapsed - embed_time))

        searches = Measurement()
        for query in corpus.queries:
            start = time.perf_counter()
            store.search(query, limit=limit)
            elapsed = time.perf_counter() - start
            searches.embed.append(timed.take())
            searches.total.append(elapsed)

        # Probe pass: the row fetch and FTS5 lookup on their own, so the SQLite
        # share of a search can be told apart from the scoring loop.
        for query in corpus.queries:
            start = time.perf_counter()
            store._conn.execute("SELECT * FROM memories").fetchall()
            store._keyword_hits(query)
            searches.sqlite.append(time.perf_counter() - start)

        store._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        db_size = _db_bytes(db_path)
        stored = store.count()

    return {
        "size": size,
        "stored": stored,
        "db_bytes": db_size,
        "db_bytes_per_memory": db_size / stored if stored else 0.0,
        "add": adds.summary(),
        "search": searches.summary(),
        "queries": len(corpus.queries),
    }


def _fmt_bytes(count: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if count < 1024 or unit == "GB":
            return f"{count:.1f} {unit}"
        count /= 1024
    return f"{count:.1f} GB"


def render_text(results: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    lines = [
        f"embedder: {meta['embedder']}   queries/size: {meta['queries']}   "
        f"limit: {meta['limit']}   seed: {meta['seed']}",
        f"machine:  {meta['machine']}",
        "",
        f"{'size':>8}  {'add p50':>9} {'add p95':>9}  {'  embed':>9} {' sqlite':>9}"
        f"  {'srch p50':>9} {'srch p95':>9}  {'  embed':>9} {' sqlite':>9} {'  score':>9}"
        f"  {'db size':>9}",
    ]
    for row in results:
        add, search = row["add"], row["search"]
        lines.append(
            f"{row['size']:>8}  "
            f"{add['p50_ms']:>9.3f} {add['p95_ms']:>9.3f}  "
            f"{add['embed_p50_ms']:>9.3f} {add['sqlite_p50_ms']:>9.3f}  "
            f"{search['p50_ms']:>9.2f} {search['p95_ms']:>9.2f}  "
            f"{search['embed_p50_ms']:>9.3f} {search['sqlite_p50_ms']:>9.2f} "
            f"{search['score_p50_ms']:>9.2f}  "
            f"{_fmt_bytes(row['db_bytes']):>9}"
        )
    lines.append("")
    lines.append("All times in milliseconds. add columns are per memory; search per query.")
    return "\n".join(lines)


def render_markdown(results: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    lines = [
        f"- embedder: `{meta['embedder']}`, {meta['queries']} queries per size, "
        f"limit {meta['limit']}, seed {meta['seed']}",
        f"- machine: {meta['machine']}",
        "",
        "| memories | add p50 | add p95 | add embed p50 | add sqlite p50 | "
        "search p50 | search p95 | search embed p50 | search sqlite p50 | "
        "search score p50 | db size |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in results:
        add, search = row["add"], row["search"]
        lines.append(
            f"| {row['size']:,} | {add['p50_ms']:.3f} ms | {add['p95_ms']:.3f} ms | "
            f"{add['embed_p50_ms']:.3f} ms | {add['sqlite_p50_ms']:.3f} ms | "
            f"{search['p50_ms']:.1f} ms | {search['p95_ms']:.1f} ms | "
            f"{search['embed_p50_ms']:.3f} ms | {search['sqlite_p50_ms']:.1f} ms | "
            f"{search['score_p50_ms']:.1f} ms | {_fmt_bytes(row['db_bytes'])} |"
        )
    return "\n".join(lines)


def machine_spec() -> str:
    return (
        f"{platform.system()} {platform.machine()}, Python "
        f"{platform.python_version()} ({platform.python_implementation()})"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmarks/run.py",
        description="Measure MemoryStore add() and search() latency at scale.",
    )
    parser.add_argument(
        "--sizes",
        default=",".join(str(s) for s in DEFAULT_SIZES),
        help="comma-separated corpus sizes (default: 1000,10000,100000)",
    )
    parser.add_argument(
        "--queries", type=int, default=DEFAULT_QUERIES, help="searches timed per size"
    )
    parser.add_argument("--limit", type=int, default=5, help="results per search")
    parser.add_argument("--seed", type=int, default=1234, help="corpus seed")
    parser.add_argument(
        "--dim", type=int, default=DEFAULT_DIM, help="stub embedder dimensions"
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help=f"use the real {DEFAULT_MODEL} model instead of the stub embedder",
    )
    parser.add_argument(
        "--format", choices=("text", "markdown", "json"), default="text", help="output format"
    )
    parser.add_argument(
        "--db-dir",
        help="where to put benchmark databases (default: a temp dir, removed afterwards)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    if not sizes:
        print("no sizes given", file=sys.stderr)
        return 2

    if args.real:
        from localmem_mcp.store import FastEmbedEmbedder

        embedder: Embedder = FastEmbedEmbedder()
    else:
        embedder = HashEmbedder(args.dim)

    if args.db_dir:
        db_dir = Path(args.db_dir).expanduser()
    else:
        db_dir = Path(tempfile.mkdtemp("-localmem-bench"))
    db_dir.mkdir(parents=True, exist_ok=True)
    temporary = args.db_dir is None

    results: list[dict[str, Any]] = []
    try:
        for size in sizes:
            corpus = make_corpus(size, args.queries, args.seed)
            db_path = db_dir / f"bench-{size}.db"
            for stale in db_dir.glob(f"bench-{size}.db*"):
                stale.unlink()
            if args.format != "json":
                print(f"running {size} memories...", file=sys.stderr)
            results.append(benchmark_size(size, corpus, db_path, embedder, args.limit))
            if temporary:
                for path in db_dir.glob(f"bench-{size}.db*"):
                    path.unlink()
    finally:
        if temporary:
            shutil.rmtree(db_dir, ignore_errors=True)

    meta = {
        "embedder": embedder.name,
        "queries": args.queries,
        "limit": args.limit,
        "seed": args.seed,
        "machine": machine_spec(),
    }
    if args.format == "json":
        print(json.dumps({"meta": meta, "results": results}, indent=2))
    elif args.format == "markdown":
        print(render_markdown(results, meta))
    else:
        print(render_text(results, meta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
