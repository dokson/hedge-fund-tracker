from app.utils.strings import get_quarter
from pathlib import Path
import pandas as pd
import csv
import re

DB_FOLDER = './database'
HEDGE_FUNDS_FILE = 'hedge_funds.csv'
STOCKS_FILE = 'stocks.csv'
LATEST_SCHEDULE_FILINGS_FILE = 'latest_filings.csv'


def get_all_quarters():
    """
    Returns a sorted (descending order) list of all quarter directories (e.g., '2025Q1')
    found in the specified database folder.
    
    Returns:
        list: A list of strings, each representing a quarter directory name.
    """
    return sorted([
        path.name for path in Path(DB_FOLDER).iterdir()
        if path.is_dir() and re.match(r'^\d{4}Q[1-4]$', path.name)
    ], reverse=True)


def get_last_quarter():
    """
    Return the last available quarter
    """
    return get_all_quarters()[0]


def get_all_quarter_files(quarter):
    """
    Returns a list of full paths for all .csv files within a given quarter directory.

    Args:
        quarter (str): The quarter in 'YYYYQN' format.

    Returns:
        list: The list of each .csv file in the quarter folder, or an empty list if the directory does not exist.
    """
    quarter_dir = Path(DB_FOLDER) / quarter

    if not quarter_dir.is_dir():
        return []

    return [
        str(file_path) for file_path in quarter_dir.glob('*.csv')
    ]


def load_hedge_funds(filepath=f"./{DB_FOLDER}/{HEDGE_FUNDS_FILE}"):
    """
    Loads hedge funds from file (hedge_funds.csv)
    """
    try:
        df = pd.read_csv(filepath, dtype={'CIK': str})
        return df.to_dict('records')
    except Exception as e:
        print(f"Errore while reading '{filepath}': {e}")
        return []


def load_stocks(filepath=f"./{DB_FOLDER}/{STOCKS_FILE}"):
    """
    Loads stocks masterdata into a pandas Series.
    Returns an empty Series if the file doesn't exist or is empty.
    """
    try:
        df = pd.read_csv(filepath, dtype={'CUSIP': str, 'Ticker': str, 'Company': str}, keep_default_na=False)
        return df.set_index('CUSIP')
    except Exception as e:
        print(f"Errore while reading '{filepath}': {e}")
        return []


def save_comparison(comparison_dataframe, date, fund_name):
    """
    Save comparison dataframe to .csv file in the appropriate folder
    """
    try:
        quarter_folder = Path(DB_FOLDER) / get_quarter(date)
        quarter_folder.mkdir(parents=True, exist_ok=True)

        filename = quarter_folder / f"{fund_name.replace(' ', '_')}.csv"
        comparison_dataframe.to_csv(filename, index=False)
        print(f"Created {filename}")
    except Exception as e:
        print(f"An error occurred while writing comparison file from dataframe: {e}")


def save_latest_schedule_filings(schedule_filings, filepath=f"./{DB_FOLDER}/{LATEST_SCHEDULE_FILINGS_FILE}"):
    """
    Combines the list of schedule filing DataFrames and saves them to a single CSV file.

    Args:
        schedule_filings (list): A list of pandas DataFrames, each representing schedule filings.
        filepath (str, optional): The path to the output CSV file. Defaults to './database/latest_filings.csv'.
    """
    if not schedule_filings:
        print("No schedule filings found to process.")
        return

    try:
        combined_schedules_df = pd.concat(schedule_filings, ignore_index=True)
        combined_schedules_df.sort_values(by='Date', ascending=False, inplace=True)
        combined_schedules_df.to_csv(filepath, index=False, encoding='utf-8', quoting=csv.QUOTE_ALL)
        print(f"Latest schedule filings saved to {filepath}")
    except Exception as e:
        print(f"An error occurred while saving latest schedule filings to '{filepath}': {e}")


def save_stock(cusip, ticker, company):
    """
    Appends a new CUSIP-Ticker pair to stocks.csv.
    """
    try:
        # Use csv.writer to properly handle quoting, ensuring all fields are enclosed in double quotes.
        with open(f'./database/{STOCKS_FILE}', 'a', newline='', encoding='utf-8') as stocks_file:
            writer = csv.writer(stocks_file, quoting=csv.QUOTE_ALL)
            writer.writerow([cusip, ticker, company])
    except Exception as e:
        print(f"An error occurred while writing file '{STOCKS_FILE}': {e}")


def sort_stocks(filepath=f'./database/{STOCKS_FILE}'):
    """
    Reads stocks.csv, sorts it by Ticker, and overwrites the file with consistent quoting.
    """
    try:
        df = pd.read_csv(filepath, dtype=str, keep_default_na=False).fillna('')
        df.sort_values(by=['Ticker', 'CUSIP'], inplace=True)
        df.to_csv(filepath, index=False, encoding='utf-8', quoting=csv.QUOTE_ALL)
    except Exception as e:
        print(f"An error occurred while writing file '{STOCKS_FILE}': {e}")
