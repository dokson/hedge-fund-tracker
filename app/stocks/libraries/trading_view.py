import logging
from datetime import date

import pandas as pd
from tvDatafeed import Interval as TvInterval
from tvDatafeed import TvDatafeed

from app.stocks.libraries.base_library import FinanceLibrary
from app.utils.console import silence_output

# Silence tvDatafeed related loggers if any
logging.getLogger("tvDatafeed").setLevel(logging.CRITICAL)


class TradingView(FinanceLibrary):
    """
    Client for searching stock information using the tvDatafeed library.
    Acts as a fallback or alternative to YFinance.
    """

    EXCHANGES = ["NASDAQ", "NYSE", "AMEX", "ARCA", "BATS", "OTC", "TSX", "TSXV"]

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
        tv = kwargs.get("tv_session") or TvDatafeed()

        try:
            for exchange in TradingView.EXCHANGES:
                try:
                    with silence_output():
                        hist = tv.get_hist(
                            symbol=ticker, exchange=exchange, interval=TvInterval.in_daily, n_bars=2
                        )
                    if hist is not None and not hist.empty:
                        return float(hist["close"].iloc[-1])
                except Exception:
                    continue

            return None

        except Exception as e:
            print(f"⚠️ TradingView fallback failed for {ticker}: {e}")
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
                    with silence_output():
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
                            o, h, l, c = (
                                row.get("open"),
                                row.get("high"),
                                row.get("low"),
                                row.get("close"),
                            )
                            if any(v is None or v != v for v in (o, h, l, c)):
                                continue
                            points.append(
                                {
                                    "date": idx.strftime("%Y-%m-%d"),
                                    "open": round(float(o), 4),
                                    "high": round(float(h), 4),
                                    "low": round(float(l), 4),
                                    "close": round(float(c), 4),
                                }
                            )
                        if points:
                            return points
                except Exception:
                    continue
            return None
        except Exception as e:
            print(f"⚠️ TradingView get_history failed for {ticker}: {e}")
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
                    with silence_output():
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

            print(f"🚨 TradingView: No data for {ticker} on {date_obj}.")
            return None

        except Exception as e:
            print(f"⚠️ TradingView get_avg_price failed for {ticker}: {e}")
            return None
