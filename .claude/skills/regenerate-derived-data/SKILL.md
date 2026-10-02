---
name: regenerate-derived-data
description: Use when filings, splits, the fund list, the stock-analysis logic or the strategy specs change and the derived files (quarterly comparisons, splits.csv, performance.csv, golden fixtures) must be rebuilt in the right order.
---

# Regenerate derived data

Run from the repo root, always through pipenv. Order matters: each step reads the previous one's output.

1. `pipenv run gen-splits` — rescan the newest quarter for splits (`gen-splits 2026Q1 2026Q2` for named quarters, `--all` for a full, slow rebuild).
2. `pipenv run regenerate [fund ...]` — rebuild quarterly comparisons from EDGAR; they apply `splits.csv`.
3. `pipenv run gen-strategy` — rebuild `database/performance.csv` from the comparisons.

After code changes:

- Stock-level aggregation (`app/analysis/stocks.py` or `dataService.ts`): `pipenv run python scripts/gen_analysis_golden.py`, then run both test suites.
- Strategy specs (`app/backtest/strategies.py`): `pipenv run python scripts/gen_strategy_definitions.py`.

Commit `database/` changes right away in their own commit; a running app or updater can overwrite uncommitted CSVs.
