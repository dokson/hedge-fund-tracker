import pandas as pd
from pandas import Series

from app.stocks.libraries import (
    FMP,
    FinanceLibrary,
    OpenFIGI,
    TradingView,
    YFinance,
)
from app.stocks.libraries.nasdaq import Nasdaq
from app.utils.database import load_stocks, save_stock, save_stocks
from app.utils.github import open_issue
from app.utils.logger import get_logger, log_safe

logger = get_logger(__name__)


class TickerResolver:
    """
    Orchestrates the resolution of CUSIPs to Tickers and Company names using a prioritized list of financial data libraries.
    """

    @staticmethod
    def get_libraries() -> list[type[FinanceLibrary]]:
        """
        Returns an ordered (based on priority) list of FinanceLibrary classes.
        """
        return [YFinance, OpenFIGI, TradingView]

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
            cusip = row["CUSIP"]
            company = row["Company"]
            ticker = None

            # If CUSIP is not in our local database, try to resolve it
            if cusip not in stocks.index:
                # Strategy: Try each library to find the ticker
                for library in libraries:
                    try:
                        ticker = library.get_ticker(cusip, company_name=company)
                        if ticker:
                            break
                    except Exception:
                        logger.warning(
                            "%s: Failed to resolve ticker for CUSIP %s",
                            library.__name__,
                            log_safe(cusip),
                            exc_info=True,
                        )
                        continue

                # If a ticker was found, try to resolve the company name
                if ticker:
                    company_name = None
                    for library in libraries:
                        try:
                            company_name = library.get_company(cusip, ticker=ticker)
                            if company_name:
                                break
                        except Exception:
                            continue

                    company_name = company_name or company

                    if not company_name:
                        # Fallback logging if company name is still missing
                        subject = f"Company not found for CUSIP '{cusip}'"
                        body = f"Could not find any company for the CUSIP: {cusip} / Ticker: '{ticker}'."
                        open_issue(subject, body)

                    # Update local database
                    # Note: We're acting on a copy of 'stocks' from load_stocks(), but save_stock updates the file.
                    stocks.loc[cusip, "Ticker"] = ticker
                    stocks.loc[cusip, "Company"] = company_name
                    save_stock(cusip, ticker, company_name)
                else:
                    # Critical failure: No ticker found across all libraries
                    subject = f"Ticker not found for CUSIP '{cusip}'"
                    body = f"Could not resolve ticker for CUSIP: {cusip} / Company: '{company}'"
                    open_issue(subject, body)

            # If CUSIP is already in database, use that info
            if cusip in stocks.index:
                ticker = stocks.loc[cusip, "Ticker"]

            # Update the row in the input DataFrame
            # Extract scalar if it's a Series (defensive)
            df.at[index, "Ticker"] = ticker.iloc[0] if isinstance(ticker, Series) else ticker

            # If input company name was empty, fill it from DB
            if company == "":
                df.at[index, "Company"] = stocks.loc[cusip, "Company"]

        return df

    @staticmethod
    def update_changed_tickers() -> list[dict]:
        """
        Fetches recent ticker symbol changes from NASDAQ and updates stocks.csv accordingly.
        Returns a list of dicts describing each applied update (cusip, old, new, company).
        """
        changes = Nasdaq.get_symbol_changes()
        if not changes:
            return []

        stocks = load_stocks()
        if stocks.empty:
            return []

        updates = []
        for change in changes:
            old_symbol = change.get("oldSymbol")
            new_symbol = change.get("newSymbol")
            company_name = change.get("companyName", "")

            if not old_symbol or not new_symbol:
                continue

            # Find all CUSIPs with the old ticker
            matching = stocks[stocks["Ticker"] == old_symbol]
            for cusip in matching.index:
                stocks.at[cusip, "Ticker"] = new_symbol
                stocks.at[cusip, "Company"] = company_name
                updates.append(
                    {
                        "cusip": cusip,
                        "old": old_symbol,
                        "new": new_symbol,
                        "company": company_name,
                    }
                )
                logger.info(
                    "%s → %s (CUSIP %s) — %s",
                    log_safe(old_symbol),
                    log_safe(new_symbol),
                    log_safe(cusip),
                    log_safe(company_name),
                    emoji="🔄",
                )

        if updates:
            save_stocks(stocks)

        return updates

    @staticmethod
    def assign_cusip(df: pd.DataFrame) -> pd.DataFrame:
        """
        Assigns a CUSIP to each Ticker in the DataFrame.

        It first uses a mapping from the local stocks database for known tickers.
        For any new tickers, it queries FMP (Financial Modeling Prep) for a fresh
        CUSIP. If FMP misses (no API key or no match), the CUSIP is left unset
        and a GitHub issue is opened so the gap is visible — stocks.csv only ever
        stores real CUSIPs. This path is primarily needed for Form 4 filings that
        don't expose CUSIP.
        """
        stocks = load_stocks().copy()

        # Create a mapping from Ticker to the first CUSIP found
        ticker_to_cusip_map = (
            stocks.reset_index()
            .drop_duplicates(subset="Ticker", keep="first")
            .set_index("Ticker")["CUSIP"]
            .to_dict()
        )

        # 1. Map existing tickers to CUSIPs
        df["CUSIP"] = df["Ticker"].map(ticker_to_cusip_map)

        # 2. Identify rows with stocks that are not in database
        missing_stocks = df["CUSIP"].isnull() & df["Ticker"].notna()

        if missing_stocks.any():

            def fetch_and_save(row):
                """
                Resolves a CUSIP for a new ticker via FMP and persists it. When FMP
                cannot resolve the ticker, opens a GitHub issue and leaves the CUSIP
                unset — no synthetic placeholders are written, so stocks.csv only
                ever contains real CUSIPs.
                """
                ticker = row["Ticker"]
                try:
                    cusip = FMP.get_cusip(ticker)
                except Exception:
                    logger.error("Failed to fetch CUSIP for %s", log_safe(ticker), exc_info=True)
                    return None

                if not cusip:
                    subject = f"No CUSIP found for ticker '{ticker}'"
                    body = f"FMP could not resolve the CUSIP for ticker: {ticker}."
                    open_issue(subject, body)
                    return None

                save_stock(cusip, ticker, row["Company"])
                return cusip

            df.loc[missing_stocks, "CUSIP"] = df[missing_stocks].apply(fetch_and_save, axis=1)

        return df
