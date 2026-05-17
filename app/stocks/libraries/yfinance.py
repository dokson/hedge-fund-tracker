import logging
import re
from datetime import date, timedelta

import pandas as pd
import requests
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

from app.stocks.libraries.base_library import FinanceLibrary
from app.utils.logger import get_logger, log_safe

logger = get_logger(__name__)

# Silence yfinance logger
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


class YFinance(FinanceLibrary):
    """
    Client for searching stock information using the yfinance library, implementing the FinanceLibrary interface.
    """

    FALLBACK_SUFFIXES = [".TO", ".V"]

    @staticmethod
    def _sanitize_ticker(ticker: str) -> str:
        """
        Sanitizes the ticker for yfinance. Replaces '.' with '-' for share classes (e.g., BRK.B), but preserves '.' for international suffixes (e.g., AAPL.TO).
        """
        if "." in ticker and not any(ticker.endswith(s) for s in YFinance.FALLBACK_SUFFIXES):
            return ticker.replace(".", "-")
        return ticker

    @staticmethod
    def get_company(cusip: str, **kwargs) -> str | None:
        """
        Searches for a company name for a given ticker using the yfinance library.

        Args:
            cusip (str): The CUSIP of the stock.
            ticker (str): The stock ticker.

        Returns:
            str | None: The company name if found, otherwise None.
        """
        ticker = kwargs.get("ticker")
        ticker = YFinance.get_ticker(cusip) if not ticker else YFinance._sanitize_ticker(ticker)

        try:
            stock_info = yf.Ticker(ticker).info
            company_name = stock_info.get("longName") or stock_info.get("shortName", "")
            if company_name:
                return re.sub(r"[.,]", "", company_name)
            logger.warning("YFinance: No company found for CUSIP %s.", log_safe(cusip))
            return None
        except Exception:
            logger.error(
                "Failed to get company for Ticker %s using YFinance",
                log_safe(ticker),
                exc_info=True,
            )
            return None

    @staticmethod
    def get_ticker(cusip: str, **kwargs) -> str | None:
        """
        Searches for a ticker for a given CUSIP by querying the Yahoo Finance search API.

        Args:
            cusip (str): The CUSIP of the stock.

        Returns:
            str | None: The ticker symbol if found, otherwise None.
        """
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={cusip}"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            quotes = data.get("quotes", [])
            for quote in quotes:
                return quote["symbol"]
            logger.warning("YFinance: No ticker found for CUSIP %s.", log_safe(cusip))
            return None
        except (requests.RequestException, ValueError):
            logger.error(
                "Failed to get ticker for CUSIP %s using YFinance", log_safe(cusip), exc_info=True
            )
            return None

    @staticmethod
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        before_sleep=lambda retry_state: logger.progress(
            f"Retrying get_avg_price for {retry_state.args[0]} (attempt #{retry_state.attempt_number})..."
        ),
    )
    def get_avg_price(ticker: str, date_obj: date, **kwargs) -> float | None:
        """
        Gets the average daily price for a ticker on a specific date using the yfinance library.
        The average price is calculated as (High + Low) / 2.
        If no data is found for the specified date (e.g., delisting), tries with current_price.

        Args:
            ticker (str): The stock ticker.
            date (date): The date for which to fetch the price.

        Returns:
            float | None: The average price if found, otherwise None.
        """

        def _get_single_avg_price(t: str) -> float | None:
            search_ticker = YFinance._sanitize_ticker(t)
            # 'end' parameter is exclusive: To get a single day, we need the next day as the end.
            price_data = yf.download(
                tickers=search_ticker,
                start=date_obj,
                end=date_obj + timedelta(days=1),
                auto_adjust=False,
                progress=False,
            )

            if price_data is None or price_data.empty:
                return None
            return round(
                (price_data["High"].iloc[0].item() + price_data["Low"].iloc[0].item()) / 2, 2
            )

        try:
            # Try original ticker first
            price = _get_single_avg_price(ticker)
            if price is not None:
                return price

            # Fallback for international tickers (e.g., TSX, TSXV)
            # Only attempt fallback if the ticker doesn't already have a separator
            if "." not in ticker and "-" not in ticker:
                for suffix in YFinance.FALLBACK_SUFFIXES:
                    try:
                        fallback_ticker = ticker + suffix
                        logger.progress(
                            "YFinance: Trying fallback %s for %s...",
                            log_safe(fallback_ticker),
                            log_safe(ticker),
                        )
                        price = _get_single_avg_price(fallback_ticker)
                        if price is not None:
                            return price
                    except Exception:
                        continue

            logger.warning(
                "Using latest available price for %s (requested date %s not available)",
                log_safe(ticker),
                date_obj,
            )
            return YFinance.get_current_price(ticker)
        except Exception as e:
            logger.error(
                "Failed to get price for Ticker %s on %s using YFinance",
                log_safe(ticker),
                date_obj,
                exc_info=True,
            )
            raise e

    @staticmethod
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        before_sleep=lambda retry_state: logger.progress(
            f"Retrying get_current_price for {retry_state.args[0]} (attempt #{retry_state.attempt_number})..."
        ),
    )
    def get_current_price(ticker: str, **kwargs) -> float | None:
        """
        Gets the current market price for a ticker using the yfinance library.

        Args:
            ticker (str): The stock ticker.

        Returns:
            float | None: The current price if found, otherwise None.
        """
        try:
            search_ticker = YFinance._sanitize_ticker(ticker)
            stock = yf.Ticker(search_ticker)
            price = stock.info.get("currentPrice")

            # Fallback for international tickers (e.g., TSX, TSXV)
            if price is None and "." not in ticker and "-" not in ticker:
                for suffix in YFinance.FALLBACK_SUFFIXES:
                    try:
                        fallback_ticker = ticker + suffix
                        logger.progress(
                            f"YFinance: Trying current price fallback {fallback_ticker} for {ticker}..."
                        )
                        price = yf.Ticker(fallback_ticker).info.get("currentPrice")
                        if price is not None:
                            break
                    except Exception:
                        continue

            return float(price) if price is not None else None
        except Exception as e:
            logger.error(
                "Failed to get current price for Ticker %s using YFinance",
                log_safe(ticker),
                exc_info=True,
            )
            raise e

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        before_sleep=lambda retry_state: logger.progress(
            f"Retrying get_stocks_info for {retry_state.args[0]} (attempt #{retry_state.attempt_number})..."
        ),
    )
    def get_stocks_info(tickers: list[str]) -> dict[str, dict]:
        """
        Gets the current market prices and sector information for a list of tickers efficiently.

        Args:
            tickers (list[str]): A list of stock tickers.

        Returns:
            dict[str, dict]: A dictionary mapping tickers to their info (price, sector).
                            Example: {'AAPL': {'price': 150.25, 'sector': 'Technology'}}
        """
        if not tickers:
            return {}

        # Create a mapping between sanitized and original tickers
        ticker_map = {YFinance._sanitize_ticker(t): t for t in tickers}
        sanitized_tickers = list(ticker_map.keys())

        stocks_info = {}

        try:
            data = yf.download(
                tickers=sanitized_tickers,
                period="1d",
                interval="1m",
                group_by="ticker",
                auto_adjust=False,
                progress=False,
            )

            data_to_use = None if data is None else data

            for sanitized, original in ticker_map.items():
                try:
                    if data_to_use is None:
                        continue
                    ticker_data = (
                        data_to_use if len(sanitized_tickers) == 1 else data_to_use[sanitized]
                    )

                    if ticker_data is None or ticker_data.empty:
                        continue
                    price = ticker_data["Close"].dropna().iloc[-1].item()
                    stocks_info[original] = {"price": float(price), "sector": None}
                except Exception:
                    continue

            # Get sector info for all tickers (both successful and failed price fetches)
            for sanitized, original in ticker_map.items():
                try:
                    stock = yf.Ticker(sanitized)
                    sector = stock.info.get("sector") or stock.info.get("industry")

                    if original in stocks_info:
                        stocks_info[original]["sector"] = sector
                    else:
                        # Price fallback
                        logger.progress("Getting current price for %s...", log_safe(original))
                        price = YFinance.get_current_price(original)
                        if price:
                            stocks_info[original] = {"price": price, "sector": sector}
                except Exception:
                    continue

            return stocks_info
        except Exception as e:
            logger.error("Failed to get stock info using YFinance", exc_info=True)
            raise e

    PERIOD_TO_INTERVAL = {
        "ytd": "1d",
        "1y": "1d",
        "2y": "1d",
        "3y": "1wk",
        "5y": "1wk",
        "10y": "1mo",
        "max": "1mo",
    }

    @staticmethod
    def get_history(ticker: str, period: str = "5y", **kwargs) -> list[dict] | None:
        """
        Gets OHLC price history for a ticker over the requested period.

        The bar interval scales with the period to keep ~150–260 points:
        daily for short ranges (<= 2y), weekly for mid (3–5y), monthly for long (10y/max).

        Args:
            ticker (str): The stock ticker.
            period (str): yfinance period string ("1y", "3y", "5y", "10y", "max", ...).

        Returns:
            list[dict] | None: List of {"date", "open", "high", "low", "close"}, or None on failure.
        """
        interval = YFinance.PERIOD_TO_INTERVAL.get(period, "1mo")
        try:
            search_ticker = YFinance._sanitize_ticker(ticker)
            history = yf.Ticker(search_ticker).history(
                period=period, interval=interval, auto_adjust=False
            )

            required = {"Open", "High", "Low", "Close"}
            if history is None or history.empty or not required.issubset(history.columns):
                return None

            points = []
            for idx, row in history.iterrows():
                o, h, low, c = row.get("Open"), row.get("High"), row.get("Low"), row.get("Close")
                if any(v is None or v != v for v in (o, h, low, c)):
                    continue
                # The values are validated as non-None above; narrow for the type-checker.
                assert o is not None and h is not None and low is not None and c is not None
                # idx is a Timestamp at runtime (DatetimeIndex), but DataFrame.iterrows()
                # widens its static type to Hashable. Narrow with isinstance so pyright
                # accepts .strftime without a `# type: ignore`.
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
            return points or None
        except Exception:
            logger.error(
                "Failed to get history for Ticker %s using YFinance",
                log_safe(ticker),
                exc_info=True,
            )
            return None

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        before_sleep=lambda retry_state: logger.progress(
            f"Retrying get_sector_tickers for {retry_state.args[0]} (attempt #{retry_state.attempt_number})..."
        ),
    )
    def get_sector_tickers(sector_key: str, limit: int | None = None) -> list[dict]:
        """
        Gets a list of tickers for companies in a specific sector.

        Args:
            sector_key (str): The sector key (e.g., 'technology', 'healthcare', 'financial-services').
            limit (int, optional): Maximum number of tickers to return. If None, returns all available.

        Returns:
            list[dict]: A list of dictionaries with ticker info.
                       Example: [{'symbol': 'AAPL', 'name': 'Apple Inc.', 'weight': 0.15}, ...]
        """
        try:
            sector = yf.Sector(sector_key)
            top_companies = sector.top_companies

            if top_companies is None or top_companies.empty:
                # Raise error to trigger @retry
                raise ValueError(f"🚨 No companies found for sector '{sector_key}'")

            companies = []
            for _, row in top_companies.iterrows():
                company_info = {
                    "symbol": row.get("symbol", ""),
                    "name": row.get("name", ""),
                    "weight": row.get("weight", 0.0) if "weight" in row else None,
                }
                companies.append(company_info)

                if limit and len(companies) >= limit:
                    break

            return companies
        except Exception as e:
            logger.error(
                "Failed to get tickers for sector '%s'", log_safe(sector_key), exc_info=True
            )
            raise e
