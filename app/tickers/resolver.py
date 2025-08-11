from .finnhub_client import get_finnhub_timeout, get_ticker_and_company
from app.utils.database import load_stocks, save_stock
import financedatabase as fd
import pandas as pd
import time


def _get_ticker_from_fd(cusip):
    """
    Searches for a ticker for a given CUSIP using financedatabase.
    If multiple tickers are found, it returns the shortest one.
    """
    result = fd.Equities().search(cusip=cusip)

    if not result.empty:
        result['ticker_length'] = [len(idx) for idx in result.index]
        result = result.sort_values(by='ticker_length')
        return result.index[0]
    else:
        print(f"⚠️\u3000Finance Database: No ticker found for CUSIP {cusip}")
        return None


def _get_company_from_fd(cusip):
    """
    Searches for a company for a given CUSIP using financedatabase.
    If multiple rows are found, it returns the one with the shortest ticker.
    """
    result = fd.Equities().search(cusip=cusip)
    
    if not result.empty:
        result['ticker_length'] = [len(idx) for idx in result.index]
        result = result.sort_values(by='ticker_length')
        return result.iloc[0]['name']
    else:
        print(f"⚠️\u3000Finance Database: No company found for CUSIP {cusip}")
        return ''


def resolve_ticker(df):
    """
    Maps CUSIPs to tickers using Finnhub (first choice) or Finance Database if Finnhub fails.
    Takes the entire comparison DataFrame as input to access both CUSIP and Company name (needed for Finnhub).
    """
    stocks = load_stocks().copy()

    for index, row in df.iterrows():
        cusip = row['CUSIP']
        company = row['Company']

        if cusip not in stocks.index:
            if company == '':
                ticker, company = get_ticker_and_company(cusip, company)
                if pd.isna(ticker):
                    ticker = _get_ticker_from_fd(cusip)
                    if pd.notna(ticker):
                        company = _get_company_from_fd(cusip)
                        stocks.loc[cusip, 'Company'] = company
            else:
                ticker, _ = get_ticker_and_company(cusip, company)
                if pd.isna(ticker):
                    ticker = _get_ticker_from_fd(cusip)

            if pd.notna(ticker):
                stocks.loc[cusip, 'Ticker'] = ticker
                save_stock(cusip, ticker, company.title())
            
            time.sleep(get_finnhub_timeout())

        df.at[index, 'Ticker'] = stocks.loc[cusip, 'Ticker']
        if company == '':
            df.at[index, 'Company'] = stocks.loc[cusip, 'Company']

    return df
