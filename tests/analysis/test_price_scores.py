import math
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from app.analysis import price_scores as ps


def _rising(n: int, rate: float = 0.01) -> list[float]:
    """
    A series compounding at ``rate`` per day.
    """
    return [100 * (1 + rate) ** i for i in range(n)]


def _alternating(n: int, step: float = 0.01) -> list[float]:
    """
    A series whose daily log returns alternate between +step and -step.
    """
    closes = [100.0]
    for i in range(n - 1):
        closes.append(closes[-1] * math.exp(step if i % 2 == 0 else -step))
    return closes


def _num(value: float | None) -> float:
    """
    Narrows an optional metric to a float, failing the test when it is None.
    """
    assert value is not None
    return value


class TestMomentum(unittest.TestCase):
    def test_rising_series_uses_21_and_252_day_offsets(self):
        """
        Close 21 days ago over close 252 days ago spans 231 daily steps.
        """
        self.assertAlmostEqual(_num(ps.momentum_12_1(_rising(300))), 1.01**231 - 1)

    def test_flat_series_has_zero_momentum(self):
        """
        No price change means no momentum.
        """
        self.assertEqual(ps.momentum_12_1([50.0] * 300), 0.0)

    def test_only_the_offset_closes_matter(self):
        """
        The latest month is skipped and older closes are ignored.
        """
        closes = [100.0] * 300
        closes[-22] = 120.0
        closes[-253] = 80.0
        closes[-1] = 1000.0
        closes[0] = 1.0
        self.assertAlmostEqual(_num(ps.momentum_12_1(closes)), 0.5)

    def test_partial_history_uses_the_oldest_available_close(self):
        """
        Between the minimum and a full year, the lookback starts at the first close.
        """
        closes = [100.0] * 200
        closes[0] = 50.0
        self.assertAlmostEqual(_num(ps.momentum_12_1(closes)), 1.0)

    def test_insufficient_history_returns_none(self):
        """
        Fewer than the minimum closes yields no metric.
        """
        self.assertIsNone(ps.momentum_12_1(_rising(ps.MIN_HISTORY - 1)))
        self.assertIsNotNone(ps.momentum_12_1(_rising(ps.MIN_HISTORY)))


class TestVolatility(unittest.TestCase):
    def test_constant_growth_and_flat_series_have_zero_volatility(self):
        """
        Identical daily log returns have zero dispersion.
        """
        self.assertAlmostEqual(_num(ps.annualized_volatility(_rising(300))), 0.0)
        self.assertEqual(ps.annualized_volatility([10.0] * 300), 0.0)

    def test_known_volatility_over_last_252_returns(self):
        """
        Alternating +/-1% log returns: sample std 0.01*sqrt(252/251), times sqrt(252).
        """
        closes = [100.0] * 50 + _alternating(253)
        self.assertAlmostEqual(_num(ps.annualized_volatility(closes)), 0.01 * 252 / math.sqrt(251))

    def test_insufficient_history_returns_none(self):
        """
        Fewer than the minimum closes yields no metric.
        """
        self.assertIsNone(ps.annualized_volatility(_alternating(ps.MIN_HISTORY - 1)))


class TestPercentileScores(unittest.TestCase):
    def test_maps_ranks_onto_1_100(self):
        """
        Lowest gets 1, highest 100, the middle one 50 or 51 (linear in rank).
        """
        scores = ps.percentile_scores({"A": 0.1, "B": 0.3, "C": 0.2}, higher_is_better=True)
        self.assertEqual(scores, {"A": 1, "B": 100, "C": 51})

    def test_lower_is_better_inverts(self):
        """
        For volatility the lowest value scores highest.
        """
        scores = ps.percentile_scores({"A": 0.1, "B": 0.3}, higher_is_better=False)
        self.assertEqual(scores, {"A": 100, "B": 1})

    def test_ties_share_the_average_rank(self):
        """
        Equal values get the same score.
        """
        scores = ps.percentile_scores({"A": 1.0, "B": 1.0, "C": 2.0}, higher_is_better=True)
        self.assertEqual(scores["A"], scores["B"])
        self.assertEqual(scores["A"], 26)
        self.assertEqual(scores["C"], 100)

    def test_single_stock_and_missing_values_are_neutral(self):
        """
        One ranked value has no peers; a missing value is not ranked.
        """
        scores = ps.percentile_scores({"A": 0.5, "B": None}, higher_is_better=True)
        self.assertEqual(scores, {"A": 50, "B": 50})

    def test_all_equal_values_are_neutral(self):
        """
        No dispersion means no ranking information.
        """
        self.assertEqual(
            ps.percentile_scores({"A": 1.0, "B": 1.0}, higher_is_better=True), {"A": 50, "B": 50}
        )


class TestScoreHistories(unittest.TestCase):
    def test_scores_and_raw_metrics_per_ticker(self):
        """
        Momentum and volatility are ranked independently across the list.
        """
        histories = {"UP": _rising(300, 0.002), "FLAT": [10.0] * 300, "CHOP": _alternating(300)}
        result = ps.score_histories(histories)
        self.assertEqual(result["UP"]["Momentum_Score"], 100)
        self.assertEqual(result["FLAT"]["Momentum_Score"], 51)
        self.assertEqual(result["CHOP"]["Low_Volatility_Score"], 1)
        self.assertGreaterEqual(result["FLAT"]["Low_Volatility_Score"], 75)
        self.assertAlmostEqual(result["FLAT"]["Momentum"], 0.0)
        self.assertIsInstance(result["UP"]["Momentum_Score"], int)

    def test_insufficient_or_missing_history_is_neutral_and_warned(self):
        """
        A short or failed history scores 50 without affecting the others.
        """
        histories = {"A": _rising(300), "B": [10.0] * 300, "IPO": _rising(30), "GONE": None}
        with patch.object(ps, "logger") as mock_logger:
            result = ps.score_histories(histories)
        for ticker in ("IPO", "GONE"):
            self.assertEqual(result[ticker]["Momentum_Score"], 50)
            self.assertEqual(result[ticker]["Low_Volatility_Score"], 50)
            self.assertIsNone(result[ticker]["Momentum"])
        self.assertEqual(result["A"]["Momentum_Score"], 100)
        self.assertEqual(mock_logger.warning.call_count, 2)


class TestFetchDailyCloses(unittest.TestCase):
    def test_limits_concurrency_and_paces_requests(self):
        """
        At most two fetches run at once and each request is preceded by a pause.
        """
        lock = threading.Lock()
        state = {"active": 0, "peak": 0}

        def fetch(ticker: str) -> list[float]:
            """
            Records peak concurrency.
            """
            with lock:
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            time.sleep(0.02)
            with lock:
                state["active"] -= 1
            return [1.0]

        sleep = MagicMock()
        result = ps.fetch_daily_closes([f"T{i}" for i in range(8)], fetch_fn=fetch, sleep=sleep)
        self.assertEqual(len(result), 8)
        self.assertLessEqual(state["peak"], ps.MAX_WORKERS)
        self.assertEqual(ps.MAX_WORKERS, 2)
        self.assertEqual(sleep.call_count, 8)

    def test_failure_backs_off_then_gives_none_without_aborting(self):
        """
        A raising fetch is retried with growing waits, then recorded as None.
        """
        calls: dict[str, int] = {}

        def fetch(ticker: str) -> list[float] | None:
            """
            Fails for one ticker, succeeds on the second try for another.
            """
            calls[ticker] = calls.get(ticker, 0) + 1
            if ticker == "BAD":
                raise RuntimeError("rate limited")
            if ticker == "FLAKY" and calls[ticker] == 1:
                return None
            return [1.0, 2.0]

        sleep = MagicMock()
        result = ps.fetch_daily_closes(["BAD", "FLAKY", "OK"], fetch_fn=fetch, sleep=sleep)
        self.assertIsNone(result["BAD"])
        self.assertEqual(result["FLAKY"], [1.0, 2.0])
        self.assertEqual(result["OK"], [1.0, 2.0])
        self.assertEqual(calls["BAD"], ps.MAX_ATTEMPTS)
        waits = [c.args[0] for c in sleep.call_args_list]
        self.assertIn(ps.BACKOFF_SECONDS * 2, waits)

    def test_default_fetch_reads_daily_closes_from_yfinance(self):
        """
        The default source is YFinance daily history, reduced to closes.
        """
        points = [{"date": "2026-01-02", "close": 5.0}, {"date": "2026-01-05", "close": 6.0}]
        with patch.object(ps.YFinance, "get_history", return_value=points) as mock_history:
            self.assertEqual(ps._yfinance_closes("AAA"), [5.0, 6.0])
        mock_history.assert_called_once_with("AAA", ps.HISTORY_PERIOD)
        self.assertEqual(ps.YFinance.PERIOD_TO_INTERVAL[ps.HISTORY_PERIOD], "1d")


if __name__ == "__main__":
    unittest.main()
