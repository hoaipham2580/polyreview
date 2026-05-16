# Contributing to PolyReview

Thanks for the interest! A few quick notes to make contributions land smoothly.

## Dev setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install     # optional
```

## Before opening a PR

```bash
ruff check src tests
black src tests
mypy src
pytest
```

PRs should keep coverage at or above the current main branch.

## Adding a new agent

1. Add an entry under `_AGENT_FOCUSES` in `src/polyreview/agents.py`.
2. Update default `enabled_agents` in `polyreview.toml` if it should be on by default.
3. Add at least one test under `tests/`.

## Architecture overview

See the architecture diagram in [`README.md`](README.md). The orchestrator runs
agents concurrently with `asyncio.gather`, deduplicates findings via
`Finding.key()`, then asks the synthesizer to produce a one-line verdict.
