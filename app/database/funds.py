"""
Hedge-fund management: add/delete/restore and the hedge_funds / excluded CSVs.

Shared constants/helpers and quarter discovery come from the package core via
``import app.database as _db`` (call-time access honours ``DB_FOLDER``
monkeypatching in tests).
"""

import csv
from pathlib import Path

import pandas as pd

import app.database as _db
from app.utils.logger import get_logger, log_safe

logger = get_logger(__name__)

__all__ = [
    "delete_fund_from_database",
    "load_excluded_hedge_funds",
    "restore_fund_to_database",
    "sort_excluded_hedge_funds",
    "sort_hedge_funds",
]


def sort_hedge_funds(filepath: str | None = None) -> None:
    """
    Sorts the hedge_funds.csv file alphabetically by Fund name (case-insensitive).
    """
    if filepath is None:
        filepath = str(Path(_db.DB_FOLDER) / _db.HEDGE_FUNDS_FILE)
    try:
        df = pd.read_csv(filepath, dtype=str, keep_default_na=False).fillna("")
        df.sort_values(by="Fund", key=lambda s: s.str.lower(), inplace=True, kind="stable")
        df.to_csv(filepath, index=False, encoding="utf-8", quoting=csv.QUOTE_ALL)
    except Exception:
        logger.error("An error occurred while processing file '%s'", filepath, exc_info=True)


def sort_excluded_hedge_funds(filepath: str | None = None) -> None:
    """
    Sorts excluded_hedge_funds.csv, preserving the first README_DISPLAY_LIMIT rows
    (the curated "most popular" set shown in the README) and sorting the remaining
    rows alphabetically by Fund name (case-insensitive).
    """
    from app.utils.readme import README_DISPLAY_LIMIT

    if filepath is None:
        filepath = str(Path(_db.DB_FOLDER) / _db.EXCLUDED_HEDGE_FUNDS_FILE)
    try:
        df = pd.read_csv(filepath, dtype=str, keep_default_na=False).fillna("")
        head = df.iloc[:README_DISPLAY_LIMIT]
        tail = df.iloc[README_DISPLAY_LIMIT:].sort_values(
            by="Fund", key=lambda s: s.str.lower(), kind="stable"
        )
        result = pd.concat([head, tail], ignore_index=True)
        result.to_csv(filepath, index=False, encoding="utf-8", quoting=csv.QUOTE_ALL)
    except Exception:
        logger.error("An error occurred while processing file '%s'", filepath, exc_info=True)


def delete_fund_from_database(fund_info: dict) -> None:
    """
    Deletes a hedge fund from the database.

    This function:
    1. Removes all quarterly filing files for the fund.
    2. Moves the fund record from hedge_funds.csv to excluded_hedge_funds.csv.

    Args:
        fund_info (dict): A dictionary containing fund information ('Fund', 'CIK', ...).
    """
    fund_name = fund_info.get("Fund")
    if not fund_name:
        logger.error("Fund name is missing.")
        return

    logger.info("Deleting '%s' from database...", log_safe(fund_name))

    # 1. Delete quarterly filing files
    fund_filename = f"{fund_name.replace(' ', '_')}.csv"
    for quarter in _db.get_all_quarters():
        try:
            filepath = _db._safe_db_join(quarter, fund_filename)
            if filepath.exists():
                filepath.unlink()
                logger.info("  - Deleted: %s/%s", quarter, fund_filename)
        except Exception:
            logger.error("  - Error deleting record in %s", quarter, exc_info=True)

    # 2. Update CSV files
    hedge_funds_path = Path(_db.DB_FOLDER) / _db.HEDGE_FUNDS_FILE
    excluded_path = Path(_db.DB_FOLDER) / _db.EXCLUDED_HEDGE_FUNDS_FILE

    try:
        # Load all hedge funds
        df_hedge_funds = pd.read_csv(hedge_funds_path, dtype=str, keep_default_na=False)

        # Find the record to move
        record_to_move = df_hedge_funds[df_hedge_funds["Fund"] == fund_name]

        if record_to_move.empty:
            logger.error("Fund '%s' not found in %s", log_safe(fund_name), _db.HEDGE_FUNDS_FILE)
        else:
            # Both files share the same schema (URL included), so the row moves as-is.
            if excluded_path.exists():
                record_to_move.to_csv(
                    excluded_path, mode="a", header=False, index=False, quoting=csv.QUOTE_ALL
                )
            else:
                record_to_move.to_csv(excluded_path, index=False, quoting=csv.QUOTE_ALL)
            logger.info("  - Added '%s' to excluded_hedge_funds.csv", log_safe(fund_name))

            # Remove from hedge_funds.csv
            df_hedge_funds = df_hedge_funds[df_hedge_funds["Fund"] != fund_name]
            df_hedge_funds.to_csv(hedge_funds_path, index=False, quoting=csv.QUOTE_ALL)
            logger.info("  - Removed '%s' from %s", log_safe(fund_name), _db.HEDGE_FUNDS_FILE)

    except Exception:
        logger.error("updating CSV files", exc_info=True)

    logger.success("Deletion of '%s' completed.", log_safe(fund_name))


def load_excluded_hedge_funds() -> list:
    """
    Loads excluded hedge funds from excluded_hedge_funds.csv as a list of dicts.
    """
    filepath = Path(_db.DB_FOLDER) / _db.EXCLUDED_HEDGE_FUNDS_FILE
    if not filepath.exists():
        return []
    try:
        df = pd.read_csv(filepath, dtype={"CIK": str, "CIKs": str}, keep_default_na=False)
        return df.to_dict("records")
    except Exception:
        logger.error("while reading '%s'", filepath, exc_info=True)
        return []


def restore_fund_to_database(fund_info: dict) -> None:
    """
    Restores a hedge fund: moves its record from excluded_hedge_funds.csv back to hedge_funds.csv.
    """
    fund_name = fund_info.get("Fund")
    if not fund_name:
        logger.error("Fund name is missing.")
        return

    logger.info("Restoring '%s' to active hedge funds...", log_safe(fund_name))

    hedge_funds_path = Path(_db.DB_FOLDER) / _db.HEDGE_FUNDS_FILE
    excluded_path = Path(_db.DB_FOLDER) / _db.EXCLUDED_HEDGE_FUNDS_FILE

    if not excluded_path.exists():
        logger.error("'%s' not found.", _db.EXCLUDED_HEDGE_FUNDS_FILE)
        return

    try:
        df_excluded = pd.read_csv(excluded_path, dtype=str, keep_default_na=False)
        record_to_move = df_excluded[df_excluded["Fund"] == fund_name]

        if record_to_move.empty:
            logger.error(
                "Fund '%s' not found in %s", log_safe(fund_name), _db.EXCLUDED_HEDGE_FUNDS_FILE
            )
            return

        if hedge_funds_path.exists():
            df_hedge_funds = pd.read_csv(hedge_funds_path, dtype=str, keep_default_na=False)
            df_hedge_funds = pd.concat([df_hedge_funds, record_to_move], ignore_index=True)
        else:
            df_hedge_funds = record_to_move
        df_hedge_funds = df_hedge_funds.sort_values(
            by="Fund", key=lambda s: s.str.casefold(), kind="stable"
        ).reset_index(drop=True)
        df_hedge_funds.to_csv(hedge_funds_path, index=False, quoting=csv.QUOTE_ALL)
        logger.info(
            "  - Added '%s' to %s (alphabetical order)", log_safe(fund_name), _db.HEDGE_FUNDS_FILE
        )

        df_excluded = df_excluded[df_excluded["Fund"] != fund_name]
        df_excluded.to_csv(excluded_path, index=False, quoting=csv.QUOTE_ALL)
        logger.info("  - Removed '%s' from %s", log_safe(fund_name), _db.EXCLUDED_HEDGE_FUNDS_FILE)

    except Exception:
        logger.error("updating CSV files", exc_info=True)
        return

    logger.success("Restoration of '%s' completed.", log_safe(fund_name))
