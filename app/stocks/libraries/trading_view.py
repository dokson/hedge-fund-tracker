from app.stocks.libraries.base_library import FinanceLibrary
from app.utils.console import silence_output
from datetime import date
from tvDatafeed import TvDatafeed, Interval as TvInterval
import logging
import pandas as pd

# Silence tvDatafeed related loggers if any
logging.getLogger('tvDatafeed').setLevel(logging.CRITICAL)


class TradingView(FinanceLibrary):
    """
    Client for searching stock information using the tvDatafeed library.
    Acts as a fallback or alternative to YFinance.
    """
    EXCHANGES = ['NASDAQ', 'NYSE', 'AMEX', 'ARCA', 'BATS', 'OTC', 'TSX', 'TSXV']


    @staticmethod
    def get_company(cusip: str, **kwargs) -> str | None:
        return None


    @staticmethod
    def get_ticker(cusip: str, **kwargs) -> str | None:
        return None


    @staticmethod
    def get_current_price(ticker: str, **kwargs) -> float | None:
        """
        Gets the current (or latest closing) market price for a ticker using tvDatafeed.
        """
        tv = kwargs.get('tv_session') or TvDatafeed()
        
        try:
            for exchange in TradingView.EXCHANGES:
                try:
                    with silence_output():
                        hist = tv.get_hist(symbol=ticker, exchange=exchange, interval=TvInterval.in_daily, n_bars=2)
                    if hist is not None and not hist.empty:
                        return float(hist['close'].iloc[-1])
                except Exception:
                    continue
            
            return None

        except Exception as e:
            print(f"⚠️ TradingView fallback failed for {ticker}: {e}")
            return None


    @staticmethod
    def get_avg_price(ticker: str, date_obj: date, **kwargs) -> float | None:
        """
        Gets the average daily price for a ticker on a specific date using tvdatafeed.
        The average price is calculated as (High + Low) / 2.
        """
        tv = kwargs.get('tv_session') or TvDatafeed()
        
        try:
            df = None
            for exchange in TradingView.EXCHANGES:
                try:
                    # Fetching 120 daily bars to cover the last quarter data
                    with silence_output():
                        hist = tv.get_hist(symbol=ticker, exchange=exchange, interval=TvInterval.in_daily, n_bars=120)
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
                high = day_data['high'].iloc[0]
                low = day_data['low'].iloc[0]
                return round((high + low) / 2, 2)
            
            print(f"🚨 TradingView: No data for {ticker} on {date_obj}.")
            return None

        except Exception as e:
            print(f"⚠️ TradingView get_avg_price failed for {ticker}: {e}")
            return None
