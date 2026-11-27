"""Shared fixtures: throwaway git repos with controlled commit dates.

Every test runs fully offline. Fixture repositories are created in
``tmp_path`` with ``git init`` and commits whose ``GIT_AUTHOR_DATE`` and
``GIT_COMMITTER_DATE`` are pinned, so recency-weighted scores are fully
deterministic. Test modules import the helpers below (``commit``,
``write_file``, ``write_binary``, ``rename_file``) to craft histories.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

NOW = int(datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC).timestamp())
DAY = 86400


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> None:
    """Run a git command inside ``repo``, raising on failure."""
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def commit(repo: Path, author: str, timestamp: int, message: str) -> None:
    """Commit staged changes with a pinned author identity and date."""
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
    git(repo, "commit", "-m", message, env=env)


def write_file(repo: Path, name: str, content: str) -> None:
    """Write a UTF-8 text file (creating parent dirs) and stage it."""
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    git(repo, "add", "--", name)


def write_binary(repo: Path, name: str, data: bytes) -> None:
    """Write a binary blob (NUL bytes make git treat it as binary) and stage it."""
    (repo / name).write_bytes(data)
    git(repo, "add", "--", name)


def rename_file(repo: Path, old: str, new: str) -> None:
    """``git mv`` a tracked file so rename following can be exercised."""
    git(repo, "mv", old, new)


@pytest.fixture
def make_repo(tmp_path: Path) -> Callable[..., Path]:
    """Factory fixture building an initialized git repo under ``tmp_path``."""

    def _make(name: str = "repo") -> Path:
        repo = tmp_path / name
        repo.mkdir()
        git(repo, "init")
        git(repo, "config", "user.name", "Test")
        git(repo, "config", "user.email", "test@example.com")
        return repo

    return _make


@pytest.fixture
def repo(make_repo: Callable[..., Path]) -> Path:
    """A fresh, empty git repository."""
    return make_repo()


@pytest.fixture
def now() -> int:
    """Fixed reference timestamp (unix seconds) for deterministic decay."""
    return NOW
