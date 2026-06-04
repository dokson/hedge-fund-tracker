"""
Quarter discovery and 13F / fund-data loaders.

Reads shared constants and path helpers from the package core via
``import app.database as _db`` so ``DB_FOLDER`` monkeypatching in tests is
honoured at call time.
"""

import csv
import re
from pathlib import Path

import pandas as pd

import app.database as _db
from app.utils.logger import get_logger, log_safe
from app.utils.strings import get_quarter

logger = get_logger(__name__)

__all__ = [
    "count_funds_in_quarter",
    "get_all_quarter_files",
    "get_all_quarters",
    "get_funds_missing_quarters",
    "get_last_quarter",
    "get_last_quarter_for_fund",
    "get_most_recent_quarter",
    "get_quarters_for_fund",
    "load_fund_data",
    "load_fund_holdings",
    "load_hedge_funds",
    "load_non_quarterly_data",
    "load_quarterly_data",
    "save_comparison",
    "save_non_quarterly_filings",
]


def get_all_quarters() -> list[str]:
    """
    Returns a sorted (descending order) list of all quarter directories (e.g., '2025Q1')
    found in the specified database folder.

    Returns:
        list: A list of strings, each representing a quarter directory name.
    """
    return sorted(
        [
            path.name
            for path in _db._get_db_root().iterdir()
            if path.is_dir() and re.match(r"^\d{4}Q[1-4]$", path.name)
        ],
        reverse=True,
    )


def get_last_quarter() -> str:
    """
    Return the last available quarter.

    Returns:
        str | None: The most recent quarter string (e.g., '2025Q1').
    """
    return get_all_quarters()[0]


def count_funds_in_quarter(quarter: str) -> int:
    """
    Counts the number of fund filings for a given quarter.

    Args:
        quarter (str): The quarter to count files for (e.g., '2025Q1').

    Returns:
        int: The number of funds with filings in the specified quarter.
    """
    return len(get_all_quarter_files(quarter))


def get_last_quarter_for_fund(fund_name: str) -> str | None:
    """
    Finds the most recent quarter for which a given fund has a filing.

    Args:
        fund_name (str): The name of the fund.

    Returns:
        str | None: The most recent quarter string (e.g., '2025Q1'), or None if no filing is found.
    """
    quarters = get_quarters_for_fund(fund_name)
    return quarters[0] if quarters else None


def get_quarters_for_fund(fund_name: str) -> list[str]:
    """
    Returns a sorted list (descending) of all quarters where a given fund has data.

    Args:
        fund_name (str): The name of the fund.

    Returns:
        list: A list of quarter strings (e.g., ['2025Q1', '2024Q4']).
    """
    fund_filename = f"{fund_name.replace(' ', '_')}.csv"
    return [
        quarter
        for quarter in get_all_quarters()
        if _db._safe_db_join(quarter, fund_filename).exists()
    ]


def get_most_recent_quarter(ticker: str) -> str | None:
    """
    Finds the most recent quarter (within the last two available) for which a given ticker has data.

    This function iterates through the last two available quarters in descending order.
    It checks all filing files in each quarter to see if any of them contain the given ticker.
    If not found, it checks the most recent non-quarterly filings (13D/G, Form 4) for IPOs.

    Args:
        ticker (str): The stock ticker to search for.

    Returns:
        str | None: The most recent quarter string (e.g., '2025Q1'), or None if no recent data is found for the ticker.
    """
    for quarter in get_all_quarters()[:2]:
        for file_path in get_all_quarter_files(quarter):
            # Read Tickers in chunks for memory efficiency on large files
            for chunk in pd.read_csv(
                file_path, usecols=["Ticker"], dtype={"Ticker": str}, chunksize=10000
            ):
                if ticker in chunk["Ticker"].values:
                    return quarter

    # Check non-quarterly data for IPOs or recent additions
    non_quarterly = load_non_quarterly_data()
    if not non_quarterly.empty and ticker in non_quarterly["Ticker"].values:
        return get_last_quarter()

    return None


def get_all_quarter_files(quarter: str) -> list[str]:
    """
    Returns a list of full paths for all .csv files within a given quarter directory.

    Args:
        quarter (str): The quarter in 'YYYYQN' format.

    Returns:
        list: The list of each .csv file in the quarter folder, or an empty list if the directory does not exist.
    """
    try:
        quarter_dir = _db._safe_db_join(quarter)
        if not quarter_dir.is_dir():
            return []
        return [str(file_path) for file_path in quarter_dir.glob("*.csv")]
    except ValueError:
        return []


def load_fund_data(fund: str, quarter: str) -> pd.DataFrame:
    """
    Loads raw 13F data for a specific fund and quarter.

    Args:
        fund (str): The name of the fund.
        quarter (str): The quarter in 'YYYYQN' format.

    Returns:
        pd.DataFrame: A DataFrame containing the fund's holdings for that quarter, or an empty DataFrame if not found.
    """
    fund_filename = f"{fund.replace(' ', '_')}.csv"
    try:
        filepath = _db._safe_db_join(quarter, fund_filename)
        if filepath.exists():
            df = pd.read_csv(filepath)
            df["Fund"] = fund
            return df[df["CUSIP"] != "Total"]
    except ValueError:
        pass
    return pd.DataFrame()


def load_fund_holdings(fund: str, quarter: str) -> pd.DataFrame:
    """
    Loads and cleans holdings data for a specific fund and quarter.
    This includes converting 'Value' and 'Shares' to numeric and calculating 'Reported_Price'.

    Args:
        fund (str): The name of the fund.
        quarter (str): The quarter in 'YYYYQN' format.

    Returns:
        pd.DataFrame: A cleaned DataFrame with numeric 'Shares', 'Value', and 'Reported_Price'.
    """
    from app.utils.pd import get_numeric_series

    df = load_fund_data(fund, quarter)
    if df.empty:
        return df

    # Clean numeric columns
    df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce").fillna(0)
    if "Value" in df.columns:
        df["Value"] = get_numeric_series(df["Value"]).fillna(0)

    # Calculate price per share from the report
    df["Reported_Price"] = df.apply(
        lambda r: r["Value"] / r["Shares"] if r["Shares"] > 0 else 0, axis=1
    )

    return df


def load_hedge_funds(filepath: str | None = None) -> list:
    """
    Loads hedge funds from file (hedge_funds.csv).

    Default path is resolved at call time against the current DB_FOLDER, so
    tests that patch DB_FOLDER see the override without having to pass the
    filepath explicitly.
    """
    if filepath is None:
        filepath = str(Path(_db.DB_FOLDER) / _db.HEDGE_FUNDS_FILE)
    try:
        df = pd.read_csv(filepath, dtype={"CIK": str, "CIKs": str}, keep_default_na=False)
        return df.to_dict("records")
    except Exception:
        logger.error("while reading '%s'", filepath, exc_info=True)
        return []


def load_non_quarterly_data(filepath: str | None = None) -> pd.DataFrame:
    """
    Loads the latest non-quarterly (13D/G and 4) filings from the CSV file.
    """
    if filepath is None:
        filepath = str(Path(_db.DB_FOLDER) / _db.LATEST_SCHEDULE_FILINGS_FILE)
    try:
        df = pd.read_csv(filepath, dtype={"Fund": str, "CUSIP": str}, keep_default_na=False)
        # Keep only the most recent entry for each Ticker for each Fund
        return df.sort_values(by=["Date", "Filing_Date"], ascending=False).drop_duplicates(
            subset=["Fund", "Ticker"], keep="first"
        )
    except Exception:
        logger.error("while reading schedule filings from '%s'", filepath, exc_info=True)
        return pd.DataFrame()


def load_quarterly_data(quarter: str) -> pd.DataFrame:
    """
    Loads all fund comparison data for a given quarter (e.g., '2025Q1').

    Args:
        quarter (str): The quarter in 'YYYYQN' format.

    Returns:
        pd.DataFrame: A concatenated DataFrame of all fund data for the quarter
    """
    all_fund_data = []

    for file_path in get_all_quarter_files(quarter):
        fund_df = pd.read_csv(file_path)
        fund_df["Fund"] = Path(file_path).stem.replace("_", " ")
        all_fund_data.append(fund_df[fund_df["CUSIP"] != "Total"])

    return pd.concat(all_fund_data, ignore_index=True)


def save_comparison(comparison_dataframe: pd.DataFrame, date: str, fund_name: str) -> None:
    """
    Saves a fund's quarterly holdings comparison to a dedicated CSV file.

    The file is placed in a subdirectory named after the quarter (e.g., '2023Q4'),
    and the filename is derived from the fund's name.

    Args:
        comparison_dataframe (pd.DataFrame): The DataFrame containing the fund's holdings.
        date (str or datetime): A date used to determine the correct quarter folder.
        fund_name (str): The name of the fund, used for the filename.
    """
    try:
        quarter_name = get_quarter(date)
        quarter_folder = _db._safe_db_join(quarter_name)
        quarter_folder.mkdir(parents=True, exist_ok=True)

        filename = _db._safe_db_join(quarter_name, f"{fund_name.replace(' ', '_')}.csv")
        comparison_dataframe.to_csv(filename, index=False)
        logger.success("Created %s", filename)
    except Exception:
        logger.error(
            "An error occurred while writing comparison file for '%s'",
            log_safe(fund_name),
            exc_info=True,
        )


def save_non_quarterly_filings(schedule_filings: list, filepath: str | None = None) -> None:
    """
    Combines the list of schedule filing DataFrames and saves them to a single CSV file.
    """
    if filepath is None:
        filepath = str(Path(_db.DB_FOLDER) / _db.LATEST_SCHEDULE_FILINGS_FILE)
    if not schedule_filings:
        logger.info("No schedule filings found to process.")
        return

    try:
        combined_schedules_df = pd.concat(schedule_filings, ignore_index=True)
        combined_schedules_df.sort_values(
            by=["Date", "Filing_Date", "Fund", "Ticker"],
            ascending=[False, False, True, True],
            inplace=True,
        )
        combined_schedules_df.to_csv(filepath, index=False, encoding="utf-8", quoting=csv.QUOTE_ALL)
        logger.success("Latest schedule filings saved to %s", filepath)
    except Exception:
        logger.error(
            "An error occurred while saving latest schedule filings to '%s'",
            filepath,
            exc_info=True,
        )


def get_funds_missing_quarters() -> dict[str, list[str]]:
    """
    Identifies funds that are missing data for one or more available quarters.

    Returns:
        dict: A dictionary mapping fund names to a list of missing quarters.
    """
    all_quarters = set(get_all_quarters())
    funds = _db.load_hedge_funds()
    missing_data_funds = {}

    for fund in funds:
        fund_name = fund["Fund"]
        fund_quarters = set(get_quarters_for_fund(fund_name))

        if fund_quarters != all_quarters:
            missing = sorted(all_quarters - fund_quarters)
            missing_data_funds[fund_name] = missing

    return missing_data_funds
