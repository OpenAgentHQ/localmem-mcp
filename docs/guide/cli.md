# Command line

The `localmem-mcp` command does double duty: with no arguments it runs the MCP
server (that's what clients invoke), and its subcommands let you inspect and
edit the same database from a terminal.

```bash
localmem-mcp [--db PATH] [--model NAME] [--json] <command> [args]
```

Shared flags work either before or after the subcommand, so both of these are
valid:

```bash
localmem-mcp --db ./project.db search "deploys"
localmem-mcp search "deploys" --db ./project.db
```

---

## `serve`

Run the MCP server over stdio. This is the default when no subcommand is given.

```bash
localmem-mcp
localmem-mcp serve
localmem-mcp serve --db ./project.db
```

It reads and writes JSON-RPC on stdin/stdout, so running it in a terminal looks
like it's hanging — that's correct. It's waiting for a client.

---

## `add`

Store a memory.

```bash
localmem-mcp add "Deploys go out on Thursdays" --tag ops --tag process
localmem-mcp add "Priya prefers async updates" --source standup
```

| Flag | Description |
| --- | --- |
| `--tag TAG` | Add a tag. Repeat for several. |
| `--source SOURCE` | Where the memory came from. |

```
stored #7: Deploys go out on Thursdays
```

---

## `search`

Search memories by meaning.

```bash
localmem-mcp search "when do we ship?"
localmem-mcp search "deployment" --tag ops -n 10 --min-score 0.4
```

| Flag | Default | Description |
| --- | --- | --- |
| `-n`, `--limit` | `5` | Maximum results. |
| `--tag TAG` | — | Only memories with **all** given tags. Repeatable. |
| `--min-score` | `0.0` | Drop results below this score. |

```
[0.812] #7 Deploys go out on Thursdays
[0.514] #3 Release notes are written the day before a deploy
```

---

## `recall`

Read a memory by id, or the most recent ones.

```bash
localmem-mcp recall 7        # one specific memory
localmem-mcp recall -n 10    # the ten most recent
```

```
#7 (2026-08-14T11:31:00+00:00) [ops, process] Deploys go out on Thursdays
```

Exits with status `1` if the id doesn't exist, so it's safe to use in scripts.

---

## `forget`

Delete a memory by id, or bulk-delete by tag and/or age.

```bash
localmem-mcp forget 7                 # one specific memory
localmem-mcp forget --tag stale       # every memory tagged "stale"
localmem-mcp forget --older-than 90d  # everything older than 90 days
localmem-mcp forget --tag scratch --older-than 30d --yes
```

| Flag | Description |
| --- | --- |
| `memory_id` | Delete the single memory with this id. |
| `--tag TAG` | Bulk-delete memories with this tag. Repeatable — all tags must match. |
| `--older-than DURATION` | Bulk-delete memories older than this. Accepts `90`, `90d`, or `8w`. |
| `--yes` | Skip the confirmation prompt for bulk deletes. |

Single-id delete:

```
forgot #7
```

Bulk delete **shows what will be removed and asks before deleting** — deleting
someone's memories on a typo is unforgivable:

```
#12 (2026-05-01T09:00:00+00:00) [stale] Old deploy notes
#9  (2026-03-14T18:30:00+00:00) [stale] Abandoned experiment
Delete 2 memories? [y/N]
```

Answer `y` to delete, anything else aborts without touching the store. Pass
`--yes` to skip the prompt in scripts. A bulk call with **no filter at all**
exits with status `2` rather than wiping the database.

With `--json`, the result is a single machine-readable payload (the
human-readable preview and prompt go to stderr):

```bash
localmem-mcp forget --tag stale --yes --json
```

```json
{ "deleted": true, "count": 2 }
```

---

## `export`

Write memories to stdout as JSONL — one JSON object per line.

```bash
localmem-mcp export > memories.jsonl
localmem-mcp export --tag work > work.jsonl
localmem-mcp export --with-embeddings > backup.jsonl
```

| Flag | Description |
| --- | --- |
| `--tag TAG` | Only memories with **all** given tags. Repeatable. |
| `--with-embeddings` | Include the stored vectors. |

```json
{"id": 7, "content": "Deploys go out on Thursdays", "tags": ["ops"], "source": null, "metadata": {}, "created_at": "2026-08-14T11:31:00+00:00", "updated_at": "2026-08-14T11:31:00+00:00"}
```

Records come out oldest first, and the output is always JSONL — `--json` has
nothing to add. A single JSON array would defeat the point of a format you can
stream, `grep`, and append to.

**Embeddings are left out by default.** A vector is only meaningful on a machine
running the same model, and the point of an export is to be portable — so the
default file is human-readable and model-agnostic. `--with-embeddings` adds
`embedding`, `embedding_model`, and `dim` to each record if you want a fuller
backup; `import` ignores them either way (see below).

---

## `import`

Read JSONL and store each memory.

```bash
localmem-mcp import memories.jsonl
localmem-mcp import memories.jsonl --dry-run
cat memories.jsonl | localmem-mcp import          # stdin is the default
```

| Flag | Description |
| --- | --- |
| `path` | JSONL file to read. Defaults to `-`, meaning stdin. |
| `--dry-run` | Report what would be stored without writing anything. |
| `--allow-duplicates` | Store records whose content is already in the database. |

Only `content` is required. `tags`, `source`, `metadata`, and `created_at` are
used when present; `id` is dropped, because the importing database assigns its
own.

```
imported 2 memories, skipped 1 duplicates
```

A few behaviours are worth knowing:

**Memories are re-embedded on the way in.** Vectors in the file are ignored,
even with `--with-embeddings` in the export. The importing machine may be
running a different model, and a vector from the wrong model isn't detectably
wrong — search just quietly stops matching. Re-embedding costs a little time
and removes that failure mode entirely.

**`created_at` is preserved**, so an imported memory keeps the day it was first
recorded rather than the day it was restored.

**A bad line is skipped, not fatal.** Malformed records are reported on stderr
with their line number and the import continues — a 10,000-line file shouldn't
die on line 3. The exit status is `1` if any line failed, so scripts can still
tell a clean import from a lossy one:

```
line 3: not valid JSON (Expecting ',' delimiter)
line 47: missing or empty 'content'
imported 9998 memories, 2 malformed lines
```

**Duplicates are skipped by default.** A record whose content already exists is
counted and passed over, so importing the same file twice doesn't double your
store. Pass `--allow-duplicates` if you actually want the second copy.

With `--json`, the summary on stdout is a single parseable payload (the per-line
errors stay on stderr):

```json
{
  "imported": 2,
  "skipped_duplicates": 1,
  "failed": 0,
  "dry_run": false,
  "errors": []
}
```

### Moving a database between machines

```bash
# on the old machine
localmem-mcp export > memories.jsonl

# on the new one — check first, then commit
localmem-mcp import memories.jsonl --dry-run
localmem-mcp import memories.jsonl
```

---

## `stats`

Show the database location, memory count, and active model.

```bash
localmem-mcp stats
```

```
db: /Users/you/.localmem/memories.db
memories: 42
model: BAAI/bge-small-en-v1.5
```

---

## JSON output

Every subcommand takes `--json`, which prints the same structures the MCP tools
return:

```bash
localmem-mcp search "deploys" --json
```

```json
[
  {
    "id": 7,
    "content": "Deploys go out on Thursdays",
    "tags": ["ops", "process"],
    "source": null,
    "metadata": {},
    "created_at": "2026-08-14T11:31:00+00:00",
    "updated_at": "2026-08-14T11:31:00+00:00",
    "score": 0.8121
  }
]
```

Which makes `jq` pipelines straightforward:

```bash
# Just the text of the top three matches
localmem-mcp search "deploys" -n 3 --json | jq -r '.[].content'

# Every memory tagged "decision", newest first
localmem-mcp recall -n 100 --json | jq -r '.[] | select(.tags[]? == "decision") | .content'
```

To get every memory out as JSONL, use [`export`](#export) rather than a large
`recall` — it streams, filters by tag, and is what `import` reads back.

---

## Useful recipes

**Pre-warm the model** so an agent never waits on the first-run download:

```bash
localmem-mcp add "First memory — localmem is working"
```

**Bulk-import notes**, one memory per line:

```bash
while IFS= read -r line; do
  [ -n "$line" ] && localmem-mcp add "$line" --tag imported --source notes.txt
done < notes.txt
```

**Check what your agent has been remembering:**

```bash
localmem-mcp recall -n 20
```

**Inspect the raw database** — it's just SQLite:

```bash
sqlite3 ~/.localmem/memories.db \
  "SELECT id, created_at, substr(content, 1, 60) FROM memories ORDER BY id DESC LIMIT 10;"
```

!!! warning "Prefer the CLI for writes"

    Reading the database directly is fine. Writing to it by hand isn't — an
    `INSERT` that skips the embedding step produces a memory that search can
    never find.
