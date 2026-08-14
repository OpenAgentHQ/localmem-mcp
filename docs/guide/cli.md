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

# Back everything up as JSONL
localmem-mcp recall -n 100000 --json | jq -c '.[]' > memories.jsonl
```

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
