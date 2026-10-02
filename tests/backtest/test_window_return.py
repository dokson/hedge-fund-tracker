"""
Pricing of a backtest window: a constituent that stops trading before the exit
date is valued at its last known price, and one the providers can no longer
price at entry enters at its filing-implied price, so neither is dropped
(survivorship bias).
"""

import unittest
from datetime import date

from app.backtest.engine import _window_return

ENTRY = date(2025, 5, 15)
EXIT = date(2025, 8, 14)


class _Prices:
    """
    Offline price source over canned daily bars, counting every lookup.
    """

    def __init__(self, bars: dict[str, dict[date, float]]):
        """
        Store the canned bars and reset the call logs.
        """
        self.bars = bars
        self.day_calls: list[tuple[str, date]] = []
        self.range_calls: list[tuple[str, date, date]] = []

    def price_fn(self, ticker: str, day: date) -> float | None:
        """
        Return the bar exactly on `day`, if any.
        """
        self.day_calls.append((ticker, day))
        return self.bars.get(ticker, {}).get(day)

    def last_price_fn(self, ticker: str, start: date, end: date) -> float | None:
        """
        Return the last bar strictly after `start` and at or before `end`.
        """
        self.range_calls.append((ticker, start, end))
        series = self.bars.get(ticker, {})
        inside = [d for d in series if start < d <= end]
        return series[max(inside)] if inside else None


class WindowReturnTest(unittest.TestCase):
    """
    _window_return keeps every constituent that had an entry price.
    """

    def _run(
        self, prices: _Prices, screen: dict[str, float], filing: dict[str, float] | None = None
    ):
        """
        Run the window over the canned prices and filing-implied entry prices.
        """
        return _window_return(
            screen,
            ENTRY,
            EXIT,
            prices.price_fn,
            prices.last_price_fn,
            (filing or {}).get,
            "test",
        )

    def test_delisted_name_is_valued_at_its_last_known_price(self):
        """
        A name whose last bar is mid-window contributes its return up to that bar.
        """
        prices = _Prices(
            {
                "UP": {ENTRY: 100.0, EXIT: 110.0},
                "GONE": {ENTRY: 100.0, date(2025, 6, 20): 40.0},
            }
        )
        result = self._run(prices, {"UP": 0.5, "GONE": 0.5})

        assert result is not None
        conviction, priced = result
        self.assertAlmostEqual(conviction, 0.5 * 0.10 + 0.5 * -0.60)
        self.assertEqual(priced, {"UP", "GONE"})

    def test_delisted_name_costs_a_single_range_lookup(self):
        """
        A name without an exit price is resolved by one range lookup, never by probing.
        """
        prices = _Prices({"GONE": {ENTRY: 100.0, date(2025, 6, 20): 40.0}})
        self._run(prices, {"GONE": 1.0})

        self.assertEqual(prices.range_calls, [("GONE", ENTRY, EXIT)])
        self.assertEqual(prices.day_calls, [("GONE", ENTRY), ("GONE", EXIT)])

    def test_exit_price_skips_the_range_lookup(self):
        """
        A name priced on the exit date never triggers a range lookup.
        """
        prices = _Prices({"UP": {ENTRY: 100.0, EXIT: 110.0}})
        self._run(prices, {"UP": 1.0})

        self.assertEqual(prices.range_calls, [])

    def test_name_without_any_later_bar_is_flat(self):
        """
        With no bar after entry, the entry price is the last known price: a 0% return.
        """
        prices = _Prices({"UP": {ENTRY: 100.0, EXIT: 120.0}, "STALE": {ENTRY: 50.0}})
        result = self._run(prices, {"UP": 0.5, "STALE": 0.5})

        assert result is not None
        self.assertAlmostEqual(result[0], 0.5 * 0.20)

    def test_name_without_provider_entry_price_enters_at_its_filing_price(self):
        """
        When no provider prices the entry, the filing-implied price is the entry price.
        """
        prices = _Prices({"GONE": {date(2025, 6, 20): 45.0}})
        result = self._run(prices, {"GONE": 1.0}, filing={"GONE": 50.0})

        assert result is not None
        self.assertAlmostEqual(result[0], -0.10)
        self.assertEqual(result[1], {"GONE"})

    def test_name_without_any_entry_price_is_excluded(self):
        """
        With neither a provider nor a filing price, the name is left out and the rest renormalized.
        """
        prices = _Prices({"UP": {ENTRY: 100.0, EXIT: 110.0}})
        result = self._run(prices, {"UP": 0.5, "NEVER": 0.5})

        assert result is not None
        self.assertAlmostEqual(result[0], 0.10)
        self.assertEqual(result[1], {"UP"})


if __name__ == "__main__":
    unittest.main()
