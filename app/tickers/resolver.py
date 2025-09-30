from app.tickers.libraries import FinanceLibrary, FinanceDatabase, Finnhub, YFinance
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


def get_libraries() -> list[FinanceLibrary]:
    """
    Returns an ordered (based on priority) list of FinanceLibrary instances.
    """
    return [YFinance(), Finnhub(), FinanceDatabase()]


def resolve_ticker(df):
    """
    Maps CUSIPs to tickers and company names by querying multiple sources in a specific order.
    It prioritizes YFinance first, then Finnhub and finally FinanceDatabase to find the information (refering to get_libraries() order).
    It takes the entire comparison DataFrame as input to access both CUSIP and Company name (needed for Finnhub).
    """
    stocks = load_stocks().copy()
    libraries = get_libraries()

    for index, row in df.iterrows():
        cusip = row['CUSIP']
        company = row['Company']

        if cusip not in stocks.index:
            ticker = None
            for library in libraries:
                ticker = library.get_ticker(cusip, company_name=company)
                if ticker:
                    break

            if ticker:
                company_name = None
                for library in libraries:
                    company_name = library.get_company(cusip, ticker=ticker)
                    if company_name:
                        break

                stocks.loc[cusip, 'Ticker'] = ticker
                stocks.loc[cusip, 'Company'] = company_name
                save_stock(cusip, ticker, company_name)

        df.at[index, 'Ticker'] = stocks.loc[cusip, 'Ticker']
        if company == '':
            df.at[index, 'Company'] = stocks.loc[cusip, 'Company']

    return df
