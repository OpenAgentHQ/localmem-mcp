# Contributing

Thanks for looking! localmem-mcp is small on purpose, and contributions that
keep it small are the most welcome kind.

By participating, you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## The one rule

**Nothing leaves the user's machine.** No telemetry, no hosted services, no API
keys, no update pings. The only network call in the whole project is fastembed's
one-time model download. A PR that breaks this won't be merged, however good it
is otherwise.

Beyond that: this is a memory tool, not an agent framework. Features that make
storing and recalling memories better are in scope; features that turn it into
something else are not. If you're unsure, open an issue before building — it's
much nicer than having a finished PR turned down.

## Setup

```bash
git clone https://github.com/OpenAgentHQ/localmem-mcp
cd localmem-mcp
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
```

Requires Python 3.10+. On Windows the venv binaries live in `.venv\Scripts\`.

The suite runs offline in about a second, because it uses a deterministic stub
embedder instead of the real model. To exercise the real fastembed path (the
first run downloads ~90 MB):

```bash
LOCALMEM_TEST_FASTEMBED=1 .venv/bin/python -m pytest -q
```

## How the code is laid out

```
src/localmem_mcp/
  store.py    MemoryStore — SQLite schema, embeddings, hybrid search. The core;
              everything else is a thin shell over it.
  server.py   FastMCP server. Tool docstrings are the agent-facing UX — they
              matter as much as the code.
  cli.py      argparse entry point. `localmem-mcp` with no args runs the server.
tests/
  test_store.py   store behaviour, against a deterministic stub embedder
  test_server.py  MCP tools end-to-end via fastmcp's in-memory Client
```

A few things that will save you time:

- **Memories are one row.** Text, tags, metadata, and the embedding (a `float32`
  blob) all live on the same row in `memories`. There's no separate vector store
  to keep in sync.
- **Search is hybrid.** Cosine similarity over every row, plus a bounded bonus
  for FTS5 keyword hits, so paraphrases and exact terms both land. Scores stay
  on the 0–1 cosine scale so `min_score` means something.
- **The embedder is injectable.** `MemoryStore(embedder=...)` takes anything with
  `.name` and `.embed(texts)`. That's how the tests stay offline.
- **The model loads lazily**, on first embed rather than at import, so MCP
  clients that spawn the server eagerly don't stall.

## Making a change

1. Branch off `main`.
2. Make the change, with a test.
3. Run `pytest -q`, `mypy --strict src/localmem_mcp`, and `ruff check .`.
4. Open a PR. The template will ask you a few questions — the "things reviewers
   should know" section is the important part.

CI runs on every PR: ruff, mypy strict type checking, the test suite (with coverage gating) across Python 3.10–3.13 on Linux,
macOS, and Windows, a job that runs everything against real fastembed
embeddings, and a packaging check. All of it must be green to merge.

Some changes need extra care, and the PR template asks about each:

- **MCP tool signatures and docstrings** are read by models to decide when to
  call a tool. A wording change is a behaviour change — quote the before/after.
- **Schema changes** need a migration story. People have real memories in these
  files, and losing them is unforgivable in a memory tool.
- **Ranking changes** are rarely free. Say what got better and what got worse.
- **New dependencies** cost install time, and install-to-working under 30
  seconds is a project goal. Justify the weight.

## Testing

Keep new tests offline — use `StubEmbedder` from `tests/test_store.py`, a small
bag-of-words vectorizer that's deterministic and needs no model. It's built so
"sqlite" scores nearer "database" than "coffee", which is enough structure to
assert real ranking behaviour.

Anything that genuinely needs the real model goes behind the
`LOCALMEM_TEST_FASTEMBED` flag, like `test_fastembed_roundtrip` does. CI runs
that job for you on every PR.

For MCP-level tests, drive the tools through `fastmcp.Client(server)` as
`tests/test_server.py` does — that's the same path a real client takes, so it
catches schema and serialization problems that calling the functions directly
would miss.

## Type checking and Coverage

### Type Checking

Run `mypy --strict src/localmem_mcp` before opening a PR. All code in `src/localmem_mcp` must pass strict mode without blanket suppressions. Strict type checking is enforced in CI via the `type-check` job.

### Coverage

Run tests with coverage locally:

```bash
.venv/bin/python -m pytest --cov=localmem_mcp --cov-report=term-missing
```

The codebase maintains a coverage floor (currently **90%**, configured via `[tool.coverage.report] fail_under` in `pyproject.toml`). CI will fail if coverage falls below this floor. The floor serves as a regression guard to prevent coverage loss on new changes, rather than an aspirational target to chase.

## Benchmarks

Performance claims in this project should come with numbers. `benchmarks/run.py`
measures `add()` and `search()` at a range of corpus sizes:

```bash
.venv/bin/python benchmarks/run.py --sizes 1000,10000,100000
```

It generates a deterministic synthetic corpus of memory-length prose (10–50
words), reports **p50 and p95** for both operations, and splits each timing into
embedding, SQLite, and scoring so you can see which one actually dominates. It
also reports database size on disk per tier.

By default it runs against a stub embedder that produces vectors of the same
width as the real model, so the numbers isolate *our* code rather than ONNX
inference. Add `--real` for end-to-end figures with the shipped model.

Useful flags:

| Flag | What it does |
| --- | --- |
| `--sizes 1000,10000` | corpus sizes to measure (default `1000,10000,100000`) |
| `--queries 50` | how many searches to time per size |
| `--real` | use the real fastembed model instead of the stub |
| `--format markdown` | emit a table for pasting into an issue (`text`, `markdown`, `json`) |
| `--db-dir DIR` | keep the benchmark databases instead of using a temp dir |
| `--seed 1234` | corpus seed — same seed, same corpus |

100k with the default 50 queries takes a while, because search at that size is
seconds per query; `--queries 10` is enough for a stable p50 there.

Committed results, with the machine they came from, live in
[`benchmarks/RESULTS.md`](benchmarks/RESULTS.md). If you change anything on the
search path, re-run the harness and update that file in the same PR — including
the machine spec, since absolute numbers are only comparable within one machine.

### Comparing search strategies

`benchmarks/sqlite_vec_eval.py` answers a narrower question: if the scan were
done some other way, what would it cost and what would it change? It runs the
same queries through the current Python loop, a vectorised numpy scan, and
[sqlite-vec](https://github.com/asg017/sqlite-vec) KNN, then reports latency
alongside how far each one's top-5 drifts from the exact scan's.

```bash
.venv/bin/pip install sqlite-vec numpy   # both optional; missing ones are skipped
.venv/bin/python benchmarks/sqlite_vec_eval.py --sizes 1000,10000
.venv/bin/python benchmarks/sqlite_vec_eval.py --sizes 10000 --tag-filter ops
```

| Flag | What it does |
| --- | --- |
| `--sizes 1000,10000` | corpus sizes to measure |
| `--queries 20` | searches to time per size |
| `--limit 5` | results per query, and the `k` recall is measured at |
| `--oversample 8` | KNN candidates fetched per requested result |
| `--tag-filter ops` | repeat every query with a tag filter |
| `--format json` | machine-readable output |

Findings from the run that closed out the sqlite-vec investigation are in
[`benchmarks/SQLITE_VEC.md`](benchmarks/SQLITE_VEC.md). Recall is measured
against the exact scan on every run rather than assumed — for a memory tool, a
dropped result is the agent claiming it was never told something.

## Style

- Type hints throughout, with `from __future__ import annotations` at the top.
- Comments explain *why*, not *what*. Match the density of what's around them.
- `ruff` is the arbiter of formatting; line length is 100.

## Good first contributions

- More MCP client setup recipes for the README (Zed, Windsurf, OpenClaw, …).
- `forget`/prune tooling: delete by tag, by age, or by id.
- Export/import to JSONL, so a memory store is portable and inspectable.
- An `update_memory` tool — the schema already carries `updated_at`.
- Faster scoring — `benchmarks/RESULTS.md` shows the Python cosine loop is over
  90% of a search.
- Docs fixes and typos — genuinely useful, always welcome.

Issues labelled [`good first issue`](https://github.com/OpenAgentHQ/localmem-mcp/labels/good%20first%20issue)
are scoped to be approachable without deep context.

## Reporting bugs

Use the issue template. Include your OS, Python version, `localmem-mcp
--version`, which MCP client you used, and the output of `localmem-mcp stats`.
Please don't paste the contents of your memory database — it's yours, and we
don't want to see it.

For security issues, see [SECURITY.md](SECURITY.md) — report those privately
rather than in a public issue.

## Releasing

Maintainers only: bump `version` in `pyproject.toml`, tag `vX.Y.Z`, and push the
tag. `.github/workflows/release.yml` builds and publishes to PyPI via Trusted
Publishing (OIDC) — there are no tokens or secrets to manage.

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).
