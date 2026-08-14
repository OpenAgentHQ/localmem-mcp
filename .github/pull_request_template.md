<!--
Thanks for contributing! Delete any section that doesn't apply.
Small, focused PRs get reviewed fastest.
-->

## What this changes

<!-- One or two sentences. What does this do, from a user's point of view? -->

## Why

<!-- The problem being solved. Link the issue if there is one: "Fixes #123" -->

## How

<!-- The approach, and anything you considered and rejected. Skip for small fixes. -->

## Checklist

- [ ] `pytest -q` passes
- [ ] `ruff check .` is clean
- [ ] New behaviour has a test (offline — use `StubEmbedder` from `tests/test_store.py`)
- [ ] No new network calls at runtime, and no new API keys or hosted services
- [ ] Docs updated if behaviour changed (README / CONTRIBUTING / docstrings)

## Things reviewers should know

<!-- Check any that apply and add detail — these are the changes that need a closer look. -->

- [ ] **Changes an MCP tool signature or docstring.** Tool docstrings are what agents read to decide when to call a tool, so wording changes are behaviour changes. Quote the before/after.
- [ ] **Changes the SQLite schema.** Describe the migration story — people have real memories in these files.
- [ ] **Changes search ranking.** Say what got better and what got worse; ranking changes are rarely free.
- [ ] **Adds a dependency.** Name it and justify the install-size cost — install-to-working under 30 seconds is a project goal.

## Verification

<!--
How did you check this works? Paste output where it helps.
If you touched the embedding path, please run:
    LOCALMEM_TEST_FASTEMBED=1 pytest -q
-->
