"""
This package contains the various financial data library clients.

By importing the classes here, we can simplify imports in other parts of the application,
allowing `from app.stocks.libraries import YFinance, Finnhub`, etc.
"""
from app.stocks.libraries.base_library import FinanceLibrary
from app.stocks.libraries.finance_database import FinanceDatabase
from app.stocks.libraries.finnhub import Finnhub
from app.stocks.libraries.trading_view import TradingView
from app.stocks.libraries.yfinance import YFinance

# Defines the public API of this package
__all__ = ["FinanceLibrary", "FinanceDatabase", "Finnhub", "TradingView", "YFinance"]
