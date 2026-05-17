from datetime import date

from app.stocks.libraries import FinanceLibrary, Nasdaq, TradingView, YFinance
from app.utils.logger import get_logger, log_safe

logger = get_logger(__name__)


class PriceFetcher:
    """
    Orchestrates the retrieval of stock prices using multiple libraries as fallbacks.
    """

    @staticmethod
    def get_libraries() -> list[type[FinanceLibrary]]:
        """
        Returns an ordered list of FinanceLibrary classes for price fetching.
        """
        return [YFinance, TradingView, Nasdaq]

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
            except Exception:
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
            except Exception:
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
            except Exception:
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
