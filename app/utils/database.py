from app.ai.clients import GitHubClient, GoogleAIClient, GroqClient, HuggingFaceClient, OpenRouterClient
from app.utils.strings import get_quarter
from pathlib import Path
import pandas as pd
import csv
import re

DB_FOLDER = './database'
HEDGE_FUNDS_FILE = 'hedge_funds.csv'
EXCLUDED_HEDGE_FUNDS_FILE = 'excluded_hedge_funds.csv'
GICS_HIERARCHY_FILE = 'GICS/hierarchy.csv'
LATEST_SCHEDULE_FILINGS_FILE = 'non_quarterly.csv'
MODELS_FILE = 'models.csv'
STOCKS_FILE = 'stocks.csv'


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
        quarter for quarter in get_all_quarters()
        if (Path(DB_FOLDER) / quarter / fund_filename).exists()
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
            for chunk in pd.read_csv(file_path, usecols=['Ticker'], dtype={'Ticker': str}, chunksize=10000):
                if ticker in chunk['Ticker'].values:
                    return quarter
                
    # Check non-quarterly data for IPOs or recent additions
    non_quarterly = load_non_quarterly_data()
    if not non_quarterly.empty and ticker in non_quarterly['Ticker'].values:
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
    quarter_dir = Path(DB_FOLDER) / quarter

    if not quarter_dir.is_dir():
        return []

    return [
        str(file_path) for file_path in quarter_dir.glob('*.csv')
    ]


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
    filepath = Path(DB_FOLDER) / quarter / fund_filename
    if filepath.exists():
        df = pd.read_csv(filepath)
        df['Fund'] = fund
        return df[df['CUSIP'] != 'Total']
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
    df['Shares'] = pd.to_numeric(df['Shares'], errors='coerce').fillna(0)
    if 'Value' in df.columns:
        df['Value'] = get_numeric_series(df['Value']).fillna(0)
    
    # Calculate price per share from the report
    df['Reported_Price'] = df.apply(
        lambda r: r['Value'] / r['Shares'] if r['Shares'] > 0 else 0,
        axis=1
    )
    
    return df


def load_hedge_funds(filepath=f"./{DB_FOLDER}/{HEDGE_FUNDS_FILE}") -> list:
    """
    Loads hedge funds from file (hedge_funds.csv)
    """
    try:
        df = pd.read_csv(filepath, dtype={'CIK': str, 'CIKs': str}, keep_default_na=False)
        return df.to_dict('records')
    except Exception as e:
        print(f"❌ Error while reading '{filepath}': {e}")
        return []


def load_models(filepath=f"./{DB_FOLDER}/{MODELS_FILE}") -> list:
    """
    Loads AI models from the file (models.csv).

    Returns:
        list: A list of dictionaries, each representing an AI model with the 'client' key holding the corresponding client class.
    """
    client_map = {
        "GitHub": GitHubClient,
        "Google": GoogleAIClient,
        "Groq": GroqClient,
        "HuggingFace": HuggingFaceClient,
        "OpenRouter": OpenRouterClient,
    }
    try:
        df = pd.read_csv(filepath, keep_default_na=False)
        df['Client'] = df['Client'].map(client_map)
        return df.to_dict('records')
    except Exception as e:
        print(f"❌ Error while reading models from '{filepath}': {e}")
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
        # Keep only the most recent entry for each Ticker for each Fund
        return df.sort_values(by=['Date', 'Filing_Date'], ascending=False).drop_duplicates(subset=['Fund', 'Ticker'], keep='first')
    except Exception as e:
        print(f"❌ Error while reading schedule filings from '{filepath}': {e}")
        return pd.DataFrame()


def load_gics_hierarchy(filepath=f"./{DB_FOLDER}/{GICS_HIERARCHY_FILE}") -> pd.DataFrame:
    """
    Loads the full GICS hierarchy from the CSV file.

    Args:
        filepath (str, optional): The path to the GICS hierarchy CSV file.

    Returns:
        pd.DataFrame: A DataFrame with the full GICS hierarchy mapping.
    """
    try:
        return pd.read_csv(filepath)
    except Exception as e:
        print(f"❌ Error while reading GICS hierarchy from '{filepath}': {e}")
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
        print(f"❌ Error while reading stocks file from '{filepath}': {e}")
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
        print(f"❌ An error occurred while writing comparison file for '{fund_name}': {e}")


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
        print(f"❌ An error occurred while saving latest schedule filings to '{filepath}': {e}")


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
        print(f"❌ An error occurred while writing to '{STOCKS_FILE}': {e}")


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
        print(f"❌ An error occurred while processing file '{filepath}': {e}")


def find_cusips_for_ticker(old_ticker: str) -> list[dict[str, str]]:
    """
    Finds all CUSIPs associated with a given ticker in the stocks.csv file.
    
    Args:
        old_ticker (str): The ticker to search for.
        
    Returns:
        list: A list of dictionaries containing CUSIP, Ticker, and Company information.
    """
    stocks_path = Path(DB_FOLDER) / STOCKS_FILE
    matching_stocks = []
    
    if not stocks_path.exists():
        print(f"❌ Error: {STOCKS_FILE} not found at {stocks_path}")
        return matching_stocks
    
    with open(stocks_path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Ticker'] == old_ticker:
                matching_stocks.append({
                    'CUSIP': row['CUSIP'],
                    'Ticker': row['Ticker'],
                    'Company': row['Company']
                })
    
    return matching_stocks


def update_stocks_csv(old_ticker: str, new_ticker: str) -> int:
    """
    Updates the ticker in stocks.csv for all matching CUSIPs.
    
    Args:
        old_ticker (str): The current ticker to replace.
        new_ticker (str): The new ticker to use.
        
    Returns:
        int: The number of rows updated.
    """
    stocks_path = Path(DB_FOLDER) / STOCKS_FILE
    
    if not stocks_path.exists():
        print(f"❌ Error: {STOCKS_FILE} not found")
        return 0
    
    # Read all rows
    rows = []
    updated_count = 0
    
    with open(stocks_path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        for row in reader:
            if row['Ticker'] == old_ticker:
                row['Ticker'] = new_ticker
                updated_count += 1
            rows.append(row)
    
    # Write back
    with open(stocks_path, 'w', encoding='utf-8', newline='') as f:
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
    quarters = get_all_quarters()
    
    for quarter in quarters:
        quarter_path = Path(DB_FOLDER) / quarter
        
        if not quarter_path.exists():
            continue
        
        csv_files = list(quarter_path.glob('*.csv'))
        
        for csv_file in csv_files:
            try:
                rows = []
                file_updated = False
                
                with open(csv_file, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames
                    
                    if 'CUSIP' not in fieldnames or 'Ticker' not in fieldnames:
                        continue
                    
                    for row in reader:
                        if row['CUSIP'] in cusips:
                            row['Ticker'] = new_ticker
                            file_updated = True
                        rows.append(row)
                
                if file_updated:
                    with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
                    
                    print(f"✅ Updated {quarter}/{csv_file.name}")
                    
            except Exception as e:
                print(f"❌ Error processing {csv_file}: {e}")



def update_non_quarterly_filings(cusips: list[str], new_ticker: str) -> int:
    """
    Updates the ticker in the non_quarterly.csv file for the specified CUSIPs.
    
    Args:
        cusips (list): List of CUSIPs to update.
        new_ticker (str): The new ticker to use.
        
    Returns:
        int: Number of rows updated.
    """
    nq_path = Path(DB_FOLDER) / LATEST_SCHEDULE_FILINGS_FILE
    
    rows = []
    updated_count = 0
    
    try:
        with open(nq_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            
            for row in reader:
                if row['CUSIP'] in cusips:
                    row['Ticker'] = new_ticker
                    updated_count += 1
                rows.append(row)
        
        with open(nq_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)
        
        if updated_count > 0:
            print(f"✅ Updated {updated_count} row(s) in {LATEST_SCHEDULE_FILINGS_FILE}")
            
    except Exception as e:
        print(f"❌ Error processing {LATEST_SCHEDULE_FILINGS_FILE}: {e}")
        return 0
    
    return updated_count


def update_ticker_for_cusip(cusip: str, new_ticker: str) -> None:
    """
    Updates the ticker for a single CUSIP across the entire database.
    
    This function:
    1. Updates the ticker for the specified CUSIP in stocks.csv
    2. Updates all quarterly filings for that CUSIP
    3. Updates the non_quarterly.csv file
    
    Args:
        cusip (str): The CUSIP to update.
        new_ticker (str): The new ticker to use.
    """
    stocks_path = Path(DB_FOLDER) / STOCKS_FILE
    
    if not stocks_path.exists():
        print(f"❌ Error: {STOCKS_FILE} not found")
        return
    
    # Update stocks.csv
    rows = []
    found = False
    old_ticker = None
    company = None
    
    with open(stocks_path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        for row in reader:
            if row['CUSIP'] == cusip:
                old_ticker = row['Ticker']
                company = row['Company']
                row['Ticker'] = new_ticker
                found = True
            rows.append(row)
    
    if not found:
        print(f"❌ CUSIP '{cusip}' not found in {STOCKS_FILE}")
        return
    
    print(f"  - CUSIP: {cusip}, Company: {company}, Old Ticker: {old_ticker} → New Ticker: {new_ticker}")
    
    # Write back stocks.csv
    with open(stocks_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)
    
    # Update quarterly filings and non-quarterly filings
    update_quarterly_filings([cusip], new_ticker)
    update_non_quarterly_filings([cusip], new_ticker)


def update_ticker(old_ticker: str, new_ticker: str) -> None:
    """
    Updates a ticker across the entire database.
    
    This function:
    1. Finds all CUSIPs associated with the old ticker in stocks.csv
    2. Updates the ticker in stocks.csv
    3. Updates all quarterly filings for those CUSIPs
    4. Updates the non_quarterly.csv file
    
    Args:
        old_ticker (str): The current ticker to replace.
        new_ticker (str): The new ticker to use.
    """
    matching_stocks = find_cusips_for_ticker(old_ticker)
    
    if not matching_stocks:
        print(f"❌ No stocks found with ticker '{old_ticker}'")
        return
    
    for stock in matching_stocks:
        print(f"  - CUSIP: {stock['CUSIP']}, Company: {stock['Company']}")
    
    cusips = [stock['CUSIP'] for stock in matching_stocks]
    
    update_stocks_csv(old_ticker, new_ticker)
    update_quarterly_filings(cusips, new_ticker)
    update_non_quarterly_filings(cusips, new_ticker)


def delete_fund_from_database(fund_info: dict, url: str = "") -> None:
    """
    Deletes a hedge fund from the database.
    
    This function:
    1. Removes all quarterly filing files for the fund.
    2. Moves the fund record from hedge_funds.csv to excluded_hedge_funds.csv with the provided URL.
    
    Args:
        fund_info (dict): A dictionary containing fund information ('Fund', 'CIK', etc.)
        url (str): The website URL of the fund.
    """
    fund_name = fund_info.get('Fund')
    if not fund_name:
        print("❌ Error: Fund name is missing.")
        return

    print(f"Deleting '{fund_name}' from database...")

    # 1. Delete quarterly filing files
    fund_filename = f"{fund_name.replace(' ', '_')}.csv"
    for quarter in get_all_quarters():
        filepath = Path(DB_FOLDER) / quarter / fund_filename
        if filepath.exists():
            try:
                filepath.unlink()
                print(f"  - Deleted: {quarter}/{fund_filename}")
            except Exception as e:
                print(f"  - ❌ Error deleting {filepath}: {e}")

    # 2. Update CSV files
    hedge_funds_path = Path(DB_FOLDER) / HEDGE_FUNDS_FILE
    excluded_path = Path(DB_FOLDER) / EXCLUDED_HEDGE_FUNDS_FILE

    try:
        # Load all hedge funds
        df_hedge_funds = pd.read_csv(hedge_funds_path, dtype=str, keep_default_na=False)
        
        # Find the record to move
        record_to_move = df_hedge_funds[df_hedge_funds['Fund'] == fund_name]
        
        if record_to_move.empty:
            print(f"❌ Fund '{fund_name}' not found in {HEDGE_FUNDS_FILE}")
        else:
            # Prepare record for excluded_hedge_funds.csv
            excluded_record = record_to_move.copy()
            excluded_record['URL'] = url
            
            # Append to excluded_hedge_funds.csv
            if excluded_path.exists():
                excluded_record.to_csv(excluded_path, mode='a', header=False, index=False, quoting=csv.QUOTE_ALL)
            else:
                excluded_record.to_csv(excluded_path, index=False, quoting=csv.QUOTE_ALL)
            print(f"  - Added '{fund_name}' to excluded_hedge_funds.csv with URL: {url}")

            # Remove from hedge_funds.csv
            df_hedge_funds = df_hedge_funds[df_hedge_funds['Fund'] != fund_name]
            df_hedge_funds.to_csv(hedge_funds_path, index=False, quoting=csv.QUOTE_ALL)
            print(f"  - Removed '{fund_name}' from {HEDGE_FUNDS_FILE}")

    except Exception as e:
        print(f"❌ Error updating CSV files: {e}")

    print(f"✅ Deletion of '{fund_name}' completed.")


def get_funds_missing_quarters() -> dict[str, list[str]]:
    """
    Identifies funds that are missing data for one or more available quarters.

    Returns:
        dict: A dictionary mapping fund names to a list of missing quarters.
    """
    all_quarters = set(get_all_quarters())
    funds = load_hedge_funds()
    missing_data_funds = {}

    for fund in funds:
        fund_name = fund['Fund']
        fund_quarters = set(get_quarters_for_fund(fund_name))
        
        if fund_quarters != all_quarters:
            missing = sorted(list(all_quarters - fund_quarters))
            missing_data_funds[fund_name] = missing

    return missing_data_funds
