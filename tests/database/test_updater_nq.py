import unittest
from unittest.mock import patch

import pandas as pd
from prometheus_client import REGISTRY

from database.updater import (
    process_fund,
    process_fund_nq,
    run_all_funds_report,
    run_fetch_nq_filings,
)

FUND = {"CIK": "0001111111", "CIKs": "", "Fund": "Fund A", "Denomination": "FUND A LLC"}


def _nq_frame(fund, ticker, cusip, date, shares=100):
    """
    Builds a non-quarterly DataFrame shaped like the rows saved to non_quarterly.csv.
    """
    return pd.DataFrame(
        [
            {
                "Fund": fund,
                "CUSIP": cusip,
                "Ticker": ticker,
                "Company": "Target Co",
                "Shares": shares,
                "Value": "1K",
                "Avg_Price": "10",
                "Date": date,
                "Filing_Date": date,
            }
        ]
    )


@patch("database.updater.get_non_quarterly_filings_dataframe")
@patch("database.updater.fetch_non_quarterly_after_date")
@patch("database.updater.get_latest_13f_filing_date", return_value="2026-05-15")
class TestProcessFundNq(unittest.TestCase):
    def test_failed_fetch_marks_the_fund_as_failed(self, _mock_date, mock_fetch, _mock_df):
        """
        A fetch that reports failure yields None results, not an empty list.
        """
        mock_fetch.return_value = None

        self.assertEqual(process_fund_nq(FUND), ("Fund A", None))

    def test_missing_13f_baseline_marks_the_fund_as_failed(self, mock_date, mock_fetch, _mock_df):
        """
        Without the latest 13F date nothing can be fetched, so the fund failed.
        """
        mock_date.return_value = None
        mock_fetch.return_value = None

        self.assertEqual(process_fund_nq(FUND), ("Fund A", None))

    def test_no_new_filings_is_not_a_failure(self, _mock_date, mock_fetch, _mock_df):
        """
        A successful fetch with no filings yields an empty result list.
        """
        mock_fetch.return_value = []

        self.assertEqual(process_fund_nq(FUND), ("Fund A", []))

    def test_failure_on_secondary_cik_marks_the_fund_as_failed(
        self, _mock_date, mock_fetch, mock_df
    ):
        """
        The fund's rows come from all its CIKs, so a failure on any of them fails the fund.
        """
        mock_fetch.side_effect = [[{"type": "4"}], None]
        mock_df.return_value = _nq_frame("Fund A", "TICK", "CUSIP0001", "2026-06-01").drop(
            columns="Fund"
        )

        self.assertEqual(process_fund_nq({**FUND, "CIKs": "0002222222"}), ("Fund A", None))


class _RecordingLock:
    """
    Stand-in for file_lock that records when the lock is entered and left.
    """

    def __init__(self, events: list[str]):
        """
        Share the event log with the read/write fakes.
        """
        self.events = events

    def __call__(self, path):
        """
        Return self as the context manager for ``path``.
        """
        self.events.append(f"lock:{path}")
        return self

    def __enter__(self):
        """
        Record the acquisition.
        """
        self.events.append("enter")

    def __exit__(self, *_exc):
        """
        Record the release.
        """
        self.events.append("exit")
        return False


@patch("database.updater.print_centered")
@patch("database.updater.non_quarterly_path", return_value="nq.csv")
@patch("database.updater.write_non_quarterly_filings")
@patch("database.updater.read_non_quarterly_rows")
@patch("database.updater.process_fund_nq")
@patch("database.updater.load_hedge_funds")
class TestRunFetchNqFilings(unittest.TestCase):
    def setUp(self):
        """
        Replace the file lock with a recorder so lock scope can be asserted.
        """
        self.events: list[str] = []
        lock = patch("database.updater.file_lock", _RecordingLock(self.events))
        lock.start()
        self.addCleanup(lock.stop)

    def test_failed_fund_keeps_its_existing_rows(
        self, mock_funds, mock_process, mock_read, mock_write, _mock_path, _mock_print
    ):
        """
        A fund whose fetch failed keeps every row it already had, while a fund
        fetched successfully is replaced by this run's results.
        """
        mock_funds.return_value = [{"Fund": "Fund A"}, {"Fund": "Fund B"}]
        fresh = _nq_frame("Fund A", "NEWT", "CUSIP0009", pd.Timestamp("2026-06-02"))
        mock_process.side_effect = lambda fund: (
            (fund["Fund"], [fresh]) if fund["Fund"] == "Fund A" else (fund["Fund"], None)
        )
        mock_read.return_value = pd.concat(
            [
                _nq_frame("Fund A", "OLDA", "CUSIP0001", "2026-05-20"),
                _nq_frame("Fund B", "OLDB", "CUSIP0002", "2026-05-21"),
                _nq_frame("Fund B", "OLDB", "CUSIP0002", "2026-05-18", shares=50),
            ],
            ignore_index=True,
        )

        run_fetch_nq_filings()

        mock_read.assert_called_once_with("nq.csv")
        saved = pd.concat(mock_write.call_args.args[0], ignore_index=True)
        self.assertEqual(sorted(saved["Ticker"]), ["NEWT", "OLDB", "OLDB"])
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(saved["Date"]))
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(saved["Filing_Date"]))

    def test_carry_over_read_and_save_share_one_lock(
        self, mock_funds, mock_process, mock_read, mock_write, _mock_path, _mock_print
    ):
        """
        The carried rows are read and the file rewritten inside a single lock scope.
        """
        mock_funds.return_value = [{"Fund": "Fund B"}]
        mock_process.return_value = ("Fund B", None)
        mock_read.side_effect = lambda _p: (
            self.events.append("read"),
            _nq_frame("Fund B", "OLDB", "CUSIP0002", "2026-05-21"),
        )[1]
        mock_write.side_effect = lambda *_a, **_k: self.events.append("write")

        run_fetch_nq_filings()

        self.assertEqual(self.events, ["lock:nq.csv", "enter", "read", "write", "exit"])

    def test_failed_carry_over_read_keeps_the_file_untouched(
        self, mock_funds, mock_process, mock_read, mock_write, _mock_path, _mock_print
    ):
        """
        If the existing rows cannot be read, saving would erase the failed funds: abort.
        """
        mock_funds.return_value = [{"Fund": "Fund A"}, {"Fund": "Fund B"}]
        fresh = _nq_frame("Fund A", "NEWT", "CUSIP0009", pd.Timestamp("2026-06-02"))
        mock_process.side_effect = lambda fund: (
            (fund["Fund"], [fresh]) if fund["Fund"] == "Fund A" else (fund["Fund"], None)
        )
        mock_read.side_effect = OSError("unreadable")

        with self.assertLogs("database.updater", level="ERROR"):
            run_fetch_nq_filings()

        mock_write.assert_not_called()

    def test_no_carry_over_when_every_fund_succeeds(
        self, mock_funds, mock_process, mock_read, mock_write, _mock_path, _mock_print
    ):
        """
        When nothing failed the existing file is not consulted.
        """
        mock_funds.return_value = [{"Fund": "Fund A"}]
        mock_process.return_value = ("Fund A", [])

        run_fetch_nq_filings()

        mock_read.assert_not_called()
        mock_write.assert_called_once_with([], "nq.csv")

    def test_returns_the_run_outcome(
        self, mock_funds, mock_process, mock_read, mock_write, _mock_path, _mock_print
    ):
        """
        The outcome reports funds, rows saved and failed funds for the run summary.
        """
        mock_funds.return_value = [{"Fund": "Fund A"}, {"Fund": "Fund B"}]
        fresh = pd.concat(
            [
                _nq_frame("Fund A", "NEWT", "CUSIP0009", pd.Timestamp("2026-06-02")),
                _nq_frame("Fund A", "NEWU", "CUSIP0010", pd.Timestamp("2026-06-03")),
            ],
            ignore_index=True,
        )
        mock_process.side_effect = lambda fund: (
            (fund["Fund"], [fresh]) if fund["Fund"] == "Fund A" else (fund["Fund"], None)
        )
        mock_read.return_value = _nq_frame("Fund B", "OLDB", "CUSIP0002", "2026-05-21")

        with self.assertLogs("database.updater", level="WARNING"):
            outcome = run_fetch_nq_filings()

        self.assertEqual(outcome.funds, 2)
        self.assertEqual(outcome.rows_saved, 2)
        self.assertEqual(outcome.failed_funds, ("Fund B",))
        self.assertTrue(outcome.saved)

    def test_unsaved_file_is_reported(
        self, mock_funds, mock_process, mock_read, mock_write, _mock_path, _mock_print
    ):
        """
        When the carry-over read fails the outcome says the file was not saved.
        """
        mock_funds.return_value = [{"Fund": "Fund B"}]
        mock_process.return_value = ("Fund B", None)
        mock_read.side_effect = OSError("unreadable")

        with self.assertLogs("database.updater", level="ERROR"):
            outcome = run_fetch_nq_filings()

        self.assertFalse(outcome.saved)

    def test_carried_over_funds_are_counted(
        self, mock_funds, mock_process, mock_read, mock_write, _mock_path, _mock_print
    ):
        """
        Every fund whose existing rows were carried over increments the metric.
        """
        mock_funds.return_value = [{"Fund": "Fund A"}, {"Fund": "Fund B"}]
        mock_process.side_effect = lambda fund: (fund["Fund"], None)
        mock_read.return_value = _nq_frame("Fund B", "OLDB", "CUSIP0002", "2026-05-21")
        before = REGISTRY.get_sample_value("hft_nq_funds_carried_over_total") or 0.0

        with self.assertLogs("database.updater", level="WARNING"):
            run_fetch_nq_filings()

        after = REGISTRY.get_sample_value("hft_nq_funds_carried_over_total")
        self.assertEqual(after, before + 2)


@patch("database.updater.print_centered")
@patch("database.updater._warn_on_unregistered_splits")
@patch("database.updater.load_hedge_funds")
class TestRunAllFundsReport(unittest.TestCase):
    def test_returns_the_number_of_comparisons_written(self, mock_funds, _mock_warn, _mock_print):
        """
        Only funds whose comparison was saved count toward the run summary.
        """
        mock_funds.return_value = [{"Fund": "Fund A"}, {"Fund": "Fund B"}, {"Fund": "Fund C"}]
        with patch(
            "database.updater.process_fund",
            side_effect=lambda fund, **_kw: fund["Fund"] != "Fund B",
        ):
            self.assertEqual(run_all_funds_report(), 2)


@patch("database.updater.fetch_latest_two_13f_filings")
class TestProcessFund(unittest.TestCase):
    def test_no_filing_is_not_a_saved_comparison(self, mock_fetch):
        """
        A fund with no 13F filing writes nothing and reports False.
        """
        mock_fetch.return_value = []

        self.assertFalse(process_fund({"CIK": "1", "Fund": "Fund A"}))

    def test_unexpected_error_reports_false(self, mock_fetch):
        """
        A failure while processing reports False instead of raising.
        """
        mock_fetch.side_effect = RuntimeError("boom")

        with patch("builtins.print"):
            self.assertFalse(process_fund({"CIK": "1", "Fund": "Fund A"}))

    def test_saved_comparison_reports_true(self, mock_fetch):
        """
        A comparison written to the database reports True.
        """
        mock_fetch.return_value = [
            {"reference_date": "2026-06-30", "date": "2026-08-10", "xml_content": "<x/>"}
        ]
        with (
            patch("database.updater.xml_to_dataframe_13f", return_value=pd.DataFrame()),
            patch("database.updater.load_split_factors", return_value={}),
            patch("database.updater.factors_between", return_value={}),
            patch("database.updater.generate_comparison", return_value=pd.DataFrame()),
            patch("database.updater.save_comparison") as mock_save,
        ):
            self.assertTrue(process_fund({"CIK": "1", "Fund": "Fund A"}))
        mock_save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
