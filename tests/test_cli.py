"""Tests for the command-line entry point.

The shared flags (`--db`, `--model`, `--json`) are declared on a parent parser
and attached to every subparser, so they accept either order. That arrangement
has a sharp edge: a subparser writes into the same namespace as the main parser,
so an ordinary default silently overwrites a value parsed before the subcommand.
Most of what's here guards that.
"""

from __future__ import annotations

import json

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

def test_list_command_parses_filters_and_pagination():
    args = _build_parser().parse_args(
        [
            "list",
            "--tag",
            "decision",
            "--tag",
            "project",
            "--limit",
            "10",
            "--offset",
            "20",
            "--order",
            "oldest",
        ]
    )

    assert args.command == "list"
    assert args.tags == ["decision", "project"]
    assert args.limit == 10
    assert args.offset == 20
    assert args.order == "oldest"

def test_db_flag_without_a_subcommand():
    # How MCP clients invoke it: no subcommand, so `serve` is implied.
    db_path, _, _ = _parse(["--db", "/tmp/x.db"])

    assert db_path == "/tmp/x.db"


def test_shared_flag_defaults_when_unset():
    db_path, model_name, as_json = _parse(["stats"])

    assert db_path is None
    assert model_name == DEFAULT_MODEL
    assert as_json is False


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


def test_recall_missing_id_exits_nonzero(tmp_path, capsys):
    db = tmp_path / "cli.db"

    assert main(["--db", str(db), "recall", "999"]) == 1

    assert "no memory with id 999" in capsys.readouterr().err

def test_list_command_filters_and_paginates(tmp_path, capsys):
    db = tmp_path / "cli.db"

    first = _add_memory(db, "first decision", tags=["decision", "project"])
    _add_memory(db, "unrelated note", tags=["personal"])
    third = _add_memory(db, "second decision", tags=["decision", "project"])

    assert (
        main(
            [
                "--db",
                str(db),
                "list",
                "--tag",
                "decision",
                "--tag",
                "project",
                "--limit",
                "1",
                "--offset",
                "0",
                "--order",
                "newest",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out

    assert f"#{third.id}" in output
    assert f"#{first.id}" not in output
    assert "showing 1 of 2 memories" in output

def test_list_command_supports_oldest_order_and_offset(tmp_path, capsys):
    db = tmp_path / "cli.db"

    first = _add_memory(db, "first memory")
    second = _add_memory(db, "second memory")
    third = _add_memory(db, "third memory")

    assert (
        main(
            [
                "--db",
                str(db),
                "list",
                "--limit",
                "1",
                "--offset",
                "1",
                "--order",
                "oldest",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out

    assert f"#{second.id}" in output
    assert f"#{first.id}" not in output
    assert f"#{third.id}" not in output

def test_list_command_json_output_is_parseable(tmp_path, capsys):
    db = tmp_path / "cli.db"

    _add_memory(db, "decision one", tags=["decision"])
    _add_memory(db, "decision two", tags=["decision"])

    assert (
        main(
            [
                "--db",
                str(db),
                "--json",
                "list",
                "--tag",
                "decision",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)

    assert payload["count"] == 2
    assert payload["total"] == 2
    assert payload["offset"] == 0
    assert payload["limit"] == 20
    assert payload["order"] == "newest"
    assert payload["tags"] == ["decision"]
    assert len(payload["memories"]) == 2

def test_list_command_empty_store(tmp_path, capsys):
    db = tmp_path / "cli.db"

    assert main(["--db", str(db), "list"]) == 0

    output = capsys.readouterr().out

    assert "no memories" in output

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
