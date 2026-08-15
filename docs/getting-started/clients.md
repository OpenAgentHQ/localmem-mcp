# Connect your client

localmem-mcp speaks MCP over stdio, so it works with any MCP-compatible client.
Below are configs for the common ones.

!!! tip "Using something else?"

    [Integrations](../integrations/index.md) has verified configs for more than
    twenty coding agents — Codex, Gemini CLI, Copilot, Cline, Goose, OpenCode,
    Zed, JetBrains, and the rest — with the file path and exact shape each one
    expects.

All of them use the same shape: run `uvx localmem-mcp`. If you installed with
`pip` instead, replace `"command": "uvx", "args": ["localmem-mcp"]` with
`"command": "localmem-mcp"` and drop the `args`.

## Claude Code

One command:

```bash
claude mcp add localmem -- uvx localmem-mcp
```

Scope it to a single project by running that inside the project directory, or
add `--scope user` to make it available everywhere.

Check it registered:

```bash
claude mcp list
```

## Claude Desktop

Edit `claude_desktop_config.json`:

- **macOS** — `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows** — `%APPDATA%\Claude\claude_desktop_config.json`

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

Restart Claude Desktop fully. The tools appear under the :material-tools: icon
in the composer.

## Cursor

Create `.cursor/mcp.json` in your project (or `~/.cursor/mcp.json` globally):

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

## Zed

In `settings.json`:

```json
{
  "context_servers": {
    "localmem": {
      "command": {
        "path": "uvx",
        "args": ["localmem-mcp"]
      }
    }
  }
}
```

## Windsurf

In `~/.codeium/windsurf/mcp_config.json`:

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

## Any other MCP client

The server runs over stdio with no arguments:

```bash
uvx localmem-mcp
```

Point your client's stdio transport at that command. If the client lets you pass
environment variables, [configuration](../guide/configuration.md) is done that
way.

For a specific agent — Codex, Gemini CLI, Copilot CLI, Goose, OpenCode, Crush,
Amp, Amazon Q, Cline, Roo Code, Kilo Code, Continue, JetBrains, Trae, Warp,
Antigravity, and more — [Integrations](../integrations/index.md) has the exact
config file and shape for each. Worth checking before you improvise: several
agents use a different root key and fail silently when they get the wrong one.

## Per-project memory

By default every client shares one database at `~/.localmem/memories.db`. To
give a project its own isolated memory, pass `--db`:

```json
{
  "mcpServers": {
    "localmem": {
      "command": "uvx",
      "args": ["localmem-mcp", "--db", "/Users/you/code/acme/.localmem.db"]
    }
  }
}
```

Or use the environment variable, if your client supports setting one:

```json
{
  "mcpServers": {
    "localmem": {
      "command": "uvx",
      "args": ["localmem-mcp"],
      "env": {
        "LOCALMEM_DB_PATH": "/Users/you/code/acme/.localmem.db"
      }
    }
  }
}
```

!!! tip "Add the database to `.gitignore`"

    If you keep the file inside the repo, don't commit it — memories are yours,
    not your team's, unless you decide otherwise.

## Troubleshooting

??? failure "The client shows no tools"

    Restart the client completely — MCP servers are only discovered at startup,
    so a new conversation isn't enough.

    Then check the command runs on its own:

    ```bash
    uvx localmem-mcp --version
    ```

    If that fails, the problem is installation, not the client. See
    [Installation](installation.md).

??? failure "`uvx: command not found`"

    Install [uv](https://docs.astral.sh/uv/getting-started/installation/), or
    use `pip install localmem-mcp` and set `"command": "localmem-mcp"` instead.

    Some clients don't inherit your shell's PATH. If `uvx` works in a terminal
    but not in the client, use its absolute path — `which uvx` will tell you.

??? failure "The first tool call times out"

    That's the one-time model download (~90 MB). Pre-warm it from a terminal so
    the agent never waits:

    ```bash
    localmem-mcp add "First memory — localmem is working"
    ```

??? failure "The agent never stores anything"

    Most agents won't store memories unless told to. Add a line to your project
    instructions:

    > "Use `store_memory` to save durable decisions and project context. Search
    > your memory before asking me something I may have already told you."

??? failure "Memories seem to have vanished"

    Check which database you're pointed at:

    ```bash
    localmem-mcp stats
    ```

    Most often the client is configured with a `--db` path (or a different
    working directory) than the terminal you're checking from.
