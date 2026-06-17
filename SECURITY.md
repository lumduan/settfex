# Security Policy

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| 0.x     | :white_check_mark: |

settfex is pre-1.0; security fixes target the latest released `0.x` version.

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report privately via one of:

- GitHub's [private vulnerability reporting](https://github.com/lumduan/settfex/security/advisories/new)
  (Security → Report a vulnerability), or
- Email **b@candythink.com**.

Please include:

- A description of the vulnerability
- Steps to reproduce
- Affected version(s) (or commit hash)
- Any suggested mitigations

You will receive an acknowledgment within 48 hours and a status update within
7 days. Once resolved, we will coordinate disclosure timing with you.

## Security tooling

This project runs automated scans (see `.github/workflows/security.yml`):

- **Bandit** — static analysis for common Python security issues.
- **pip-audit** — checks dependencies for known CVEs.

To run locally:

```bash
uv run bandit -c pyproject.toml -r settfex
uv run pip-audit
```

## Scope note

settfex fetches public market data from SET/TFEX endpoints. It is **not**
officially affiliated with SET or TFEX. Never commit credentials or API tokens;
handle any sensitive configuration via environment variables.
