# steward-codeowners

<!-- builder:badges:start -->
[![CI](https://github.com/aman-abeb/steward-codeowners/actions/workflows/ci.yml/badge.svg)](https://github.com/aman-abeb/steward-codeowners/actions/workflows/ci.yml) ![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white) ![License: MIT](https://img.shields.io/badge/license-MIT-green)
<!-- builder:badges:end -->


`steward` ranks file expertise from git history using a recency-weighted
(exponential half-life decay) authorship model: the more lines an author
touched in a file, and the more recently they touched them, the higher
their expertise score.

## Install

```bash
pip install -e .
```

This provides the `steward` console script.

## Usage

```bash
steward expertise [path] [--half-life DAYS] [--top N]
```

`steward expertise` prints a plain-text table of every file found in the
repository history together with its top experts (default: top 3), scored
with:

```text
score = lines * 0.5 ** (age_days / half_life_days)
```

### Example

```text
$ steward expertise .
app.py      alice (9.9), bob (1.8)
lib.py      alice (5.0), bob (5.0)
```

Ties are broken deterministically by author name. Binary files are
excluded, and renames are followed, so a file keeps its history across
renames. Repositories without commits are handled gracefully with a
friendly message instead of an error.

## Development

```bash
pip install pytest
pytest
```

The test suite runs fully offline: it builds throwaway repositories in
`tmp_path` with controlled `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE` values
and asserts decay ordering, tie-breaking, binary-file exclusion, rename
following, and empty-repo handling.

## License

MIT
