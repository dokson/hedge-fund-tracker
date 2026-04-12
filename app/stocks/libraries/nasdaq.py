from app.stocks.libraries.base_library import FinanceLibrary
from datetime import date, timedelta
import requests


class Nasdaq(FinanceLibrary):
    """
    Client for fetching stock prices from the Nasdaq API.
    Covers stocks, ETFs, and mutual funds that yfinance/TradingView may miss.
    """
    BASE_URL = "https://api.nasdaq.com/api/quote"
    HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    ASSET_CLASSES = ["mutualfunds"]


    SYMBOL_CHANGE_URL = "https://api.nasdaq.com/api/quote/list-type-extended/symbolchangehistory"


    @staticmethod
    def get_symbol_changes() -> list[dict]:
        """
        Fetches the list of recent ticker symbol changes from the NASDAQ API.
        Returns a list of dicts with 'oldSymbol', 'newSymbol', and 'companyName' keys.
        """
        try:
            resp = requests.get(Nasdaq.SYMBOL_CHANGE_URL, headers=Nasdaq.HEADERS, timeout=10)
            data = resp.json().get("data")
            if not data:
                return []
            return data.get("symbolChangeHistoryTable", {}).get("rows", [])
        except Exception:
            return []


    @staticmethod
    def get_ticker(cusip: str, **kwargs) -> str | None:
        """
        Not supported by the Nasdaq API.
        """
        return None


    @staticmethod
    def get_company(cusip: str, **kwargs) -> str | None:
        """
        Not supported by the Nasdaq API.
        """
        return None


    @staticmethod
    def _fetch_historical(ticker: str, date_obj: date) -> dict | None:
        """
        Fetches a single day of historical data from the Nasdaq API, trying all asset classes.
        Returns the first row of data found, or None.
        """
        from_str = date_obj.strftime("%Y-%m-%d")
        to_str = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
        expected_date = date_obj.strftime("%m/%d/%Y")
        for asset_class in Nasdaq.ASSET_CLASSES:
            try:
                url = (
                    f"{Nasdaq.BASE_URL}/{ticker}/historical"
                    f"?assetclass={asset_class}&fromdate={from_str}&todate={to_str}&limit=5"
                )
                resp = requests.get(url, headers=Nasdaq.HEADERS, timeout=10)
                data = resp.json().get("data")
                if data and data.get("tradesTable", {}).get("rows"):
                    for row in data["tradesTable"]["rows"]:
                        if row.get("date") == expected_date:
                            return row
            except Exception:
                continue
        return None


    @staticmethod
    def _parse_price(value: str) -> float | None:
        """
        Parses a price string from the Nasdaq API, stripping $ and commas.
        """
        if not value or value == "N/A":
            return None
        return float(value.replace("$", "").replace(",", ""))


    @staticmethod
    def get_avg_price(ticker: str, date_obj: date, **kwargs) -> float | None:
        """
        Gets the average daily price for a ticker on a specific date from the Nasdaq API.
        Falls back to close price for assets without high/low data (e.g., mutual funds).
        """
        row = Nasdaq._fetch_historical(ticker, date_obj)
        if not row:
            return None

        high = Nasdaq._parse_price(row.get("high"))
        low = Nasdaq._parse_price(row.get("low"))

        if high is not None and low is not None and high != low:
            return round((high + low) / 2, 2)

        # Mutual funds report the same value for open/high/low/close (NAV)
        close = Nasdaq._parse_price(row.get("close"))
        return round(close, 2) if close is not None else None


    @staticmethod
    def get_current_price(ticker: str, **kwargs) -> float | None:
        """
        Gets the most recent available price from the Nasdaq API.
        Uses a 5-day window to find the latest trading day.
        """
        today = date.today()
        date_str_from = (today - timedelta(days=5)).strftime("%Y-%m-%d")
        date_str_to = today.strftime("%Y-%m-%d")

        for asset_class in Nasdaq.ASSET_CLASSES:
            try:
                url = (
                    f"{Nasdaq.BASE_URL}/{ticker}/historical"
                    f"?assetclass={asset_class}&fromdate={date_str_from}&todate={date_str_to}&limit=1"
                )
                resp = requests.get(url, headers=Nasdaq.HEADERS, timeout=10)
                data = resp.json().get("data")
                if data and data.get("tradesTable", {}).get("rows"):
                    close = Nasdaq._parse_price(data["tradesTable"]["rows"][0].get("close"))
                    if close is not None:
                        return round(close, 2)
            except Exception:
                continue
        return None
