# Contributing

Thanks for looking! localmem-mcp is small on purpose, and contributions that
keep it small are the most welcome kind.

## The one rule

**Nothing leaves the user's machine.** No telemetry, no hosted services, no API
keys, no update pings. The only network call in the whole project is fastembed's
one-time model download. A PR that breaks this won't be merged, however good it
is otherwise.

Beyond that: this is a memory tool, not an agent framework. Features that make
storing and recalling memories better are in scope; features that turn it into
something else are not.

## Setup

```bash
git clone https://github.com/OpenAgentHQ/localmem-mcp
cd localmem-mcp
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
```

The suite runs offline in about a second, because it uses a deterministic stub
embedder instead of the real model. To exercise the real fastembed path (first
run downloads ~90 MB):

```bash
LOCALMEM_TEST_FASTEMBED=1 .venv/bin/python -m pytest -q
```

## Before you open a PR

- `.venv/bin/python -m pytest -q` passes.
- `.venv/bin/ruff check .` is clean.
- New behaviour has a test. Keep new tests offline — use `StubEmbedder` from
  `tests/test_store.py`, and gate anything needing the real model behind
  `LOCALMEM_TEST_FASTEMBED`.
- If you changed an MCP tool's signature or docstring, say so in the PR
  description — those docstrings are what agents read to decide when to call the
  tool, so wording changes are behaviour changes.
- If you changed the SQLite schema, note the migration story for existing
  databases. People have real memories in these files.

## Good first contributions

- More MCP client setup recipes for the README (Zed, Windsurf, OpenClaw, …).
- `forget`/prune tooling: delete by tag, by age, or by id.
- Export/import to JSONL, so a memory store is portable and inspectable.
- Benchmarks: how does search hold up at 10k / 100k memories?
- Docs fixes and typos — genuinely useful, always welcome.

## Reporting bugs

Include your OS, Python version, `localmem-mcp --version`, which MCP client you
used, and the output of `localmem-mcp stats`. Please don't paste the contents of
your memory database — it's yours, and we don't want to see it.

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).
