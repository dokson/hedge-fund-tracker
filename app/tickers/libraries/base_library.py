from abc import ABC, abstractmethod


class FinanceLibrary(ABC):
    """
    Abstract base class for financial data libraries.

    Defines a standard contract for classes that resolve CUSIPs to tickers and fetch company information from different financial data sources.
    """
    @abstractmethod
    def get_ticker(self, cusip: str, **kwargs) -> str | None:
        """
        Gets the ticker for a given CUSIP.
        """
        pass


    @abstractmethod
    def get_company(self, cusip: str, **kwargs) -> str | None:
        """
        Gets the company name for a given CUSIP.
        """
        pass
