"""
stocks.csv CRUD, the cross-process stocks lock, and ticker-change cascades.

Shared constants/helpers and quarter loaders come from the package core via
``import app.database as _db`` (call-time access honours ``DB_FOLDER``
monkeypatching in tests).
"""

import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, suppress
from pathlib import Path

import pandas as pd

import app.database as _db
from app.utils.logger import get_logger, log_safe

logger = get_logger(__name__)

__all__ = [
    "clean_stocks",
    "find_cusips_for_ticker",
    "load_sector_hierarchy",
    "load_stocks",
    "save_stock",
    "save_stocks",
    "sort_stocks",
    "stocks_lock",
    "update_non_quarterly_filings",
    "update_quarterly_filings",
    "update_stocks_csv",
    "update_ticker",
    "update_ticker_for_cusip",
]


def load_sector_hierarchy(filepath: str | None = None) -> pd.DataFrame:
    """
    Loads the Yahoo Finance sector → industry hierarchy from the CSV file.

    The hierarchy maps each Industry to its parent Sector. It is used to derive
    the Sector for any stock by joining on the Industry column of stocks.csv.
    """
    if filepath is None:
        filepath = str(Path(_db.DB_FOLDER) / _db.SECTOR_HIERARCHY_FILE)
    try:
        return pd.read_csv(filepath, dtype=str, keep_default_na=False)
    except Exception:
        logger.error("while reading sector hierarchy from '%s'", filepath, exc_info=True)
        return pd.DataFrame()


def load_stocks(filepath: str | None = None) -> pd.DataFrame:
    """
    Loads the stock master data (CUSIP, Ticker, Company, Industry) from the CSV file.

    The Sector is intentionally not stored here — it is derivable by joining the
    `Industry` column against `database/sector_hierarchy.csv`. Legacy CSVs missing
    the Industry column are backfilled with empty strings so callers always see
    the full schema.
    """
    if filepath is None:
        filepath = str(Path(_db.DB_FOLDER) / _db.STOCKS_FILE)
    try:
        df = pd.read_csv(filepath, dtype=str, keep_default_na=False)
        if "Industry" not in df.columns:
            df["Industry"] = ""
        return df.set_index("CUSIP")
    except Exception:
        logger.error("while reading stocks file from '%s'", filepath, exc_info=True)
        return pd.DataFrame()


@contextmanager
def stocks_lock(timeout=30):
    """
    Synchronize access to stocks.csv across both threads (in-process) and
    processes (cross-process).

    Same-process threads serialize on a module-level threading.Lock first,
    which is fair and instantaneous. Cross-process callers then contend on a
    .lock file via O_CREAT|O_EXCL with bounded retry. Without the in-process
    lock, sibling threads on Windows can starve waiting for the lock-file
    creation/removal cycle to settle.
    """
    lock_path = Path(_db.DB_FOLDER) / f"{_db.STOCKS_FILE}.lock"
    start_time = time.time()
    acquired_file = False

    with _db._stocks_thread_lock:
        try:
            while True:
                try:
                    fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.close(fd)
                    acquired_file = True
                    break
                except FileExistsError as exc:
                    if time.time() - start_time > timeout:
                        raise TimeoutError(
                            f"Could not acquire lock for {_db.STOCKS_FILE} within {timeout} seconds."
                        ) from exc

                    # Reclaim a stale lock that outlived its owner (>60s).
                    try:
                        if time.time() - Path(lock_path).stat().st_mtime > 60:
                            try:
                                Path(lock_path).unlink()
                                continue
                            except OSError:
                                pass
                    except OSError:
                        pass

                    time.sleep(0.05)
                except OSError:
                    time.sleep(0.05)

            yield
        finally:
            if acquired_file:
                with suppress(OSError):
                    Path(lock_path).unlink()


def save_stock(
    cusip: str,
    ticker: str,
    company: str,
    industry: str = "",
) -> None:
    """Appends a new stock record to the master stocks CSV file.

    This function appends a new row while ensuring no duplicates are created.
    It uses a lock and then re-checks if the CUSIP exists (Double-Checked Locking).

    Args:
        cusip (str): The CUSIP identifier of the stock.
        ticker (str): The stock ticker symbol.
        company (str): The name of the company.
        industry (str): Yahoo Finance industry classification (default empty).
            The Sector is not stored — derive it via database/sector_hierarchy.csv.
    """
    try:
        # Use csv.writer to properly handle quoting, ensuring all fields are enclosed in double quotes.
        with stocks_lock():
            # Double-check if the CUSIP was already added by another process/thread while we were waiting for the lock.
            stocks_df = load_stocks()
            if not stocks_df.empty and cusip in stocks_df.index:
                # Already exists, skip appending
                return

            with (Path(_db.DB_FOLDER) / _db.STOCKS_FILE).open(
                "a", newline="", encoding="utf-8"
            ) as stocks_file:
                writer = csv.writer(stocks_file, quoting=csv.QUOTE_ALL)
                writer.writerow(
                    [
                        cusip.strip(),
                        ticker.strip(),
                        company.strip(),
                        industry.strip(),
                    ]
                )
    except Exception:
        logger.error("An error occurred while writing to '%s'", _db.STOCKS_FILE, exc_info=True)


def save_stocks(stocks_df: pd.DataFrame, filepath: str | None = None) -> None:
    """
    Overwrites the master stocks CSV file with the given DataFrame.
    """
    if filepath is None:
        filepath = str(Path(_db.DB_FOLDER) / _db.STOCKS_FILE)
    try:
        stocks_df.to_csv(filepath, quoting=csv.QUOTE_ALL)
    except Exception:
        logger.error("An error occurred while writing to '%s'", _db.STOCKS_FILE, exc_info=True)


def clean_stocks(filepath: str | None = None) -> None:
    """
    Identifies and removes orphan CUSIPs from the master stocks CSV file.
    An orphan CUSIP is one that exists in stocks.csv but not in any filing (quarterly or non-quarterly),
    and belongs to a ticker that has more than one CUSIP entry.
    """
    if filepath is None:
        filepath = str(Path(_db.DB_FOLDER) / _db.STOCKS_FILE)
    try:
        stocks_df = load_stocks().reset_index()
        if stocks_df.empty:
            return

        all_stock_cusips = set(stocks_df["CUSIP"])
        all_filing_cusips: set[str] = set()

        # 1. Collect CUSIPs from every quarterly fund CSV.
        # Hot path: this used to call load_quarterly_data() which reads every
        # column of every fund CSV (then concats) — ~600 files × full schema
        # only to extract the CUSIP column. Now we stream usecols=["CUSIP"] in
        # parallel across all quarters/funds; the work is pure I/O so a
        # ThreadPoolExecutor scales near-linearly with the file count.
        def _cusips_from_file(file_path: str) -> set[str]:
            cusips = pd.read_csv(file_path, usecols=["CUSIP"], dtype=str)["CUSIP"]
            return {c for c in cusips.dropna() if c != "Total"}

        all_files = [
            file_path
            for quarter in _db.get_all_quarters()
            for file_path in _db.get_all_quarter_files(quarter)
        ]
        with ThreadPoolExecutor(max_workers=min(16, max(4, len(all_files)))) as pool:
            for partial in pool.map(_cusips_from_file, all_files):
                all_filing_cusips.update(partial)

        # 2. Collect all CUSIPs from non-quarterly filings
        non_quarterly = _db.load_non_quarterly_data()
        if not non_quarterly.empty:
            all_filing_cusips.update(non_quarterly["CUSIP"].dropna().unique())

        # 3. Find orphan CUSIPs (present in stocks.csv but not in any filings)
        orphan_cusips = all_stock_cusips - all_filing_cusips

        if not orphan_cusips:
            return

        # 4. Filter orphans to find only those belonging to Tickers with more than one CUSIP
        ticker_cusip_counts = stocks_df.groupby("Ticker")["CUSIP"].nunique()
        tickers_with_multiple_cusips = ticker_cusip_counts[ticker_cusip_counts > 1].index

        # Isolate orphan CUSIPs that belong to these tickers
        final_orphans_df = stocks_df[
            (stocks_df["CUSIP"].isin(orphan_cusips))
            & (stocks_df["Ticker"].isin(tickers_with_multiple_cusips))
        ]

        if final_orphans_df.empty:
            return

        logger.info("Found %d orphan CUSIPs to remove:", len(final_orphans_df), emoji="🧹")
        for _, row in final_orphans_df.iterrows():
            logger.info(
                "  - %s (%s): %s",
                log_safe(row["CUSIP"]),
                log_safe(row["Ticker"]),
                log_safe(row["Company"]),
            )

        orphan_cusips_to_remove = set(final_orphans_df["CUSIP"])

        # 5. Remove orphans and save
        with stocks_lock():
            # Reload to ensure we have the latest data before saving
            current_stocks_df = pd.read_csv(filepath, dtype=str, keep_default_na=False).fillna("")
            cleaned_df = current_stocks_df[
                ~current_stocks_df["CUSIP"].isin(orphan_cusips_to_remove)
            ]
            cleaned_df.to_csv(filepath, index=False, encoding="utf-8", quoting=csv.QUOTE_ALL)
            logger.success(
                "Removed %d orphan CUSIPs from %s.", len(orphan_cusips_to_remove), _db.STOCKS_FILE
            )

    except Exception:
        logger.error("An error occurred while removing orphan CUSIPs", exc_info=True)


def sort_stocks(filepath: str | None = None) -> None:
    """
    Reads, sorts, and overwrites the master stocks CSV file.

    This function ensures the stocks file is clean, sorted, and consistently formatted.
    It sorts entries primarily by 'Ticker' and secondarily by 'CUSIP'.
    Any duplicates are removed keeping 'CUSIP' as the primary key.
    """
    if filepath is None:
        filepath = str(Path(_db.DB_FOLDER) / _db.STOCKS_FILE)
    try:
        with stocks_lock():
            df = pd.read_csv(filepath, dtype=str, keep_default_na=False).fillna("")
            df.drop_duplicates(subset=["CUSIP"], keep="first", inplace=True)
            df.sort_values(by=["Ticker", "CUSIP"], inplace=True)
            df.to_csv(filepath, index=False, encoding="utf-8", quoting=csv.QUOTE_ALL)
    except Exception:
        logger.error("An error occurred while processing file '%s'", filepath, exc_info=True)


def find_cusips_for_ticker(old_ticker: str) -> list[dict[str, str]]:
    """
    Finds all CUSIPs associated with a given ticker in the stocks.csv file.

    Args:
        old_ticker (str): The ticker to search for.

    Returns:
        list: A list of dictionaries containing CUSIP, Ticker, and Company information.
    """
    stocks_path = Path(_db.DB_FOLDER) / _db.STOCKS_FILE
    matching_stocks: list[dict[str, str]] = []

    if not stocks_path.exists():
        logger.error("%s not found at %s", _db.STOCKS_FILE, stocks_path)
        return matching_stocks

    with stocks_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Ticker"] == old_ticker:
                matching_stocks.append(
                    {"CUSIP": row["CUSIP"], "Ticker": row["Ticker"], "Company": row["Company"]}
                )

    return matching_stocks


def update_stocks_csv(old_ticker: str, new_ticker: str, new_company: str | None = None) -> int:
    """
    Updates the ticker (and optionally company name) in stocks.csv for all matching CUSIPs.

    Args:
        old_ticker (str): The current ticker to replace.
        new_ticker (str): The new ticker to use.
        new_company (str, optional): The new company name. If None, the existing name is preserved.

    Returns:
        int: The number of rows updated.
    """
    stocks_path = Path(_db.DB_FOLDER) / _db.STOCKS_FILE

    if not stocks_path.exists():
        logger.error("%s not found", _db.STOCKS_FILE)
        return 0

    # Read all rows
    rows = []
    updated_count = 0

    with stocks_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        for row in reader:
            if row["Ticker"] == old_ticker:
                row["Ticker"] = new_ticker
                if new_company:
                    row["Company"] = new_company
                updated_count += 1
            rows.append(row)

    # Write back
    with stocks_lock(), stocks_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)

    return updated_count


def update_quarterly_filings(cusips: list[str], new_ticker: str) -> None:
    """
    Updates the ticker in all quarterly filing CSV files for the specified CUSIPs.

    Args:
        cusips (list): List of CUSIPs to update.
        new_ticker (str): The new ticker to use.
    """
    quarters = _db.get_all_quarters()

    for quarter in quarters:
        quarter_path = Path(_db.DB_FOLDER) / quarter

        if not quarter_path.exists():
            continue

        csv_files = list(quarter_path.glob("*.csv"))

        for csv_file in csv_files:
            try:
                rows = []
                file_updated = False

                with Path(csv_file).open(encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames or []

                    if "CUSIP" not in fieldnames or "Ticker" not in fieldnames:
                        continue

                    for row in reader:
                        if row["CUSIP"] in cusips:
                            row["Ticker"] = new_ticker
                            file_updated = True
                        rows.append(row)

                if file_updated:
                    with Path(csv_file).open("w", encoding="utf-8", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)

                    logger.success("Updated %s/%s", quarter, csv_file.name)

            except Exception:
                logger.error("processing %s", csv_file, exc_info=True)


def update_non_quarterly_filings(cusips: list[str], new_ticker: str) -> int:
    """
    Updates the ticker in the non_quarterly.csv file for the specified CUSIPs.

    Args:
        cusips (list): List of CUSIPs to update.
        new_ticker (str): The new ticker to use.

    Returns:
        int: Number of rows updated.
    """
    nq_path = Path(_db.DB_FOLDER) / _db.LATEST_SCHEDULE_FILINGS_FILE

    rows = []
    updated_count = 0

    try:
        with nq_path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []

            for row in reader:
                if row["CUSIP"] in cusips:
                    row["Ticker"] = new_ticker
                    updated_count += 1
                rows.append(row)

        with nq_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)

        if updated_count > 0:
            logger.success(
                "Updated %d row(s) in %s", updated_count, _db.LATEST_SCHEDULE_FILINGS_FILE
            )

    except Exception:
        logger.error("processing %s", _db.LATEST_SCHEDULE_FILINGS_FILE, exc_info=True)
        return 0

    return updated_count


def update_ticker_for_cusip(cusip: str, new_ticker: str, new_company: str | None = None) -> None:
    """
    Updates the ticker for a single CUSIP across the entire database.

    This function:
    1. Updates the ticker (and optionally company name) for the specified CUSIP in stocks.csv
    2. Updates all quarterly filings for that CUSIP
    3. Updates the non_quarterly.csv file

    Args:
        cusip (str): The CUSIP to update.
        new_ticker (str): The new ticker to use.
        new_company (str, optional): The new company name. If None, the existing name is preserved.
    """
    stocks_path = Path(_db.DB_FOLDER) / _db.STOCKS_FILE

    if not stocks_path.exists():
        logger.error("%s not found", _db.STOCKS_FILE)
        return

    # Update stocks.csv
    rows = []
    found = False
    old_ticker = None
    company = None

    with stocks_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        for row in reader:
            if row["CUSIP"] == cusip:
                old_ticker = row["Ticker"]
                company = row["Company"]
                row["Ticker"] = new_ticker
                if new_company:
                    row["Company"] = new_company
                found = True
            rows.append(row)

    if not found:
        logger.error("CUSIP '%s' not found in %s", log_safe(cusip), _db.STOCKS_FILE)
        return

    logger.info(
        "  - CUSIP: %s, Company: %s, Old Ticker: %s -> New Ticker: %s",
        log_safe(cusip),
        log_safe(company),
        log_safe(old_ticker),
        log_safe(new_ticker),
    )

    # Write back stocks.csv
    with stocks_lock(), stocks_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)

    # Update quarterly filings and non-quarterly filings
    update_quarterly_filings([cusip], new_ticker)
    update_non_quarterly_filings([cusip], new_ticker)


def update_ticker(old_ticker: str, new_ticker: str, new_company: str | None = None) -> None:
    """
    Updates a ticker across the entire database.

    This function:
    1. Finds all CUSIPs associated with the old ticker in stocks.csv
    2. Updates the ticker (and optionally company name) in stocks.csv
    3. Updates all quarterly filings for those CUSIPs
    4. Updates the non_quarterly.csv file

    Args:
        old_ticker (str): The current ticker to replace.
        new_ticker (str): The new ticker to use.
        new_company (str, optional): The new company name. If None, the existing name is preserved.
    """
    matching_stocks = find_cusips_for_ticker(old_ticker)

    if not matching_stocks:
        logger.error("No stocks found with ticker '%s'", log_safe(old_ticker))
        return

    for stock in matching_stocks:
        logger.info("  - CUSIP: %s, Company: %s", stock["CUSIP"], stock["Company"])

    cusips = [stock["CUSIP"] for stock in matching_stocks]

    update_stocks_csv(old_ticker, new_ticker, new_company)
    update_quarterly_filings(cusips, new_ticker)
    update_non_quarterly_filings(cusips, new_ticker)
