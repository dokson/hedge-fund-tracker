from app.stocks.libraries import FinanceLibrary, FinanceDatabase, Finnhub, YFinance, TradingView
from app.utils.database import load_stocks, save_stock
from app.utils.github import open_issue
from pandas import Series
import pandas as pd


class TickerResolver:
    """
    Orchestrates the resolution of CUSIPs to Tickers and Company names using a prioritized list of financial data libraries.
    """
    @staticmethod
    def get_libraries() -> list[type[FinanceLibrary]]:
        """
        Returns an ordered (based on priority) list of FinanceLibrary classes.
        """
        return [YFinance, Finnhub, FinanceDatabase, TradingView]


    @staticmethod
    def resolve_ticker(df: pd.DataFrame) -> pd.DataFrame:
        """
        Maps CUSIPs to tickers and company names by querying multiple sources in a specific order.
        It prioritizes libraries defined in `get_libraries()`.
        
        Args:
            df (pd.DataFrame): DataFrame containing 'CUSIP' and 'Company' columns.
            
        Returns:
            pd.DataFrame: The verified DataFrame with 'Ticker' and 'Company' columns updated.
        """
        stocks = load_stocks().copy()
        libraries = TickerResolver.get_libraries()

        for index, row in df.iterrows():
            cusip = row['CUSIP']
            company = row['Company']

            # If CUSIP is not in our local database, try to resolve it
            if cusip not in stocks.index:
                ticker = None
                # Strategy: Try each library to find the ticker
                for library in libraries:
                    try:
                        ticker = library.get_ticker(cusip, company_name=company)
                        if ticker:
                            break
                    except Exception as e:
                        print(f"⚠️ {library.__name__}: Failed to resolve ticker for CUSIP {cusip}: {e}")
                        continue

                # If a ticker was found, try to resolve the company name
                if ticker:
                    company_name = None
                    for library in libraries:
                        try:
                            company_name = library.get_company(cusip, ticker=ticker)
                            if company_name:
                                break
                        except Exception as e:
                            continue

                    company_name = company_name or company
                    
                    if not company_name:
                        # Fallback logging if company name is still missing
                        subject = f"Company not found for CUSIP '{cusip}'"
                        body = f"Could not find any company for the CUSIP: {cusip} / Ticker: '{ticker}'."
                        open_issue(subject, body)

                    # Update local database
                    # Note: We're acting on a copy of 'stocks' from load_stocks(), but save_stock updates the file.
                    stocks.loc[cusip, 'Ticker'] = ticker
                    stocks.loc[cusip, 'Company'] = company_name
                    save_stock(cusip, ticker, company_name)
                else:
                    # Critical failure: No ticker found across all libraries
                    subject = f"Ticker not found for CUSIP '{cusip}'"
                    body = f"Could not resolve ticker for CUSIP: {cusip} / Company: '{company}'"
                    open_issue(subject, body)

            # If CUSIP is already in database, use that info
            if cusip in stocks.index:
                ticker = stocks.loc[cusip, 'Ticker']

            # Update the row in the input DataFrame
            # Extract scalar if it's a Series (defensive)
            df.at[index, 'Ticker'] = ticker.iloc[0] if isinstance(ticker, Series) else ticker
            
            # If input company name was empty, fill it from DB
            if company == '':
                df.at[index, 'Company'] = stocks.loc[cusip, 'Company']

        return df

    @staticmethod
    def assign_cusip(df: pd.DataFrame) -> pd.DataFrame:
        """
        Assigns a CUSIP to each Ticker in the DataFrame.

        It first uses a mapping from the local stocks database for known tickers.
        For any new tickers, it queries FinanceDatabase to find the CUSIP and updates the local database.
        This is primarily needed for Form 4 filings that don't expose CUSIP information.
        """
        stocks = load_stocks().copy()

        # Create a mapping from Ticker to the first CUSIP found
        ticker_to_cusip_map = stocks.reset_index().drop_duplicates(subset='Ticker', keep='first').set_index('Ticker')['CUSIP'].to_dict()

        # 1. Map existing tickers to CUSIPs
        df['CUSIP'] = df['Ticker'].map(ticker_to_cusip_map)

        # 2. Identify rows with stocks that are not in database
        missing_stocks = df['CUSIP'].isnull() & df['Ticker'].notna()
        
        if missing_stocks.any():
            # 3. For new tickers, fetch the CUSIP and save it
            def fetch_and_save(row):
                # Currently assigning CUSIP relies specifically on FinanceDatabase logic
                try:
                    cusip = FinanceDatabase.get_cusip(row['Ticker'])
                    if cusip:
                        save_stock(cusip, row['Ticker'], row['Company'])
                    return cusip
                except Exception as e:
                    print(f"⚠️ Failed to fetch CUSIP for {row['Ticker']}: {e}")
                    return None

            df.loc[missing_stocks, 'CUSIP'] = df[missing_stocks].apply(fetch_and_save, axis=1)

        return df
