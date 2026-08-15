# Integrations

localmem-mcp speaks MCP over stdio and takes no arguments, so it works with
every MCP-capable coding agent. What differs between them is only *where* the
config file lives and *what shape* it expects.

These pages give you the exact file and the exact snippet for each agent —
checked against that agent's own documentation, not transcribed from another
one's.

<div class="grid cards" markdown>

-   :material-console: **Terminal agents**

    Claude Code, Codex CLI, Gemini CLI, Copilot CLI, Goose, OpenCode, Crush,
    Amp, Amazon Q, Qwen Code, Junie, Antigravity CLI, Warp.

    [:octicons-arrow-right-24: CLI agents](cli-agents.md)

-   :material-application-braces: **IDEs and editors**

    Cursor, Windsurf, Zed, VS Code, JetBrains AI Assistant, Trae,
    Antigravity IDE.

    [:octicons-arrow-right-24: IDEs and editors](ide-agents.md)

-   :material-puzzle: **VS Code extensions**

    Cline, Roo Code, Kilo Code, Continue.

    [:octicons-arrow-right-24: VS Code extensions](vscode-extensions.md)

-   :material-desktop-classic: **Desktop and custom**

    Claude Desktop, ChatGPT desktop, and driving the store from your own
    Python.

    [:octicons-arrow-right-24: Desktop and custom](desktop-and-custom.md)

</div>

## The two shapes

Nearly every agent wants one of two things. If yours isn't listed anywhere on
these pages, try the first shape — it's the one most clients accept.

=== "JSON (most agents)"

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

    Used by Claude Code, Claude Desktop, Cursor, Windsurf, Cline, Roo Code,
    JetBrains, Junie, Trae, Warp, Amazon Q, Copilot CLI, Antigravity, and
    Gemini CLI.

=== "TOML (Codex)"

    ```toml
    [mcp_servers.localmem]
    command = "uvx"
    args = ["localmem-mcp"]
    ```

    Used by OpenAI Codex — CLI, IDE extension, and the ChatGPT desktop app,
    which all share one file.

The rest are variations worth knowing about, because each one fails *silently*
when you paste the wrong shape:

| Variation | Agents | What's different |
| --- | --- | --- |
| Root key `servers` | VS Code | Not `mcpServers`. A pasted Cursor config does nothing. |
| `command` is an array | OpenCode, Kilo Code | `"command": ["uvx", "localmem-mcp"]` — no separate `args`. |
| Root key `mcp` | Crush, Kilo Code | Not `mcpServers`. |
| Root key `context_servers` | Zed | And `args` is required even when empty. |
| Root key `extensions`, `cmd` | Goose | YAML, and the key is `cmd`, not `command`. |
| A YAML *list* | Continue | Entries carry their own `name` field. |
| Prefixed key | Amp | `amp.mcpServers`, inside a settings file. |

## Support matrix

Every agent below runs localmem-mcp over stdio. "Add command" means the agent
can register the server for you without your editing any file.

| Agent | Config file | Add command |
| --- | --- | --- |
| [Claude Code](cli-agents.md#claude-code) | `~/.claude.json` · `.mcp.json` | `claude mcp add` |
| [OpenAI Codex CLI](cli-agents.md#openai-codex-cli) | `~/.codex/config.toml` | `codex mcp add` |
| [Gemini CLI](cli-agents.md#gemini-cli) | `~/.gemini/settings.json` | `gemini mcp add` |
| [GitHub Copilot CLI](cli-agents.md#github-copilot-cli) | `~/.copilot/mcp-config.json` | `copilot mcp add` |
| [Goose](cli-agents.md#goose) | `~/.config/goose/config.yaml` | `goose configure` |
| [OpenCode](cli-agents.md#opencode) | `~/.config/opencode/opencode.json` | `opencode mcp add` |
| [Crush](cli-agents.md#crush) | `crush.json` | `mcp add` in `crushrc` |
| [Amp](cli-agents.md#amp) | `~/.config/amp/settings.json` | `amp mcp add` |
| [Amazon Q Developer CLI](cli-agents.md#amazon-q-developer-cli) | `~/.aws/amazonq/mcp.json` | `q mcp add` |
| [Qwen Code](cli-agents.md#qwen-code) | `~/.qwen/settings.json` | — |
| [Junie](cli-agents.md#junie) | `~/.junie/mcp/mcp.json` | `/mcp` |
| [Antigravity CLI](cli-agents.md#google-antigravity) | `~/.gemini/config/mcp_config.json` | `/mcp` |
| [Warp](cli-agents.md#warp) | `~/.warp/.mcp.json` | `/agent-add-mcp` |
| [Cursor](ide-agents.md#cursor) | `~/.cursor/mcp.json` · `.cursor/mcp.json` | — |
| [Windsurf](ide-agents.md#windsurf) | `~/.codeium/windsurf/mcp_config.json` | — |
| [Zed](ide-agents.md#zed) | `~/.config/zed/settings.json` | Agent Panel |
| [VS Code](ide-agents.md#vs-code-copilot-agent-mode) | `.vscode/mcp.json` | `code --add-mcp` |
| [JetBrains AI Assistant](ide-agents.md#jetbrains-ai-assistant) | Settings dialog | — |
| [Trae](ide-agents.md#trae) | `.trae/mcp.json` | Settings → MCP |
| [Antigravity IDE](ide-agents.md#google-antigravity-ide) | `~/.gemini/config/mcp_config.json` | MCP Store |
| [Cline](vscode-extensions.md#cline) | `cline_mcp_settings.json` | MCP panel |
| [Roo Code](vscode-extensions.md#roo-code) | `mcp_settings.json` · `.roo/mcp.json` | MCP panel |
| [Kilo Code](vscode-extensions.md#kilo-code) | `~/.config/kilo/kilo.jsonc` | Settings → MCP |
| [Continue](vscode-extensions.md#continue) | `.continue/mcpServers/*.yaml` | — |
| [Claude Desktop](desktop-and-custom.md#claude-desktop) | `claude_desktop_config.json` | — |
| [ChatGPT desktop](desktop-and-custom.md#chatgpt-desktop-app) | `~/.codex/config.toml` | `codex mcp add` |
| [Your own Python](desktop-and-custom.md#your-own-python) | — | — |

## Before you start

**Install nothing.** Every snippet on these pages runs `uvx localmem-mcp`, and
[`uv`](https://docs.astral.sh/uv/) fetches the package on demand. If you'd
rather install it, `pip install localmem-mcp` and then use `"command":
"localmem-mcp"` with no `args`.

**Pre-warm the model.** The first embedding triggers a one-time ~90 MB download,
which can look like a hung tool call inside an agent. Get it out of the way:

```bash
uvx localmem-mcp add "First memory — localmem is working"
```

**Use an absolute path if the agent can't find `uvx`.** GUI-launched agents
often don't inherit your shell's `PATH`. `which uvx` gives you the path to
paste in place of `"uvx"`. This is the single most common failure across every
agent on these pages.

## Making the agent actually use it

Registering the server gives the agent four tools. It does not make the agent
*reach for them* — most agents won't store a memory unless told to. Put this in
whatever file the agent reads as project instructions (`CLAUDE.md`,
`AGENTS.md`, `.cursor/rules/`, `.github/copilot-instructions.md`,
`GEMINI.md`, `.windsurfrules`, …):

```markdown
## Memory

You have persistent memory via the localmem MCP server.

- Search it with `search_memory` before asking about project context — the
  answer may already be there from an earlier session.
- Save durable facts with `store_memory`: decisions and their rationale,
  conventions, preferences, gotchas. Tag them.
- Don't store transient state — current diffs, task lists, or anything true
  only for this session.
```

The [MCP tools reference](../guide/mcp-tools.md) covers what each tool does and
when the agent should choose it.

## Per-project memory

By default every agent shares one database at `~/.localmem/memories.db` — which
is usually what you want for preferences that should follow you everywhere.
Project context is often better kept separate, so unrelated work doesn't dilute
search results.

Two ways, and every agent on these pages supports at least one:

=== "Extra arguments"

    Append `--db` and a path to the command's arguments:

    ```json
    "args": ["localmem-mcp", "--db", "/Users/you/code/acme/.localmem.db"]
    ```

=== "Environment variable"

    If the agent lets you set env vars for the server:

    ```json
    "env": { "LOCALMEM_DB_PATH": "/Users/you/code/acme/.localmem.db" }
    ```

You can also run both at once — a global server for preferences and a
project-scoped one for context — by registering two entries under different
names. [Configuration](../guide/configuration.md) has the full picture.

!!! tip "Add project databases to `.gitignore`"

    ```gitignore
    .localmem.db
    .localmem.db-wal
    .localmem.db-shm
    ```

## Troubleshooting

??? failure "The agent shows no localmem tools"

    Restart it completely. MCP servers are discovered at startup, so a new
    conversation in an already-running agent isn't enough.

    Then confirm the command works standalone:

    ```bash
    uvx localmem-mcp --version
    ```

    If that fails, the problem is installation rather than the agent — see
    [Installation](../getting-started/installation.md).

??? failure "The config looks right but nothing loads"

    Check the root key against the [variations table](#the-two-shapes) above.
    Most agents fail silently on an unrecognised shape: VS Code wants
    `servers`, Crush and Kilo Code want `mcp`, Zed wants `context_servers`,
    Goose wants `extensions`. Codex ignores `mcp-servers` and `mcpservers` —
    only `mcp_servers` works.

    Then validate the file. A trailing comma or a missing bracket takes down
    every server in the file, not just the one you added.

??? failure "`uvx: command not found`"

    Either install [uv](https://docs.astral.sh/uv/getting-started/installation/),
    or `pip install localmem-mcp` and use `"command": "localmem-mcp"`.

    If `uvx` works in your terminal but not in the agent, the agent isn't
    inheriting your `PATH`. Use the absolute path from `which uvx`.

??? failure "The first tool call hangs or times out"

    That's the one-time model download. Pre-warm it from a terminal:

    ```bash
    uvx localmem-mcp add "First memory — localmem is working"
    ```

??? failure "Memories from another agent don't show up"

    Different agents are pointed at different databases. Ask each one for
    `memory_stats`, or check from a terminal:

    ```bash
    uvx localmem-mcp stats
    ```

    Agents sharing memory need to resolve to the same `--db` path. Note that a
    relative path resolves against the agent's working directory, which is
    rarely what you want — use absolute paths when sharing.

??? failure "Windows: the server won't start"

    Some agents can't launch `uvx` directly on Windows. Wrap it:

    ```json
    {
      "command": "cmd",
      "args": ["/c", "uvx", "localmem-mcp"]
    }
    ```

    And remember that backslashes in JSON paths need escaping:
    `"C:\\Users\\you\\.localmem\\memories.db"`.
