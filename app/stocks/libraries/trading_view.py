import logging
import re
from datetime import date

import pandas as pd
import requests
from tvDatafeed import Interval as TvInterval
from tvDatafeed import TvDatafeed

from app.stocks.libraries.base_library import FinanceLibrary
from app.stocks.utils.identifiers import cusip_to_isin, normalize_ticker
from app.utils.logger import get_logger, log_safe
from app.utils.strings import format_string

# TradingView's symbol_search wraps matched substrings with <em>...</em> tags when
# the query is a free-text name (highlight markup). Strip them before persisting.
_EM_TAGS = re.compile(r"</?em>")

logger = get_logger(__name__)

# Silence tvDatafeed related loggers if any
logging.getLogger("tvDatafeed").setLevel(logging.CRITICAL)


class TradingView(FinanceLibrary):
    """
    Client for searching stock information using TradingView.

    For CUSIP→ticker/company lookups, calls the public symbol_search endpoint with the
    derived US ISIN. For price/history data, uses the tvDatafeed library.
    """

    EXCHANGES = ["NASDAQ", "NYSE", "AMEX", "ARCA", "BATS", "OTC", "TSX", "TSXV"]
    US_EXCHANGES = {"NASDAQ", "NYSE", "AMEX", "ARCA", "BATS", "OTC", "NYSE Arca", "CBOE"}
    SYMBOL_SEARCH_URL = "https://symbol-search.tradingview.com/symbol_search/"
    SYMBOL_SEARCH_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Referer": "https://www.tradingview.com/",
        "Origin": "https://www.tradingview.com",
        "Accept": "application/json",
    }
    SYMBOL_SEARCH_TIMEOUT = 8

    @staticmethod
    def _search_by_text(query: str) -> list[dict]:
        """
        Calls the TradingView symbol_search endpoint with an arbitrary query string
        (ISIN or company name) and returns the raw symbols list, or an empty list on
        network/HTTP/JSON failure.
        """
        params = {"text": query, "hl": "1", "lang": "en", "domain": "production"}
        try:
            response = requests.get(
                TradingView.SYMBOL_SEARCH_URL,
                params=params,
                headers=TradingView.SYMBOL_SEARCH_HEADERS,
                timeout=TradingView.SYMBOL_SEARCH_TIMEOUT,
            )
        except requests.RequestException:
            logger.warning("TradingView: network error during symbol_search", exc_info=True)
            return []

        if not response.ok:
            logger.warning("TradingView: symbol_search HTTP %s", response.status_code)
            return []

        try:
            payload = response.json()
        except ValueError:
            return []

        symbols = payload.get("symbols") if isinstance(payload, dict) else payload
        if not symbols:
            return []
        # Strip <em>...</em> highlight markup from symbol and description fields.
        for entry in symbols:
            for field in ("symbol", "description"):
                value = entry.get(field)
                if isinstance(value, str):
                    entry[field] = _EM_TAGS.sub("", value)
        return symbols

    @staticmethod
    def _first_us_match(symbols: list[dict]) -> dict | None:
        """
        Returns the first symbol listed on a recognised US exchange, or None.
        """
        for entry in symbols:
            if entry.get("exchange") in TradingView.US_EXCHANGES:
                return entry
        return None

    @staticmethod
    def _symbol_search(cusip: str, company_name: str | None = None) -> dict | None:
        """
        Resolves a CUSIP to a US-listed TradingView symbol. Searches first by the
        derived US ISIN; if that yields only non-US listings, retries the search
        using the *description* of the first non-US match — that description carries
        the current company name (which handles renames, e.g. Ekso Bionics → ChronoScale,
        where the SEC 13F still lists the stale name).

        Returns None when no US listing can be found. Accepting a non-US listing as
        the canonical ticker would silently corrupt stocks.csv. The company_name
        argument is accepted for API compatibility but currently unused — the TV
        non-US description is a more reliable source of the current name than a
        possibly-stale 13F filing.
        """
        del company_name  # tolerated for chain interface; intentionally not used
        try:
            isin = cusip_to_isin(cusip)
        except ValueError:
            return None

        isin_results = TradingView._search_by_text(isin)
        us_match = TradingView._first_us_match(isin_results)
        if us_match:
            return us_match

        if not isin_results:
            return None

        description = isin_results[0].get("description")
        if not description:
            return None

        name_results = TradingView._search_by_text(description)
        return TradingView._first_us_match(name_results)

    @staticmethod
    def get_company(cusip: str, **kwargs) -> str | None:
        """
        Returns the formatted company description for a given CUSIP, or None.
        """
        match = TradingView._symbol_search(cusip, company_name=kwargs.get("company_name"))
        if not match:
            return None
        description = match.get("description")
        if not description:
            return None
        return format_string(description)

    @staticmethod
    def get_ticker(cusip: str, **kwargs) -> str | None:
        """
        Returns the ticker for a given CUSIP, or None if no match is found.
        """
        match = TradingView._symbol_search(cusip, company_name=kwargs.get("company_name"))
        if not match:
            return None
        symbol = match.get("symbol")
        if not symbol:
            return None
        return normalize_ticker(symbol) or None

    @staticmethod
    def get_current_price(ticker: str, **kwargs) -> float | None:
        """
        Gets the current (or latest closing) market price for a ticker using tvDatafeed.
        """
        tv = kwargs.get("tv_session") or TvDatafeed()

        try:
            for exchange in TradingView.EXCHANGES:
                try:
                    hist = tv.get_hist(
                        symbol=ticker, exchange=exchange, interval=TvInterval.in_daily, n_bars=2
                    )
                    if hist is not None and not hist.empty:
                        return float(hist["close"].iloc[-1])
                except Exception:
                    continue

            return None

        except Exception:
            logger.error("TradingView fallback failed for %s", log_safe(ticker), exc_info=True)
            return None

    @staticmethod
    def get_history(ticker: str, period: str = "5y", **kwargs) -> list[dict] | None:
        """
        Gets monthly close prices for a ticker over the requested period via tvDatafeed.

        Args:
            ticker (str): The stock ticker.
            period (str): A period string ("1y", "3y", "5y", "10y", "max").

        Returns:
            list[dict] | None: List of {"date": "YYYY-MM-DD", "close": float}, or None on failure.
        """
        period_to_cfg = {
            "ytd": (TvInterval.in_daily, 260),
            "1y": (TvInterval.in_daily, 260),
            "2y": (TvInterval.in_daily, 520),
            "3y": (TvInterval.in_weekly, 160),
            "5y": (TvInterval.in_weekly, 260),
            "10y": (TvInterval.in_monthly, 120),
            "max": (TvInterval.in_monthly, 240),
        }
        tv_interval, n_bars = period_to_cfg.get(period, (TvInterval.in_monthly, 60))
        tv = kwargs.get("tv_session") or TvDatafeed()

        try:
            for exchange in TradingView.EXCHANGES:
                try:
                    hist = tv.get_hist(
                        symbol=ticker, exchange=exchange, interval=tv_interval, n_bars=n_bars
                    )
                    if hist is not None and not hist.empty:
                        hist.index = pd.to_datetime(hist.index)
                        if period == "ytd":
                            year_start = pd.Timestamp(date.today().year, 1, 1)
                            hist = hist[hist.index >= year_start]
                        points = []
                        for idx, row in hist.iterrows():
                            o, h, low, c = (
                                row.get("open"),
                                row.get("high"),
                                row.get("low"),
                                row.get("close"),
                            )
                            if any(v is None or v != v for v in (o, h, low, c)):
                                continue
                            assert (
                                o is not None
                                and h is not None
                                and low is not None
                                and c is not None
                            )
                            if not isinstance(idx, pd.Timestamp):
                                continue
                            date_str = idx.strftime("%Y-%m-%d")
                            points.append(
                                {
                                    "date": date_str,
                                    "open": round(float(o), 4),
                                    "high": round(float(h), 4),
                                    "low": round(float(low), 4),
                                    "close": round(float(c), 4),
                                }
                            )
                        if points:
                            return points
                except Exception:
                    continue
            return None
        except Exception:
            logger.error("TradingView get_history failed for %s", log_safe(ticker), exc_info=True)
            return None

    @staticmethod
    def get_avg_price(ticker: str, date_obj: date, **kwargs) -> float | None:
        """
        Gets the average daily price for a ticker on a specific date using tvdatafeed.
        The average price is calculated as (High + Low) / 2.
        """
        tv = kwargs.get("tv_session") or TvDatafeed()

        try:
            df = None
            for exchange in TradingView.EXCHANGES:
                try:
                    # Fetching 120 daily bars to cover the last quarter data
                    hist = tv.get_hist(
                        symbol=ticker,
                        exchange=exchange,
                        interval=TvInterval.in_daily,
                        n_bars=120,
                    )
                    if hist is not None and not hist.empty:
                        df = hist
                        break
                except Exception:
                    continue

            if df is None:
                return None

            # Filter by date
            df.index = pd.to_datetime(df.index)
            target_date = pd.Timestamp(date_obj)

            mask = df.index.normalize() == target_date
            day_data = df[mask]

            if not day_data.empty:
                high = day_data["high"].iloc[0]
                low = day_data["low"].iloc[0]
                return round((high + low) / 2, 2)

            logger.warning("TradingView: No data for %s on %s.", log_safe(ticker), date_obj)
            return None

        except Exception:
            logger.error("TradingView get_avg_price failed for %s", log_safe(ticker), exc_info=True)
            return None
