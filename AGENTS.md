# AGENTS.md

Single source of truth for AI coding agents (Claude Code, Codex, Copilot Coding Agent, etc.). `CLAUDE.md` is a one-line `@AGENTS.md` pointer so Claude Code picks it up automatically.

## What this project is

Tracks **hedge fund SEC filings** (13F quarterly, 13D/G ownership changes, Form 4 insider trades) and runs AI-powered analysis to identify promising stocks.

```
SEC EDGAR → app/scraper/ → app/analysis/ → app/ai/ (Promise Scores) → web UI / CLI
                          ↓
                  database/ (CSV files)
```

**The angle that makes this tool different**: 13F-only trackers show data 45+ days stale. We merge 13D/G (≤10 days) and Form 4 (≤2 business days) on top of quarterly snapshots, so the consensus view reflects recent institutional activity.

## Common tasks

```bash
# First-time setup
pipenv install
cp .env.example .env                        # all keys optional; app degrades gracefully
cd app/frontend && npm install --legacy-peer-deps && cd ../..

# Run the app
pipenv run app                              # web UI on auto-discovered port from 8000
pipenv run app-cli                          # legacy terminal menu (6 analysis options)
pipenv run update                           # database management CLI

# Tests
pipenv run python -m unittest discover                                   # all (Python)
pipenv run python -m unittest tests.stocks.test_price_fetcher            # single file
cd app/frontend && npm test                                              # frontend (vitest)

# Lint & format
pipenv run lint            # ruff check (Python)
pipenv run format          # ruff format
pipenv run typecheck       # mypy (informational)
cd app/frontend && npm run lint && npm run type-check && npm run format:check
pre-commit run --all-files # everything at once

# Docker
docker compose up --build                   # foreground
pipenv run docker-up                        # auto-port discovery wrapper
```

## Footguns

These are real incidents — read before changing code in these areas.

- **Stale frontend dist served silently.** The dev server auto-rebuilds when `frontend/src/` mtimes are newer than `dist/index.html`. If you bypass `pipenv run app` and serve dist directly, edits to `.tsx` or `src/data/*.json` are invisible. Trust the auto-rebuild or run `pipenv run build-frontend` explicitly.

- **SSE stdout capture is per-request.** `app/server.py` installs a `_ContextAwareStdout` wrapper at module import that consults a `ContextVar` on every `write()`. Each `_make_sse_stream` call sets its own queue in the contextvar; threads spawned to run the target inherit the context. Result: concurrent SSE streams are isolated, no global lock needed. Don't reintroduce `sys.stdout = ...` redirections — they break this isolation.

- **Wrong `Denomination` breaks non-quarterly merging.** 13D/G and Form 4 filings match by *legal name string*, not CIK. The `Denomination` column in `hedge_funds.csv` must be exact. Mismatch = silent gap in non-quarterly view.

- **`os.path.basename()` in `_sanitize_path_parts` is intentional.** It's the CodeQL-recognised sanitizer for `py/path-injection`. The `# noqa: PTH119` is load-bearing — don't "modernize" it to `Path(s).name`.

- **`stocks.csv` is auto-sorted on exit.** A diff that only shows reordering = something else changed. Don't commit "sort cleanup" PRs without inspecting actual content changes.

- **`scripts/regenerate_samples.py` imports after `sys.path.insert`.** The `# noqa: E402` lines are required — moving imports above the path setup breaks resolution of `app.*` modules.

- **CRLF on Windows.** Git auto-converts. Don't fight it. Pre-commit hooks and `.editorconfig` enforce LF in repo; checkout converts as needed.

- **GH Pages mode is a separate build.** `IS_GH_PAGES_MODE=true` (set via `--mode gh-pages`) hides routes and disables AI features (no backend). Test both modes when touching routing or feature flags.

## Architecture

### Web UI

React 19 + TypeScript + Vite, served by FastAPI (`app/server.py`). `pipenv run app` starts the server on the first free port from 8000, builds dist if stale, opens browser. `--cli` falls back to terminal menu.

**Frontend stack**: React 19, TypeScript, Vite, Tailwind, shadcn/ui (subset), Recharts, TanStack Query, react-router-dom.

**SSE pattern** (`_make_sse_stream`): runs the target in a background thread, captures stdout via a context-local queue (see `_ContextAwareStdout` + `_request_log_q`), streams each line as `data: {"type": "log", ...}`, sends final `{"type": "result", ...}` then closes. Concurrent streams isolated via `contextvars` — no shared lock.

**Server port**: locally auto-discovers from 8000. In Docker (`DOCKER_ENV=1`) binds `0.0.0.0` on `PORT` env var. `/health` for container probes.

**AI provider routing**: every AI request includes `model_id` + `provider_id`. Backend uses `provider_id` to pick the exact client class. `database/models.csv` is the single source of truth — no hardcoded model lists in TS or Python.

### GitHub Pages

Static build via `npm run build:gh-pages`:
- **Hidden pages** in GH Pages: `/database`, `/ai-settings`
- **Disabled pages**: `/ai-ranking`, `/ai-diligence` show `FeatureNotAvailable`
- **Read-only pages**: `/funds-config` (data visible, write actions hidden)
- CSV bundled into `dist/database/` via `scripts/copy-database.mjs`
- SPA routing: `public/404.html` redirects to `index.html` with path encoded as query
- Config: `app/frontend/src/lib/config.ts` (`IS_GH_PAGES_MODE`, `BASE_PATH`, `DATABASE_URL`, `API_BASE`)

### Docker

Multi-stage Dockerfile (Node frontend build → Python runtime). Volumes: `database/`, `__llmcache__/`, `__reports__/`, `.env`. `entrypoint.sh` seeds DB from `database-seed/` on first run. `scripts/docker_up.py` probes a free host port (loopback bind, never `0.0.0.0`) before `docker compose up`.

### Modules at a glance

- **`app/scraper/`** — SEC EDGAR retrieval. `sec_scraper.py` fetches 13F-HR, 13D/G, Form 4 with tenacity retries + custom User-Agent. `xml_processor.py` parses 13F XML into DataFrames.
- **`app/analysis/`** — `quarterly_report.py` (delta shares/values, NEW/CLOSE positions), `stocks.py` (multi-fund consensus), `non_quarterly.py` (13D/G + Form 4 integration), `performance_evaluator.py` (HBR).
- **`app/stocks/`** — CUSIP→Ticker via fallback chain: yfinance → Finnhub → FinanceDatabase → TradingView. Maintains `stocks.csv`. `PriceFetcher` uses a separate chain: yfinance → TradingView → Nasdaq (Nasdaq covers mutual funds others miss).
- **`app/ai/`** — Multi-provider LLM. `agent.py` runs **two-phase analysis**: (1) AI picks metric weights for current market, (2) AI computes scores using those weights. Retries up to 7× on invalid response. Clients in `clients/`: GitHub Models, Google Gemini, Groq, HuggingFace, OpenRouter.

### Key frontend files

- `src/lib/dataService.ts` — all CSV reads via HTTP; single source for analysis logic
- `src/lib/aiClient.ts` — SSE calls to `/api/ai/*`
- `src/components/ModelSelector.tsx` — reads `models.csv` via `getModels()`; `CLIENT_TO_PROVIDER_ID` maps CSV `Client` column to provider IDs
- `src/components/TerminalOutput.tsx` — macOS-style streaming terminal
- `src/pages/` — AIRanking, AIDueDiligence, FundsConfig, AISettings, DatabaseOperations

### Database (CSV files)

All in `database/`:

- **`hedge_funds.csv`** — curated tracked funds. Columns: CIK, name, manager, **Denomination** (exact legal name for non-quarterly matching — see Footguns), additional CIKs (comma-separated), URL.
- **`models.csv`** — available AI models (id, description, provider). Editable at runtime.
- **`stocks.csv`** — CUSIP → Ticker → Company. Auto-sorted on exit.
- **`non_quarterly.csv`** — recent 13D/G + Form 4 activity.
- **`{YEAR}Q{N}/`** — per-fund 13F per quarter (one CSV per fund).
- **`GICS/hierarchy.csv`** — 163 sub-industries, populated by `GICS/updater.py` (Wikipedia parser).
- **`excluded_hedge_funds.csv`** — funds intentionally not tracked, with CIKs (re-add by moving rows back to `hedge_funds.csv`).

## Data updates / GH Actions automation

Three workflows touch the repo:

**`.github/workflows/filings-fetch.yml`** — 4× daily Mon–Fri (01:30, 13:30, 17:30, 21:30 UTC) + Saturday 04:00 UTC. Fetches new filings, commits to **`automated/filings-fetch` branch** (NOT master). Opens GitHub Issues for unidentified filers. To merge: review the branch's diff, then merge into master.

**`.github/workflows/deploy-pages.yml`** — Triggers on push to `master` when `app/frontend/**` or `database/**` change. Builds `--mode gh-pages`, deploys via `actions/deploy-pages@v4`. Requires Settings > Pages > Source = "GitHub Actions".

**`.github/workflows/python-tests.yml`** — Full test suite on push/PR.

**`.github/workflows/lint.yml`** — Ruff + format check + mypy + ESLint + Prettier check + tsc on push/PR. Blocks merging if dirty.

## Branch hygiene

- **Don't push directly to `master`.** Open a PR even for tiny changes — CI runs lint and tests.
- **`automated/filings-fetch` is bot-owned.** Don't commit hand changes there; they get overwritten.
- **Feature branches**: short imperative name (`feat/portfolio-tracker`, `fix/sse-leak`).
- **Before pushing**: `pre-commit run --all-files` should pass clean.

## Conventions

### TDD is mandatory

Iron rule: **no production code without a failing test first**.

1. Write the failing test
2. Run it; verify it fails for the *expected* reason
3. Write minimal code to pass
4. Run all tests; nothing else broke
5. Refactor while green

**Red flags**:
- Code exists before a test exists → delete the code, start with TDD
- Test passes immediately → you're testing existing behavior, not new
- Can't explain the original failure → the test isn't proving anything

### Done checklist

Before marking a task complete:

- [ ] Failing test written first (watched it fail for the right reason)
- [ ] All tests green: Python (`pipenv run python -m unittest discover`) + frontend (`cd app/frontend && npm test`)
- [ ] Lint clean: `pipenv run lint && cd app/frontend && npm run lint && npm run type-check`
- [ ] Format clean: `pipenv run format` and `cd app/frontend && npm run format`
- [ ] Edge cases covered, no rationalizations ("I'll test after" / "I already manually tested")

### Docstrings

Every Python function and method has a docstring. Triple-double-quote, description on its own line:

```python
def my_function():
    """
    Description of what this function does.
    """
```

Not inline `"""description"""`. No exceptions.

### Language

All code, comments, docstrings, commit messages, and user-facing strings: **English only**.

### Code patterns

- **AI clients**: subclass `AIClient` (`app/ai/clients/base_client.py`). Same interface, different APIs.
- **Retries**: `tenacity` library, exponential backoff. Used in scrapers and AI clients.
- **Validation loop**: `AnalystAgent` retries AI responses up to 7× via `promise_score_validator.py`.
- **Caches**: `__llmcache__/` (AI responses), `__reports__/` (generated reports). Both gitignored.

### Data consistency

- `stocks.csv` auto-sorted on DB exit (avoids git noise; see Footguns)
- `non_quarterly.csv` refreshed by GH Action and by manual `pipenv run update`
- `hedge_funds.csv` updates auto-sync the README's excluded-funds section

## Data freshness limits

- **13F**: filed within 45 days of quarter-end → 45+ days old when public
- **13D/G**: filed within ~10 days of trigger event
- **Form 4**: filed within ~2 business days

The tool merges non-quarterly into quarterly views to compensate for 13F lag, but understand the inherent gaps:
- Only US long equity (no shorts, derivatives, non-US)
- Non-quarterly matching depends on `Denomination` accuracy
- Data is incomplete by design

## Environment variables

Copy `.env.example` → `.env`. All keys optional:

| Var | What it enables |
|---|---|
| `FINNHUB_API_KEY` | Better CUSIP → ticker resolution |
| `GITHUB_TOKEN` | GitHub Models provider (free tier) — recommended minimum |
| `GOOGLE_API_KEY` | Google Gemini |
| `GROQ_API_KEY` | Groq (free) |
| `HF_TOKEN` | HuggingFace Inference API |
| `OPENROUTER_API_KEY` | OpenRouter aggregator |

App degrades gracefully when keys are missing — providers without keys are simply skipped in the model picker.

## Hedge fund curation

`hedge_funds.csv` is a **curated** list selected via custom methodology emphasizing cumulative returns while penalizing volatility (Sharpe-like) and drawdowns (Sterling-like, with dampened recovery penalty). Actively maintained — underperformers removed, strong performers added.

Specialists (healthcare/biotech) and mega-funds (Berkshire, Citadel, Bridgewater) are intentionally excluded — analysis quality drops when tracking very large/diverse portfolios. See `excluded_hedge_funds.csv` for the full list with CIKs (re-add by moving rows back).
