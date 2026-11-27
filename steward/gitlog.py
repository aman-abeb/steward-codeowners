"""Parse git history into per-file, per-author line changes."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

_RECORD_SEP = "\x1e"
_FIELD_SEP = "\x1f"


@dataclass
class FileChange:
    """A single file's line changes within one commit."""

    path: str
    author: str
    timestamp: int
    lines_added: int
    lines_deleted: int


def _git(repo: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def _clean_path(raw: str) -> str:
    """Resolve rename notation (``old => new``) to the new path."""
    path = raw
    if " => " in path:
        path = path.partition(" => ")[2].replace("}", "")
    return path


def parse_git_log(repo: Path) -> list[FileChange]:
    """Return per-file line changes with author and commit timestamp.

    Binary files (reported as ``-`` by numstat) are excluded. Rename
    detection is enabled so a file's history follows it across renames.
    Repositories without any commits yield an empty list.
    """
    repo = Path(repo)
    probe = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "HEAD"],
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        return []

    fmt = "%x1e%H%x1f%an%x1f%ae%x1f%ad"
    out = _git(
        repo,
        ["log", "--numstat", "-M", f"--format={fmt}", "--date=unix"],
    ).stdout

    changes: list[FileChange] = []
    author = ""
    timestamp = 0
    # NOTE: split on "\n" only -- str.splitlines() also breaks on \x1e (record
    # separator), which would strip the commit-header marker and lose the
    # author/timestamp for every numstat line that follows it.
    for line in out.split("\n"):
        if not line:
            continue
        if line.startswith(_RECORD_SEP):
            _hash, author, _email, ts = line[1:].split(_FIELD_SEP)
            timestamp = int(ts)
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, deleted, raw_path = parts
        if added == "-" or deleted == "-":
            continue  # binary file
        changes.append(
            FileChange(
                path=_clean_path(raw_path),
                author=author,
                timestamp=timestamp,
                lines_added=int(added),
                lines_deleted=int(deleted),
            )
        )
    return changes
