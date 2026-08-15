# VS Code extensions

Four agents that ship as editor extensions and keep their **own** MCP config,
separate from VS Code's `.vscode/mcp.json`. Configuring one doesn't configure
the others, and all of them can coexist — pointed at the same database, they
share one memory.

## Cline

Open the Cline sidebar, click the **MCP servers** icon, then **Configure MCP
Servers** to open `cline_mcp_settings.json` directly. Or find it yourself:

| OS | Path |
| --- | --- |
| macOS | `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` |
| Windows | `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json` |
| Linux | `~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` |

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

Cline reconnects on save — no reload needed. Green dot in the MCP panel means
it's live.

On VS Code Insiders substitute `Code - Insiders` for `Code` in those paths; on
VSCodium, `VSCodium`. The Cline CLI uses `~/.cline/mcp.json` instead.

Auto-approve is per server in the MCP panel. Reasonable for localmem — every
call is a local SQLite read or write.

## Roo Code

Two scopes, and the project one wins when a server name appears in both:

- **Global** — `mcp_settings.json`, reachable from the MCP panel's
  **Edit Global MCP** button.
- **Project** — `.roo/mcp.json` in the repo root, which you can commit.

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

Roo's modes each have their own tool permissions. If localmem's tools don't
appear, check that MCP tools are enabled for the mode you're in.

## Kilo Code

Kilo Code uses the root key `mcp` (not `mcpServers`), and `command` is an
**array** — the executable and its arguments together.

- **Global** — `~/.config/kilo/kilo.jsonc`
- **Project** — `kilo.jsonc` in the repo root, or `.kilo/kilo.jsonc`

```json
{
  "mcp": {
    "localmem": {
      "type": "local",
      "command": ["uvx", "localmem-mcp"],
      "enabled": true,
      "timeout": 10000
    }
  }
}
```

Project config takes precedence over global. Through the UI:
**Settings → Agent Behaviour → MCP Servers → Add Server → Local (stdio)**,
which writes the same thing.

Environment variables go under `environment`:

```json
"environment": { "LOCALMEM_DB_PATH": "/Users/you/code/acme/.localmem.db" }
```

On Windows, wrap the invocation:

```json
"command": ["cmd", "/c", "uvx", "localmem-mcp"]
```

## Continue

Continue uses YAML, and `mcpServers` is a **list** — each entry carries its own
`name`.

Create `.continue/mcpServers/localmem.yaml` in your workspace:

```yaml
name: localmem
version: 0.0.1
schema: v1
mcpServers:
  - name: localmem
    command: uvx
    args:
      - localmem-mcp
```

The `name`, `version`, and `schema` fields at the top are required in standalone
block files. If you'd rather keep everything in one place, add the list to
`~/.continue/config.yaml` instead, where those three fields aren't needed:

```yaml
mcpServers:
  - name: localmem
    command: uvx
    args:
      - localmem-mcp
```

!!! info "MCP tools are agent-mode only"

    Continue exposes MCP tools in **Agent** mode, not Chat. Switch modes in the
    Continue panel if the tools don't appear.

??? tip "Reuse a config you already wrote"

    Continue reads JSON MCP files dropped into `.continue/mcpServers/` — so a
    `mcp.json` copied from Cursor or Claude Desktop works as-is. You can also
    point at another agent's file from `config.yaml`:

    ```yaml
    mcpServersJSON: ~/.cursor/mcp.json
    ```

## Sharing one memory across extensions

Running several of these side by side is fine. They all default to
`~/.localmem/memories.db`, so they already share memory — one agent stores a
decision, the next one finds it.

To scope that shared memory to a project instead, give every extension the same
**absolute** path:

```json
"args": ["localmem-mcp", "--db", "/Users/you/code/acme/.localmem.db"]
```

A relative path resolves against each extension's working directory, which is
rarely the same one — that's the usual reason two agents that look identically
configured can't see each other's memories. Ask either agent for
`memory_stats`, or run `uvx localmem-mcp stats`, to see which file it's actually
using.

## Next

- [IDEs and editors](ide-agents.md) — Cursor, Windsurf, Zed, VS Code, JetBrains
- [MCP tools reference](../guide/mcp-tools.md) — what the agent gets
- [Troubleshooting](index.md#troubleshooting) — when nothing shows up
