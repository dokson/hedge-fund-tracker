from app.stocks.libraries.base_library import FinanceLibrary
from datetime import date
from tvDatafeed import TvDatafeed, Interval as TvInterval
import pandas as pd

TRADINGVIEW_EXCHANGES = ['NASDAQ', 'NYSE', 'AMEX', 'ARCA', 'BATS', 'OTC']


class TradingView(FinanceLibrary):
    """
    Client for searching stock information using the tvDatafeed library.
    Acts as a fallback or alternative to YFinance.
    """
    _TV = None

    @staticmethod
    def _get_tv():
        if TradingView._TV is None:
            TradingView._TV = TvDatafeed()
        return TradingView._TV


    @staticmethod
    def _reset_tv():
        """
        Resets the TvDatafeed session if a connection error occurs.
        """
        TradingView._TV = None
        print("🚨 TradingView: Connection issue detected. Resetting session...")
        return None


    @staticmethod
    def get_current_price(ticker: str) -> float | None:
        """
        Gets the current (or latest closing) market price for a ticker using tvDatafeed.
        """
        try:
            tv = TradingView._get_tv()
            
            for exchange in TRADINGVIEW_EXCHANGES:
                try:
                    hist = tv.get_hist(symbol=ticker, exchange=exchange, interval=TvInterval.in_daily, n_bars=2)
                    if hist is not None and not hist.empty:
                        return float(hist['close'].iloc[-1])
                except Exception as e:
                    if "Connection" in str(e) or "remote host" in str(e):
                        TradingView._reset_tv()
                        return TradingView.get_current_price(ticker) # Retry with new session
                    continue
            
            return None

        except Exception as e:
            if "Connection" in str(e) or "remote host" in str(e):
                TradingView._reset_tv()
            print(f"⚠️ TradingView fallback failed for {ticker}: {e}")
            return None


    @staticmethod
    def get_avg_price(ticker: str, date_obj: date) -> float | None:
        """
        Gets the average daily price for a ticker on a specific date using tvdatafeed.
        The average price is calculated as (High + Low) / 2.
        """
        try:
            # TvDatafeed initialization
            tv = TradingView._get_tv()
            
            df = None
            for exchange in TRADINGVIEW_EXCHANGES:
                try:
                    # Fetching 100 daily bars to cover the last 3 months
                    hist = tv.get_hist(symbol=ticker, exchange=exchange, interval=TvInterval.in_daily, n_bars=100)
                    if hist is not None and not hist.empty:
                        df = hist
                        break
                except Exception as e:
                    if "Connection" in str(e) or "remote host" in str(e):
                        TradingView._reset_tv()
                        return TradingView.get_avg_price(ticker, date_obj) # Retry
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
