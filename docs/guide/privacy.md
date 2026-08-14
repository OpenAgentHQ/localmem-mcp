# Privacy model

The premise of localmem-mcp is simple: **your memories never leave your
machine.** This page is the precise version of that claim, including its limits.

## What runs locally

Everything.

- **Storage** — one SQLite file on your disk.
- **Embeddings** — computed on-device by [fastembed](https://github.com/qdrant/fastembed)
  running an ONNX model on your CPU.
- **Search** — plain arithmetic over vectors already on your disk.

No API keys exist anywhere in the project, because there's nothing to
authenticate to.

## The one network call

The first time you store or search, fastembed downloads the embedding model
(~90 MB) from Hugging Face and caches it. That request contains nothing but the
model name — no memory content, because at that point nothing has been embedded
yet.

After the download, localmem-mcp works with your network cable unplugged.

!!! success "Verify it yourself"

    Store some memories, then cut off network access and keep using it. Or watch
    it with `tcpdump`, Little Snitch, or your firewall of choice. The claim is
    meant to be checkable, not taken on faith.

## Where your data lives

```
~/.localmem/memories.db        your memories (SQLite)
~/.cache/fastembed/            the downloaded model
```

The database is a normal SQLite file. You can open it with any SQLite browser,
back it up, sync it, or move it. Paths are configurable — see
[Configuration](configuration.md).

To delete everything:

```bash
rm -rf ~/.localmem ~/.cache/fastembed
```

There is no server-side copy, no retention window, and no account to close. When
the file is gone, the memory is gone.

## What is not protected

Being precise about the limits matters more than the pitch.

### Memories are stored unencrypted

The database is plain SQLite, protected by your filesystem permissions and
nothing else. Anyone who can read the file can read your memories.

This is a deliberate trade — encryption at rest would mean key management, which
means either a password prompt on every agent call or a key sitting next to the
data. If you need it, put the database on an encrypted volume (FileVault,
LUKS, BitLocker), which is the right layer for this.

### Recalled memories enter the model's context

The whole point is that an agent can recall what it stored. When it does, that
text goes into the model's context — and if you're using a hosted model, that
context goes to the model provider, exactly like anything else you type.

localmem-mcp guarantees your memories aren't *stored* remotely. It cannot
control what your agent does with one after recalling it.

!!! warning "Store accordingly"

    Don't put credentials, secrets, or anything you wouldn't paste into a chat
    into agent memory. A memory tool is not a password manager.

### Stored memories are recallable input

Anything an agent stores, it can later recall — and recalled text influences its
behaviour. If something untrustworthy gets stored, it can influence a later
session. Treat stored memories with the same care as any other context you feed
a model.

### Shared databases are shared

If several clients point at the same database, they share memories. That's often
what you want; occasionally it isn't. Per-project databases are one flag away —
see [Configuration](configuration.md).

## Summary

| | |
| --- | --- |
| Memory content sent over the network | Never |
| Telemetry, analytics, update pings | None |
| API keys or accounts | None |
| Network calls at runtime | None after the one-time model download |
| Works fully offline | Yes |
| Encrypted at rest | No — use an encrypted volume |
| Recalled memories reach your model provider | Yes, like any other context |
| Deleting your data | Delete the file |

## Reporting a problem

Anything that sends memory content off the machine is a security vulnerability,
not a bug. Please report it privately — see the
[security policy](https://github.com/OpenAgentHQ/localmem-mcp/blob/main/SECURITY.md).
