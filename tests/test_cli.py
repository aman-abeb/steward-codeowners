"""CLI smoke tests for ``steward expertise`` (plain-text table output)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from conftest import DAY, commit, write_file
from steward.cli import build_parser, main

ROW_RE = re.compile(r"^\S+\s{2,}(?:\w+ \(\d+\.\d+\))(?:, \w+ \(\d+\.\d+\))*$")


def _now() -> int:
    """Wall-clock timestamp; the CLI scores against the current time."""
    return int(datetime.now(UTC).timestamp())


def test_cli_prints_top_experts_table(repo: Path, capsys) -> None:
    now = _now()
    write_file(repo, "app.py", "a\n" * 4)
    commit(repo, "alice", now - DAY, "alice")
    write_file(repo, "app.py", "a\n" * 4 + "b\n" * 2)
    commit(repo, "bob", now - DAY, "bob")

    assert main(["expertise", str(repo)]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    assert ROW_RE.fullmatch(lines[0]), lines[0]
    assert lines[0].startswith("app.py")
    assert lines[0].index("alice") < lines[0].index("bob")


def test_cli_multiple_files_sorted_and_aligned(repo: Path, capsys) -> None:
    now = _now()
    write_file(repo, "zeta.py", "z\n")
    commit(repo, "alice", now - DAY, "z")
    write_file(repo, "alpha.py", "a\n")
    commit(repo, "bob", now - DAY, "a")

    assert main(["expertise", str(repo)]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert [line.split()[0] for line in lines] == ["alpha.py", "zeta.py"]
    assert all(ROW_RE.fullmatch(line) for line in lines)
    # the experts column starts at the same offset on every row
    assert lines[0].index("(") == lines[1].index("(")


def test_cli_top_option_limits_experts(repo: Path, capsys) -> None:
    now = _now()
    content = ""
    for author in ("carol", "bob", "alice"):
        content += f"{author}\n"
        write_file(repo, "shared.py", content)
        commit(repo, author, now - DAY, author)

    assert main(["expertise", str(repo), "--top", "1"]) == 0
    out = capsys.readouterr().out
    assert "alice" in out
    assert "bob" not in out
    assert "carol" not in out


def test_cli_half_life_option(repo: Path, capsys) -> None:
    now = _now()
    write_file(repo, "old.py", "x\n" * 100)
    commit(repo, "alice", now - 365 * DAY, "old")

    assert main(["expertise", str(repo), "--half-life", "365"]) == 0
    assert "alice (50.0)" in capsys.readouterr().out


def test_cli_empty_repo_message(repo: Path, capsys) -> None:
    assert main(["expertise", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "No git history" in out
    assert str(repo) in out


def test_cli_default_path_is_cwd(repo: Path, capsys, monkeypatch) -> None:
    now = _now()
    write_file(repo, "here.py", "x\n")
    commit(repo, "alice", now - DAY, "c")
    monkeypatch.chdir(repo)

    assert main(["expertise"]) == 0
    assert "here.py" in capsys.readouterr().out


def test_cli_requires_a_subcommand() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2


def test_parser_defaults() -> None:
    args = build_parser().parse_args(["expertise"])
    assert args.command == "expertise"
    assert args.path == "."
    assert args.half_life_days == 365.0
    assert args.top_n == 3
