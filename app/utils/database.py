from app.ai.clients import GoogleAIClient, GroqClient, OpenRouterClient
from app.utils.strings import get_quarter
from pathlib import Path
import pandas as pd
import csv
import re

DB_FOLDER = './database'
HEDGE_FUNDS_FILE = 'hedge_funds.csv'
MODELS_FILE = 'models.csv'
STOCKS_FILE = 'stocks.csv'
LATEST_SCHEDULE_FILINGS_FILE = 'non_quarterly.csv'


def get_all_quarters() -> list[str]:
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
    fund_filename = f"{fund_name.replace(' ', '_')}.csv"
    for quarter in get_all_quarters():
        if (Path(DB_FOLDER) / quarter / fund_filename).exists():
            return quarter
    return None


def get_most_recent_quarter(ticker: str) -> str | None:
    """
    Finds the most recent quarter (within the last two available) for which a given ticker has data.
 
    This function iterates through the last two available quarters in descending order.
    It checks all filing files in each quarter to see if any of them contain the given ticker.
 
    Args:
        ticker (str): The stock ticker to search for.
 
    Returns:
        str | None: The most recent quarter string (e.g., '2025Q1'), or None if no recent data is found for the ticker.
    """
    for quarter in get_all_quarters()[:2]:
        for file_path in get_all_quarter_files(quarter):
            # Read Tickers in chunks for memory efficiency on large files
            for chunk in pd.read_csv(file_path, usecols=['Ticker'], dtype={'Ticker': str}, chunksize=10000):
                if ticker in chunk['Ticker'].values:
                    return quarter
    return None


def get_all_quarter_files(quarter: str) -> list[str]:
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


def load_hedge_funds(filepath=f"./{DB_FOLDER}/{HEDGE_FUNDS_FILE}") -> list:
    """
    Loads hedge funds from file (hedge_funds.csv)
    """
    try:
        df = pd.read_csv(filepath, dtype={'CIK': str, 'CIKs': str}, keep_default_na=False)
        return df.to_dict('records')
    except Exception as e:
        print(f"Error while reading '{filepath}': {e}")
        return []


def load_models(filepath=f"./{DB_FOLDER}/{MODELS_FILE}") -> list:
    """
    Loads AI models from the file (models.csv).

    Returns:
        list: A list of dictionaries, each representing an AI model with the 'client' key holding the corresponding client class.
    """
    client_map = {
        "Google": GoogleAIClient,
        "Groq": GroqClient,
        "OpenRouter": OpenRouterClient,
    }
    try:
        df = pd.read_csv(filepath, keep_default_na=False)
        df['Client'] = df['Client'].map(client_map)
        return df.to_dict('records')
    except Exception as e:
        print(f"Error while reading models from '{filepath}': {e}")
        return []


def load_non_quarterly_data(filepath=f"./{DB_FOLDER}/{LATEST_SCHEDULE_FILINGS_FILE}") -> pd.DataFrame:
    """
    Loads the latest non-quarterly (13D/G and 4) filings from the CSV file.

    Args:
        filepath (str, optional): The path to the CSV file.

    Returns:
        pd.DataFrame: A DataFrame containing the most recent filing for each Fund-Ticker combination.
    """
    try:
        df = pd.read_csv(filepath, dtype={'Fund': str, 'CUSIP': str}, keep_default_na=False)
        # Keep only the most recent entry for each Ticker
        return df.sort_values(by=['Ticker', 'Filing_Date', 'Date'], ascending=False).drop_duplicates(subset='Ticker', keep='first')
    except Exception as e:
        print(f"Error while reading schedule filings from '{filepath}': {e}")
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
        fund_df['Fund'] = Path(file_path).stem.replace('_', ' ')
        all_fund_data.append(fund_df[fund_df['CUSIP'] != 'Total'])

    return pd.concat(all_fund_data, ignore_index=True)


def load_stocks(filepath=f"./{DB_FOLDER}/{STOCKS_FILE}") -> pd.DataFrame:
    """
    Loads the stock master data (CUSIP, Ticker, Company) from the CSV file.

    Args:
        filepath (str, optional): The path to the stocks CSV file.

    Returns:
        pd.DataFrame: A DataFrame with CUSIP as the index, or an empty DataFrame if the file is not found or an error occurs.
    """
    try:
        df = pd.read_csv(filepath, dtype={'CUSIP': str, 'Ticker': str, 'Company': str}, keep_default_na=False)
        return df.set_index('CUSIP')
    except Exception as e:
        print(f"Error while reading stocks file from '{filepath}': {e}")
        return pd.DataFrame()


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
        quarter_folder = Path(DB_FOLDER) / get_quarter(date)
        quarter_folder.mkdir(parents=True, exist_ok=True)

        filename = quarter_folder / f"{fund_name.replace(' ', '_')}.csv"
        comparison_dataframe.to_csv(filename, index=False)
        print(f"Created {filename}")
    except Exception as e:
        print(f"An error occurred while writing comparison file for '{fund_name}': {e}")


def save_non_quarterly_filings(schedule_filings: list, filepath=f"./{DB_FOLDER}/{LATEST_SCHEDULE_FILINGS_FILE}") -> None:
    """
    Combines the list of schedule filing DataFrames and saves them to a single CSV file.

    Args:
        schedule_filings (list): A list of pandas DataFrames, each representing schedule filings.
        filepath (str, optional): The path to the output CSV file.
    """
    if not schedule_filings:
        print("No schedule filings found to process.")
        return

    try:
        combined_schedules_df = pd.concat(schedule_filings, ignore_index=True)
        combined_schedules_df.sort_values(by=['Date', 'Filing_Date', 'Fund', 'Ticker'], ascending=[False, False, True, True], inplace=True)
        combined_schedules_df.to_csv(filepath, index=False, encoding='utf-8', quoting=csv.QUOTE_ALL)
        print(f"Latest schedule filings saved to {filepath}")
    except Exception as e:
        print(f"An error occurred while saving latest schedule filings to '{filepath}': {e}")


def save_stock(cusip: str, ticker: str, company: str) -> None:
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
        with open(Path(DB_FOLDER) / STOCKS_FILE, 'a', newline='', encoding='utf-8') as stocks_file:
            writer = csv.writer(stocks_file, quoting=csv.QUOTE_ALL)
            writer.writerow([cusip, ticker, company])
    except Exception as e:
        print(f"An error occurred while writing to '{STOCKS_FILE}': {e}")


def sort_stocks(filepath=f'./database/{STOCKS_FILE}') -> None:
    """
    Reads, sorts, and overwrites the master stocks CSV file.

    This function ensures the stocks file is clean, sorted, and consistently formatted.
    It sorts entries primarily by 'Ticker' and secondarily by 'CUSIP'.
    Any duplicates are removed keeping 'CUSIP' as the primary key.

    Args:
        filepath (str, optional): The path to the stocks CSV file.
    """
    try:
        df = pd.read_csv(filepath, dtype=str, keep_default_na=False).fillna('')
        df.drop_duplicates(subset=['CUSIP'], keep='first', inplace=True)
        df.sort_values(by=['Ticker', 'CUSIP'], inplace=True)
        df.to_csv(filepath, index=False, encoding='utf-8', quoting=csv.QUOTE_ALL)
    except Exception as e:
        print(f"An error occurred while processing file '{filepath}': {e}")
