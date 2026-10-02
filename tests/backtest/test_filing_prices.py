"""
Filing-implied prices: a quarter's own 13F market value per share, the price of
last resort for a name the providers no longer serve.
"""

import unittest

import pandas as pd

from app.backtest.filing_prices import implied_prices, latest_filing_price

_STOCKS = pd.DataFrame(
    {"Ticker": ["AAA", "AAA", "BBB", "CCC"]},
    index=pd.Index(["000000101", "000000202", "000000303", "000000404"], name="CUSIP"),
)


class ImpliedPricesTest(unittest.TestCase):
    """
    implied_prices turns quarter rows into a ticker -> price-per-share map.
    """

    def test_sums_equity_holdings_across_funds_and_cusips(self):
        """
        Value over shares is computed on every equity row of the ticker, across funds and CUSIPs.
        """
        quarter = pd.DataFrame(
            {
                "CUSIP": ["000000101", "000000101", "000000202"],
                "Shares": ["100", "300", "100"],
                "Value": ["10K", "30K", "10K"],
            }
        )
        self.assertEqual(implied_prices(quarter, _STOCKS), {"AAA": 100.0})

    def test_ignores_debt_rows_zero_shares_and_unknown_cusips(self):
        """
        A debt CUSIP, a zero-share row and a CUSIP missing from stocks never set a price.
        """
        quarter = pd.DataFrame(
            {
                "CUSIP": ["000000303", "000000AB3", "000000404", "999999901"],
                "Shares": ["10", "1000000", "0", "5"],
                "Value": ["1K", "1M", "5K", "5K"],
            }
        )
        self.assertEqual(implied_prices(quarter, _STOCKS), {"BBB": 100.0})


class LatestFilingPriceTest(unittest.TestCase):
    """
    latest_filing_price walks back to the last quarter that still priced the name.
    """

    PRICES = {"2025Q1": {"AAA": 10.0, "BBB": 7.0}, "2025Q2": {"AAA": 12.0}, "2025Q3": {}}
    QUARTERS = ["2025Q1", "2025Q2", "2025Q3"]

    def _price(self, ticker: str, quarter: str) -> float | None:
        """
        Resolve a price over the canned per-quarter maps.
        """
        return latest_filing_price(ticker, quarter, self.QUARTERS, self.PRICES.__getitem__)

    def test_uses_the_screen_quarter_first(self):
        """
        A name held in the screen quarter takes that quarter's price.
        """
        self.assertEqual(self._price("AAA", "2025Q2"), 12.0)

    def test_closed_position_falls_back_to_the_last_quarter_it_was_held(self):
        """
        A position closed in the screen quarter takes the most recent earlier filing price.
        """
        self.assertEqual(self._price("AAA", "2025Q3"), 12.0)
        self.assertEqual(self._price("BBB", "2025Q3"), 7.0)

    def test_never_looks_forward(self):
        """
        A later quarter's price is never used, and an unknown name has no price.
        """
        self.assertIsNone(self._price("AAA", "2024Q4"))
        self.assertIsNone(self._price("ZZZ", "2025Q3"))


if __name__ == "__main__":
    unittest.main()
