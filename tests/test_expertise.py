"""Offline tests for the recency-weighted expertise engine.

Repositories are built with the shared ``conftest`` fixtures using pinned
``GIT_AUTHOR_DATE`` values, so decay ordering, tie-breaking, rename
following, and binary exclusion are all asserted exactly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import DAY, commit, rename_file, write_binary, write_file
from steward.expertise import compute_expertise, decay_score
from steward.gitlog import parse_git_log


def test_decay_score_halves_at_half_life() -> None:
    assert decay_score(100, 0) == 100.0
    assert decay_score(100, 365) == 50.0
    assert decay_score(100, 730) == 25.0


def test_decay_score_edge_cases() -> None:
    assert decay_score(0, 0) == 0.0
    assert decay_score(-3, 0) == 0.0
    assert decay_score(100, 10, half_life_days=0) == 0.0
    # future-dated commits clamp to age zero
    assert decay_score(100, -5) == 100.0


def test_recent_commit_outweighs_old(repo: Path, now: int) -> None:
    write_file(repo, "app.py", "a\n" * 10)
    commit(repo, "alice", now - 900 * DAY, "old")
    write_file(repo, "app.py", "a\n" * 10 + "b\n" * 10)
    commit(repo, "bob", now - DAY, "recent")

    experts = compute_expertise(repo, now=now, half_life_days=365)["app.py"]
    assert experts[0][0] == "bob"
    assert experts[0][1] == pytest.approx(decay_score(10, 1, 365))
    assert experts[1][1] == pytest.approx(decay_score(10, 900, 365))
    assert experts[0][1] > experts[1][1]


def test_tie_break_by_author_name(repo: Path, now: int) -> None:
    write_file(repo, "lib.py", "x\n" * 5)
    commit(repo, "bob", now - DAY, "bob")
    write_file(repo, "lib.py", "x\n" * 5 + "y\n" * 5)
    commit(repo, "alice", now - DAY, "alice")

    experts = compute_expertise(repo, now=now)["lib.py"]
    assert [name for name, _ in experts] == ["alice", "bob"]
    assert experts[0][1] == pytest.approx(decay_score(5, 1, 365))
    assert experts[1][1] == pytest.approx(decay_score(5, 1, 365))


def test_binary_files_excluded(repo: Path, now: int) -> None:
    write_binary(repo, "data.bin", b"\x00\x01\x02\x03\x00\xff")
    commit(repo, "alice", now - DAY, "binary")
    write_file(repo, "code.py", "print('hi')\n")
    commit(repo, "alice", now - DAY, "code")

    changes = parse_git_log(repo)
    assert all(change.path != "data.bin" for change in changes)
    assert set(compute_expertise(repo, now=now)) == {"code.py"}


def test_rename_following(repo: Path, now: int) -> None:
    write_file(repo, "old.txt", "line\n" * 20)
    commit(repo, "alice", now - 10 * DAY, "create")
    rename_file(repo, "old.txt", "new.txt")
    write_file(repo, "new.txt", "line\n" * 20 + "extra\n")
    commit(repo, "alice", now - DAY, "rename")

    changes = parse_git_log(repo)
    # the rename commit is attributed to the new path, never "old => new"
    assert not any("=>" in change.path for change in changes)
    rename_entries = [c for c in changes if c.path == "new.txt"]
    assert any(c.lines_added == 1 and c.author == "alice" for c in rename_entries)

    results = compute_expertise(repo, now=now)
    assert results["new.txt"][0][0] == "alice"
    assert results["new.txt"][0][1] == pytest.approx(decay_score(1, 1, 365))
    # the pre-rename creation commit still scores under the original path
    assert results["old.txt"][0][1] == pytest.approx(decay_score(20, 10, 365))


def test_empty_repo(repo: Path, now: int) -> None:
    assert parse_git_log(repo) == []
    assert compute_expertise(repo, now=now) == {}


def test_non_git_directory(tmp_path: Path, now: int) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert parse_git_log(plain) == []
    assert compute_expertise(plain, now=now) == {}


def test_top_n_limits_experts(repo: Path, now: int) -> None:
    content = ""
    for author in ("dave", "carol", "bob", "alice"):
        content += f"{author}\n"
        write_file(repo, "shared.py", content)
        commit(repo, author, now - DAY, author)

    top2 = compute_expertise(repo, now=now, top_n=2)["shared.py"]
    assert [name for name, _ in top2] == ["alice", "bob"]
    top3 = compute_expertise(repo, now=now, top_n=3)["shared.py"]
    assert [name for name, _ in top3] == ["alice", "bob", "carol"]


def test_results_sorted_by_path(repo: Path, now: int) -> None:
    write_file(repo, "zeta.py", "z\n")
    commit(repo, "alice", now - DAY, "z")
    write_file(repo, "pkg/mod.py", "m\n")
    commit(repo, "alice", now - DAY, "m")
    write_file(repo, "alpha.py", "a\n")
    commit(repo, "alice", now - DAY, "a")

    assert list(compute_expertise(repo, now=now)) == ["alpha.py", "pkg/mod.py", "zeta.py"]


def test_half_life_parameter_scales_scores(repo: Path, now: int) -> None:
    write_file(repo, "f.py", "x\n" * 8)
    commit(repo, "alice", now - 30 * DAY, "c")

    slow = compute_expertise(repo, now=now, half_life_days=365)["f.py"][0][1]
    fast = compute_expertise(repo, now=now, half_life_days=1)["f.py"][0][1]
    assert slow == pytest.approx(decay_score(8, 30, 365))
    assert fast == pytest.approx(decay_score(8, 30, 1))
    assert fast < slow
