# Security Policy

## Reporting a vulnerability

Please report security issues privately through
[GitHub's private vulnerability reporting](https://github.com/OpenAgentHQ/localmem-mcp/security/advisories/new)
rather than opening a public issue.

Include what you can: affected version, how to reproduce, and what an attacker
gains. We'll acknowledge within a few days and keep you posted as we work on it.

## What counts as a vulnerability here

localmem-mcp's whole premise is that your memories stay on your machine, so the
bar is shaped around that. These are in scope:

- **Anything that sends memory content off the machine.** Any unexpected network
  call at all, beyond the documented one-time model download.
- **SQL injection** or any path where memory content or a query escapes into a
  statement it shouldn't. Note that free-text search input reaches SQLite's FTS5
  query parser — it's sanitized in `_fts_query()`, and holes there are in scope.
- **Path traversal** through `LOCALMEM_DB_PATH`, `LOCALMEM_HOME`, or `--db`
  leading to reads or writes outside the intended location.
- **Overly permissive file permissions** on the database, letting other local
  users read memories they shouldn't.
- **Supply chain issues** in how the package is built or published.

## What doesn't

- **Memory content is unencrypted at rest.** This is by design — it's a SQLite
  file you own, protected by your filesystem permissions. If you need
  encryption, put the database on an encrypted volume. We're open to an
  encryption-at-rest feature, but its absence isn't a vulnerability.
- **Prompt injection through stored memories.** Anything an agent stores, it can
  later recall, and recalled text enters the model's context. That's the tool
  working as intended. Treat stored memories with the same trust you'd give any
  other context you feed a model.
- **The one-time model download** from Hugging Face on first use. It's
  documented, and it's the only network call in the project.

## Supported versions

This is a young project — fixes go onto the latest release. Please upgrade
before reporting.
