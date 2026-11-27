"""Offline tests for the steward expertise engine."""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from steward.cli import main
from steward.expertise import compute_expertise, decay_score
from steward.gitlog import parse_git_log

NOW = int(datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC).timestamp())
DAY = 86400


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def _commit(repo: Path, author: str, timestamp: int, message: str) -> None:
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": author,
            "GIT_AUTHOR_EMAIL": f"{author}@example.com",
            "GIT_COMMITTER_NAME": author,
            "GIT_COMMITTER_EMAIL": f"{author}@example.com",
            "GIT_AUTHOR_DATE": f"{timestamp} +0000",
            "GIT_COMMITTER_DATE": f"{timestamp} +0000",
        }
    )
    _git(repo, "commit", "-m", message, env=env)


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    return repo


def _write(repo: Path, name: str, content: str) -> None:
    (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", name)


def test_decay_score_halves_at_half_life() -> None:
    assert decay_score(100, 0) == 100.0
    assert decay_score(100, 365) == 50.0
    assert decay_score(0, 0) == 0.0


def test_recent_commit_outweighs_old(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _write(repo, "app.py", "a\n" * 10)
    _commit(repo, "alice", NOW - 900 * DAY, "old")
    _write(repo, "app.py", "a\n" * 10 + "b\n" * 10)
    _commit(repo, "bob", NOW - DAY, "recent")

    results = compute_expertise(repo, now=NOW, half_life_days=365)
    experts = results["app.py"]
    assert experts[0][0] == "bob"
    assert experts[0][1] > experts[1][1]


def test_tie_break_by_author_name(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _write(repo, "lib.py", "x\n" * 5)
    _commit(repo, "bob", NOW - DAY, "bob")
    _write(repo, "lib.py", "x\n" * 5 + "y\n" * 5)
    _commit(repo, "alice", NOW - DAY, "alice")

    results = compute_expertise(repo, now=NOW)
    assert [name for name, _ in results["lib.py"]] == ["alice", "bob"]


def test_binary_files_excluded(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "data.bin").write_bytes(b"\x00\x01\x02\x03")
    _git(repo, "add", "data.bin")
    _commit(repo, "alice", NOW - DAY, "binary")
    _write(repo, "code.py", "print('hi')\n")
    _commit(repo, "alice", NOW - DAY, "code")

    results = compute_expertise(repo, now=NOW)
    assert "data.bin" not in results
    assert "code.py" in results


def test_rename_following(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _write(repo, "old.txt", "one\n")
    _commit(repo, "alice", NOW - 10 * DAY, "create")
    _git(repo, "mv", "old.txt", "new.txt")
    (repo / "new.txt").write_text("one\ntwo\n", encoding="utf-8")
    _git(repo, "add", "new.txt")
    _commit(repo, "alice", NOW - DAY, "rename")

    results = compute_expertise(repo, now=NOW)
    assert "new.txt" in results
    assert results["new.txt"][0][0] == "alice"
    changes = parse_git_log(repo)
    assert any(c.path == "new.txt" and c.lines_added == 1 for c in changes)


def test_empty_repo_handled(tmp_path: Path, capsys) -> None:
    repo = _make_repo(tmp_path)
    assert compute_expertise(repo, now=NOW) == {}
    assert main(["expertise", str(repo)]) == 0
    assert "No git history" in capsys.readouterr().out


def test_cli_prints_table(tmp_path: Path, capsys) -> None:
    repo = _make_repo(tmp_path)
    _write(repo, "app.py", "a\n" * 4)
    _commit(repo, "alice", NOW - DAY, "work")
    assert main(["expertise", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "app.py" in out
    assert "alice" in out
