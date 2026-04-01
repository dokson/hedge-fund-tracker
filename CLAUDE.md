# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pipenv install

# Build the React frontend (required before first run or after UI changes)
pipenv run build-frontend

# Build the frontend for GitHub Pages deployment
pipenv run build-gh-pages

# Run the web UI (default — opens browser, auto-discovers free port from 8000)
pipenv run app

# Run with Docker (alternative to pipenv)
docker compose up --build

# Run the legacy CLI menu instead of the web UI
pipenv run app-cli

# Run the database management CLI
pipenv run update

# Run all Python tests (as in CI)
pipenv run python -m unittest discover

# Run a single test file
pipenv run python -m unittest tests.stocks.test_price_fetcher

# Run a specific test class
pipenv run python -m unittest tests.stocks.test_price_fetcher.TestPriceFetcher

# Run a specific test method
pipenv run python -m unittest tests.stocks.test_price_fetcher.TestPriceFetcher.test_get_current_price_returns_price_from_first_library

# Run all frontend tests
cd app/frontend && npm test

# Run frontend tests in watch mode
cd app/frontend && npm run test:watch
```

## Architecture

The project tracks **hedge fund SEC filings** (13F quarterly, 13D/G significant ownership, Form 4 insider trades) and provides AI-powered portfolio analysis to identify promising stocks.

### Data Flow

```
SEC EDGAR → app/scraper/ (13F, 13D/G, Form 4) → app/analysis/ → app/ai/ (Promise Scores) → CLI output
                        ↓
                database/ (CSV files)
```

**Key Insight**: The tool integrates multiple filing types to provide a _more current_ view than 13F-only trackers. Latest 13D/G and Form 4 activity is merged into quarterly analysis to show recent institutional activity within 10 days of occurrence (vs 45+ days delay for 13F).

### Filing Types Tracked

- **13F-HR** (quarterly): Portfolio snapshot at quarter-end; filed within 45 days
- **13D/G** (non-quarterly): Significant ownership change (5%+); filed within 10 days
- **Form 4** (non-quarterly): Insider/large shareholder trades; filed within 2 business days

### Web UI

The application ships a **React + Vite frontend** (`app/frontend/`) served by the FastAPI backend. Running `python -m app.main` (default) starts the FastAPI server on port 8000, builds/serves the React dist, and opens the browser automatically. The `--cli` flag falls back to the original terminal menu.

**Frontend stack**: React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui (subset), Recharts, TanStack Query, react-router-dom.

### GitHub Pages Deployment

The frontend can be deployed as a **static site on GitHub Pages** via `npm run build:gh-pages`. A `IS_GH_PAGES_MODE` flag (injected at build time via Vite `define`) distinguishes local vs production:

- **Hidden pages** (`IS_GH_PAGES_MODE=true`): `/database`, `/ai-settings` — routes not registered
- **Disabled pages**: `/ai-ranking`, `/ai-diligence` — show `FeatureNotAvailable` component with setup instructions
- **Read-only pages**: `/funds-config` — data visible, action buttons hidden

**Static data**: CSV files are bundled into `dist/database/` during build via `scripts/copy-database.mjs`. This script also generates `manifest.json` per quarter (fund list) and `metadata.json` (latest quarter info).

**SPA routing**: `public/404.html` redirects unmatched paths back to `index.html` with path encoded as query parameter. A script in `index.html` restores the original path via `history.replaceState`.

**Environment config** (`app/frontend/src/lib/config.ts`):
- `IS_GH_PAGES_MODE` — build-time boolean (`true` when `--mode gh-pages`)
- `BASE_PATH` — `'/hedge-fund-tracker'` in GH Pages mode, `''` locally
- `DATABASE_URL` — relative paths in GH Pages mode, `http://localhost:8000/database` locally
- `API_BASE` — `null` in GH Pages mode (no backend), `http://localhost:8000` locally

**Deploy workflow** (`.github/workflows/deploy-pages.yml`): triggers on push to `master` when `app/frontend/**` or `database/**` change. Uses `actions/deploy-pages@v4` (no `gh-pages` branch — direct upload to GitHub Pages).

### Docker

Multi-stage `Dockerfile` (Node frontend build → Python runtime). `docker-compose.yml` mounts `database/`, `__llmcache__/`, `__reports__/`, and `.env` as volumes. `entrypoint.sh` seeds the database from `database-seed/` on first run and generates `.env` from environment variables if not mounted.

**Key frontend files:**
- `app/frontend/src/lib/dataService.ts` — all CSV reads/writes via HTTP; single source of truth for analysis logic
- `app/frontend/src/lib/aiClient.ts` — SSE streaming calls to `/api/ai/*` endpoints; no hardcoded model list
- `app/frontend/src/components/ModelSelector.tsx` — reads models from `database/models.csv` via `getModels()`
- `app/frontend/src/components/TerminalOutput.tsx` — macOS-style terminal for streaming AI/DB output
- `app/frontend/src/pages/` — AIRanking, AIDueDiligence, FundsConfig, AISettings, DatabaseOperations

**SSE streaming pattern** (`app/server.py → _make_sse_stream`):
- Redirects `sys.stdout` in a background thread to capture all print output
- Uses a `threading.Lock` (`_sse_lock`) to prevent concurrent stdout redirections from mixing streams
- Sends each line as `data: {"type": "log", "text": "..."}` SSE events
- Sends final result as `data: {"type": "result", "data": ...}` then closes stream
- `os.environ.setdefault("COLUMNS", "80")` ensures terminal width consistency

**Server port**: `run_server()` auto-discovers a free port starting from 8000 (locally). In Docker/production (`DOCKER_ENV=1`), binds to `0.0.0.0` on the configured `PORT` without port scanning or browser open. A `/health` endpoint is available for container health checks.

**Frontend API base**: All frontend code uses `window.location.origin` instead of hardcoded `localhost:8000`, so it works on any port.

**AI provider routing**: Every AI request includes both `model_id` and `provider_id`. The backend uses `provider_id` to select the exact client class; falls back to first available provider only when `provider_id` is absent.

**models.csv as single source of truth**: No hardcoded model arrays anywhere in TypeScript or Python. All model data flows from `database/models.csv`. The `Client` column maps to provider ID strings via `CLIENT_TO_PROVIDER_ID` in `ModelSelector.tsx`.

### Entry Points

- **`app/main.py`** — Starts FastAPI web server (default) or interactive CLI (`--cli`) for analysis with 6 options:
  1. View latest non-quarterly filings (13D/G, Form 4) from past 30 days
  2. Analyze hedge fund stock trends for a quarter
  3. Analyze specific fund's quarterly portfolio
  4. Analyze specific stock across multiple funds
  5. Run AI Analyst (Promise Score ranking)
  6. Run AI Due Diligence on a stock

- **`database/updater.py`** — Data management CLI for fetching and regenerating filing data

### Key Modules

**`app/scraper/`** — SEC EDGAR data retrieval

- `sec_scraper.py`: Fetches 13F-HR, 13D/G, Form 4 filings with retry logic and custom User-Agent
- `xml_processor.py`: Parses 13F XML holdings into DataFrames

**`app/analysis/`** — Financial analysis

- `quarterly_report.py`: Compares consecutive 13F filings; computes delta shares/values, identifies NEW/CLOSE positions
- `stocks.py`: Aggregates multi-fund consensus metrics by ticker or fund (buyer/seller/holder counts)
- `non_quarterly.py`: Processes 13D/G and Form 4 ownership changes and integrates them into quarterly views
- `performance_evaluator.py`: Holding-Based Return (HBR) calculations

**`app/stocks/`** — CUSIP → Ticker resolution with fallback chain

1. yfinance (free, no API key)
2. Finnhub (optional, requires `FINNHUB_API_KEY`)
3. FinanceDatabase (free)
4. TradingView (free)

Maintains `stocks.csv` master database; automatically sorted on exit.

**Price fetching** (`PriceFetcher`) uses a separate fallback chain: yfinance → TradingView → Nasdaq API. The Nasdaq fallback covers mutual funds (e.g., FMSMX) that other sources miss.

**`app/ai/`** — Multi-provider LLM integration

- `agent.py`: `AnalystAgent` — generates "Promise Scores" for stocks
  - **Two-phase analysis**:
    1. AI determines optimal metric weights (strategist role) for current market conditions
    2. AI calculates quantitative scores (momentum, risk, etc.) using those weights
  - Retries up to 7 times if AI response is invalid

- `clients/`: Abstract base + 5 implementations:
  - GitHub Models (free tier, Grok-3)
  - Google Gemini (free API key)
  - Groq (free, various OSS models)
  - HuggingFace Inference API (free tier)
  - OpenRouter (aggregator, some free models)

- `prompts/`: Carefully tuned system prompts for Promise Score and stock due diligence analysis
- `response_parser.py` / `promise_score_validator.py`: Extract and validate AI JSON responses (handles toon encoding)

### Database (CSV Files)

All persistent data lives in `database/`:

- **`hedge_funds.csv`** — Curated list of tracked institutional investors (CIK, name, manager, denomination, additional CIKs)
  - `Denomination`: The exact legal name used in non-quarterly filings; critical for matching 13D/G and Form 4 records
  - `CIKs`: Optional comma-separated list of related entity CIKs (some firms have multiple filing entities)
  - Editable at runtime; actively managed to maintain quality
  - Can be extended with funds from `excluded_hedge_funds.csv`

- **`models.csv`** — Available AI models for Promise Score analysis (ID, description, provider)
  - Easy to add custom models from any supported provider
  - Editable at runtime

- **`stocks.csv`** — Master stock database (CUSIP → Ticker → Company name)
  - Auto-sorted alphabetically on database exit
  - Populated incrementally as filings are processed

- **`non_quarterly.csv`** — Recent 13D/G and Form 4 activity (updated with each fetch)

- **`{YEAR}Q{N}/`** folders — Per-fund quarterly 13F reports (one CSV per fund per quarter)

- **`GICS/hierarchy.csv`** — Full GICS classification database (163 sub-industries)
  - Populated by autonomous Wikipedia parser in `GICS/updater.py`
  - Provides granular industry context to AI analyst

### GitHub Actions Automation

**`.github/workflows/deploy-pages.yml`**

- Triggers on push to `master` when `app/frontend/**` or `database/**` change (+ manual dispatch)
- Builds frontend with `--mode gh-pages`, copies database CSVs to `dist/database/`
- Deploys to GitHub Pages using `actions/deploy-pages@v4` (no `gh-pages` branch)
- Requires Settings > Pages > Source = "GitHub Actions"

**`.github/workflows/filings-fetch.yml`**

- Runs 4× daily Mon–Fri (01:30, 13:30, 17:30, 21:30 UTC) + once Saturday (04:00 UTC)
- Fetches new 13F, 13D/G, Form 4 filings for tracked funds
- Commits to **`automated/filings-fetch` branch** (not main) for user review
- Opens GitHub Issues for unidentified filers (funds not in `hedge_funds.csv`)
- Enables non-blocking background updates

**`.github/workflows/python-tests.yml`**

- Runs full test suite on push/PR
- Tests all AI clients, analysis modules, scrapers, stock resolution

## Important Concepts

### Hedge Fund Curation Strategy

`hedge_funds.csv` contains a **curated list of top-performing institutional investors** selected via custom methodology emphasizing cumulative returns while penalizing volatility (Sharpe-like) and drawdowns (Sterling-like, with dampened penalty for recovery). The list is actively maintained — underperformers may be removed, strong performers added.

**Notable Exclusions** (by design): Healthcare/biotech specialists (Nextech, Enavate, Caligan, Boxer) due to domain complexity; also major figures like Berkshire, Citadel, Bridgewater, etc. are excluded because analysis quality is lower when tracking too many large/diverse portfolios.

See `excluded_hedge_funds.csv` for a full list of excluded funds (and their CIKs, so you can add them if desired).

### Data Freshness & Limitations

- **13F filings** are 45+ days old by the time they're public (filed within 45 days of quarter-end)
- **13D/G filings** are current within ~10 days
- **Form 4 filings** are current within ~2 business days

The tool mitigates 13F staleness by automatically merging recent 13D/G and Form 4 data into quarterly analyses. However, understand:

- Only US long equity positions shown (no shorts, no derivatives, no non-US holdings)
- Non-quarterly filings require correct `Denomination` to match reliably
- Data is incomplete by design (represents only institutional activity in US equities)

## Development Notes

### Docstring Convention

Every function and method must have a docstring. No exceptions — undocumented code is not acceptable.

All docstrings must use triple-double-quote format with the description on its own line between the delimiters:

```python
def my_function():
    """
    Description of what this function does.
    """
```

Not inline: `"""description"""` — always break onto a separate line.

### Language

All code comments, docstrings, commit messages, and user-facing text in this repository must be in **English** only.

### Test-Driven Development (TDD)

**This project follows strict TDD discipline:**

1. **Write failing test first** — Before any production code
2. **Watch it fail** — Verify the test fails for the right reason
3. **Write minimal code** — Just enough to pass the test
4. **Verify green** — Confirm the test passes
5. **Refactor** — Clean up while keeping tests green

**Iron rule:** No production code without a failing test first. If you're tempted to skip this "just this once," delete the code and start with TDD.

### Testing

The test suite is extensive (30+ test files covering all major modules):

- AI clients and response parsing
- Financial analysis calculations
- Data I/O and CSV handling
- SEC scraper and XML processing
- Stock ticker resolution
- GICS utilities

**Running tests:**

```bash
# Run all tests (as in CI)
pipenv run python -m unittest discover

# Run a specific test file
pipenv run python -m unittest tests.stocks.test_price_fetcher

# Run a specific test class
pipenv run python -m unittest tests.stocks.test_price_fetcher.TestPriceFetcher

# Run a specific test method
pipenv run python -m unittest tests.stocks.test_price_fetcher.TestPriceFetcher.test_get_current_price_returns_price_from_first_library
```

**When adding features or fixing bugs:**

1. Write the test that demonstrates the required behavior
2. Run it and confirm it fails for the expected reason
3. Write minimal code to pass the test
4. Run all tests to ensure nothing else broke
5. Refactor if needed (while keeping tests green)

### Code Patterns

**AI Client Strategy Pattern**: `app/ai/clients/` uses an abstract `AIClient` base with multiple provider implementations. Each implements the same interface but talks to different APIs. Add new providers by subclassing `AIClient`.

**Scraper Retry Logic**: Uses `tenacity` library for robust retries with exponential backoff on SEC EDGAR and API calls.

**Response Validation Loop**: `AnalystAgent` retries AI responses up to 7 times if they're invalid. Validation logic in `promise_score_validator.py`.

**Ticker Resolution Fallback**: `TickerResolver` tries multiple libraries in order (yfinance → Finnhub → FinanceDatabase → TradingView) until one succeeds.

**Cache Directory**: `__llmcache__/` stores AI response caches to avoid re-querying the same analysis. `__reports__/` stores generated analysis output.

### Data Consistency

- `stocks.csv` is auto-sorted on database exit (prevents Git noise and improves lookup performance)
- `non_quarterly.csv` is refreshed by GitHub Actions and manual fetches
- `hedge_funds.csv` auto-documentation syncs the README's excluded funds section when database is refreshed

### TDD Verification Checklist

Before marking work complete:

- [ ] Wrote a failing test first (watched it fail for the right reason)
- [ ] Code is minimal and just passes the test
- [ ] All tests pass (`pipenv run python -m pytest tests/`)
- [ ] No test setup complexity (if complex, design might be too coupled)
- [ ] Tests use real code, not mocks (mocks only if unavoidable)
- [ ] Edge cases and error conditions covered
- [ ] No rationalizations like "I'll test after" or "I already manually tested"

**Red flags:**

- Code exists before a test exists → delete code, start with TDD
- Test passes immediately → you're testing existing behavior, not new behavior
- Can't explain why the test failed initially → test isn't proving your code works

## Environment Variables

Copy `.env.example` to `.env`. All API keys are optional — the app degrades gracefully:

- `FINNHUB_API_KEY` — improves CUSIP → ticker resolution
- `GITHUB_TOKEN` — enables GitHub Models provider (free tier)
- `GOOGLE_API_KEY` — enables Google Gemini models
- `GROQ_API_KEY` — enables Groq provider (free)
- `HF_TOKEN` — enables HuggingFace Inference API
- `OPENROUTER_API_KEY` — enables OpenRouter aggregator

**Recommendation**: At minimum, set `GITHUB_TOKEN` (free and generous for development). Other keys are optional and can be added as you experiment with different AI models.
