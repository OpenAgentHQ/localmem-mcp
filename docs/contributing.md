# Contributing

localmem-mcp is small on purpose, and contributions that keep it small are the
most welcome kind. The whole project is about 700 lines — you can read it in one
sitting.

By participating, you agree to the
[Code of Conduct](https://github.com/OpenAgentHQ/localmem-mcp/blob/main/CODE_OF_CONDUCT.md).

## The one rule

!!! danger "Nothing leaves the user's machine"

    No telemetry, no hosted services, no API keys, no update pings. The only
    network call in the whole project is fastembed's one-time model download. A
    PR that breaks this won't be merged, however good it is otherwise.

Beyond that: this is a memory tool, not an agent framework. Features that make
storing and recalling memories better are in scope; features that turn it into
something else are not. If you're unsure, open an issue before building — much
nicer than having a finished PR turned down.

## Setup

```bash
git clone https://github.com/OpenAgentHQ/localmem-mcp
cd localmem-mcp
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
```

Python 3.10+. On Windows the venv binaries live in `.venv\Scripts\`.

The suite runs offline in about a second, because it uses a deterministic stub
embedder instead of the real model. To exercise the real fastembed path (the
first run downloads ~90 MB):

```bash
LOCALMEM_TEST_FASTEMBED=1 .venv/bin/python -m pytest -q
```

## Working on the docs

```bash
.venv/bin/pip install -e ".[docs]"
.venv/bin/mkdocs serve
```

Live-reloads at `http://127.0.0.1:8000`. The API reference is generated from
docstrings by mkdocstrings, so improving a docstring improves the site.

## Where things are

```
src/localmem_mcp/
  store.py    MemoryStore — SQLite schema, embeddings, hybrid search. The core.
  server.py   FastMCP server. Tool docstrings are the agent-facing UX.
  cli.py      argparse entry point. No args = run the server.
tests/
  test_store.py   store behaviour, against a stub embedder
  test_server.py  MCP tools end-to-end via fastmcp's in-memory Client
benchmarks/   run.py — latency harness; RESULTS.md — committed numbers
docs/         this site
```

[Architecture](reference/architecture.md) explains how the pieces fit and why.

## Making a change

1. Branch off `main`.
2. Make the change, with a test.
3. Run `pytest -q` and `ruff check .`.
4. Open a PR.

CI runs ruff, the suite across Python 3.10–3.13 on Linux/macOS/Windows, a job
against real fastembed embeddings, and a packaging check. All green to merge.

Some changes need extra care, and the PR template asks about each:

!!! warning "MCP tool signatures and docstrings"

    Models read these to decide when to call a tool. A wording change is a
    behaviour change — quote the before/after in your PR.

!!! warning "Schema changes"

    Describe the migration story. People have real memories in these files, and
    losing them is unforgivable in a memory tool.

!!! warning "Ranking changes"

    Rarely free. Say what got better *and* what got worse.

!!! warning "New dependencies"

    Install-to-working under 30 seconds is a project goal. Justify the weight.

## Testing

Keep new tests offline — use `StubEmbedder` from `tests/test_store.py`. It's
built so "sqlite" scores nearer "database" than "coffee", which is enough
structure to assert real ranking behaviour without a model.

Anything genuinely needing the real model goes behind `LOCALMEM_TEST_FASTEMBED`,
like `test_fastembed_roundtrip` does. CI runs that job for you.

For MCP-level tests, drive the tools through `fastmcp.Client(server)` as
`tests/test_server.py` does — that's the path a real client takes, so it catches
problems that calling the functions directly would miss.

## Benchmarks

Performance claims here should come with numbers. `benchmarks/run.py` measures
`add()` and `search()` at any corpus size, splitting each timing into embedding,
SQLite, and scoring:

```bash
.venv/bin/python benchmarks/run.py --sizes 1000,10000,100000
```

It runs against a stub embedder by default, so the numbers isolate localmem's
own code; `--real` uses the shipped model. If you change anything on the search
path, re-run it and update `benchmarks/RESULTS.md` in the same PR.

Current results and what they imply are on the
[Benchmarks](reference/benchmarks.md) page.

## Style

- Type hints throughout, with `from __future__ import annotations` at the top.
- Comments explain *why*, not *what*. Match the density around them.
- `ruff` is the arbiter; line length 100.

## Good first contributions

- More client setup recipes for [Connect your client](getting-started/clients.md)
- `forget`/prune tooling: delete by tag, by age, or by id
- Export/import to JSONL, so a memory store is portable
- An `update_memory` tool — the schema already carries `updated_at`
- Faster scoring: the [benchmarks](reference/benchmarks.md) show the Python
  cosine loop is over 90% of a search
- Docs fixes and typos — genuinely useful, always welcome

Issues labelled [`good first issue`](https://github.com/OpenAgentHQ/localmem-mcp/labels/good%20first%20issue)
are scoped to be approachable without deep context.

## Reporting bugs

Use the [issue template](https://github.com/OpenAgentHQ/localmem-mcp/issues/new/choose).
Include your OS, Python version, `localmem-mcp --version`, which client you used,
and the output of `localmem-mcp stats`.

Please don't paste the contents of your memory database — it's yours, and we
don't want to see it.

For security issues, report privately via the
[security policy](https://github.com/OpenAgentHQ/localmem-mcp/blob/main/SECURITY.md)
rather than a public issue.

## Releasing

Maintainers only: bump `version` in `pyproject.toml`, tag `vX.Y.Z`, push the tag.
The release workflow builds and publishes to PyPI via Trusted Publishing (OIDC)
— no tokens or secrets to manage.
