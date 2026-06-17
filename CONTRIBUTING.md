# Contributing to settfex

Thanks for your interest in improving **settfex** — an async Python library for
SET (Stock Exchange of Thailand) and TFEX (Thailand Futures Exchange) data.

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for dependency management

## Getting started

```bash
git clone https://github.com/lumduan/settfex.git
cd settfex
uv sync --group dev
uv run pre-commit install   # run the quality gate automatically on every commit
```

All Python work goes through `uv` — use `uv add <pkg>` / `uv add --group dev <pkg>`
to manage dependencies (never `pip`/`poetry`/`conda`), and run code with
`uv run python ...`. `uv.lock` is committed and must stay in sync.

## Quality gate

Every change must pass the same checks CI runs:

```bash
uv run ruff check .            # lint
uv run ruff format --check .   # formatting
uv run mypy settfex/           # strict type checking
uv run pytest                  # tests + coverage gate
```

Or run everything via the pre-commit hooks:

```bash
uv run pre-commit run --all-files
```

## Conventions

- **Type safety**: full type hints on all functions; mypy strict mode.
- **Async-first**: all I/O uses `async`/`await`.
- **Pydantic models** for all inputs/outputs.
- **Tests**: add tests for new behavior and **mock all external API calls** — the
  suite must run offline. Target ≥80% coverage (the CI floor is raised over time).
- **Service pattern**: new services follow the existing pattern — `fetch_*()`
  (Pydantic) + `fetch_*_raw()` (dict) + a `get_*()` convenience function, with
  `en`/`th` and symbol normalization. See `CLAUDE.md` and existing services under
  `settfex/services/` for reference.
- **Conventional Commits**: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, etc.

Detailed engineering guidelines live in [`.github/instructions/`](.github/instructions/).

## Pull requests

1. Branch off `main` (e.g. `feature/...`, `fix/...`).
2. Make your change with tests and docs.
3. Update `CHANGELOG.md` under `## [Unreleased]` if the change is user-facing.
4. Ensure the quality gate passes.
5. Open a PR using the template and link any related issue.

## Reporting security issues

Please do **not** open public issues for vulnerabilities — see
[`SECURITY.md`](SECURITY.md).
