"""Recency-weighted expertise scoring over git authorship."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from steward.gitlog import parse_git_log

DEFAULT_HALF_LIFE_DAYS = 365.0
DEFAULT_TOP_N = 3
_SECONDS_PER_DAY = 86400.0


def decay_score(
    lines: int,
    age_days: float,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
) -> float:
    """Exponential half-life decay: ``lines * 0.5 ** (age / half_life)``."""
    if lines <= 0 or half_life_days <= 0:
        return 0.0
    return lines * (0.5 ** (max(age_days, 0.0) / half_life_days))


def compute_expertise(
    repo: Path,
    now: float | None = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, list[tuple[str, float]]]:
    """Return ``{file: [(author, score), ...]}`` with top_n experts per file.

    Scores are aggregated per file per author and ranked descending; ties
    are broken deterministically by author name (ascending).
    """
    if now is None:
        now = datetime.now(UTC).timestamp()
    scores: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for change in parse_git_log(Path(repo)):
        age_days = (now - change.timestamp) / _SECONDS_PER_DAY
        lines = change.lines_added + change.lines_deleted
        scores[change.path][change.author] += decay_score(lines, age_days, half_life_days)
    ranked: dict[str, list[tuple[str, float]]] = {}
    for path in sorted(scores):
        experts = sorted(scores[path].items(), key=lambda item: (-item[1], item[0]))
        ranked[path] = experts[:top_n]
    return ranked
