import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

from app.analysis.splits import (
    detect_splits,
    factors_between,
    rebuild_split_registry,
    splits_for_transition,
    unregistered_splits,
)


def _position(fund, cusip, shares, price, shares_previous, price_previous):
    """
    Builds one holder row in the shape detect_splits consumes.
    """
    return {
        "Fund": fund,
        "CUSIP": cusip,
        "Shares": shares,
        "Value": shares * price,
        "Shares_previous": shares_previous,
        "Value_previous": shares_previous * price_previous,
    }


class TestDetectSplits(unittest.TestCase):
    def test_detects_forward_split_from_agreeing_holders(self):
        # 10:1 split: three untouched holders land on exactly 10x the share
        # count at a tenth of the price. A fourth holder also traded.
        positions = pd.DataFrame(
            [
                _position("Alpha", "SPLIT0001", 40000, 12.0, 4000, 110.0),
                _position("Beta", "SPLIT0001", 96000, 12.0, 9600, 110.0),
                _position("Gamma", "SPLIT0001", 15000, 12.0, 1500, 110.0),
                _position("Delta", "SPLIT0001", 30000, 12.0, 1000, 110.0),
            ]
        )

        self.assertEqual(detect_splits(positions), {"SPLIT0001": 10.0})

    def test_detects_reverse_split(self):
        positions = pd.DataFrame(
            [
                _position("Alpha", "SPLIT0002", 500, 40.0, 2500, 9.0),
                _position("Beta", "SPLIT0002", 1200, 40.0, 6000, 9.0),
                _position("Gamma", "SPLIT0002", 80, 40.0, 400, 9.0),
            ]
        )

        self.assertEqual(detect_splits(positions), {"SPLIT0002": 0.2})

    def test_ignores_holders_that_merely_doubled_their_positions(self):
        # Three funds doubling into a flat price is ordinary accumulation: the
        # price did not halve, so no split happened.
        positions = pd.DataFrame(
            [
                _position("Alpha", "TRADE0001", 8000, 50.0, 4000, 48.0),
                _position("Beta", "TRADE0001", 2000, 50.0, 1000, 48.0),
                _position("Gamma", "TRADE0001", 30000, 50.0, 15000, 48.0),
            ]
        )

        self.assertEqual(detect_splits(positions), {})

    def test_requires_three_agreeing_holders(self):
        positions = pd.DataFrame(
            [
                _position("Alpha", "SPLIT0003", 40000, 12.0, 4000, 110.0),
                _position("Beta", "SPLIT0003", 96000, 12.0, 9600, 110.0),
            ]
        )

        self.assertEqual(detect_splits(positions), {})

    def test_snaps_factor_to_a_simple_ratio(self):
        # Rounded share counts leave holders a hair apart; the reported factor
        # must still be exactly 3, or untouched holders would show a residual
        # delta once the previous quarter is rescaled.
        positions = pd.DataFrame(
            [
                _position("Alpha", "SPLIT0004", 12001, 20.0, 4000, 61.0),
                _position("Beta", "SPLIT0004", 29999, 20.0, 10000, 61.0),
                _position("Gamma", "SPLIT0004", 4502, 20.0, 1500, 61.0),
            ]
        )

        self.assertEqual(detect_splits(positions), {"SPLIT0004": 3.0})

    def test_snaps_a_factor_that_is_simple_only_over_a_large_denominator(self):
        # Holders agreeing near 4.98 describe a 5:1 split, not a 249/50 one:
        # a factor is simple in its numerator too, or nothing snaps.
        positions = pd.DataFrame(
            [
                _position("Alpha", "SPLIT0005", 49800, 24.0, 10000, 119.0),
                _position("Beta", "SPLIT0005", 12450, 24.0, 2500, 119.0),
                _position("Gamma", "SPLIT0005", 4482, 24.0, 900, 119.0),
            ]
        )

        self.assertEqual(detect_splits(positions), {"SPLIT0005": 5.0})

    def test_returns_empty_for_an_empty_frame(self):
        positions = pd.DataFrame(
            columns=["Fund", "CUSIP", "Shares", "Value", "Shares_previous", "Value_previous"]
        )

        self.assertEqual(detect_splits(positions), {})


class TestUnregisteredSplits(unittest.TestCase):
    def test_reports_only_splits_missing_from_the_registry(self):
        detected = [
            {"Quarter": "2026Q2", "CUSIP": "146869102", "Ticker": "CVNA", "Factor": 5.0},
            {"Quarter": "2026Q3", "CUSIP": "64110L106", "Ticker": "NFLX", "Factor": 2.0},
        ]
        registry = {"2026Q2": {"146869102": 5.0}}

        self.assertEqual(
            unregistered_splits(detected, registry),
            [{"Quarter": "2026Q3", "CUSIP": "64110L106", "Ticker": "NFLX", "Factor": 2.0}],
        )

    def test_a_changed_factor_counts_as_unregistered(self):
        detected = [{"Quarter": "2026Q2", "CUSIP": "146869102", "Ticker": "CVNA", "Factor": 5.0}]
        registry = {"2026Q2": {"146869102": 4.0}}

        self.assertEqual(unregistered_splits(detected, registry), detected)

    def test_empty_when_the_registry_is_current(self):
        detected = [{"Quarter": "2026Q2", "CUSIP": "146869102", "Ticker": "CVNA", "Factor": 5.0}]

        self.assertEqual(unregistered_splits(detected, {"2026Q2": {"146869102": 5.0}}), [])


class TestSplitsForTransition(unittest.TestCase):
    def _positions(self, ratio=10.0, price_ratio=0.1, holders=3):
        """
        Builds holders of one security whose share counts all moved by ratio.
        """
        return pd.DataFrame(
            [
                _position(
                    f"Fund{i}",
                    "SPLIT0001",
                    int(1000 * (i + 1) * ratio),
                    100.0 * price_ratio,
                    1000 * (i + 1),
                    100.0,
                )
                | {"Ticker": "SPLT"}
                for i in range(holders)
            ]
        )

    def test_records_a_split_the_provider_confirms_inside_the_quarter(self):
        rows = splits_for_transition(
            self._positions(), "2026Q2", lambda _ticker: [(date(2026, 5, 8), 10.0)]
        )

        self.assertEqual(
            rows,
            [
                {
                    "Quarter": "2026Q2",
                    "Date": "2026-05-08",
                    "CUSIP": "SPLIT0001",
                    "Ticker": "SPLT",
                    "Factor": 10.0,
                }
            ],
        )

    def test_ignores_a_split_dated_outside_the_quarter(self):
        rows = splits_for_transition(
            self._positions(), "2026Q2", lambda _ticker: [(date(2026, 3, 31), 10.0)]
        )

        self.assertEqual(rows, [])

    def test_provider_saying_no_split_overrules_the_filings(self):
        # Share counts that look like a split but Yahoo reports none: this is
        # what keeps ordinary accumulation from being erased as a split.
        rows = splits_for_transition(self._positions(), "2026Q2", lambda _ticker: [])

        self.assertEqual(rows, [])

    def test_compounds_two_splits_in_the_same_quarter(self):
        rows = splits_for_transition(
            self._positions(),
            "2026Q2",
            lambda _ticker: [(date(2026, 4, 10), 2.0), (date(2026, 6, 2), 5.0)],
        )

        self.assertEqual(rows[0]["Factor"], 10.0)
        self.assertEqual(rows[0]["Date"], "2026-06-02")

    def test_falls_back_to_holder_agreement_when_the_lookup_fails(self):
        rows = splits_for_transition(self._positions(), "2026Q2", lambda _ticker: None)

        # A row inferred from holders carries no ex-date; that is what marks it.
        self.assertEqual(rows[0]["Factor"], 10.0)
        self.assertEqual(rows[0]["Date"], "")

    def test_a_failed_lookup_without_agreement_records_nothing(self):
        rows = splits_for_transition(self._positions(holders=1), "2026Q2", lambda _ticker: None)

        self.assertEqual(rows, [])

    def _holders(self, ratios, price_ratio):
        """
        Builds holders of one security with the given per-holder share ratios.
        """
        return pd.DataFrame(
            [
                _position(
                    f"Fund{i}", "SPLIT0001", int(1000 * ratio), 100.0 * price_ratio, 1000, 100.0
                )
                | {"Ticker": "SPLT"}
                for i, ratio in enumerate(ratios)
            ]
        )

    def test_rejects_a_factor_the_filed_share_counts_do_not_confirm(self):
        # A spinoff: Yahoo records a price-basis adjustment as a split, but the
        # share counts never moved. Applying it would erase real positions.
        rows = splits_for_transition(
            self._holders([1.0, 1.0, 1.29, 2.22], 0.42),
            "2025Q4",
            lambda _ticker: [(date(2025, 11, 3), 2.39)],
        )

        self.assertEqual(rows, [])

    def test_rejects_a_factor_inside_the_ordinary_trading_band(self):
        # A ~1% stock dividend is not a split; treating it as one would put a
        # residual delta on every untouched holder.
        rows = splits_for_transition(
            self._holders([0.585, 0.989, 1.01, 1.01], 0.99),
            "2025Q2",
            lambda _ticker: [(date(2025, 5, 12), 1.009)],
        )

        self.assertEqual(rows, [])

    def test_accepts_a_factor_holders_confirm_only_roughly(self):
        # Holders that also traded across the split land near the factor, not
        # on it: the median is what has to agree, not any single holder.
        rows = splits_for_transition(
            self._holders([14.662, 15.364], 1 / 15),
            "2025Q2",
            lambda _ticker: [(date(2025, 6, 9), 15.0)],
        )

        self.assertEqual(rows[0]["Factor"], 15.0)

    def test_securities_that_did_not_move_are_never_looked_up(self):
        looked_up = []

        def provider(ticker):
            looked_up.append(ticker)
            return []

        splits_for_transition(self._positions(ratio=1.05, price_ratio=1.0), "2026Q2", provider)

        self.assertEqual(looked_up, [])


class TestIncrementalRebuild(unittest.TestCase):
    QUARTERS = ["2025Q4", "2026Q1", "2026Q2"]

    def _positions(self, quarter):
        """
        A single holder whose share count is unchanged, so nothing is a candidate.
        """
        return pd.DataFrame(
            [
                {
                    "Fund": "Alpha",
                    "CUSIP": "AAA000001",
                    "Ticker": "AAA",
                    "Shares": 1000,
                    "Value": 50000.0,
                }
            ]
        )

    @patch("app.analysis.splits.splits_for_transition", return_value=[])
    @patch("app.analysis.splits.get_all_quarters")
    def test_scans_every_transition_by_default(self, mock_quarters, mock_transition):
        mock_quarters.return_value = self.QUARTERS

        with patch("app.analysis.splits._quarter_positions", self._positions):
            rebuild_split_registry(provider=lambda _t: [])

        scanned = [call.args[1] for call in mock_transition.call_args_list]
        self.assertEqual(scanned, ["2026Q1", "2026Q2"])

    @patch("app.analysis.splits.splits_for_transition", return_value=[])
    @patch("app.analysis.splits.get_all_quarters")
    def test_scans_only_the_requested_quarters(self, mock_quarters, mock_transition):
        mock_quarters.return_value = self.QUARTERS

        with patch("app.analysis.splits._quarter_positions", self._positions):
            rebuild_split_registry(provider=lambda _t: [], quarters=["2026Q2"])

        scanned = [call.args[1] for call in mock_transition.call_args_list]
        self.assertEqual(scanned, ["2026Q2"])

    @patch("app.analysis.splits.splits_for_transition", return_value=[])
    @patch("app.analysis.splits.get_all_quarters")
    def test_the_earliest_quarter_has_no_transition_to_scan(self, mock_quarters, mock_transition):
        mock_quarters.return_value = self.QUARTERS

        with patch("app.analysis.splits._quarter_positions", self._positions):
            rebuild_split_registry(provider=lambda _t: [], quarters=["2025Q4"])

        self.assertEqual(mock_transition.call_args_list, [])


class TestFactorsBetween(unittest.TestCase):
    REGISTRY = {
        "2026Q1": {"AAA000001": 2.0, "BBB000002": 10.0},
        "2026Q2": {"AAA000001": 3.0},
    }

    def test_consecutive_quarters_take_only_the_recent_quarters_splits(self):
        self.assertEqual(
            factors_between(self.REGISTRY, "2026Q1", "2026Q2"),
            {"AAA000001": 3.0},
        )

    def test_a_skipped_quarter_compounds_every_split_it_spans(self):
        # A fund that filed nothing for 2026Q1 compares 2026Q2 against 2025Q4,
        # so both quarters' splits sit between the two filings.
        self.assertEqual(
            factors_between(self.REGISTRY, "2025Q4", "2026Q2"),
            {"AAA000001": 6.0, "BBB000002": 10.0},
        )

    def test_spans_a_year_boundary(self):
        registry = {"2026Q1": {"AAA000001": 2.0}}

        self.assertEqual(factors_between(registry, "2025Q3", "2026Q1"), {"AAA000001": 2.0})

    def test_no_previous_quarter_means_no_factors(self):
        self.assertEqual(factors_between(self.REGISTRY, None, "2026Q2"), {})

    def test_empty_registry(self):
        self.assertEqual(factors_between({}, "2025Q4", "2026Q2"), {})


if __name__ == "__main__":
    unittest.main()
