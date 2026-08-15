# IDEs and editors

Seven editors with a built-in agent. For agents that arrive as a VS Code
extension — Cline, Roo Code, Kilo Code, Continue — see
[VS Code extensions](vscode-extensions.md) instead; they keep their own config
files, separate from VS Code's.

Throughout: replace `"command": "uvx", "args": ["localmem-mcp"]` with
`"command": "localmem-mcp"` and no `args` if you installed with `pip`.

## Cursor

Create `.cursor/mcp.json` in the project, or `~/.cursor/mcp.json` to have it
everywhere:

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

Cursor picks it up without a restart. Check **Settings → MCP** for a green dot
and the four tools.

MCP tools are only called in Agent mode, not in Ask. To make Cursor reach for
memory on its own, add a rule in `.cursor/rules/memory.mdc`:

```markdown
---
alwaysApply: true
---
Search localmem with `search_memory` before asking about project context.
Save durable decisions with `store_memory`.
```

## Windsurf

Edit `~/.codeium/windsurf/mcp_config.json`:

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

Then **Settings → Cascade → MCP Servers → Refresh**. Windsurf shows a hammer
icon in Cascade with the tool count once the server is live.

Project instructions go in `.windsurfrules`.

## Zed

Root key is `context_servers`, and **`args` is required even when empty** — a
stdio entry without it silently fails to load.

Open settings with `Cmd+Shift+P` → `zed: open settings`, or edit
`~/.config/zed/settings.json` (`%APPDATA%\Zed\settings.json` on Windows):

```json
{
  "context_servers": {
    "localmem": {
      "command": "uvx",
      "args": ["localmem-mcp"],
      "env": {}
    }
  }
}
```

You can also add it through the UI: **Settings → AI → MCP Servers → Add Server →
Add Local Server**, which writes the same JSON.

Zed prompts before every tool call by default. To auto-approve just the reads:

```json
{
  "tool_permissions": {
    "mcp:localmem:search_memory": "allow",
    "mcp:localmem:recall_memory": "allow",
    "mcp:localmem:memory_stats": "allow",
    "mcp:localmem:store_memory": "confirm"
  }
}
```

!!! failure "`data did not match any variant of untagged enum ContextServerSettingsContent`"

    Zed's log for a malformed entry. Almost always a missing `args`, or a nested
    `"command": { "path": ..., "args": ... }` object instead of a flat
    `"command": "uvx"` string.

## VS Code (Copilot agent mode)

**The root key is `servers`, not `mcpServers`.** Pasting a Cursor or Claude
Desktop config here does nothing at all, with no error.

Fastest path:

```bash
code --add-mcp '{"name":"localmem","command":"uvx","args":["localmem-mcp"]}'
```

Or create `.vscode/mcp.json` in the workspace:

```json
{
  "servers": {
    "localmem": {
      "type": "stdio",
      "command": "uvx",
      "args": ["localmem-mcp"]
    }
  }
}
```

For every workspace, run **MCP: Open User Configuration** from the Command
Palette and add the same block there.

Two more things:

- **Agent mode is required.** MCP tools are invisible in Ask and Edit mode. Open
  Copilot Chat and pick Agent from the mode dropdown.
- **Verify** with **MCP: List Servers** from the Command Palette.

Project instructions go in `.github/copilot-instructions.md`.

??? tip "Dev Containers"

    Put the server in `devcontainer.json` and it starts with the container:

    ```json
    {
      "customizations": {
        "vscode": {
          "mcp": {
            "servers": {
              "localmem": { "command": "uvx", "args": ["localmem-mcp"] }
            }
          }
        }
      }
    }
    ```

    Point `LOCALMEM_DB_PATH` at a mounted volume if you want memories to survive
    the container being rebuilt.

## JetBrains AI Assistant

Works across IntelliJ IDEA, PyCharm, WebStorm, GoLand, and the rest.

1. Press `Ctrl+Alt+S` (`Cmd+,` on macOS) to open Settings.
2. **Tools → AI Assistant → Model Context Protocol (MCP)**.
3. Click **Add**, choose the stdio connection type, and paste:

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

You can also reach this screen by typing `/` in the AI chat and choosing **Add
Command**.

If you use Junie inside the same IDE, it reads its own config —
see [Junie](cli-agents.md#junie).

!!! tip "GUI launch and `PATH`"

    A JetBrains IDE started from Spotlight or the Dock doesn't get your shell's
    `PATH`. If the server won't start, use the absolute path from `which uvx`.

## Trae

Two ways in, both under **Settings → MCP**:

- **Add → Manually add**, then paste the JSON below.
- Or click **Raw config (JSON)** and edit `mcp.json` directly.

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

For a project-scoped server, create `.trae/mcp.json` in the repo root and turn
on **Enable project-level MCP** in **Settings → MCP**.

Trae's `command` field must not contain spaces — it's parsed as a single
executable, with everything else going in `args`. If the model download makes
startup slow, raise the timeout:

```json
"env": { "START_MCP_TIMEOUT_MS": "60000" }
```

## Google Antigravity IDE

1. Click **…** at the top of the agent side panel → **MCP Servers**.
2. **Manage MCP Servers** → **View raw config**.
3. Add localmem to `mcp_config.json`:

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

The file is `~/.gemini/config/mcp_config.json` globally, or
`.agents/mcp_config.json` in the workspace. Save, then hit refresh in the
Installed MCP Servers list.

Same two gotchas as the CLI: **no `type` field**, and Antigravity doesn't
inherit your shell's `PATH`, so use the absolute path to `uvx` if the server
won't start. See [Antigravity CLI](cli-agents.md#google-antigravity) for the
rest.

## Next

- [VS Code extensions](vscode-extensions.md) — Cline, Roo Code, Kilo Code, Continue
- [MCP tools reference](../guide/mcp-tools.md) — what the agent gets
- [Troubleshooting](index.md#troubleshooting) — when nothing shows up
