# Installation

localmem-mcp needs **Python 3.10 or newer** and nothing else. No database
server, no API key, no account.

## As an MCP server

=== "uvx (recommended)"

    You don't need to install anything. [`uv`](https://docs.astral.sh/uv/) fetches
    and runs it on demand:

    ```bash
    uvx localmem-mcp
    ```

    This is what you'll put in your client config. It keeps the tool isolated
    from your project environments and updates cleanly.

=== "pip"

    ```bash
    pip install localmem-mcp
    ```

    Then `localmem-mcp` is on your PATH. Use this if you'd rather pin a version
    or don't have `uv`.

=== "pipx"

    ```bash
    pipx install localmem-mcp
    ```

    Isolated like `uvx`, but installed persistently.

Verify it:

```bash
localmem-mcp --version
localmem-mcp stats
```

`stats` prints where your database will live, how many memories are in it, and
which embedding model is configured. On a fresh install the count is zero — that
is the expected output, not an error.

## As a Python library

```bash
pip install localmem-mcp
```

```python
from localmem_mcp import MemoryStore
```

See the [Python library guide](../guide/python-library.md).

## The first-run model download

The first time you store or search a memory, `fastembed` downloads the embedding
model — about 90 MB, from Hugging Face. It's cached (`~/.cache/fastembed` by
default) and never fetched again.

!!! info "This is the only network call in the project"

    After that download, localmem-mcp works completely offline. Nothing you
    store is ever transmitted anywhere. See the
    [privacy model](../guide/privacy.md) for the full picture.

The model loads lazily — on your first `store_memory` or `search_memory` call,
not at startup. So the server itself starts instantly, and clients that spawn it
eagerly don't stall waiting on a download.

!!! tip "Pre-warming"

    To get the download out of the way before an agent needs it:

    ```bash
    localmem-mcp add "First memory — localmem is working"
    ```

## Installing from source

```bash
git clone https://github.com/OpenAgentHQ/localmem-mcp
cd localmem-mcp
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
```

On Windows the venv binaries live in `.venv\Scripts\`.

## Upgrading

=== "uvx"

    `uvx` resolves the latest version each run. To force a refresh:

    ```bash
    uvx --refresh localmem-mcp
    ```

=== "pip"

    ```bash
    pip install --upgrade localmem-mcp
    ```

Your memories are unaffected by upgrades — the database lives outside the
package, at `~/.localmem/memories.db` unless you've configured otherwise.

## Uninstalling

```bash
pip uninstall localmem-mcp
rm -rf ~/.localmem          # your memories
rm -rf ~/.cache/fastembed   # the cached model
```

Two directories and the tool is gone, along with everything it ever knew.
