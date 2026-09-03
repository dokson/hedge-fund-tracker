<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Security Policy

## Supported Versions

This project ships from `master` and is released as it evolves; only the latest release line receives security fixes.

| Version | Supported |
| ------- | --------- |
| Latest release (`v2.0.x`) | ✅ |
| `master` (HEAD) | ✅ |
| Older releases | ❌ |

If you are running an older version, upgrade to the latest before reporting — the issue may already be fixed.

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

Report privately through GitHub's [**Private Vulnerability Reporting**](https://github.com/dokson/hedge-fund-tracker/security/advisories/new). This keeps the report confidential until a fix is available and lets us coordinate a disclosure with you.

Please include:

- A description of the vulnerability and its impact.
- Steps to reproduce (proof-of-concept welcome).
- Affected version / commit and your environment.
- Any suggested remediation, if you have one.

**What to expect:**

- **Acknowledgement** within 5 business days.
- **Triage and severity assessment** within 10 business days.
- Progress updates through the advisory thread until resolution.
- Credit in the advisory once a fix is published, unless you prefer to remain anonymous.

## Scope

The supported posture is a **local-first, single-user tool** that retrieves public SEC EDGAR filings and runs analysis on your own machine (or a static GitHub Pages build with no backend). In that mode the app binds to loopback and has no accounts.

**Experimental multi-user stack.** The repository also contains an unfinished multi-user path: `fastapi-users` cookie sessions backed by database access tokens (`app/auth/`), a Postgres schema and Alembic migrations (`app/db/`), envelope-encrypted BYOK provider keys under a master KEK (`app/security/envelope.py`), and the four secrets the Docker Compose stack requires (`POSTGRES_PASSWORD`, `MASTER_KEY`, `RESET_PASSWORD_TOKEN_SECRET`, `VERIFICATION_TOKEN_SECRET`). This is **experimental and not the supported production mode**: it has not been hardened for internet exposure and should not be deployed publicly yet. Security findings in it are still welcome and will be triaged like any other report — just say which components your report concerns, since fixes there may land as behavior changes rather than advisories.

In scope:

- Code execution, path traversal, or injection reachable from untrusted input (e.g. crafted filing data, CSV rows, AI provider responses).
- Leakage of secrets configured in `.env` (API keys) into logs, the SSE stream, generated reports, or committed artifacts.
- Log forgery / output sanitization bypasses (see `log_safe()` in `app/utils/logger.py`).
- Vulnerabilities in the GitHub Pages build that affect visitors.

Out of scope (by design):

- In local mode, the web UI's admin endpoints are **unauthenticated by design** — the app binds to loopback and is intended for single-user local use. Exposing it to an untrusted network is unsupported and not a vulnerability in itself.
- Issues requiring a malicious local user who already has filesystem access.
- Rate limits or data gaps inherent to the upstream SEC EDGAR / third-party data sources.

## Handling Secrets

Never commit `.env`, API keys, or files under `__llmcache__/` and `__reports__/`. Secret scanning and push protection are enabled on this repository, but treat them as a backstop, not a guarantee — review your diff before pushing.
