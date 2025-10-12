from app.tickers.libraries import FinanceLibrary, FinanceDatabase, Finnhub, YFinance
from app.utils.database import load_stocks, save_stock


def assign_cusip(df):
    """
    Assigns a CUSIP to each Ticker in the DataFrame.

    It first uses a mapping from the local stocks database for known tickers.
    For any new tickers, it queries FinanceDatabase to find the CUSIP and updates the local database. This is needed for Form 4 filings that don't expose CUSIP information.
    """
    stocks = load_stocks().copy()

    # Create a mapping from Ticker to the first CUSIP found (because we can have multiple CUSIPs for the same Ticker)
    ticker_to_cusip_map = stocks.reset_index().drop_duplicates(subset='Ticker', keep='first').set_index('Ticker')['CUSIP'].to_dict()

    # 1. Map existing tickers to CUSIPs
    df['CUSIP'] = df['Ticker'].map(ticker_to_cusip_map)

    # 2. Identify rows with stocks that are not in database
    missing_stocks = df['CUSIP'].isnull() & df['Ticker'].notna()
    if missing_stocks.any():
        # 3. For new tickers, fetch the CUSIP and save it
        def fetch_and_save(row):
            cusip = FinanceDatabase.get_cusip(row['Ticker'])
            save_stock(cusip, row['Ticker'], row['Company'])
            return cusip

        df.loc[missing_stocks, 'CUSIP'] = df[missing_stocks].apply(fetch_and_save, axis=1)

    return df


def get_libraries() -> list[FinanceLibrary]:
    """
    Returns an ordered (based on priority) list of FinanceLibrary instances.
    """
    return [YFinance, Finnhub, FinanceDatabase]


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
