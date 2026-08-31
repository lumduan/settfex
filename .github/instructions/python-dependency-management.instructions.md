---
applyTo: '**'
---
**Dependency Management & Python Execution:**

- All Python dependencies are managed with [uv](https://github.com/astral-sh/uv) via
  `pyproject.toml` + `uv.lock`. There is no `requirements.txt` in this repo.
- Install the project (including the dev group): `uv sync`. CI installs with
  `uv sync --group dev --frozen` and gates lock freshness with `uv lock --check`.
- Add/remove dependencies: `uv add <package>` / `uv remove <package>` (or edit
  `pyproject.toml` and run `uv lock`). Always commit the updated `uv.lock`.
- Upgrade ONE package in the lock: `uv lock --upgrade-package <name>==<version>` —
  never a bare `uv lock --upgrade`. See the **Dependency policy** section in `CLAUDE.md`
  for constraint style, the backward-compat gates, and the curl_cffi live-probe rule.
- Run Python: `uv run python <script.py>` / `uv run python -m <module>`; tools likewise
  (`uv run pytest`, `uv run ruff check .`, `uv run mypy .`).
- Do NOT use bare pip, `uv pip install` against the project env, poetry, or conda for
  dependency management or Python execution.
