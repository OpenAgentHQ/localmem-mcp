---
title: localmem-mcp
hide:
  - navigation
  - toc
---

<div class="lm-hero" markdown>

<span class="lm-eyebrow"><span class="lm-dot"></span> v0.1.0 · MIT · zero API keys</span>

# Memory for AI agents that never leaves your machine

<p class="lm-lede"><strong>localmem-mcp</strong> gives your agent persistent memory backed by SQLite and on-device embeddings. No cloud, no keys, no per-call billing — and after one model download, no network at all.</p>

<div class="lm-badges" markdown>
[![PyPI - Version](https://img.shields.io/pypi/v/localmem-mcp.svg)](https://pypi.org/project/localmem-mcp/)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/localmem-mcp.svg)](https://pypi.org/project/localmem-mcp/)
</div>

<div class="lm-actions" markdown>
[Get started](getting-started/quickstart.md){ .md-button .md-button--primary }
[How search works](guide/how-search-works.md){ .md-button }
[GitHub](https://github.com/OpenAgentHQ/localmem-mcp){ .md-button }
</div>

<div class="lm-term">
<div class="lm-term__bar"><span></span><span></span><span></span><em>~/your-project</em></div>

```bash
$ uvx localmem-mcp
```

</div>

</div>

<div class="grid cards" markdown>

-   :material-rocket-launch: **Working in 30 seconds**

    One line in your MCP client config. `uvx` handles the rest — nothing to
    install, nothing to configure.

    [:octicons-arrow-right-24: Quickstart](getting-started/quickstart.md)

-   :material-lock: **Genuinely private**

    Memories live in one SQLite file you own. The only network call in the
    entire project is a one-time model download.

    [:octicons-arrow-right-24: Privacy model](guide/privacy.md)

-   :material-magnify: **Finds meaning, not keywords**

    "Which database did we pick?" finds "we went with SQLite" — while exact
    terms like error codes still land.

    [:octicons-arrow-right-24: How search works](guide/how-search-works.md)

-   :material-language-python: **A library, not just a server**

    The MCP server is a thin shell over a `MemoryStore` you can import and use
    in any Python project.

    [:octicons-arrow-right-24: Python library](guide/python-library.md)

</div>

## The problem

Every new session, your agent starts from nothing. You re-explain the project.
You re-state the decisions. You re-paste the context you pasted yesterday.

The usual fix is a hosted memory service — which means your project context,
your preferences, and your half-finished thoughts get shipped to someone else's
server, metered per call, behind an API key you have to manage.

## The fix

One line in your client config, and your agent gets three tools: store a memory,
search memories by meaning, recall a specific one. Everything lands on disk, in a
file you can read, back up, or delete.

=== "Store"

    > "Remember that we chose SQLite over Postgres for this project because it
    > ships in a single file."

    The agent calls `store_memory`. The text is embedded locally and written to
    a SQLite row.

=== "Recall, days later"

    > "What database did we pick, and why?"

    The agent calls `search_memory`. Semantic similarity surfaces the memory
    even though you never said the word "SQLite" this time.

=== "Under the hood"

    ```python
    from localmem_mcp import MemoryStore

    store = MemoryStore()
    store.add("We chose SQLite over Postgres", tags=["decision"])

    for hit in store.search("what database are we using?"):
        print(hit.score, hit.memory.content)
    ```

## What makes it different

|  | localmem-mcp | Hosted memory services |
| --- | --- | --- |
| Where memories live | A SQLite file you own | Someone else's database |
| Network calls at runtime | None | Every store and every recall |
| API keys | None | Required |
| Cost per call | Zero | Metered |
| Works offline | Yes | No |
| Deleting your data | `rm memories.db` | Trust their retention policy |

## Where to next

- **New here?** [Install it](getting-started/installation.md), then
  [connect your client](getting-started/clients.md).
- **Want the tool details?** The [MCP tools reference](guide/mcp-tools.md)
  covers all four tools and their arguments.
- **Curious how it works?** [Architecture](reference/architecture.md) walks the
  whole design in about five minutes.
- **Want to contribute?** The project is small enough to read in one sitting —
  see [Contributing](contributing.md).
