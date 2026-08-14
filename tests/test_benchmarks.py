"""Smoke tests for the benchmark harness.

The harness isn't shipped in the package, so it's loaded from ``benchmarks/``
by path. These run at a tiny size — they check the harness still works, not how
fast anything is.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

BENCH_PATH = Path(__file__).resolve().parent.parent / "benchmarks" / "run.py"


@pytest.fixture(scope="module")
def bench():
    spec = importlib.util.spec_from_file_location("localmem_benchmarks_run", BENCH_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


def test_hash_embedder_is_deterministic_and_shaped(bench):
    embedder = bench.HashEmbedder(dim=32)
    first = embedder.embed(["sqlite storage decision"])
    second = embedder.embed(["sqlite storage decision"])

    assert first == second
    assert len(first[0]) == 32
    # An empty string still gets a non-zero vector, or cosine would be undefined.
    assert any(embedder.embed([""])[0])


def test_corpus_is_seeded_and_within_length_bounds(bench):
    corpus = bench.make_corpus(size=20, queries=3, seed=7)
    again = bench.make_corpus(size=20, queries=3, seed=7)

    assert corpus.contents == again.contents
    assert corpus.queries == again.queries
    assert len(corpus.contents) == len(corpus.tags) == 20
    # Memory-length prose: 10-50 words of body, plus the two- or three-word lead.
    assert all(10 <= len(c.split()) <= 55 for c in corpus.contents)


def test_percentile_picks_by_rank(bench):
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]

    assert bench._percentile(values, 50) == 5.0
    assert bench._percentile(values, 95) == 10.0
    assert bench._percentile([], 50) == 0.0


def test_main_reports_every_size_as_json(bench, tmp_path, capsys):
    exit_code = bench.main(
        [
            "--sizes", "5,10",
            "--queries", "2",
            "--dim", "16",
            "--db-dir", str(tmp_path),
            "--format", "json",
        ]
    )
    assert exit_code == 0

    payload = json.loads(capsys.readouterr().out)
    assert [row["size"] for row in payload["results"]] == [5, 10]
    for row in payload["results"]:
        assert row["stored"] == row["size"]
        assert row["db_bytes"] > 0
        assert row["add"]["p50_ms"] >= 0.0
        # The breakdown has to add up: embedding is a slice of the whole call.
        assert row["add"]["embed_p50_ms"] <= row["add"]["p50_ms"] + 1e-9
        assert row["search"]["embed_p50_ms"] <= row["search"]["p50_ms"] + 1e-9


def test_main_renders_text_and_markdown(bench, tmp_path, capsys):
    for fmt, needle in (("text", "add p50"), ("markdown", "| memories |")):
        assert bench.main(
            ["--sizes", "5", "--queries", "1", "--dim", "16",
             "--db-dir", str(tmp_path), "--format", fmt]
        ) == 0
        assert needle in capsys.readouterr().out
