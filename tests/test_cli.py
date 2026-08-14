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

from localmem_mcp.cli import _build_parser, _shared, main
from localmem_mcp.store import DEFAULT_MODEL


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
