"""Stdlib argparse command-line interface for steward."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from steward.expertise import (
    DEFAULT_HALF_LIFE_DAYS,
    DEFAULT_TOP_N,
    compute_expertise,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steward",
        description="Recency-weighted git authorship tools.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    exp = sub.add_parser("expertise", help="Show top experts per file.")
    exp.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository path (default: current directory).",
    )
    exp.add_argument(
        "--half-life",
        dest="half_life_days",
        type=float,
        default=DEFAULT_HALF_LIFE_DAYS,
        help="Half-life in days for the decay function (default: 365).",
    )
    exp.add_argument(
        "--top",
        dest="top_n",
        type=int,
        default=DEFAULT_TOP_N,
        help="Number of experts to show per file (default: 3).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "expertise":
        repo = Path(args.path).resolve()
        results = compute_expertise(
            repo,
            half_life_days=args.half_life_days,
            top_n=args.top_n,
        )
        if not results:
            print(f"No git history found in {repo}.")
            return 0
        width = max(len(path) for path in results)
        for path, experts in results.items():
            names = ", ".join(f"{author} ({score:.1f})" for author, score in experts)
            print(f"{path:<{width}}  {names}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
