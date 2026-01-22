from abc import ABC, abstractmethod


class FinanceLibrary(ABC):
    """
    Abstract base class for financial data libraries.

    Defines a standard contract for classes that resolve CUSIPs to tickers and fetch company information from different financial data sources.
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
