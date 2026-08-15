# Terminal agents

Thirteen command-line coding agents, each with the exact file it reads and the
exact shape it expects. All of them run the same server —
`uvx localmem-mcp` over stdio.

If you installed with `pip` instead of using `uvx`, replace `"command": "uvx"`
with `"command": "localmem-mcp"` and drop `localmem-mcp` from the arguments.

## Claude Code

One command:

```bash
claude mcp add localmem -- uvx localmem-mcp
```

Run it inside a project to scope it there, or add `--scope user` to make it
available everywhere. `--scope project` writes to `.mcp.json` in the repo root,
which you can commit so the whole team gets it.

Verify:

```bash
claude mcp list
```

Then tell Claude Code to use it by adding a memory section to `CLAUDE.md` — see
[making the agent actually use it](index.md#making-the-agent-actually-use-it).

## OpenAI Codex CLI

Codex uses TOML, and the table name must be `mcp_servers` with an underscore.
`mcp-servers` and `mcpservers` are ignored with no error.

```bash
codex mcp add localmem -- uvx localmem-mcp
```

Or edit `~/.codex/config.toml` directly:

```toml
[mcp_servers.localmem]
command = "uvx"
args = ["localmem-mcp"]
```

For one project only, put the same table in `.codex/config.toml` in the repo —
Codex reads project config only for projects you've marked trusted.

Check it with `codex mcp list`, or `/mcp` inside the TUI.

!!! info "One config, three clients"

    The Codex CLI, the Codex IDE extension, and the ChatGPT desktop app all read
    `~/.codex/config.toml`. Configure localmem once and it's in all three — and
    a TOML syntax error breaks all three at once.

## Gemini CLI

```bash
gemini mcp add localmem uvx localmem-mcp
```

That writes to `.gemini/settings.json` in the project by default; pass
`-s user` for `~/.gemini/settings.json` instead. The resulting block:

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

Confirm with `/mcp` inside the CLI. Gemini CLI also accepts `cwd`, `timeout`,
and `trust` per server if you need them.

## GitHub Copilot CLI

```bash
copilot mcp add localmem -- uvx localmem-mcp
```

That writes to `~/.copilot/mcp-config.json`:

```json
{
  "mcpServers": {
    "localmem": {
      "type": "local",
      "command": "uvx",
      "args": ["localmem-mcp"],
      "tools": ["*"]
    }
  }
}
```

`"type": "local"` is Copilot CLI's name for stdio. `"tools": ["*"]` exposes all
four localmem tools; narrow it to a list if you want the agent to see fewer.

Project-level config takes precedence over the user file, and may use either the
`mcpServers` wrapper shown above or a bare top-level object keyed by server
name.

Manage servers with `/mcp` in the session, or `copilot mcp list` from the shell.

## Goose

Goose calls MCP servers **extensions**, uses YAML, and the key is `cmd` rather
than `command`.

Interactively:

```bash
goose configure
# → Add Extension → Command-line Extension
```

Or edit `~/.config/goose/config.yaml`:

```yaml
extensions:
  localmem:
    name: localmem
    type: stdio
    cmd: uvx
    args: ["localmem-mcp"]
    enabled: true
    timeout: 300
```

For a one-off session without touching config:

```bash
goose session --with-extension "uvx localmem-mcp"
```

## OpenCode

`command` is a single array — the executable and its arguments together. There
is no separate `args` key.

```bash
opencode mcp add localmem uvx localmem-mcp
```

Or in `~/.config/opencode/opencode.json` (globally) or `opencode.json` in the
project:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "localmem": {
      "type": "local",
      "command": ["uvx", "localmem-mcp"],
      "enabled": true
    }
  }
}
```

Environment variables go under `environment`, not `env`, and support
`{env:VAR_NAME}` expansion:

```json
"environment": { "LOCALMEM_DB_PATH": "{env:HOME}/code/acme/.localmem.db" }
```

## Crush

Root key `mcp`, and `type` is required.

```json
{
  "$schema": "https://charm.land/crush.json",
  "mcp": {
    "localmem": {
      "type": "stdio",
      "command": "uvx",
      "args": ["localmem-mcp"],
      "timeout": 120
    }
  }
}
```

Or from `crushrc`:

```shell
mcp add localmem --command uvx --args localmem-mcp --timeout 120
```

`disabled: true` parks a server without deleting it, and `disabled_tools` hides
individual tools — useful if you want the agent to search memory but never write
to it.

## Amp

```bash
amp mcp add localmem -- uvx localmem-mcp
```

Add `--workspace` to write to `.amp/settings.json` in the current project
instead of `~/.config/amp/settings.json`. Either way the key is prefixed:

```json
{
  "amp.mcpServers": {
    "localmem": {
      "command": "uvx",
      "args": ["localmem-mcp"]
    }
  }
}
```

Amp expands `${VAR_NAME}` inside these values, so
`"env": { "LOCALMEM_DB_PATH": "${HOME}/.localmem/memories.db" }` works.

!!! warning "Workspace servers need approval"

    MCP servers defined in `.amp/settings.json` must be explicitly approved
    before they run — a deliberate guard against a cloned repo executing
    commands. `amp mcp doctor` shows anything awaiting approval.

## Amazon Q Developer CLI

Edit `~/.aws/amazonq/mcp.json` for all workspaces, or `.amazonq/mcp.json` in a
project:

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

Then `q chat`, and `/tools` to confirm the localmem tools are listed. `q mcp
list` works from the shell.

Q trusts no MCP tool by default and will prompt on each call. `/tools trust
localmem` stops the prompting once you're satisfied — reasonable here, since
every tool call is a local SQLite read or write.

## Qwen Code

Qwen Code follows Gemini CLI's configuration model. Add the server to
`~/.qwen/settings.json`, or `.qwen/settings.json` for one project:

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

Restart and run `/mcp` to list connected servers.

## Junie

Junie CLI and Junie in JetBrains IDEs share one MCP config file:
`~/.junie/mcp/mcp.json` for you, or `.junie/mcp/mcp.json` in the project for the
team.

```json
{
  "mcpServers": {
    "localmem": {
      "command": "uvx",
      "args": ["localmem-mcp"],
      "env": {}
    }
  }
}
```

Or use `/mcp` in Junie CLI and let the MCP Installation Assistant write the file
for you. `/mcp` also lists each server's status — Starting, Active, Inactive,
Disabled, Failed.

## Google Antigravity

Antigravity 2.0, the IDE, and the CLI all share one configuration format. The
file is `~/.gemini/config/mcp_config.json` globally, or `.agents/mcp_config.json`
in your workspace.

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

Type `/mcp` in the CLI prompt panel to open the interactive MCP Manager, which
shows live connection status and server logs.

!!! warning "Two Antigravity-specific gotchas"

    - There is **no `type` field**. Including one is rejected as invalid.
    - Antigravity doesn't inherit your shell's `PATH`. If the server fails with
      "executable file not found", replace `"uvx"` with the absolute path from
      `which uvx`.

    (For remote servers Antigravity also requires `serverUrl` rather than `url`
    — not relevant to localmem, which is stdio only, but worth knowing if you
    copy configs between agents.)

## Warp

Ask Warp's agent to do it — the bundled `/agent-add-mcp` skill writes the config
and asks whether you want it global or project-scoped:

```
/agent-add-mcp
```

Or write `~/.warp/.mcp.json` (global) or `.warp/.mcp.json` (project root)
yourself:

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

Warp also **reads other agents' configs** — Claude Code's `~/.claude.json`,
Codex's `~/.codex/config.toml`, and `~/.agents/.mcp.json`. If you've already set
localmem up in one of those, Warp can pick it up without a second config; those
providers need auto-spawn toggled on, whereas Warp's own file is on by default.

## Next

- [MCP tools reference](../guide/mcp-tools.md) — what the agent gets
- [Configuration](../guide/configuration.md) — database paths and models
- [Troubleshooting](index.md#troubleshooting) — when nothing shows up
