from datetime import date

from curl_cffi import requests

from app.stocks.libraries.base_library import FinanceLibrary
from app.utils.logger import get_logger, log_safe

logger = get_logger(__name__)


class StockAnalysis(FinanceLibrary):
    """
    Client for fetching stock prices from stockanalysis.com's public history API.

    Retains full daily history for delisted/acquired tickers (e.g. after an M&A
    delisting) that yfinance, TradingView and Nasdaq have already purged, since it
    reads from Tiingo / S&P Global Market Intelligence rather than a live feed.
    """

    BASE_URL = "https://stockanalysis.com/api/symbol/s"
    HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

    PERIOD_TO_RANGE = {
        "ytd": ("YTD", "Daily"),
        "1y": ("1Y", "Daily"),
        "2y": ("2Y", "Daily"),
        "3y": ("5Y", "Weekly"),
        "5y": ("5Y", "Weekly"),
        "10y": ("10Y", "Monthly"),
        "max": ("10Y", "Monthly"),
    }

    @staticmethod
    def get_ticker(cusip: str, **kwargs) -> str | None:
        """
        Not supported: stockanalysis.com's public API has no CUSIP lookup.
        """
        return None

    @staticmethod
    def get_company(cusip: str, **kwargs) -> str | None:
        """
        Not supported: stockanalysis.com's public API has no CUSIP lookup.
        """
        return None

    @staticmethod
    def _fetch_history(ticker: str, api_range: str, api_period: str) -> list[dict]:
        """
        Fetches raw daily/weekly/monthly bars for a ticker, newest-first as returned
        by the API. Returns an empty list on any failure or when no data exists.
        """
        url = f"{StockAnalysis.BASE_URL}/{ticker}/history?range={api_range}&period={api_period}"
        try:
            response = requests.get(url, headers=StockAnalysis.HEADERS, timeout=10)
            data = response.json().get("data")
            return data or []
        except Exception:
            logger.warning(
                "StockAnalysis: failed to fetch history for %s", log_safe(ticker), exc_info=True
            )
            return []

    @staticmethod
    def get_avg_price(ticker: str, date_obj: date, **kwargs) -> float | None:
        """
        Gets the average daily price for a ticker on a specific date.
        The average price is calculated as (High + Low) / 2. If the requested date
        is not a trading day, the most recent trading day at or before it is used.
        """
        rows = StockAnalysis._fetch_history(ticker, "5Y", "Daily")
        target = date_obj.isoformat()

        for row in rows:
            if row.get("t") and row["t"] <= target:
                return round((row["h"] + row["l"]) / 2, 2)

        logger.warning("StockAnalysis: No data for %s at or before %s.", log_safe(ticker), date_obj)
        return None

    @staticmethod
    def get_current_price(ticker: str, **kwargs) -> float | None:
        """
        Gets the most recent available closing price for a ticker.
        """
        rows = StockAnalysis._fetch_history(ticker, "1M", "Daily")
        if not rows:
            return None
        return rows[0].get("c")

    @staticmethod
    def get_history(ticker: str, period: str = "5y", **kwargs) -> list[dict] | None:
        """
        Gets OHLC price history for a ticker over the requested period, oldest first.
        """
        api_range, api_period = StockAnalysis.PERIOD_TO_RANGE.get(period, ("5Y", "Weekly"))
        rows = StockAnalysis._fetch_history(ticker, api_range, api_period)
        if not rows:
            return None

        points = [
            {
                "date": row["t"],
                "open": row["o"],
                "high": row["h"],
                "low": row["l"],
                "close": row["c"],
            }
            for row in reversed(rows)
        ]
        return points or None
