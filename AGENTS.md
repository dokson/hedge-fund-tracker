<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# AGENTS.md

Single source of truth for AI coding agents (Claude Code, Codex, Copilot, Cursor, Gemini CLI, etc.). `CLAUDE.md` is a one-line `@AGENTS.md` pointer so Claude Code picks it up automatically.

**Agent configuration is centralized in `.agents/`**: `agents.json` (manifest), `hooks/` (tool-agnostic hook scripts) and `skills/` (shared skills, read natively by Codex). `.claude/settings.json`, `.claude/skills/`, `.codex/`, `.gemini/`, `.cursor/hooks.json` and `.github/skills/` are **generated** by `python scripts/sync_agent_configs.py`; never edit them by hand. CI and pre-commit run `--check` to catch drift.

## What this project is

Tracks **hedge fund SEC filings** (13F quarterly, 13D/G ownership changes, Form 4 insider trades) and runs AI-powered analysis to identify promising stocks.

```
SEC EDGAR → app/scraper/ → app/analysis/ → app/ai/ (Promise Scores) → web UI / CLI
                          ↓
                  database/ (CSV files)
```

**The angle that makes this tool different**: 13F-only trackers show data 45+ days stale. We merge 13D/G (13D ≤5 business days; 13G varies, see *Data freshness limits*) and Form 4 (≤2 business days) on top of quarterly snapshots, so the consensus view reflects recent institutional activity.

## Running Python tooling (must read)

**Always run Python tooling through the pipenv venv** — `pipenv run <cmd>` (or `python -m pipenv run <cmd>` if `pipenv` is not on PATH, common on Windows; if a venv is already active in the shell its python lacks pipenv — use `py -3.14 -m pipenv run <cmd>`). The system Python lacks `pandas-stubs` and `fastapi_users` — running tests/pyright outside the venv produces import errors and ~150 false type errors. Sanity-check at session start: `python -m pipenv --venv`.

A pre-shell hook (script: `.agents/hooks/enforce_pipenv.py`, wired into every agent) blocks bare invocations of `pyright`/`ruff`/`mypy`/`pytest` and `python -m <those>` when not preceded by `pipenv run`.

## Common tasks

```bash
# First-time setup
# Requires Python 3.14 (see Pipfile) and Node 26 (see .nvmrc, the single Node version source;
# the Dockerfile's FROM must match it, pinned by tests/test_toolchain_versions.py)
pipenv install
cp .env.example .env                        # all keys optional; app degrades gracefully
cd app/frontend && npm install && cd ../..

# Run the app
pipenv run app                              # web UI on auto-discovered port from 8000
pipenv run app-cli                          # legacy terminal menu (7 analysis options)
pipenv run update                           # database management CLI
pipenv run regenerate [fund ...]            # rebuild all quarterly comparisons from EDGAR (amendment-aware); optional fund-name filter
pipenv run gen-strategy                     # rebuild database/performance.csv (7-strategy backtest vs S&P 500)
pipenv run gen-fund-performance             # rebuild database/fund_performance.csv (per-fund quarterly HBR vs S&P 500)
pipenv run gen-splits                       # rescan the newest quarter for splits (incremental; run before regenerate)
pipenv run gen-splits 2026Q1 2026Q2         # rescan named quarters
pipenv run gen-splits --all                 # full rebuild (hundreds of paced provider lookups)
pipenv run check-filings                    # rescan saved 13Fs for rows priced unlike their CUSIP; updates database/filing_anomalies.csv

# Tests
pipenv run test                                                          # all (Python); alias for unittest discover
pipenv run cov                                                           # Python tests + coverage report (informational)
pipenv run python -m unittest tests.stocks.test_price_fetcher            # single file
pipenv run test-frontend                                                 # frontend (vitest); or: cd app/frontend && npm test
cd app/frontend && npm run test:coverage                                 # frontend tests + coverage report (informational)

# Lint & format
pipenv run lint            # ruff check (Python)
pipenv run format          # ruff format
pipenv run pyright         # type-checker (config: pyrightconfig.json)
cd app/frontend && npm run lint && npm run type-check && npm run format:check
pre-commit run --all-files # everything at once

# Docker
docker compose up --build                   # foreground
pipenv run docker-up                        # auto-port discovery wrapper
```

## Logging conventions

All status/error reporting goes through `app.utils.logger.get_logger(__name__)`. The shared `_PrefixFormatter` auto-prepends a per-level emoji marker; **don't repeat the marker inside the message body** — it doubles up.

Available levels and their auto-prefix:

| Method | Level | Auto-prefix | Typical use |
|---|---|---|---|
| `logger.debug` | 10 | `🚧 ` | dev diagnostics (filtered by default) |
| `logger.info` | 20 | `ℹ️  ` | normal events |
| `logger.progress` | 22 | `⏳ ` | "Sending request", "Trying fallback X" |
| `logger.money` | 23 | `💲 ` | price / value reporting |
| `logger.success` | 25 | `✅ ` | completed operation |
| `logger.warning` | 30 | `🚨 WARNING: ` | recoverable anomaly |
| `logger.deprecated` | 35 | `⚠️  DEPRECATED: ` | obsolete API in use |
| `logger.error` | 40 | `❌ ERROR - ` | failure (always pair with `exc_info=True` inside `except`) |
| `logger.critical` | 50 | `❌ CRITICAL - ` | severe failure |

The `emoji="..."` kwarg works on every method and **overrides the default prefix** — use it for occasional one-off markers (`logger.info("Rebuilding", emoji="🔄")`).

**Don't use `print()` outside `app/main.py` and `app/utils/console.py`.** Those two are CLI/UI rendering and are intentionally exempt; everything else goes through the logger so the SSE pipeline in `app/api/sse.py` (`_ContextAwareStdout`) can route each log line to the right per-request queue. The logger's stdout handler resolves `sys.stdout` lazily on every emit, which is what keeps SSE working — don't rebind the handler's stream.

## Observability

- **Request correlation**: `app/api/observability.py` assigns every request an `X-Request-ID` (a safe incoming one is reused) and logs one access line (method, path, status, ms); the id is bound to log records via `request_id_var`, including SSE worker threads.
- **Log format**: `LOG_FORMAT=json` switches the logger to one-line JSON for containers (`compose.yaml` sets it); the default stays the human format with emoji prefixes.
- **Metrics**: `GET /metrics` (Prometheus, `app/utils/metrics.py`) counts HTTP requests/latency, SEC EDGAR requests by outcome, price-provider failures and rate limits, LLM calls by provider and outcome, and non-quarterly funds carried over after a failed fetch. Labels stay low-cardinality: never add tickers or fund names. The endpoint is unauthenticated; block it at the proxy on a public deployment.
- **Scheduled fetch summary**: `.github/scripts/fetcher.py` writes a Markdown summary (funds, failures, saved rows, raised alerts) to `$GITHUB_STEP_SUMMARY` via `app/utils/run_summary.py`, followed by the filing-anomaly table from `check_filings`.

## Footguns

These are real incidents — read before changing code in these areas.

- **Stale frontend dist served silently.** The dev server auto-rebuilds when `frontend/src/` mtimes are newer than `dist/index.html`. If you bypass `pipenv run app` and serve dist directly, edits to `.tsx` or `src/data/*.json` are invisible. Trust the auto-rebuild or run `pipenv run build-frontend` explicitly.

- **`npm run build:gh-pages` leaves `dist/` unusable for the local server, and the auto-rebuild won't fix it.** The gh-pages build emits asset paths under `/hedge-fund-tracker/`; the local server has no such prefix, so the SPA fallback returns `index.html` for every asset and the browser reports `Failed to load module script … MIME type ('text/html')` on a blank page. The staleness check compares `src/` mtimes against `dist/index.html` — the fresh gh-pages dist is *newer*, so `pipenv run app` skips the rebuild and serves it anyway. After any gh-pages build, run `npm run build` before serving locally.

- **`oxlint`'s `ignorePatterns` are relative to the CWD, not to `.oxlintrc.json`'s location.** Running `npx oxlint` from the repo root (even with `--config app/frontend/.oxlintrc.json`) does NOT ignore `src/components/ui/**` or `scripts/**` — false positives appear in vendored shadcn/ui files and build scripts that are meant to be excluded. Always run oxlint from `app/frontend` (`npm run lint`, or CI's `working-directory: app/frontend`), never from the repo root.

- **SSE stdout capture is per-request.** `app/api/sse.py` installs a `_ContextAwareStdout` wrapper at module import (so it must stay on the boot path — `app/server.py` imports it) that consults a `ContextVar` on every `write()`. Concurrent SSE streams are isolated via `contextvars` — no global lock. Don't reintroduce `sys.stdout = ...` redirections, and don't bind a logger handler to a fixed stream (the project logger resolves `sys.stdout` lazily on every emit — see "Logging conventions"). Both patterns break isolation.

- **A NASDAQ name mismatch does NOT mean a ticker change is bogus.** A genuine rebrand or reverse merger changes the company name, so it is indistinguishable from a ticker collision by name alone — gating on the name guard silently dropped legitimate renames. `_verify_change` in `app/stocks/ticker_changes.py` resolves it with two further signals: the change's `effective` date (NASDAQ's feed carries years of history, and freed symbols get reassigned, so a change older than `_MAX_CHANGE_AGE_DAYS` describes the ticker's *previous* occupant, not what we track), and whether the destination symbol is already tracked under a different CUSIP (a real collision). Don't collapse these back into the name check. An applied change also re-runs `resolve_industry`, because a rename usually follows a reverse merger and the stored industry then describes a business the issuer has left; an unresolvable industry leaves the stored one alone rather than blanking it.

- **Wrong `Denomination` breaks non-quarterly merging.** 13D/G and Form 4 filings match by *legal name string*, not CIK. The `Denomination` column in `hedge_funds.csv` must be exact. Mismatch = silent gap in non-quarterly view.

- **`os.path.basename()` in `_safe_db_join` is intentional.** It's the CodeQL-recognised sanitizer for `py/path-injection`. The `# noqa: PTH119` is load-bearing — don't "modernize" it to `Path(s).name`.

- **`log_safe()` in `app/utils/logger.py` sanitizes log interpolations.** Fund names, tickers, CUSIPs and other user-controlled values are wrapped in `log_safe(...)` before being passed to `logger.X("msg %s", value)`. The helper strips non-printable characters (newlines, ANSI escapes, NUL) and truncates to 64 chars, preventing log forgery (a CSV row injecting `\nFAKE LOG LINE` would otherwise appear as a separate log entry in the SSE stream and CI logs). Apply the same wrapping when adding new logs that interpolate external strings; prefer lazy `%`-formatting (`"... %s ...", log_safe(x)`) over f-strings so the sanitized value is the one ultimately serialized.

- **Per-fund quarter CSVs are faithful filing records.** Every filed long row is kept, debt/PRN positions included — a parse-time "equity-only" filter once collapsed a credit fund's AUM from ~$200M to ~$21M. Equity-only views belong to the analysis layer, never to the parser or the saved CSVs. Two documented exceptions: option rows (`Put/Call` set) are dropped at parse time, and a row the filing register books under another CUSIP (`Kind=cusip`) is saved under the corrected one. Values are stored rounded (`80.13M`) and the `Total` row is the sum of the saved rows: nothing checks it against EDGAR's declared `tableValueTotal`.

- **Filed figures are corrected on top, never in the CSVs.** Funds file wrong CUSIPs (a rotated CUSIP column, a neighbour's CUSIP) and wrong values (stale prices, a value copied from the previous quarter, ×10 scale, share counts on a post-split basis). `app/analysis/filing_anomalies.py::CusipAnomalyDetector` flags a row only against the median price ≥3 funds report for the same CUSIP that quarter — never against the fund's own history, where genuine moves look the same — and decides each correction; `database/filing_anomalies.csv` is the single source of the result. A CUSIP correction needs exact evidence inside the filing (a closed cycle of flagged rows, or a position the filing closes with a similar share count, price within 5%); everything else is restated at the funds' price, its value by default or its share count when the gap equals a registered split factor. The loaders (`app/database/quarters.py` and `lib/data/filingRegister.ts`) only copy the register's figures and re-weight `Portfolio%`, pinned by `tests/fixtures/restatement_cases.json`; never compute a correction in either loader. Names are never compared: filings keep the name a company had when filed.

- **Share counts are filed as of quarter end, so a split reads as a giant purchase.** A 10:1 split multiplies every holder's `Shares` without anyone trading, and `Delta_Shares`/`Delta_Value`/`Delta%` are all derived from share counts — so an untouched position reported `+900%` and hundreds of millions of fake `Delta_Value`. Forward splits do NOT change the CUSIP, so `_link_cusip_changes` never sees them. **The price provider decides, not the filings**: `app/analysis/splits.py` uses the filings only to pick which securities are worth a `YFinance.get_splits` lookup, because share counts alone cannot tell a 2:1 split from a fund doubling its position — on this database, filing-only candidates were right once in twenty-two. Holder *agreement* (three holders landing on the same share ratio to within 1%) is the fallback for securities the provider can't serve (delisted, foreign, mutual funds); it needs three holders and two thirds of the universe is held by fewer, so never promote it back to primary. The registry (`splits.csv`) exists because the detector needs the whole universe at once, which the per-fund fetch path never sees.

- **A split correction must span every quarter between the two filings compared.** When a fund skips a quarter, `build_comparison_pairs` (and the updater) fall back to *two* quarters back, so applying only the recent quarter's factor silently reintroduces the error. `factors_between()` compounds them; don't replace it with a single `registry[quarter]` lookup.

- **A 13D/G on a foreign issuer counts ordinary shares, not the listed receipts.** A 13F reports the depositary receipt (the section 13(f) security); a 13D/G reports ownership of the *class*, so its share count is in the underlying ordinary shares. Pricing that count at the receipt's price, or merging it against 13F receipt counts, overstates the position by the depositary ratio — one holding was carried at $423M instead of $85M at a 5:1 ratio. `app/analysis/depositary.py::listed_units` restates it, deriving the ratio from the filing's own `classPercent` against the listed line's shares outstanding. The ratio is only trusted when rounding it to a whole number is unambiguous: candidates sit 1/n apart, so above ~10 they are closer together than the error in the quotient and the percentage of the class is used directly instead. Don't widen that threshold — at a ratio of 27 the neighbours are 3.7% apart and the rounding picks between indistinguishable candidates.

- **`generate_comparison` links CUSIP changes.** An unambiguous NEW/CLOSE pair resolving to the same ticker collapses into one continuing position (equity-style CUSIPs only — numeric issue code in chars 7-8; debt is never linked to the issuer's equity). Missing CLOSE rows for renamed tickers are intentional.

- **A "NEW HOLDINGS" 13F-HR/A lists only the added positions.** Taking it as the period's report shrank one fund's book to two rows and turned its next comparison into +2,800% of NEW positions. `app/scraper/amendments.py::consolidate_period` (regenerate) and `sec_scraper.complete_new_holdings` (updater) merge a partial one into the report it amends; filers also put the label on complete reports, so an amendment worth at least half the report it amends is taken as a restatement. The scraper reads `amendmentType` from the raw cover page (`primary_doc.xml`, not the XSL-rendered copy), only for 13F-HR/A filings.

- **An empty 13F is a real state, an unreadable one is an error.** A fund that hands its mandates to another manager files a 13F-HR whose table holds one zeroed placeholder (CUSIP `000000000`); it parses to an empty frame and the quarter is saved as all CLOSE. `xml_processor.xml_to_dataframe_13f` raises `UnparseableHoldingsError` instead when the table has no entry at all or every real position has an unreadable number, because either would be indistinguishable from "closed everything". A fund-quarter with no position left is dropped from the stock-level consensus (see below), from that quarter on: its earlier quarters are untouched.

- **"Latest quarter" is the newest usable quarter.** A quarter counts once it holds at least `MIN_QUARTER_COVERAGE` (50%) of the filings of the last usable quarter before it (`quarters.last_usable_quarter`, `getLatestQuarter` in `lib/quarters.ts`, built from the per-quarter counts `copy-database.mjs` writes into `metadata.json`), so a quarter with a single early filing does not become the default view. The quarter selector still lists every quarter.

- **EDGAR ordering is by publication date, except same-day batches.** Filings filed the same day can list in ascending period order, and funds publish old periods late. Never assume list position == recency of period; 13F-HR/A amendments win because comparisons match by reference date, latest-published first.

- **Stock-level analysis is duplicated in Python and TS, pinned by a golden fixture.** `app/analysis/stocks.py` (`_calculate_fund_level_flags`→`_aggregate_stock_data`→`_calculate_derived_metrics`) and `dataService.ts::aggregateStockLevel` must produce identical output — the TS copy is required because GH Pages has no backend. Both assert against `tests/fixtures/analysis_golden.json`. After an intentional change to either, regenerate with `pipenv run python scripts/gen_analysis_golden.py` and update both sides, or the equivalence tests fail.

  Both chains first drop every fund with no position in the quarter (`Shares` is 0 on all its rows): it has left the universe and is not a seller of what it held. The fixture carries a `FundGone` case for it.

- **`stocks.csv` is auto-sorted on exit.** A diff that only shows reordering = something else changed. Don't commit "sort cleanup" PRs without inspecting actual content changes.

- **The backtest is a descriptive track record, not a forecast — and its params aren't tuned on return.** `app/backtest/` reads only consolidated (matured) windows; the current sample is tiny and single-regime (no down-quarter yet), so every strategy beating the S&P 500 is largely beta, not skill — even "Decreasing" beat the market because the whole institutional universe rose. `min_holders` is `ceil(funds/10)` per quarter on a *breadth* principle (~10% of funds), and the five non-Avg-Portfolio screens are top-30 — NOT tuned to maximise the backtest number. The price cache lives in gitignored `__pricecache__/` — historical prices never change, so it makes a fund-list-change regeneration near-instant; don't commit it and don't expect it in CI (CI rebuilds cold). It also records *settled misses* (blank-price rows for lookups more than `MISS_SETTLE_DAYS` old), because unpriceable delisted/foreign tickers were the slowest part of every rerun; delete a row by hand if a provider later gains that symbol.

- **`scripts/regenerate_samples.py` imports after `sys.path.insert`.** The `# noqa: E402` lines are required — moving imports above the path setup breaks resolution of `app.*` modules.

- **No price-derived or daily-churning values in committed CSVs.** They turn every regeneration into a full-file git diff. The hosted site will fetch live prices at runtime; snapshots that must accumulate belong in the future history store, not in git.

- **The smart score is institutional-only and computed on the fly, by product decision.** No sell-side analyst inputs (a Yahoo analyst-ratings integration was tried and removed: differentiation beats me-too data) and no precomputed CSV: the Python `score_core` and its TypeScript mirror (`lib/smartScore.ts`, pinned by hand-computed parity tests) derive it from the quarter-analysis frame, so every tab/page/backtest shows the same formula on the same universe. Don't tune score weights on backtest returns — same principle as the strategy screens — and keep the two implementations in lockstep when changing the formula.

- **Yahoo rate-limits bulk yfinance sweeps.** A concurrent fetch over thousands of tickers got the IP temporarily banned (`YFRateLimitError`) and silently degraded to empty responses. If a mass yfinance fetch ever returns, pace requests, keep workers ≤2 and back off on rate limits rather than recording gaps.

- **`.dockerignore` patterns need `**/` to match below the root.** A bare `node_modules` once let the host's Windows `app/frontend/node_modules` into the build context, overwriting the image's `npm ci` output.

- **`package-lock.json` written on Windows can break `npm ci` on Linux.** npm prunes optional platform entries it doesn't need locally. If CI or the Docker build reports a lock out of sync, regenerate it in a Linux container (`docker run --rm -v "$PWD":/w -w /w node:26-slim npm install --package-lock-only`).

- **CRLF on Windows.** Git converts on checkout; pre-commit hooks and `.editorconfig` enforce LF in the repo. Files written by scripts or tools on Windows can come out CRLF and fail the `mixed-line-ending` hook at commit time — the hook fixes them in place, so re-stage and commit again (in Python, write with `newline="\n"` to avoid it).

- **GH Pages mode is a separate build.** `IS_GH_PAGES_MODE=true` (set via `--mode gh-pages`) hides routes and disables AI features (no backend). Test both modes when touching routing or feature flags.

## Architecture

### Web UI

React 19 + TypeScript + Vite, served by FastAPI (`app/server.py`). `pipenv run app` starts the server on the first free port from 8000, builds dist if stale, opens browser. `--cli` falls back to terminal menu.

**Frontend stack**: React 19, TypeScript, Vite, Tailwind, shadcn/ui (subset), Recharts, TanStack Query, react-router.

**SSE pattern** (`_make_sse_stream`): runs the target in a background thread, captures stdout via a context-local queue (see `_ContextAwareStdout` + `_request_log_q`), streams each line as `data: {"type": "log", ...}`, sends final `{"type": "result", ...}` then closes. Concurrent streams isolated via `contextvars` — no shared lock.

**Server port**: locally auto-discovers from 8000. In Docker (`DOCKER_ENV=1`) binds `0.0.0.0` on `PORT` env var. `/health` for container probes.

**AI provider routing**: every AI request includes `model_id` + `provider_id`. Backend uses `provider_id` to pick the exact client class. `database/models.csv` is the single source of truth — no hardcoded model lists in TS or Python.

### Shell, routing & branding

- **Layout** (`DashboardLayout.tsx` + `AppSidebar.tsx`): a full-height left sidebar (brand/logo at top, then nav, then footer) beside a content column with its own top-navbar (global search + theme toggle). The **logo is the sidebar toggle** (no hamburger): clicking it collapses the rail to an icon-only strip and back; state persists across reloads via SidebarProvider's `sidebar:state` cookie (read by `readSidebarOpen()`). On phones the sidebar is hidden and `MobileNav.tsx` takes over: a full-screen overlay (not a drawer) with 44px rows, opened by the logo.
- **Ways home and up**: the sidebar brand links home on desktop; on phones the top bar carries a Home icon and the brand row of the `MobileNav` overlay is a home link too (the header logo only opens the menu). Single-item pages (`/stock/:ticker`, a fund page) lead with a `Breadcrumb` and a back arrow: the arrow uses `useBack(fallback)` (return to where the visitor came from, the list only when the page was the entry point), and the page ends with `PageEnd` (next places to go + back to top). A metric the UI shows must be defined where it appears: the Smart Score panel and the `/stocks` Score tab link to the FAQ entry `what-is-smart-score` (`learnItem`), and `InfoTooltip` is a real button so a tap or the keyboard opens it.
- **Routes are centralised** in `src/lib/routes.ts` — `ROUTES` constants + builders (`stockPath`, `fundPath`, `stocksByIndustry`, `aiDiligenceFor`). **Never hardcode path strings**; a slug change happens in one place. Home `/` is the marketing **`Landing`** page (rendered inside the shell, so the sidebar persists); Latest Filings lives at **`/latest`**.
- **Logo assets** live in `public/`: `logo-mark.webp` (cyborg-bull mark, rendered by `BrandLogo` in the header/sidebar/landing for both themes — the transparent background reads on light and dark, so there is no theme swap) and the 512px `logo.png`, kept for social cards and JSON-LD. Plus `favicon-16/32.png` (transparent) and `apple-touch-icon.png` (on a dark navy tile, since iOS has no alpha). Raster assets are regenerated with ImageMagick (`magick`); there is no SVG source.
- **Colour roles** (`src/index.css`, HSL tokens): in dark the neutrals are tinted to the brand hue (236, 14-30% saturation) so the page reads as ink-indigo rather than grey; the active nav row is a primary wash with a leading bar; panel headers carry a faint primary wash. Status chips (`chip` + `text-positive|warning|negative`) get a 14% wash of their tone **in dark only**: in light that wash fell to 2.13:1, so light keeps the neutral chip. Recheck the text tokens' ratios on `--muted`, the lightest ground, whenever a surface token moves. The fund list's "Filed" pill follows `filingFreshness`: green on the board quarter or past it, yellow up to two quarters behind, red beyond.
- **Mobile tables → cards**: wide data tables are unusable on phones, so below `md` each becomes a stacked card list. The pattern is a `hidden md:block` table next to a `md:hidden` card list (Dashboard, StockBrowser, FundPortfolio, QuarterlyTrends, StockAnalysis, AIRanking, FundsConfig).
- **Shared search**: in-page search boxes filter through `matchesQuery()` (`src/lib/utils.ts`) — case-insensitive, null-safe, empty-query-matches-all. The "Consider Starred only" filter row is the shared `StarredFilterToggle` component. (The top-bar `GlobalSearch` is separate — it does ranked scoring, not a boolean filter.)

### GitHub Pages

Static build via `npm run build:gh-pages`:
- **Hidden pages** in GH Pages (route unreachable + sidebar entry removed): `/funds-config`, `/ai-settings`, `/database`
- **Disabled pages**: `/ai-ranking`, `/ai-diligence` show `FeatureNotAvailable`
- CSV bundled into `dist/database/` via `scripts/copy-database.mjs`
- **Static pre-render**: the `staticSeo` Vite plugin (`vite.config.ts`, gh-pages only) writes one HTML file per public route listed in `src/lib/pageMeta.ts` (`PUBLIC_PAGES`, also the source of each page's live `usePageMeta` title/description), each with its own head (canonical, Open Graph, JSON-LD) and a static body the SPA replaces on mount; `/learn` carries the full Q&A. From the newest quarter's CSVs it also writes `dist/stock/<TICKER>.html` (only stocks held by ≥`MIN_HOLDERS_FOR_PAGE` funds with a dot-free ticker — the static host would read `.B` as an extension) and `dist/funds/<Fund Name>.html`, linked from the `/stocks` and `/funds` hubs (`src/lib/entityPages.ts`; titles mirror StockAnalysis/FundPortfolio). It also emits `dist/sitemap.xml` (dated from the data CSVs; the build fails if it lists a URL with no file) + `dist/robots.txt`. **Files are flat (`dist/latest.html`), never `dist/latest/index.html`**: without the file, GH Pages answers the route with the SPA's `404.html` and a real HTTP 404 that search engines drop; with a folder index it 301s to the trailing-slash URL and splits the canonical. Caveat: under the GH Pages *project* path, `robots.txt` isn't host-root so it's not authoritative until the custom domain is live.
- SPA routing: `public/404.html` redirects to `index.html` with path encoded as query
- Config: `app/frontend/src/lib/config.ts` (`IS_GH_PAGES_MODE`, `BASE_PATH`, `DATABASE_URL`, `API_BASE`)

### Docker

Three-stage Dockerfile (Node frontend build → Python deps venv → slim runtime as UID 1001; base images pinned by digest). `compose.yaml` runs app + Postgres. Volumes: `database/`, `__llmcache__/`, `__reports__/`, `.env`. `entrypoint.sh` seeds DB from `database-seed/` on first run. `scripts/docker_up.py` probes a free host port (loopback bind, never `0.0.0.0`) before `docker compose up`.

### Modules at a glance

- **`app/scraper/`** — SEC EDGAR retrieval. `sec_scraper.py` fetches 13F-HR, 13D/G, Form 4 with tenacity retries + custom User-Agent. `xml_processor.py` parses 13F XML into DataFrames.
- **`app/analysis/`** — `quarterly_report.py` (delta shares/values, NEW/CLOSE positions), `stocks.py` (multi-fund consensus), `non_quarterly.py` (13D/G + Form 4 integration), `performance_evaluator.py` (HBR), `smart_scores.py` (the smart-score core: composite 1-10 from **institutional signals only** — breadth/momentum percentiles + conviction with a capped +10/high-conviction-entry bonus; deliberately NO sell-side analyst inputs, that's the product stance. Pure compute, NO persistence: the backtest derives it per point-in-time frame and the UI mirrors it in TS (`lib/smartScore.ts`) on the fly, like every other consensus metric).
- **`app/stocks/`** — CUSIP→Ticker via fallback chain: yfinance → OpenFIGI → TradingView. Reverse ticker→CUSIP (Form 4 path) via FMP (requires `FMP_API_KEY`). Industry classification via `app/stocks/classification.py::resolve_industry`: yfinance → same-Company match in stocks.csv → LLM pick from the `sector_hierarchy.csv` vocabulary (JSON schema; enum-constrained except on Gemini, which 400s on enums over ~100 values, so membership is also checked in code): Gemini `gemini-3.5-flash-lite` first, Groq `GroqClient.DEFAULT_MODEL` fallback when `GOOGLE_API_KEY` is missing or Gemini fails/answers off-vocabulary; a `Shell Companies` answer is only kept for blank-check-looking names, otherwise the same provider is re-asked once without that label. Maintains `stocks.csv`. `PriceFetcher` uses a separate chain: yfinance → TradingView → Nasdaq (Nasdaq covers mutual funds others miss).
- **`app/ai/`** — Multi-provider LLM. `agent.py` runs **two-phase analysis**: (1) the LLM picks relative metric weights, which code normalizes into a 0-100 Promise Score over rank-transformed metrics; (2) for the top stocks the LLM supplies only a risk score (industry comes from `stocks.csv`, else YFinance), while Momentum/Low-Volatility scores are computed from daily price history in `app/analysis/price_scores.py` (12-1 return and annualized volatility, cross-sectional 1-100 percentiles, 50 when history is short). Clients in `clients/`: Google Gemini, Groq, Ollama Cloud, OpenRouter, Z.AI.
- **`app/backtest/`** — Strategy backtester. `strategies.py` defines the seven `/quarterly` screens as `StrategySpec`s (Smart Score first, then Avg Portfolio, Consensus Buys, New Consensus, Big Bets, Increasing, Decreasing) — each mirrors its tab's default sort + filters; all but Avg Portfolio take **top 30**. Smart Score ranks by the score core the engine derives lazily on each point-in-time frame (`app/analysis/smart_scores.py::score_core`). `engine.py` reconstructs each screen point-in-time per quarter (reusing `app/analysis/stocks.py` aggregation — NOT the non-quarterly-merged view), weights every screen by `Avg_Portfolio_Pct` normalized to 100% (so strategies differ in *what* they hold, not *how* it's weighted), holds filing-date→next-filing (a holding that stops trading mid-window is valued at its last known price; only names with no entry price are dropped), and computes returns vs the **S&P 500** (`BENCHMARKS`, extensible to more indices; `run_backtest`, long-format rows); `min_holders_for_quarter` = ceil(funds/10) per quarter. `price_cache.py` persists `(ticker, date)→price` (gitignored `__pricecache__/`) so regeneration after a fund-list change is near-instant. `report.py` writes `database/performance.csv`. Run via `pipenv run gen-strategy` or updater option 11. Compute is offline → the CSV is bundled for GH Pages; the `/performance` page only reads it (no PriceFetcher in TS).
- **`app/api/`** — FastAPI routers, each `include_router`'d by `app/server.py`: `ai.py` (Promise Score / due-diligence, blocking + SSE), `admin.py` (filing fetches, ticker/CUSIP corrections, NASDAQ ticker-change apply, quarter-gap report), plus `me.py`/`api_keys.py`/`starred.py`. Shared infra lives in `common.py` (rate limiter, request validation, JSON-safe serialization) and `sse.py` (the per-request stdout-capture wrapper — imported on the boot path so it installs once). `server.py` keeps only app setup, static-file/SPA serving, and the quarter-listing routes.
- **`app/database/`** — CSV data-access layer, a package split into `quarters.py` (quarter discovery + 13F loaders), `stocks.py` (stocks.csv CRUD, the stocks lock, ticker cascades), `funds.py` (hedge-fund add/delete/restore). The package `__init__` owns the shared constants (`DB_FOLDER`, `*_FILE`) + path-safety helpers and re-exports everything, so `from app.database import X` is unchanged. Submodules read `DB_FOLDER` as `_db.DB_FOLDER` (call-time) so tests can monkeypatch it.

### Key frontend files

- `src/lib/data/*.ts` — the data layer: CSV reads (`fetch.ts`, `quarterData.ts`, …), the filing register overlay (`filingRegister.ts`) and the analysis (`analysis.ts`); `src/lib/dataService.ts` re-exports them as the single import point
- `src/lib/smartScore.ts` — TS mirror of the Python smart-score core (`smartScoreComponents`/`withSmartScores`, applied by the quarter loaders) + the score tone/chip class helpers; parity with Python pinned by hand-computed percentile tests
- `src/lib/strategies.ts` — the seven `StrategyDef`s (tabs, icons, sort keys) pinned to `tests/fixtures/strategies.json`; regenerate the fixture with `pipenv run python scripts/gen_strategy_definitions.py` after changing the Python specs
- `src/lib/routes.ts` — single source of truth for route paths (`ROUTES` + `stockPath`/`fundPath`/… builders)
- `src/lib/aiClient.ts` — SSE calls to `/api/ai/*`
- `src/components/ModelSelector.tsx` — reads `models.csv` via `getModels()`; `CLIENT_TO_PROVIDER_ID` maps CSV `Client` column to provider IDs
- `src/components/TerminalOutput.tsx` — macOS-style streaming terminal
- `src/pages/` — Landing (home `/`), Dashboard (Latest Filings, `/latest`), QuarterlyTrends, StrategyPerformance (`/performance`), FundRanking (`/ranking`), Learn (FAQ, `/learn`), About (`/about`), FundPortfolio, StockBrowser, StockAnalysis, AIRanking, AIDueDiligence, FundsConfig, AISettings, DatabasePage
- `src/pages/FundRanking.tsx` + `src/lib/fundRanking.ts` — `/ranking`, every tracked fund ranked over `fund_performance.csv` (return, excess vs the S&P 500, quarters ahead, worst quarter, consistency = mean quarterly excess over its sample deviation). A fund missing quarters is ranked on the ones it has, against the S&P 500 over those same quarters, and marked `n/NQ`: its excess compares, its raw return covers a shorter window. Display-only, so no Python twin. The window label starts at the quarter of the first starting book (`previousQuarter`), like the fund pages' chart.
- `src/components/EquityCurveChart.tsx` + `src/lib/equityCurve.ts` — multi-series cumulative-return curve for the `/performance` page (one line per strategy + benchmark, toggled via pills). `buildChartData` + `seriesColor` are the pure transforms (kept out of the component file for fast-refresh); the long CSV is parsed into per-series records by `parsePerformanceRows` in `dataService.ts`.
- `src/pages/Learn.tsx` (FAQ) + `src/lib/faqContent.ts` (content as plain data) + `src/lib/seo.ts` (React-free helpers: `canonicalUrl`, `buildFaqJsonLd`/`buildBreadcrumbJsonLd`, `renderFaqStaticHtml`) + `src/hooks/usePageMeta.ts` (per-route title/description/canonical/OG + JSON-LD for the live SPA, no `react-helmet`). The canonical origin is the single constant `SITE_ORIGIN`/`SITE_BASE` in `seo.ts` — switching to a custom domain is one edit (keep `SITE_BASE` in sync with `BASE_PATH`).

### Database (CSV files)

All in `database/`:

- **`hedge_funds.csv`** — curated tracked funds. Columns: CIK, name, manager, **Denomination** (exact legal name for non-quarterly matching — see Footguns), additional CIKs (comma-separated; used ONLY for non-quarterly filings by design, never for 13F fetches), URL.
- **`models.csv`** — available AI models (id, description, provider). Editable at runtime.
- **`stocks.csv`** — CUSIP → Ticker → Company. Auto-sorted on exit.
- **`non_quarterly.csv`** — recent 13D/G + Form 4 activity.
- **`{YEAR}Q{N}/`** — per-fund 13F per quarter (one CSV per fund).
- **`sector_hierarchy.csv`** — Yahoo Finance sector → industry mapping, derived empirically from `stocks.csv` after the classification backfill. The Sector for any stock is derived at read time by joining this file on the Industry column.
- **`filing_anomalies.csv`** — the filing register: one row per flagged filed row (Quarter, Fund, Filed_CUSIP, Filed_Company) with the funds' reference price, `Status` (`auto-corrected`, `corrected` by hand, `carried`, `dismissed`, `open`), `Kind` (`cusip`, `value`, `shares`, `carried`) and the restated `Shares`/`Value`/`Delta_Shares`/`Delta_Value`/`Delta`. Written by `pipenv run check-filings` (also run by the scheduled fetch), which never rewrites a decided row; `carried` rows are rebuilt on every scan. A `cusip` row takes effect on `pipenv run regenerate <fund>`; the others on the next load. Bundled to GH Pages.
- **`splits.csv`** — stock-split registry: one row per (Quarter, Date, CUSIP, Ticker, Factor). A `Date` is the provider's ex-date; an empty one marks a row inferred from holder agreement, which is the kind worth double-checking. `gen-splits` is **incremental** — it rescans only the quarters it is given (newest by default) and carries every other quarter's rows over untouched, so hand-added rows survive unless their own quarter is rescanned. Consumed by `generate_comparison` so both quarters are compared on the same share basis.
- **`fund_performance.csv`** — one row per (fund, quarter) with the fund's **Holding-Based Return** (start-of-quarter 13F book, value-weighted price change, split-corrected via `factors_between`) and the S&P 500 over the same window, plus both cumulative. Built offline by `app/analysis/fund_performance.py` (also the engine behind the CLI's `PerformanceEvaluator`, so both report one number). Reported prices arrive already restated by the filing register (see *Filed figures are corrected on top*); this module never corrects a filed price itself. A split is applied on whichever basis the prices are actually on (`_nearest_basis`) — some funds file post-split share counts before the ex-date, so dividing by the registry factor blindly double-applied it. Exits are priced at the other funds' quarter-end median, then the market (`__pricecache__/`, last trade for delisted names); what stays unpriced counts flat and is reported as `unpriced_weight` (the UI flags quarters above 5%). A missing S&P 500 window fails the run rather than blanking every later cumulative. Drawn by `FundPerformancePanel` on every fund page and baked into the static fund pages, labelled an *estimate*: no dividends, fees, shorts, options, cash or intra-quarter trades, top 100 positions. Known gaps: CUSIP changes are not linked here, PRN rows that exit use the issuer's stock price, and the market fallback is the day's mid, not the close. The funds are pre-selected on performance and the sample is short (one market phase), so `/ranking` states that caveat on the page, marks funds measured on fewer quarters and flags low price coverage; read it as descriptive, not as evidence of skill.
- **`performance.csv`** — multi-strategy backtest in **long format**: one row per (series, consolidated window), where a series is a strategy or a benchmark (`series_type`/`series_id`). Carries per-window + cumulative return, plus (strategies) stock count, excess vs SPY, turnover. Regenerated by `pipenv run gen-strategy` / updater option 11; bundled to GH Pages and read by the `/performance` page.

## Frontend: Global Search & Company Logos

- **`app/frontend/src/components/GlobalSearch.tsx`** — top-bar search across tickers, companies, fund names and managers. Substring scoring with prefix priority, grouped dropdown, keyboard nav (`⌘K`). Builds its index from `getStocks()` + `getHedgeFunds()` (no extra fetch).
- **`app/frontend/src/components/CompanyLogo.tsx`** + **`companyLogoUrl.ts`** — renders logos via Cloudinary fetch URL pointing at Financial Modeling Prep's public symbol endpoint. The `cloud_name` is hardcoded in `config.ts` (it's public by design). Logos are cached at the CDN edge after first fetch.
- **Cloudinary security**: Strict transformations ON, with `dokson.github.io` whitelisted in *Allowed strict referral domains*. *Allowed fetch domains* restricted to `images.financialmodelingprep.com`. Source pivoting and arbitrary new transformations are blocked.
- **`excluded_hedge_funds.csv`** — funds intentionally not tracked, with CIKs (re-add by moving rows back to `hedge_funds.csv`).

## Data updates / GH Actions automation

Workflows in `.github/workflows/`:

**`.github/workflows/filings-fetch.yml`** — 4× daily Mon–Fri (01:30, 13:30, 17:30, 21:30 UTC) + Saturday 04:00 UTC. Fetches new filings, commits to **`automated/filings-fetch` branch** (NOT master). Opens GitHub Issues for unidentified filers. To merge: review the branch's diff, then merge into master.

**`.github/workflows/deploy-pages.yml`** — Triggers on push to `master` when `app/frontend/**` or `database/**` change. Builds `--mode gh-pages`, deploys via `actions/deploy-pages@v4`. Requires Settings > Pages > Source = "GitHub Actions".

**`.github/workflows/run-tests.yml`** — Python + frontend test suites on push/PR (and manual dispatch).

**`.github/workflows/lint.yml`** — Ruff + format check + pyright + oxlint + oxfmt check + tsc on push/PR. Blocks merging if dirty.

**`.github/workflows/docker.yml`** — `docker build --check` (BuildKit's Dockerfile linter) + `compose config` + image build and healthcheck smoke test, on changes to the Docker files or `app/`.

**`.github/workflows/refresh-badges.yml`** — every 4h, purges GitHub's Camo cache for README badges that render as broken.

**`.github/workflows/popularity-refresh.yml`** — monthly (1st, 05:00 UTC) popularity refresh of the excluded funds.

**`.github/workflows/dependabot-automerge.yml`** — auto-merges Dependabot PRs.

## Branch hygiene

- **Solo maintainer pushes directly to `master`** — CI (lint + tests) still runs on every push. **External contributors must open a PR**; see [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the full flow.
- **`automated/filings-fetch` is bot-owned.** Don't commit hand changes there; they get overwritten.
- **Feature branches**: short imperative name (`feat/portfolio-tracker`, `fix/sse-leak`).
- **Before pushing**: `pre-commit run --all-files` should pass clean.

## Conventions

### TDD is mandatory

Write the failing test before the production code: a test you never saw fail doesn't prove the change works.

1. Write the failing test
2. Run it; verify it fails for the *expected* reason
3. Write minimal code to pass
4. Run all tests; nothing else broke
5. Refactor while green

If code already exists without a test, write the test now and confirm it fails with the change reverted, rather than deleting working code. A test that passes immediately is testing existing behavior: that's right for a regression guard around a refactor, but it can't be the test that drives new behavior. If you can't explain why a test failed, it isn't proving anything yet.

### Done checklist

Before marking a task complete:

- [ ] Failing test written first (watched it fail for the right reason)
- [ ] All tests green: `pipenv run python -m unittest discover` + `cd app/frontend && npm test`
- [ ] Type-check clean: `pipenv run pyright` (config in `pyrightconfig.json`)
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

### Inline comments

Default to no inline comments — clear naming should carry the WHAT. Only add one when the WHY is non-obvious: a hidden constraint, a subtle invariant, a workaround for a specific bug, behavior that would surprise a reader. Never restate what the next line already says, never leave stale/obvious `# TODO`s, and never reference the current task, PR, or issue number (that belongs in the commit message, not the code). Keep the ones you do write to a single short line — no comment blocks.

### Formatting

Two formatters only: `ruff format` for Python, `oxfmt` for everything else (TS/JS, JSON, CSS, YAML, TOML), configured once in the root `.oxfmtrc.json`. Run it repo-wide with `cd app/frontend && npm run format`. Markdown is not auto-formatted: README sections are generated by `app/utils/readme.py`, and reflowing tables would fight the generator.

### Encoding

UTF-8 everywhere. Standard streams are switched once, in `app/utils/encoding.py` (run by `import app`), so no entry point needs `python -X utf8`. Text file I/O passes `encoding="utf-8"` explicitly; ruff `PLW1514` enforces it, because on Windows the default is the locale codepage. pandas already defaults to UTF-8.

### Language

All code, comments, docstrings, commit messages, and user-facing strings: **English only**.

### Tooling choices

- **Python**: `pyright` for types, `ruff format` for formatting, `unittest` for tests (use `subTest` for cases, no pytest fixtures), `pathlib` and `X | None`, `pipenv run` for every tool. Docstrings follow *Docstrings*; an `Args:`/`Returns:` block is welcome.
- **TypeScript**: `oxlint` + `oxfmt`, `vitest`, `tsc -b` strict; tests sit next to the source as `*.test.ts(x)`.
- **Coverage**: no percentage target. TDD and the *Done checklist* decide what is tested.

### Code patterns

- **AI clients**: subclass `AIClient` (`app/ai/clients/base_client.py`). Same interface, different APIs.
- **Retries**: `tenacity` library, exponential backoff. Used in scrapers and AI clients.
- **Validation loop**: `AnalystAgent` validates every AI response in code and retries invalid ones (weights 7×, scores and due diligence 5×).
- **LLM I/O formats**: prompt *inputs* are TOON (`toon_format.encode`, ~2.4× smaller than JSON — matters under Groq's tokens/min limit); *outputs* are JSON enforced by the provider. Each prompt module exports its strict JSON Schema (`WEIGHTS_SCHEMA`, `SCORES_SCHEMA`, `DUE_DILIGENCE_SCHEMA`), passed as `generate_content(..., response_schema=...)`. `AIClient._generate_with_structure` tries provider-enforced schema → plain JSON mode → schema-in-prompt, remembering rejections per (provider, model); providers only implement the request hooks and `_is_structured_output_rejected`. Range/enum/duplicate checks stay in the agent — never trust the schema alone.
- **Caches**: `__llmcache__/` (AI responses), `__reports__/` (generated reports). Both gitignored.
- **Lazy imports in handlers**: `app/server.py` route handlers `import` their service deps *inside the function body*, not at module top. This is deliberate — it keeps server startup fast (heavy modules like `yfinance`/`AnalystAgent` load on first use) and avoids import cycles between the server and the analysis/AI layers. Keep new handlers consistent; put business logic in a service module (e.g. `app/stocks/ticker_changes.py`) and have the handler lazy-import and delegate.

### Data consistency

- `stocks.csv` auto-sorted on DB exit (avoids git noise; see Footguns)
- `non_quarterly.csv` refreshed by GH Action and by manual `pipenv run update`
- `hedge_funds.csv` updates auto-sync the README's excluded-funds section

## Data freshness limits

- **13F**: filed within 45 days of quarter-end → 45+ days old when public
- **13D**: filed within 5 business days of the acquisition; amendments within 2 business days (17 CFR 240.13d-1(a), 240.13d-2(a), as amended by Release 33-11253). The pre-2024 "10 days" is superseded — do not reintroduce it
- **13G**: not uniformly fast. A passive investor files within 5 business days; a Qualified Institutional Investor files 45 days after the end of the calendar quarter, i.e. the same lag as a 13F (240.13d-1(b)(2), (c)(2))
- **Form 4**: filed within ~2 business days

The tool merges non-quarterly into quarterly views to compensate for 13F lag, but understand the inherent gaps:
- Only US long equity (no shorts, derivatives, non-US)
- Non-quarterly matching depends on `Denomination` accuracy
- Data is incomplete by design

## Environment variables

Copy `.env.example` → `.env`. All keys optional:

| Var | What it enables |
|---|---|
| `GOOGLE_API_KEY` | Google Gemini — the default AI provider |
| `GROQ_API_KEY` | Groq (free) |
| `OLLAMA_API_KEY` | Ollama Cloud |
| `OPENROUTER_API_KEY` | OpenRouter aggregator |
| `ZAI_API_KEY` | Z.AI (GLM) |
| `OPENFIGI_API_KEY` | OpenFIGI CUSIP→ticker resolution (raises rate limit from 25 to 250 req/min) |
| `FMP_API_KEY` | Financial Modeling Prep ticker→CUSIP reverse lookup for Form 4 (free tier 250 req/day). Without it, new Form 4 tickers get a GitHub issue and the CUSIP stays null until the next 13F cycle. |

App degrades gracefully when keys are missing — providers without keys are simply skipped in the model picker.

## Hedge fund curation

`hedge_funds.csv` is a **curated** list selected via custom methodology emphasizing cumulative returns while penalizing volatility (Sharpe-like) and drawdowns (Sterling-like, with dampened recovery penalty). Actively maintained — underperformers removed, strong performers added.

Specialists (healthcare/biotech) and mega-funds (Berkshire, Citadel, Bridgewater) are intentionally excluded — analysis quality drops when tracking very large/diverse portfolios. See `excluded_hedge_funds.csv` for the full list with CIKs (re-add by moving rows back).

## License

This repository is licensed in three parts:

- **Source code** — proprietary, All Rights Reserved (see `LICENSE`).
- **Markdown documentation** (`*.md`, including this file) — Creative Commons Attribution 4.0 International (CC BY 4.0); see `LICENSE-DOCS`. Reuse with attribution to Alessandro Colace (https://github.com/dokson/hedge-fund-tracker).
- **Data** (`database/`, also served under `/database/`) — Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0); see `LICENSE-DATA`. Non-commercial because a premium tier is planned. Like `LICENSE-DOCS`, the body is the verbatim canonical legal code with the scope note on the copyright line only, so license scanners still match it exactly; never reflow or "fix" it.
