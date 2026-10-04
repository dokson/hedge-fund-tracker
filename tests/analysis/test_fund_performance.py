"""
Tests for the per-fund quarterly Holding-Based Return series.
"""

import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from app.analysis.fund_performance import (
    build_fund_performance,
    cached_market_return,
    holding_based_return,
    position_returns,
    reported_prices,
    unpriced_weight,
    write_fund_performance,
)


def holdings(*rows: tuple[str, str, float, float]) -> pd.DataFrame:
    """
    Builds a holdings frame from (CUSIP, Ticker, Shares, Value) tuples.
    """
    df = pd.DataFrame(rows, columns=["CUSIP", "Ticker", "Shares", "Value"])
    df["Company"] = df["Ticker"]
    df["Reported_Price"] = df["Value"] / df["Shares"]
    return df


START, END = date(2026, 3, 31), date(2026, 6, 30)


def no_market(_ticker: str, _start: date, _end: date) -> float | None:
    """
    A market price source that knows nothing.
    """
    return None


class TestPriceSanity(unittest.TestCase):
    """
    One fund's filing is checked against what every tracked fund reported.
    """

    def test_split_applied_once_when_the_fund_already_restated(self):
        """
        A start row already on the post-split basis is not divided again.
        """
        prev = holdings(("B1", "BKNG", 1, 168.0))
        curr = holdings(("B1", "BKNG", 1, 170.0))
        frame = position_returns(
            prev,
            curr,
            {"B1": 25.0},
            no_market,
            start=START,
            end=END,
            universe_start_prices={"B1": 4210.0},
            universe_prices={"B1": 170.0},
        )
        self.assertAlmostEqual(float(frame["Return"].iloc[0]), 170.0 / 168.0 - 1)

    def test_split_still_applied_when_most_funds_restated(self):
        """
        A post-split median does not trigger a second division.
        """
        prev = holdings(("B1", "BKNG", 1, 168.0))
        curr = holdings(("B1", "BKNG", 1, 170.0))
        frame = position_returns(
            prev,
            curr,
            {"B1": 25.0},
            no_market,
            start=START,
            end=END,
            universe_start_prices={"B1": 168.0},
            universe_prices={"B1": 170.0},
        )
        self.assertAlmostEqual(float(frame["Return"].iloc[0]), 170.0 / 168.0 - 1)

    def test_a_filed_price_is_never_corrected_here(self):
        """
        Filed figures are corrected once, by the filing register the loaders
        apply; a price the register let through is the fund's own.
        """
        prev = holdings(("Q1", "QQQ", 1, 100.0))
        curr = holdings(("Q1", "QQQ", 1, 135.0))
        frame = position_returns(
            prev,
            curr,
            {},
            no_market,
            start=START,
            end=END,
            universe_start_prices={"Q1": 100.0},
            universe_prices={"Q1": 100.0},
        )
        self.assertAlmostEqual(float(frame["Return"].iloc[0]), 0.35)

    def test_an_exit_is_priced_at_the_funds_median(self):
        """
        With no own price at the end, the other funds' median is the price.
        """
        prev = holdings(("Q1", "QQQ", 1, 700.0))
        curr = holdings(("Q1", "QQQ", 0, 0.0))
        frame = position_returns(
            prev,
            curr,
            {},
            no_market,
            start=START,
            end=END,
            universe_start_prices={"Q1": 700.0},
            universe_prices={"Q1": 736.0},
        )
        self.assertAlmostEqual(float(frame["Return"].iloc[0]), 736.0 / 700.0 - 1)

    def test_genuine_large_move_is_kept(self):
        """
        A big return reported consistently by the universe is not clipped.
        """
        prev = holdings(("S1", "SNDK", 1, 100.0))
        curr = holdings(("S1", "SNDK", 1, 358.0))
        frame = position_returns(
            prev,
            curr,
            {},
            no_market,
            start=START,
            end=END,
            universe_start_prices={"S1": 101.0},
            universe_prices={"S1": 355.0},
        )
        self.assertAlmostEqual(float(frame["Return"].iloc[0]), 2.58)

    def test_market_return_across_a_split_is_restated(self):
        """
        A market return spanning a split basis change is put back on one basis.
        """
        prev = holdings(("B1", "BKNG", 1, 4200.0))
        frame = position_returns(
            prev,
            holdings(("Z9", "ZZZ", 1, 1)),
            {"B1": 25.0},
            lambda _t, _s, _e: 170.0 / 4200.0 - 1,
            start=START,
            end=END,
        )
        self.assertAlmostEqual(float(frame["Return"].iloc[0]), 170.0 / 168.0 - 1)


class _StubCache:
    """
    A price cache that knows a delisted name's start price and its last trade.
    """

    def get(self, ticker: str, day: date) -> float | None:
        """
        Only the start-of-quarter price is known.
        """
        return 20.0 if (ticker, day) == ("GONE", START) else None

    def last_in_range(self, ticker: str, start: date, end: date) -> float | None:
        """
        The name stopped trading at 26 inside the quarter.
        """
        return 26.0 if (ticker, start, end) == ("GONE", START, END) else None


class TestCachedMarketReturn(unittest.TestCase):
    """
    Market fallback for positions no tracked fund still reports.
    """

    def test_delisted_name_uses_its_last_trade(self):
        """
        A takeover or delisting is priced at the last bar, not counted flat.
        """
        market = cached_market_return(_StubCache())
        result = market("GONE", START, END)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result or 0.0, 0.30)

    def test_unknown_name_is_none(self):
        """
        No start price means no measurable return.
        """
        self.assertIsNone(cached_market_return(_StubCache())("NOPE", START, END))


class TestUnpricedWeight(unittest.TestCase):
    """
    The share of the book whose quarter return could not be priced.
    """

    def test_unpriced_positions_are_flagged_and_weighed(self):
        """
        A position with no price anywhere counts flat but is reported.
        """
        prev = holdings(("A1", "AAA", 10, 300), ("B1", "BBB", 10, 100))
        curr = holdings(("A1", "AAA", 10, 330))
        frame = position_returns(prev, curr, {}, no_market, start=START, end=END)
        self.assertEqual(list(frame["Priced"]), [True, False])
        self.assertAlmostEqual(unpriced_weight(frame), 0.25)


class TestPositionReturns(unittest.TestCase):
    """
    Weights and returns of the positions held at the start of a quarter.
    """

    def test_weights_by_start_value_and_returns_from_reported_prices(self):
        """
        Kept positions return their end price over their start price.
        """
        prev = holdings(("A1", "AAA", 10, 300), ("B1", "BBB", 10, 100))
        curr = holdings(("A1", "AAA", 10, 330), ("B1", "BBB", 10, 90))
        frame = position_returns(prev, curr, {}, no_market, start=START, end=END)
        weights = dict(zip(frame["Ticker"], frame["Weight"], strict=True))
        returns = dict(zip(frame["Ticker"], frame["Return"], strict=True))
        self.assertAlmostEqual(float(weights["AAA"]), 0.75)
        self.assertAlmostEqual(float(returns["AAA"]), 0.10)
        self.assertAlmostEqual(float(returns["BBB"]), -0.10)

    def test_split_is_not_read_as_a_crash(self):
        """
        A 10:1 split restates the start price onto the new share basis.
        """
        prev = holdings(("A1", "AAA", 10, 1000))
        curr = holdings(("A1", "AAA", 100, 1100))
        frame = position_returns(prev, curr, {"A1": 10.0}, no_market, start=START, end=END)
        self.assertAlmostEqual(frame["Return"].iloc[0], 0.10)

    def test_closed_position_uses_market_return(self):
        """
        A position gone by quarter end takes its market return over the quarter.
        """
        prev = holdings(("A1", "AAA", 10, 100))
        curr = holdings(("Z9", "ZZZ", 1, 1))
        frame = position_returns(prev, curr, {}, lambda _t, _s, _e: 0.25, start=START, end=END)
        self.assertAlmostEqual(frame["Return"].iloc[0], 0.25)

    def test_closed_position_prefers_other_funds_reported_price(self):
        """
        Another fund's quarter-end filing prices the exit on the same basis.
        """
        prev = holdings(("A1", "AAA", 10, 100))
        curr = holdings(("Z9", "ZZZ", 1, 1))
        frame = position_returns(
            prev,
            curr,
            {},
            lambda _t, _s, _e: 0.99,
            start=START,
            end=END,
            universe_prices={"A1": 12.0},
        )
        self.assertAlmostEqual(float(frame["Return"].iloc[0]), 0.20)

    def test_closed_position_without_market_price_counts_as_flat(self):
        """
        Without a market return the closed position contributes nothing.
        """
        prev = holdings(("A1", "AAA", 10, 100))
        frame = position_returns(
            prev, holdings(("Z9", "ZZZ", 1, 1)), {}, no_market, start=START, end=END
        )
        self.assertEqual(frame["Return"].iloc[0], 0.0)


class TestReportedPrices(unittest.TestCase):
    """
    The quarter-end price of each security across every fund's filing.
    """

    def test_median_of_reported_prices_ignoring_empty_positions(self):
        """
        One outlier filing does not move the price; zero-share lines are skipped.
        """
        frames = [
            holdings(("A1", "AAA", 10, 100)),
            holdings(("A1", "AAA", 10, 110)),
            holdings(("A1", "AAA", 10, 900), ("B1", "BBB", 0, 0)),
        ]
        self.assertEqual(reported_prices(frames), {"A1": 11.0})

    def test_two_reports_are_no_consensus(self):
        """
        The median of two filings is their mean: one bad row poisons it.
        """
        frames = [holdings(("U1", "URG", 1000, 161330)), holdings(("U1", "URG", 1000, 1400))]
        self.assertEqual(reported_prices(frames), {})


class TestImplausibleMoves(unittest.TestCase):
    """
    A held position's move is the filed one, however large: genuine moves and
    errors look alike against the fund's own history, and filed errors are
    corrected upstream by the filing register.
    """

    def test_an_extreme_reported_move_is_kept_without_asking_the_market(self):
        """
        A real collapse (a bankruptcy) stays a collapse instead of counting flat.
        """
        calls: list[str] = []

        def market(ticker: str, _s: date, _e: date) -> float | None:
            calls.append(ticker)
            return None

        prev = holdings(("T1", "TSEOF", 1000, 2350))
        curr = holdings(("T1", "TSEOF", 1000, 497))
        frame = position_returns(prev, curr, {}, market, start=START, end=END)
        self.assertAlmostEqual(float(frame["Return"].iloc[0]), 497 / 2350 - 1)
        self.assertTrue(bool(frame["Priced"].iloc[0]))
        self.assertEqual(calls, [])

    def test_moderate_move_needs_no_market_check(self):
        """
        An ordinary move keeps the reported prices and never asks the market.
        """
        calls: list[str] = []

        def market(ticker: str, _s: date, _e: date) -> float | None:
            calls.append(ticker)
            return 0.0

        prev = holdings(("A1", "AAA", 10, 100))
        curr = holdings(("A1", "AAA", 10, 180))
        frame = position_returns(prev, curr, {}, market, start=START, end=END)
        self.assertAlmostEqual(float(frame["Return"].iloc[0]), 0.8)
        self.assertEqual(calls, [])


class TestHoldingBasedReturn(unittest.TestCase):
    """
    The weighted sum of position returns.
    """

    def test_weighted_sum(self):
        """
        0.75 * 10% + 0.25 * -10% = 5%.
        """
        prev = holdings(("A1", "AAA", 10, 300), ("B1", "BBB", 10, 100))
        curr = holdings(("A1", "AAA", 10, 330), ("B1", "BBB", 10, 90))
        result = holding_based_return(
            position_returns(prev, curr, {}, no_market, start=START, end=END)
        )
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result or 0.0, 0.05)

    def test_empty_portfolio_has_no_return(self):
        """
        Nothing held at the start means no measurable return.
        """
        empty = holdings()
        self.assertIsNone(
            holding_based_return(
                position_returns(empty, empty, {}, no_market, start=START, end=END)
            )
        )


class TestBuildFundPerformance(unittest.TestCase):
    """
    One row per fund and quarter, with cumulative returns against the benchmark.
    """

    def setUp(self):
        """
        Three quarters of a fund that gains 10% then 20%, against a flat index.
        """
        self.data = {
            ("Alpha", "2025Q4"): holdings(("A1", "AAA", 10, 100)),
            ("Alpha", "2026Q1"): holdings(("A1", "AAA", 10, 110)),
            ("Alpha", "2026Q2"): holdings(("A1", "AAA", 10, 132)),
        }

    def holdings_fn(self, fund: str, quarter: str) -> pd.DataFrame:
        """
        Looks up the fixture holdings, empty when the fund did not file.
        """
        return self.data.get((fund, quarter), holdings())

    def build(self, quarters: list[str]) -> list[dict[str, object]]:
        """
        Runs the builder over the fixture with a benchmark that returns 5% a quarter.
        """
        return build_fund_performance(
            ["Alpha"],
            quarters,
            holdings_fn=self.holdings_fn,
            factors_fn=lambda _prev, _curr: {},
            closed_return_fn=no_market,
            benchmark_return_fn=lambda _s, _e: 0.05,
        )

    def test_rows_compound_fund_and_benchmark(self):
        """
        Cumulative returns compound each quarter's return.
        """
        rows = self.build(["2025Q4", "2026Q1", "2026Q2"])
        self.assertEqual([r["quarter"] for r in rows], ["2026Q1", "2026Q2"])
        self.assertAlmostEqual(float(str(rows[0]["fund_return"])), 0.10)
        self.assertAlmostEqual(float(str(rows[1]["fund_cum_return"])), 0.32)
        self.assertAlmostEqual(float(str(rows[1]["benchmark_cum_return"])), 1.05 * 1.05 - 1)

    def test_exit_priced_from_another_funds_quarter_end_filing(self):
        """
        A position the fund sold is priced from a fund still holding it.
        """
        self.data[("Alpha", "2026Q1")] = holdings(("Z9", "ZZZ", 1, 1))
        rows = build_fund_performance(
            ["Alpha"],
            ["2025Q4", "2026Q1"],
            holdings_fn=self.holdings_fn,
            factors_fn=lambda _prev, _curr: {},
            closed_return_fn=no_market,
            benchmark_return_fn=lambda _s, _e: 0.05,
            universe_prices_fn=lambda quarter: {"A1": 13.0} if quarter == "2026Q1" else {},
        )
        self.assertAlmostEqual(float(str(rows[0]["fund_return"])), 0.30)

    def test_skipped_quarter_breaks_no_window(self):
        """
        A quarter without a filing on either side yields no row for that window.
        """
        del self.data[("Alpha", "2026Q1")]
        self.assertEqual(self.build(["2025Q4", "2026Q1", "2026Q2"]), [])

    def test_unknown_benchmark_fails_the_run(self):
        """
        A missing index price would blank every later cumulative: refuse to publish.
        """
        with self.assertRaisesRegex(ValueError, "2026Q1"):
            build_fund_performance(
                ["Alpha"],
                ["2025Q4", "2026Q1"],
                holdings_fn=self.holdings_fn,
                factors_fn=lambda _prev, _curr: {},
                closed_return_fn=no_market,
                benchmark_return_fn=lambda _s, _e: None,
            )

    def test_rows_report_the_unpriced_weight(self):
        """
        Each row says how much of the book went unpriced.
        """
        self.data[("Alpha", "2025Q4")] = holdings(("A1", "AAA", 10, 100), ("B1", "BBB", 10, 100))
        rows = self.build(["2025Q4", "2026Q1"])
        self.assertAlmostEqual(float(str(rows[0]["unpriced_weight"])), 0.5)


class TestWriteFundPerformance(unittest.TestCase):
    """
    The CSV the static site reads.
    """

    def test_writes_rounded_rows_with_header(self):
        """
        Values are rounded and blanks stay blank.
        """
        rows: list[dict[str, object]] = [
            {
                "fund": "Alpha",
                "quarter": "2026Q1",
                "fund_return": 0.1234567891,
                "benchmark_return": None,
                "fund_cum_return": 0.1234567891,
                "benchmark_cum_return": None,
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "fund_performance.csv"
            write_fund_performance(rows, target)
            with target.open(encoding="utf-8", newline="") as handle:
                written = list(csv.DictReader(handle))
        self.assertEqual(written[0]["fund_return"], "0.123457")
        self.assertEqual(written[0]["benchmark_return"], "")


if __name__ == "__main__":
    unittest.main()
