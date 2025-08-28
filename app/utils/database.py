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


def is_last_quarter(quarter):
    """
    Checks if the given quarter is the most recent one available in the database.

    Args:
        quarter (str): The quarter string to check, in 'YYYYQN' format.

    Returns:
        bool: True if the quarter is the last available one, False otherwise.
    """
    return quarter == get_last_quarter()


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


def load_quarter_data(quarter):
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
        fund_df['Fund'] = Path(file_path).stem.replace('_', ' ')
        all_fund_data.append(fund_df[fund_df['CUSIP'] != 'Total'])

    return pd.concat(all_fund_data, ignore_index=True)


def load_schedules_data(filepath=f"./{DB_FOLDER}/{LATEST_SCHEDULE_FILINGS_FILE}"):
    """
    Loads the latest schedule filings (13D/G) from the CSV file.

    Args:
        filepath (str, optional): The path to the CSV file. Defaults to './database/latest_filings.csv'.

    Returns:
        pd.DataFrame: A DataFrame with a ['Fund', 'CUSIP'] MultiIndex, or an empty DataFrame if the file is not found or an error occurs.
    """
    try:
        df = pd.read_csv(filepath, dtype={'Fund': str, 'CUSIP': str}, keep_default_na=False)
        return df.set_index(['Fund', 'CUSIP'])
    except Exception as e:
        print(f"Error while reading schedule filings from '{filepath}': {e}")
        return pd.DataFrame()


def load_stocks(filepath=f"./{DB_FOLDER}/{STOCKS_FILE}"):
    """
    Loads the stock master data (CUSIP, Ticker, Company) from the CSV file.

    Args:
        filepath (str, optional): The path to the stocks CSV file.
                                  Defaults to './database/stocks.csv'.

    Returns:
        pd.DataFrame: A DataFrame with CUSIP as the index, or an empty DataFrame if the file is not found or an error occurs.
    """
    try:
        df = pd.read_csv(filepath, dtype={'CUSIP': str, 'Ticker': str, 'Company': str}, keep_default_na=False)
        return df.set_index('CUSIP')
    except Exception as e:
        print(f"Error while reading stocks file from '{filepath}': {e}")
        return pd.DataFrame()


def save_comparison(comparison_dataframe, date, fund_name):
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
        quarter_folder = Path(DB_FOLDER) / get_quarter(date)
        quarter_folder.mkdir(parents=True, exist_ok=True)

        filename = quarter_folder / f"{fund_name.replace(' ', '_')}.csv"
        comparison_dataframe.to_csv(filename, index=False)
        print(f"Created {filename}")
    except Exception as e:
        print(f"An error occurred while writing comparison file for '{fund_name}': {e}")


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
    """Appends a new stock record to the master stocks CSV file.

    This function appends a new row without checking for duplicates.
    It is intended to be used in conjunction with `sort_stocks` to clean up the file.
    If the file is new, it will also write the header row.

    Args:
        cusip (str): The CUSIP identifier of the stock.
        ticker (str): The stock ticker symbol.
        company (str): The name of the company.
    """
    try:
        # Use csv.writer to properly handle quoting, ensuring all fields are enclosed in double quotes.
        with open(f'./database/{STOCKS_FILE}', 'a', newline='', encoding='utf-8') as stocks_file:
            writer = csv.writer(stocks_file, quoting=csv.QUOTE_ALL)
            writer.writerow([cusip, ticker, company])
    except Exception as e:
        print(f"An error occurred while writing to '{STOCKS_FILE}': {e}")


def sort_stocks(filepath=f'./database/{STOCKS_FILE}'):
    """
    Reads, sorts, and overwrites the master stocks CSV file.

    This function ensures the stocks file is clean, sorted, and consistently formatted.
    It sorts entries primarily by 'Ticker' and secondarily by 'CUSIP'.
    Duplicates are removed based on 'CUSIP', keeping the first occurrence.

    Args:
        filepath (str, optional): The path to the stocks CSV file.
                                  Defaults to the standard path if None.
    """
    try:
        df = pd.read_csv(filepath, dtype=str, keep_default_na=False).fillna('')
        df.sort_values(by=['Ticker', 'CUSIP'], inplace=True)
        df.to_csv(filepath, index=False, encoding='utf-8', quoting=csv.QUOTE_ALL)
    except Exception as e:
        print(f"An error occurred while processing file '{filepath}': {e}")
