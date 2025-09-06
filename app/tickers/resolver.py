from app.tickers.finnhub_client import get_ticker_and_company
from app.tickers.financedatabase import get_ticker, get_company
from app.utils.database import load_stocks, save_stock
import pandas as pd
import time


def assign_cusip(df):
    """
    Assigns the first corresponding CUSIP to Tickers using the local stocks database.
    This is needed for Form 4 filings that don't expose CUSIP information.
    """
    # Create a mapping from Ticker to the first CUSIP found (because we can have multiple CUSIPs for the same Ticker)
    ticker_to_cusip_map = load_stocks().reset_index().drop_duplicates(subset='Ticker', keep='first').set_index('Ticker')['CUSIP'].to_dict()

    df['CUSIP'] = [ticker_to_cusip_map.get(ticker, '') for ticker in df['Ticker']]
    return df


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
                    ticker = get_ticker(cusip)
                    if pd.notna(ticker):
                        company = get_company(cusip)
                        stocks.loc[cusip, 'Company'] = company
            else:
                ticker, _ = get_ticker_and_company(cusip, company)
                if pd.isna(ticker):
                    ticker = get_ticker(cusip)

            if pd.notna(ticker):
                stocks.loc[cusip, 'Ticker'] = ticker
                save_stock(cusip, ticker, company.title())
            
            time.sleep(1)

        df.at[index, 'Ticker'] = stocks.loc[cusip, 'Ticker']
        if company == '':
            df.at[index, 'Company'] = stocks.loc[cusip, 'Company']

    return df
