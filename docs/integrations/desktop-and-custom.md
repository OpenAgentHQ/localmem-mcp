# Desktop and custom

Desktop chat apps that can call MCP tools, and how to reach the same memories
from your own code when no MCP client is involved at all.

## Claude Desktop

Edit `claude_desktop_config.json`:

- **macOS** — `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows** — `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux** — `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "localmem": {
      "command": "uvx",
      "args": ["localmem-mcp"]
    }
  }
}
```

Reach it through **Settings → Developer → Edit Config**, which opens the file
and creates it if it doesn't exist.

Then quit Claude Desktop **completely** — closing the window isn't enough, since
MCP servers are only spawned at startup. The tools appear under the
:material-tools: icon in the composer.

!!! tip "The `PATH` problem, in its most common form"

    Claude Desktop is launched by the OS, not your shell, so it usually can't
    see `uvx`. If the server shows as failed, run `which uvx` and paste the
    absolute path:

    ```json
    "command": "/Users/you/.local/bin/uvx"
    ```

Claude Desktop has no project-instructions file, so tell it what to do with the
memory in the conversation, or set it up as a Project instruction if you use
Projects.

## ChatGPT desktop app

The ChatGPT desktop app reads Codex's config file, so setting localmem up for
Codex sets it up here too:

```bash
codex mcp add localmem -- uvx localmem-mcp
```

Or edit `~/.codex/config.toml` by hand — note the underscore in `mcp_servers`:

```toml
[mcp_servers.localmem]
command = "uvx"
args = ["localmem-mcp"]
```

One file covers the ChatGPT desktop app, the Codex CLI, and the Codex IDE
extension. See [Codex CLI](cli-agents.md#openai-codex-cli) for the details.

## Any other MCP client

The server runs over stdio and takes no required arguments:

```bash
uvx localmem-mcp
```

Point your client's stdio transport at that command. If it lets you set
environment variables, [configuration](../guide/configuration.md) is done that
way; if it only lets you pass arguments, use `--db` and `--model`.

Start from the [JSON shape](index.md#the-two-shapes) — it's what most clients
accept — and check the [variations table](index.md#the-two-shapes) if nothing
loads.

## Your own Python

You don't need an MCP client at all. The server is a thin shell over a
`MemoryStore` you can import, and it reads the same database your agents use:

```python
from localmem_mcp import MemoryStore

with MemoryStore() as store:                     # ~/.localmem/memories.db
    store.add("Deploys go out on Thursdays", tags=["ops"])

    for hit in store.search("when do we ship?"):
        print(f"{hit.score:.3f}  {hit.memory.content}")
```

This is how you give a custom agent — one built on the Claude Agent SDK,
LangGraph, or nothing at all — the same memory your editor agents have. Pass
`db_path` to point at a project database:

```python
store = MemoryStore(db_path="./.localmem.db")
```

The [Python library guide](../guide/python-library.md) covers the full API, and
the [Python API reference](../reference/api.md) has every method.

### Serving your own tools alongside it

If you're building an MCP server of your own and want memory in it, import the
store rather than nesting servers:

```python
from fastmcp import FastMCP
from localmem_mcp import MemoryStore

mcp = FastMCP("my-agent-tools")
store = MemoryStore()

@mcp.tool
def remember(content: str, tags: list[str] | None = None) -> int:
    """Save a durable fact. Returns the new memory's id."""
    return store.add(content, tags=tags).id
```

### From a script or a cron job

The CLI is the shortest path when you just want to pipe something in:

```bash
uvx localmem-mcp add "Release 2.1 shipped" --tag release
uvx localmem-mcp search "what shipped recently?"
uvx localmem-mcp export > memories.jsonl
```

See the [command line guide](../guide/cli.md) for every command.

## Next

- [Terminal agents](cli-agents.md) — Claude Code, Codex, Gemini, and ten more
- [Python library](../guide/python-library.md) — the full store API
- [Privacy model](../guide/privacy.md) — what leaves your machine, and when
