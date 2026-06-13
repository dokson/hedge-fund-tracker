import csv
import os
import tempfile
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pandas as pd

import app.database as _db
from app.backtest.engine import run_backtest
from app.database import PERFORMANCE_FILE
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Column order of database/performance.csv — long format, one row per (series, window).
# A series is a strategy (series_type="strategy") or a benchmark (series_type="benchmark").
CSV_FIELDS = [
    "series_type",
    "series_id",
    "label",
    "quarter_in",
    "quarter_out",
    "entry_date",
    "exit_date",
    "n_stocks",
    "window_return",
    "cum_return",
    "excess_return",
    "turnover",
]


def _round(value: object) -> object:
    """
    Round float values to 6 decimals for stable, compact CSV output.
    """
    return round(value, 6) if isinstance(value, float) else value


def write_rows(rows: list[dict], path: Path | str) -> None:
    """
    Atomically write backtest rows to a QUOTE_ALL CSV (header even when empty).
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp")
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _round(row.get(field)) for field in CSV_FIELDS})
        tmp_path.replace(target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def rebuild_strategy_performance(
    path: Path | str | None = None,
    *,
    price_fn: Callable[[str, date], float | None] | None = None,
    as_of: date | None = None,
    analysis_fn: Callable[[str], pd.DataFrame] | None = None,
    quarters: list[str] | None = None,
    fund_count_fn: Callable[[str], int] | None = None,
) -> str:
    """
    Run the full backtest and persist ``database/performance.csv``.

    Dependencies are injectable for testing; defaults use the cache-backed price
    chain, today's date, and all available quarters. Returns the written path.
    """
    rows = run_backtest(
        price_fn=price_fn,
        as_of=as_of,
        analysis_fn=analysis_fn,
        quarters=quarters,
        fund_count_fn=fund_count_fn,
    )
    target = Path(path) if path is not None else _db._safe_db_join(PERFORMANCE_FILE)
    write_rows(rows, target)
    logger.success("Wrote %d performance row(s) to %s", len(rows), target)
    return str(target)
