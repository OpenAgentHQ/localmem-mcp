"""Tests for the command-line entry point.

The shared flags (`--db`, `--model`, `--json`) are declared on a parent parser
and attached to every subparser, so they accept either order. That arrangement
has a sharp edge: a subparser writes into the same namespace as the main parser,
so an ordinary default silently overwrites a value parsed before the subcommand.
Most of what's here guards that.
"""

from __future__ import annotations

import io
import json
import sys

import pytest
from test_store import StubEmbedder

from localmem_mcp.cli import _build_parser, _days_arg, _shared, main
from localmem_mcp.store import DEFAULT_MODEL, MemoryStore, _days_ago


def _parse(argv: list[str]):
    return _shared(_build_parser().parse_args(argv))


@pytest.mark.parametrize(
    "argv",
    [
        ["--db", "/tmp/x.db", "stats"],
        ["stats", "--db", "/tmp/x.db"],
        ["--db", "/tmp/x.db", "search", "q"],
        ["search", "q", "--db", "/tmp/x.db"],
        ["--db", "/tmp/x.db", "add", "note"],
        ["add", "note", "--db", "/tmp/x.db"],
        ["--db", "/tmp/x.db", "recall"],
        ["--db", "/tmp/x.db", "forget", "7"],
        ["forget", "7", "--db", "/tmp/x.db"],
        ["--db", "/tmp/x.db", "serve"],
    ],
)
def test_db_flag_survives_either_side_of_the_subcommand(argv):
    db_path, _, _ = _parse(argv)

    assert db_path == "/tmp/x.db"


def test_db_flag_without_a_subcommand():
    # How MCP clients invoke it: no subcommand, so `serve` is implied.
    db_path, _, _ = _parse(["--db", "/tmp/x.db"])

    assert db_path == "/tmp/x.db"


def test_shared_flag_defaults_when_unset():
    db_path, model_name, as_json = _parse(["stats"])

    assert db_path is None
    assert model_name == DEFAULT_MODEL
    assert as_json is False


def test_model_environment_variable_is_used_when_flag_is_unset(monkeypatch):
    monkeypatch.setenv("LOCALMEM_MODEL", "BAAI/bge-base-en-v1.5")

    _, model_name, _ = _parse(["stats"])

    assert model_name == "BAAI/bge-base-en-v1.5"


@pytest.mark.parametrize(
    "argv",
    [["--model", "custom/model", "stats"], ["stats", "--model", "custom/model"]],
)
def test_model_flag_survives_either_side(argv):
    _, model_name, _ = _parse(argv)

    assert model_name == "custom/model"


@pytest.mark.parametrize("argv", [["--json", "stats"], ["stats", "--json"]])
def test_json_flag_survives_either_side(argv):
    _, _, as_json = _parse(argv)

    assert as_json is True


def test_the_last_occurrence_wins():
    db_path, _, _ = _parse(["--db", "/tmp/first.db", "stats", "--db", "/tmp/second.db"])

    assert db_path == "/tmp/second.db"


# -- end to end, against a real database ------------------------------------
#
# These use the store for real, so they need embeddings. `stats` and `recall`
# never embed anything, which keeps them offline and fast.


def test_stats_reports_the_database_given_before_the_subcommand(tmp_path, capsys):
    db = tmp_path / "cli.db"

    assert main(["--db", str(db), "stats"]) == 0

    assert str(db) in capsys.readouterr().out


def test_stats_reports_the_database_given_after_the_subcommand(tmp_path, capsys):
    db = tmp_path / "cli.db"

    assert main(["stats", "--db", str(db)]) == 0

    assert str(db) in capsys.readouterr().out


def test_json_output_is_parseable(tmp_path, capsys):
    db = tmp_path / "cli.db"

    assert main(["--db", str(db), "--json", "stats"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["memories"] == 0
    assert payload["db_path"] == str(db)


def test_recall_missing_id_closes_store(tmp_path, capsys, monkeypatch):
    db = tmp_path / "cli.db"
    closed = []

    original_close = MemoryStore.close

    def tracking_close(store):
        closed.append(True)
        original_close(store)

    monkeypatch.setattr(MemoryStore, "close", tracking_close)

    assert main(["--db", str(db), "recall", "999"]) == 1

    assert "no memory with id 999" in capsys.readouterr().err
    assert closed == [True]


# -- forget ----------------------------------------------------------------
#
# The forget path never embeds, so these stay offline and fast. Memories are
# seeded through a StubEmbedder store; the CLI then opens the same database.


def _add_memory(db, content, tags=None):
    with MemoryStore(db_path=db, embedder=StubEmbedder()) as s:
        return s.add(content, tags=tags)


def test_days_arg_parses_durations():
    assert _days_arg("30") == 30
    assert _days_arg("90d") == 90
    assert _days_arg("8w") == 56
    assert _days_arg(" 7d ") == 7


def test_days_arg_rejects_garbage():
    from argparse import ArgumentTypeError

    with pytest.raises(ArgumentTypeError):
        _days_arg("soon")
    with pytest.raises(ArgumentTypeError):
        _days_arg("-1")


def test_forget_single_id_deletes(tmp_path, capsys):
    db = tmp_path / "cli.db"
    memory = _add_memory(db, "temporary note")

    assert main(["--db", str(db), "forget", str(memory.id)]) == 0

    assert f"forgot #{memory.id}" in capsys.readouterr().out
    with MemoryStore(db_path=db, embedder=StubEmbedder()) as s:
        assert s.get(memory.id) is None


def test_forget_single_id_missing_exits_nonzero(tmp_path, capsys):
    db = tmp_path / "cli.db"

    assert main(["--db", str(db), "forget", "999"]) == 1

    assert "no memory with id 999" in capsys.readouterr().err


def test_forget_bulk_previews_and_requires_confirmation(tmp_path, capsys, monkeypatch):
    db = tmp_path / "cli.db"
    memory = _add_memory(db, "stale note", tags=["stale"])
    monkeypatch.setattr("builtins.input", lambda: "n")

    assert main(["--db", str(db), "forget", "--tag", "stale"]) == 1

    captured = capsys.readouterr()
    assert "stale note" in captured.out  # preview shown before deleting
    assert "aborted" in captured.err
    with MemoryStore(db_path=db, embedder=StubEmbedder()) as s:
        assert s.get(memory.id) is not None  # nothing was deleted


def test_forget_bulk_confirms_with_yes_input(tmp_path, capsys, monkeypatch):
    db = tmp_path / "cli.db"
    memory = _add_memory(db, "stale note", tags=["stale"])
    monkeypatch.setattr("builtins.input", lambda: "y")

    assert main(["--db", str(db), "forget", "--tag", "stale"]) == 0

    with MemoryStore(db_path=db, embedder=StubEmbedder()) as s:
        assert s.get(memory.id) is None


def test_forget_bulk_yes_flag_skips_prompt(tmp_path, capsys):
    db = tmp_path / "cli.db"
    memory = _add_memory(db, "stale note", tags=["stale"])

    assert main(["--db", str(db), "forget", "--tag", "stale", "--yes"]) == 0

    assert "forgot 1 memories" in capsys.readouterr().out
    with MemoryStore(db_path=db, embedder=StubEmbedder()) as s:
        assert s.get(memory.id) is None


def test_forget_bulk_by_age(tmp_path, capsys):
    db = tmp_path / "cli.db"
    with MemoryStore(db_path=db, embedder=StubEmbedder()) as s:
        old = s.add("ancient note")
        s.add("fresh note")
        s._conn.execute(
            "UPDATE memories SET created_at = ? WHERE id = ?",
            (_days_ago(200), old.id),
        )
        s._conn.commit()

    assert main(["--db", str(db), "forget", "--older-than", "90d", "--yes"]) == 0

    with MemoryStore(db_path=db, embedder=StubEmbedder()) as s:
        assert s.count() == 1
        assert s.get(old.id) is None


def test_forget_bulk_requires_a_filter(tmp_path, capsys):
    db = tmp_path / "cli.db"
    _add_memory(db, "keep me")

    assert main(["--db", str(db), "forget"]) == 2

    assert "at least one" in capsys.readouterr().err
    with MemoryStore(db_path=db, embedder=StubEmbedder()) as s:
        assert s.count() == 1


def test_forget_nothing_matches(tmp_path, capsys):
    db = tmp_path / "cli.db"
    _add_memory(db, "a note", tags=["current"])

    assert main(["--db", str(db), "forget", "--tag", "stale"]) == 0

    assert "nothing matches those filters" in capsys.readouterr().err


def test_forget_bulk_json_output_is_parseable(tmp_path, capsys):
    db = tmp_path / "cli.db"
    _add_memory(db, "stale note", tags=["stale"])

    assert main(["--db", str(db), "--json", "forget", "--tag", "stale", "--yes"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == {"deleted": True, "count": 1}


# -- export and import -------------------------------------------------------
#
# The CLI builds its own store, which would reach for fastembed. `_offline`
# swaps in the StubEmbedder so these stay fast and offline like the rest.


@pytest.fixture
def _offline(monkeypatch):
    def _store(db_path=None, model_name=None):
        return MemoryStore(db_path=db_path, embedder=StubEmbedder())

    # Fetch the module out of sys.modules rather than by dotted name: the
    # package re-exports `main` as a function, which shadows the submodule of
    # the same name for both `import` and monkeypatch's string lookup.
    monkeypatch.setattr(sys.modules["localmem_mcp.commands.main"], "MemoryStore", _store)


def test_export_writes_one_json_object_per_line(tmp_path, capsys):
    db = tmp_path / "cli.db"
    _add_memory(db, "first note", tags=["work"])
    _add_memory(db, "second note")

    assert main(["--db", str(db), "export"]) == 0

    lines = capsys.readouterr().out.strip().splitlines()
    assert [json.loads(line)["content"] for line in lines] == ["first note", "second note"]
    assert json.loads(lines[0])["tags"] == ["work"]


def test_export_filters_by_tag(tmp_path, capsys):
    db = tmp_path / "cli.db"
    _add_memory(db, "work note", tags=["work"])
    _add_memory(db, "home note", tags=["home"])

    assert main(["--db", str(db), "export", "--tag", "work"]) == 0

    lines = capsys.readouterr().out.strip().splitlines()
    assert [json.loads(line)["content"] for line in lines] == ["work note"]


def test_export_with_embeddings_includes_the_vector(tmp_path, capsys):
    db = tmp_path / "cli.db"
    _add_memory(db, "a note")

    assert main(["--db", str(db), "export", "--with-embeddings"]) == 0

    record = json.loads(capsys.readouterr().out.strip())
    assert record["embedding_model"] == "stub-bow"
    assert record["dim"] == len(record["embedding"])


def test_export_import_round_trip_through_files(tmp_path, capsys, _offline):
    source_db = tmp_path / "source.db"
    _add_memory(source_db, "sqlite storage", tags=["decision"])
    _add_memory(source_db, "coffee in the morning")

    assert main(["--db", str(source_db), "export"]) == 0
    dump = tmp_path / "memories.jsonl"
    dump.write_text(capsys.readouterr().out, encoding="utf-8")

    fresh_db = tmp_path / "fresh.db"
    assert main(["--db", str(fresh_db), "import", str(dump)]) == 0

    assert "imported 2 memories" in capsys.readouterr().out
    with MemoryStore(db_path=fresh_db, embedder=StubEmbedder()) as s:
        restored = [{k: v for k, v in r.items() if k != "id"} for r in s.export_records()]
    with MemoryStore(db_path=source_db, embedder=StubEmbedder()) as s:
        original = [{k: v for k, v in r.items() if k != "id"} for r in s.export_records()]
    assert restored == original


def test_import_reads_stdin_by_default(tmp_path, capsys, monkeypatch, _offline):
    db = tmp_path / "cli.db"
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"content": "piped note"}) + "\n"))

    assert main(["--db", str(db), "import"]) == 0

    with MemoryStore(db_path=db, embedder=StubEmbedder()) as s:
        assert s.recent()[0].content == "piped note"


def test_import_skips_malformed_lines_and_exits_nonzero(tmp_path, capsys, _offline):
    db = tmp_path / "cli.db"
    dump = tmp_path / "memories.jsonl"
    dump.write_text(
        json.dumps({"content": "good"}) + "\n{broken\n" + json.dumps({"content": "also good"}),
        encoding="utf-8",
    )

    assert main(["--db", str(db), "import", str(dump)]) == 1

    captured = capsys.readouterr()
    assert "line 2" in captured.err  # the bad line is named, not fatal
    assert "imported 2 memories" in captured.out
    with MemoryStore(db_path=db, embedder=StubEmbedder()) as s:
        assert s.count() == 2


def test_import_dry_run_stores_nothing(tmp_path, capsys, _offline):
    db = tmp_path / "cli.db"
    dump = tmp_path / "memories.jsonl"
    dump.write_text(json.dumps({"content": "a note"}), encoding="utf-8")

    assert main(["--db", str(db), "import", str(dump), "--dry-run"]) == 0

    assert "would import 1 memories" in capsys.readouterr().out
    with MemoryStore(db_path=db, embedder=StubEmbedder()) as s:
        assert s.count() == 0


def test_import_twice_does_not_duplicate(tmp_path, capsys, _offline):
    db = tmp_path / "cli.db"
    dump = tmp_path / "memories.jsonl"
    dump.write_text(json.dumps({"content": "a note"}), encoding="utf-8")

    assert main(["--db", str(db), "import", str(dump)]) == 0
    assert main(["--db", str(db), "import", str(dump)]) == 0

    assert "skipped 1 duplicates" in capsys.readouterr().out
    with MemoryStore(db_path=db, embedder=StubEmbedder()) as s:
        assert s.count() == 1


def test_import_json_output_is_parseable(tmp_path, capsys, _offline):
    db = tmp_path / "cli.db"
    dump = tmp_path / "memories.jsonl"
    dump.write_text(json.dumps({"content": "a note"}), encoding="utf-8")

    assert main(["--db", str(db), "--json", "import", str(dump)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["imported"] == 1
    assert payload["failed"] == 0
    assert payload["dry_run"] is False


def test_import_missing_file_exits_two(tmp_path, capsys, _offline):
    db = tmp_path / "cli.db"

    assert main(["--db", str(db), "import", str(tmp_path / "nope.jsonl")]) == 2

    assert "cannot read" in capsys.readouterr().err


# -- list ------------------------------------------------------------------


def test_list_command_text_output(tmp_path, capsys):
    db = tmp_path / "cli.db"
    _add_memory(db, "first note")
    _add_memory(db, "second note")

    assert main(["--db", str(db), "list"]) == 0

    out = capsys.readouterr().out
    assert "second note" in out
    assert "first note" in out


def test_list_command_empty_store_text_output(tmp_path, capsys):
    db = tmp_path / "cli.db"

    assert main(["--db", str(db), "list"]) == 0

    assert "no memories found" in capsys.readouterr().out


def test_list_command_json_output(tmp_path, capsys):
    db = tmp_path / "cli.db"
    _add_memory(db, "work note 1", tags=["work"])
    _add_memory(db, "work note 2", tags=["work"])
    _add_memory(db, "personal note", tags=["personal"])

    assert (
        main(
            [
                "--db",
                str(db),
                "--json",
                "list",
                "--tag",
                "work",
                "-n",
                "1",
                "--order",
                "oldest",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert payload["total"] == 2
    assert payload["limit"] == 1
    assert payload["offset"] == 0
    assert payload["order"] == "oldest"
    assert payload["tags"] == ["work"]
    assert payload["memories"][0]["content"] == "work note 1"
