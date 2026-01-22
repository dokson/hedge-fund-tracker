from app.stocks.libraries import FinanceLibrary, YFinance, TradingView
from datetime import date


class PriceFetcher:
    """
    Orchestrates the retrieval of stock prices using multiple libraries as fallbacks.
    """
    @staticmethod
    def get_libraries() -> list[FinanceLibrary]:
        """
        Returns an ordered list of FinanceLibrary instances for price fetching.
        """
        return [YFinance, TradingView]


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
            except Exception as e:
                print(f"⚠️ {library.__name__} failed to get price for {ticker}: {e}")
                continue
        
        print(f"❌ PriceFetcher: Failed to get current price for {ticker} from all sources.")
        return None


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
            except Exception as e:
                print(f"⚠️ {library.__name__} failed to get avg price for {ticker}: {e}")
                continue
        
        print(f"❌ PriceFetcher: Failed to get avg price for {ticker} on {date_obj} from all sources.")
        return None
