import json
from datetime import date

from curl_cffi import requests
from curl_cffi.requests.exceptions import RequestException
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.stocks.libraries.base_library import FinanceLibrary
from app.stocks.lookup_status import note_provider_failure
from app.utils.logger import get_logger, log_safe
from app.utils.metrics import PRICE_LOOKUP_FAILURES

logger = get_logger(__name__)


class StockAnalysis(FinanceLibrary):
    """
    Client for fetching stock prices from stockanalysis.com's public history API.

    Retains full daily history for delisted/acquired tickers (e.g. after an M&A
    delisting) that yfinance, TradingView and Nasdaq have already purged, since it
    reads from Tiingo / S&P Global Market Intelligence rather than a live feed.

    The site sits behind Cloudflare, which answers 403 to a client that does not
    look like a browser, for every symbol: requests impersonate Chrome, and a 403
    that still comes back disables the provider for the rest of the process.
    A symbol unknown on the US listing is looked up again on the OTC one, where
    names delisted to the pink sheets (bankruptcies, foreign ADRs) keep their history,
    and a NYSE warrant stored without separators (GROYWS) under the site's own
    form (groy.ws).
    """

    BASE_URL = "https://stockanalysis.com/api/symbol"
    LISTINGS = ("s/{ticker}", "a/otc-{ticker}")
    _blocked = False

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
    @retry(
        retry=retry_if_exception_type(RequestException),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
        before_sleep=lambda rs: logger.progress(
            "StockAnalysis: retrying %s (attempt #%d)...", rs.args[0], rs.attempt_number
        ),
    )
    def _get(url: str) -> requests.Response:
        """
        One API request; a timeout or connection failure is retried, since the
        price cache would otherwise record the miss for good.
        """
        return requests.get(url, impersonate="chrome", timeout=10)

    @staticmethod
    def _fetch_history(ticker: str, api_range: str, api_period: str) -> list[dict]:
        """
        Fetches raw daily/weekly/monthly bars for a ticker, newest-first as returned
        by the API: from the first listing that has data, the OTC one only when the
        US one answered without any. Returns an empty list on failure or no data.
        """
        paths = [listing.format(ticker=ticker) for listing in StockAnalysis.LISTINGS]
        if len(ticker) > 2 and ticker.endswith("WS"):
            paths.append(f"s/{ticker[:-2]}.ws")
        for path in paths:
            rows = StockAnalysis._fetch_listing(path, ticker, api_range, api_period)
            if rows is None or rows:
                return rows or []
        return []

    @staticmethod
    def _fetch_listing(
        path: str, ticker: str, api_range: str, api_period: str
    ) -> list[dict] | None:
        """
        The bars of one listing: empty when it answered without data, None when it
        could not answer (blocked, unreadable, failed request).
        """
        if StockAnalysis._blocked:
            note_provider_failure()
            return None
        url = f"{StockAnalysis.BASE_URL}/{path}/history?range={api_range}&period={api_period}"
        try:
            response = StockAnalysis._get(url)
            if response.status_code == 403:
                StockAnalysis._blocked = True
                note_provider_failure()
                PRICE_LOOKUP_FAILURES.labels(provider="StockAnalysis").inc()
                logger.warning("StockAnalysis: blocked (HTTP 403), skipped for the rest of the run")
                return None
            try:
                payload = response.json()
            except json.JSONDecodeError:
                note_provider_failure()
                PRICE_LOOKUP_FAILURES.labels(provider="StockAnalysis").inc()
                logger.warning(
                    "StockAnalysis: no history for %s (HTTP %s, non-JSON response)",
                    log_safe(ticker),
                    response.status_code,
                )
                return None
            return payload.get("data") or []
        except Exception:
            note_provider_failure()
            PRICE_LOOKUP_FAILURES.labels(provider="StockAnalysis").inc()
            logger.warning(
                "StockAnalysis: failed to fetch history for %s", log_safe(ticker), exc_info=True
            )
            return None

    @staticmethod
    def get_avg_price(ticker: str, date_obj: date, **kwargs) -> float | None:
        """
        Gets the average daily price for a ticker on a specific date.
        The average price is calculated as (High + Low) / 2. If the requested date
        is not a trading day, the most recent trading day at or before it is used.
        """
        if StockAnalysis._blocked:
            note_provider_failure()
            return None
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
