# Releasing settfex

settfex publishes to PyPI through **one canonical path: pushing a `vX.Y.Z` git tag.**

The tag triggers [`.github/workflows/release.yml`](.github/workflows/release.yml), which:

1. validates the tag matches `pyproject.toml`,
2. runs the full CI gate (ruff, format, mypy, pytest),
3. builds the sdist + wheel,
4. publishes to PyPI via an **OIDC Trusted Publisher** (no API token), and
5. creates the GitHub Release with the changelog body + built artifacts.

There is intentionally **no second PyPI upload path in the repo** — the workflow is the only
thing that runs `twine`. Its publish step uses `skip-existing: true`, so re-tagging (or a one-off
manual rescue) never hard-fails on an already-published file.

## Cut a release

1. Bump the version in **both** `pyproject.toml` and `settfex/__init__.py` (keep them in sync).
2. Add a `## [X.Y.Z] - YYYY-MM-DD` section to `CHANGELOG.md`.
3. Commit, open a PR, and merge to `main`.
4. From an up-to-date `main`, tag and push:

   ```bash
   git checkout main && git pull --ff-only
   git tag -a vX.Y.Z -m "settfex X.Y.Z"
   git push origin vX.Y.Z
   ```

   CI does the rest — watch:
   <https://github.com/lumduan/settfex/actions/workflows/release.yml>

> **Maintainer convenience.** A local, gitignored `scripts/publish.sh` performs the same tag
> push behind pre-flight checks (version sync between `pyproject.toml` and `settfex/__init__.py`,
> a clean/synced `main`, the CHANGELOG section, and tag uniqueness). It never runs `twine`; it
> only tags. It is not shipped in the repo because the tag push above is the real interface.

## One-time setup: PyPI Trusted Publisher (required for the OIDC publish)

This must be done once on pypi.org or the publish step will fail. On
<https://pypi.org/manage/project/settfex/settings/publishing/>, add a **GitHub Actions**
publisher:

| Field | Value |
|---|---|
| Owner | `lumduan` |
| Repository | `settfex` |
| Workflow name | `release.yml` |
| Environment | `pypi` |

Then create the `pypi` environment under **GitHub → Settings → Environments** (it can be empty;
the workflow references `environment: pypi`).

## Break-glass: manual publish (fallback only)

Use **only** if the tag/CI path is unavailable (e.g. an Actions outage). Requires a
project-scoped token in a gitignored `.env` (`PYPI_TOKEN=pypi-…`):

```bash
rm -rf dist
uv run python -m build
uv run twine check dist/*
uv run twine upload dist/* --username __token__ --password "$PYPI_TOKEN"
```

Prefer the tag-driven path. Because CI uses `skip-existing: true`, a later tag for the same
version still succeeds and just backfills the GitHub Release.

## Recommended follow-up

Single-source the version (e.g. Hatchling `[tool.hatch.version] path = "settfex/__init__.py"`
with `dynamic = ["version"]`) so `pyproject.toml` and the package can never drift again. The
release workflow's validate step reads `project.version`, so adjust it if you switch.
