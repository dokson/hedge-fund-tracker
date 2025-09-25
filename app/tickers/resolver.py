from app.tickers.finance_database import FinanceDatabase
from app.tickers.finnhub import Finnhub
from app.tickers.yfinance import YFinance
from app.utils.database import load_stocks, save_stock


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
    Maps CUSIPs to tickers and company names by querying multiple sources in a specific order.
    It prioritizes YFinance first, then Finnhub and finally FinanceDatabase.
    It takes the entire comparison DataFrame as input to access both CUSIP and Company name (needed for Finnhub).
    """
    stocks = load_stocks().copy()

    for index, row in df.iterrows():
        cusip = row['CUSIP']
        company = row['Company']

        if cusip not in stocks.index:
            ticker = YFinance.get_ticker(cusip)
            if not ticker:
                ticker = Finnhub.get_ticker(cusip, company)
            if not ticker:
                ticker = FinanceDatabase.get_ticker(cusip)
            
            if ticker:
                company_name = YFinance.get_company(ticker)
                if not company_name:
                    company_name = Finnhub.get_company(cusip)
                if not company_name:
                    company_name = FinanceDatabase.get_company(cusip)

                stocks.loc[cusip, 'Ticker'] = ticker
                stocks.loc[cusip, 'Company'] = company_name
                save_stock(cusip, ticker, company_name)

        df.at[index, 'Ticker'] = stocks.loc[cusip, 'Ticker']
        if company == '':
            df.at[index, 'Company'] = stocks.loc[cusip, 'Company']

    return df
