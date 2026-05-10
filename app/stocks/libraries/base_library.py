from abc import ABC, abstractmethod
from datetime import date


class FinanceLibrary(ABC):
    """
    Abstract base class for financial data libraries.

    Defines a standard contract for classes that resolve CUSIPs to tickers and fetch
    company / price information from different financial data sources.

    `get_ticker` and `get_company` are required (every library must implement them).
    Price-related methods are optional — subclasses override the ones they support;
    the base no-op default returns None so PriceFetcher can iterate over libraries
    without runtime hasattr checks.
    """

    @staticmethod
    @abstractmethod
    def get_ticker(cusip: str, **kwargs) -> str | None:
        """
        Gets the ticker for a given CUSIP.
        """
        pass

    @staticmethod
    @abstractmethod
    def get_company(cusip: str, **kwargs) -> str | None:
        """
        Gets the company name for a given CUSIP.
        """
        pass

    @staticmethod
    def get_current_price(ticker: str, **kwargs) -> float | None:
        """
        Gets the current price for a ticker. Default no-op; override in subclasses.
        """
        return None

    @staticmethod
    def get_avg_price(ticker: str, date_obj: date, **kwargs) -> float | None:
        """
        Gets the average price for a ticker on a specific date. Default no-op.
        """
        return None

    @staticmethod
    def get_history(ticker: str, period: str = "5y", **kwargs) -> list[dict] | None:
        """
        Gets historical price points for a ticker. Default no-op.
        """
        return None
