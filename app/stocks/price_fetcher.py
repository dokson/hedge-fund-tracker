from datetime import date

from yfinance.exceptions import YFRateLimitError

from app.stocks.libraries import FinanceLibrary, Nasdaq, StockAnalysis, TradingView, YFinance
from app.utils.logger import get_logger, log_safe
from app.utils.metrics import PRICE_LOOKUP_FAILURES, PRICE_RATE_LIMITED

logger = get_logger(__name__)


def _record_failure(library: type[FinanceLibrary], exc: Exception) -> None:
    """
    Count a provider failure, and separately a rate limit, under the provider's class name.
    """
    PRICE_LOOKUP_FAILURES.labels(provider=library.__name__).inc()
    if isinstance(exc, YFRateLimitError):
        PRICE_RATE_LIMITED.labels(provider=library.__name__).inc()


class PriceFetcher:
    """
    Orchestrates the retrieval of stock prices using multiple libraries as fallbacks.
    """

    @staticmethod
    def get_libraries() -> list[type[FinanceLibrary]]:
        """
        Returns an ordered list of FinanceLibrary classes for price fetching.
        """
        return [YFinance, TradingView, Nasdaq, StockAnalysis]

    @staticmethod
    def get_current_price(ticker: str) -> float | None:
        """
        Gets the current price for a ticker by querying libraries in order.
        """
        for library in PriceFetcher.get_libraries():
            try:
                price = library.get_current_price(ticker)
                if price is not None:
                    return price
            except Exception as exc:
                _record_failure(library, exc)
                logger.error(
                    "%s failed to get price for %s",
                    library.__name__,
                    log_safe(ticker),
                    exc_info=True,
                )
                continue

        logger.error(
            "PriceFetcher: Failed to get current price for %s from all sources.",
            log_safe(ticker),
            exc_info=True,
        )
        return None

    @staticmethod
    def get_history(ticker: str, period: str = "5y") -> list[dict]:
        """
        Gets monthly close-price history for a ticker by querying libraries in order.

        Returns the first non-empty list of {"date", "close"} points produced by any library,
        or an empty list if every source fails.
        """
        for library in PriceFetcher.get_libraries():
            try:
                points = library.get_history(ticker, period)
                if points:
                    return points
            except Exception as exc:
                _record_failure(library, exc)
                logger.error(
                    "%s failed to get history for %s",
                    library.__name__,
                    log_safe(ticker),
                    exc_info=True,
                )
                continue

        logger.error(
            "PriceFetcher: Failed to get history for %s from all sources.",
            log_safe(ticker),
            exc_info=True,
        )
        return []

    @staticmethod
    def get_avg_price(ticker: str, date_obj: date) -> float | None:
        """
        Gets the average price for a ticker on a specific date by querying libraries in order.
        """
        for library in PriceFetcher.get_libraries():
            try:
                price = library.get_avg_price(ticker, date_obj)
                if price is not None:
                    return price
            except Exception as exc:
                _record_failure(library, exc)
                logger.error(
                    "%s failed to get avg price for %s",
                    library.__name__,
                    log_safe(ticker),
                    exc_info=True,
                )
                continue

        logger.error(
            "PriceFetcher: Failed to get avg price for %s on %s from all sources.",
            log_safe(ticker),
            date_obj,
        )
        return None

    @staticmethod
    def get_last_price_in_range(ticker: str, start: date, end: date) -> float | None:
        """
        Gets the price of the last bar in (start, end] for a ticker by querying libraries in order.
        """
        for library in PriceFetcher.get_libraries():
            try:
                price = library.get_last_price_in_range(ticker, start, end)
                if price is not None:
                    return price
            except Exception as exc:
                _record_failure(library, exc)
                logger.error(
                    "%s failed to get last price in range for %s",
                    library.__name__,
                    log_safe(ticker),
                    exc_info=True,
                )
                continue

        logger.warning(
            "PriceFetcher: No bar for %s between %s and %s from any source.",
            log_safe(ticker),
            start,
            end,
        )
        return None
