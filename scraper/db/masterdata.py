import pandas as pd


HEDGE_FUNDS_FILE = 'hedge_funds.csv'
STOCKS_FILE = 'stocks.csv'


def load_hedge_funds(filepath=f"./database/{HEDGE_FUNDS_FILE}"):
    """
    Loads hedge funds from file (hedge_funds.csv)
    """
    try:
        df = pd.read_csv(filepath, dtype={'cik': str})

        return df[['cik', 'hedge_fund', 'portfolio_manager']].to_dict('records')

    except Exception as e:
        print(f"Errore while reading '{filepath}': {e}")
        return []
    

def load_stocks(filepath=f"./database/{STOCKS_FILE}"):
    """
    Loads stocks masterdata into a pandas Series.
    Returns an empty Series if the file doesn't exist or is empty.
    """
    try:
        df = pd.read_csv(filepath, dtype={'CUSIP': str, 'Ticker': str, 'Company': str})
        return df.set_index('CUSIP')['Ticker']
    except Exception as e:
        print(f"Errore while reading '{filepath}': {e}")
        return []


def save_stock(cusip, ticker, company):
    """Appends a new CUSIP-Ticker pair to stocks.csv."""
    
    try:
        with open(f'./database/{STOCKS_FILE}', 'a', newline='', encoding='utf-8') as f:
            f.write(f'{cusip},{ticker},{company.title()}\n')
    except Exception as e:
        print(f"An error occurred while writing file '{STOCKS_FILE}': {e}")


def sort_stocks(filepath = f'./database/{STOCKS_FILE}'):
    """
    Reads stocks.csv, sorts it by Ticker, removes duplicate CUSIPs, and overwrites the file.
    """
    try:
        df = pd.read_csv(filepath, dtype=str).fillna('')
        df.sort_values(by='Ticker', inplace=True)
        df.to_csv(filepath, index=False, encoding='utf-8')
    except Exception as e:
        print(f"An error occurred while writing file '{STOCKS_FILE}': {e}")
