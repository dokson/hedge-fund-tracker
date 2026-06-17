<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Contributing

Thanks for considering a contribution! This document covers what you need to know to land a change.

For deep architectural context (modules, data flow, footguns), read [`AGENTS.md`](./AGENTS.md) — it's written for AI agents but works equally well for humans.

## TL;DR

```bash
# 1. Fork & clone
git clone <your-fork>
cd hedge-fund-tracker

# 2. Install
pipenv install --dev
cd app/frontend && npm install --legacy-peer-deps && cd ../..
pipenv run pre-commit install         # auto-runs lint on commit

# 3. Branch
git checkout -b feat/short-imperative-name

# 4. Code (TDD: failing test FIRST, then implementation)
pipenv run python -m unittest discover                    # Python tests
cd app/frontend && npm test                                # frontend tests

# 5. Lint clean
pipenv run lint && pipenv run format
cd app/frontend && npm run lint && npm run type-check && npm run format
# OR all at once:
pre-commit run --all-files

# 6. Push & open PR
git push -u origin <branch>
gh pr create
```

## Ground rules

### TDD is mandatory

No production code without a failing test first. The flow:

1. Write the failing test
2. Run it; verify it fails for the *expected* reason (not a typo, not an import error)
3. Write the minimum code to pass
4. Run all tests; nothing else broke
5. Refactor while green

If you find yourself thinking "I'll just add a quick fix and test later" — stop, delete the code, start with the test. It's faster than re-doing it after review.

**Red flags** (your reviewer will catch these):
- Code exists before any test exists
- Test passes the moment you write it (you're testing existing behavior)
- You can't articulate why the test failed initially

### English everywhere

Code, comments, docstrings, commit messages, UI strings — English only. The codebase has multiple contributors using different keyboards; mixing languages creates friction.

### Docstrings on every Python function

Every function and method has a multi-line docstring:

```python
def my_function():
    """
    Description of what this function does.
    """
```

Not inline `"""description"""`. Single-line docstrings are not accepted in PR review.

### Lint must be clean before merge

CI (`.github/workflows/lint.yml`) blocks PRs that fail lint or type-check. To check locally:

```bash
# Everything at once
pre-commit run --all-files

# Or individually
pipenv run lint                                 # Ruff
pipenv run format                               # Ruff format
pipenv run typecheck                            # mypy (informational, not blocking)
cd app/frontend && npm run lint                 # ESLint --max-warnings=0
cd app/frontend && npm run type-check           # tsc --noEmit
cd app/frontend && npm run format:check         # Prettier
```

If you hit a rule that genuinely doesn't fit your case, **prefer rewriting the code over disabling the rule**. If you must disable, do it inline with a one-line reason (`# noqa: PTH119 — CodeQL sanitizer pattern`), never via blanket config.

## Branching & commits

- **Don't push to `master`.** Open a PR.
- **Branch naming**: short imperative, prefix with type — `feat/portfolio-tracker`, `fix/sse-stream-leak`, `docs/agents-md-refresh`, `chore/bump-deps`.
- **Commit messages**: [Conventional Commits](https://www.conventionalcommits.org/) preferred. Subject line ≤ 70 chars; body explains *why*, not *what*. Example:

  ```
  fix(server): drop sys.stdout redirection on client disconnect

  Previously a disconnected SSE client kept the redirection thread alive
  forever, leaking stdout from subsequent requests. The lock now releases
  on StreamingResponse close.
  ```

- **Never** commit `.env`, API keys, or files in `__llmcache__/`, `__reports__/`. The pre-commit hook `detect-private-key` catches some leaks but isn't perfect — review your diff.
- **Don't commit to `automated/filings-fetch`.** That branch is bot-owned; hand commits get overwritten.

## What makes a good PR

- **One concern per PR.** Refactors next to feature work make review hard. Split.
- **Description filled in.** The PR template asks the right questions — answer them. "Self-explanatory" usually isn't.
- **Screenshots for UI changes.** Before/after if the look changes.
- **Test plan that a reviewer can follow.** Even three lines is fine: "ran X, observed Y, ran tests".
- **No drive-by formatting.** Don't reformat unrelated files; it bloats diffs.
- **Address review comments by pushing new commits, don't force-push** until approval. Once approved, squash on merge (or rebase) is fine.

## Reporting bugs / requesting features

- **Bugs**: open a GitHub Issue using the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.yml). Include reproduction steps, environment, and the commit you're on. Issues without reproduction usually stall.
- **Features**: use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.yml). For open-ended ideas or design discussion, prefer [GitHub Discussions](../../discussions) — issues should be actionable.
- **Security vulnerabilities**: do **NOT** open a public issue. Use [private security advisories](../../security/advisories/new). Requires "Private vulnerability reporting" enabled in the repo settings (Settings → Code security).

## Releasing / data updates

You don't need to release anything to contribute — that's maintainer territory. For context:

- **Filing data** is fetched 4× daily by `.github/workflows/filings-fetch.yml`, committed to `automated/filings-fetch`. Maintainer reviews and merges into `master`.
- **GitHub Pages** auto-deploys on push to `master` when `app/frontend/**` or `database/**` change.
- **No npm/PyPI release** — this is an app, not a library.

## Questions?

Open a [Discussion](../../discussions) or comment on a related issue. Don't DM — keeping conversations public benefits future contributors.
