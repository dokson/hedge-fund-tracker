from .finnhub_client import get_ticker_with_fallback
from scraper.db.masterdata import load_stocks, save_stock
import financedatabase as fd
import pandas as pd

FINANCE_DATABASE = fd.Equities()


def _get_ticker_from_fd(cusip):
    """
    Searches for a ticker for a given CUSIP using financedatabase.
    If multiple tickers are found, it returns the shortest one.
    """
    result = FINANCE_DATABASE.search(cusip=cusip)

    if not result.empty:
        result["ticker_length"] = [len(idx) for idx in result.index]
        result = result.sort_values(by="ticker_length")
        return result.index[0]
    else:
        print(f"Finance Database: No ticker found for CUSIP {cusip}.")
        return None


def get_ticker(df_comparison):
    """
    Maps CUSIPs to tickers using Finnhub (first choice) or Finance Database if Finnhub fails.
    Takes the entire comparison DataFrame as input to access both CUSIP and Company name (needed for Finnhub).
    """

    stocks = load_stocks().copy()

    for index, row in df_comparison.iterrows():
        cusip = row['CUSIP']
        company = row['Company']

        if cusip not in stocks.index:
            print(f"Getting Tickers for unknown CUSIP ({cusip})...")
            ticker = get_ticker_with_fallback(cusip, company) or _get_ticker_from_fd(cusip)
            stocks.loc[cusip] = ticker
            if pd.notna(ticker):
                save_stock(cusip, ticker, company)

    return stocks
