import unittest
from unittest.mock import patch

import pandas as pd

from app.analysis.non_quarterly import (
    get_non_quarterly_filings_dataframe,
    update_quarter_with_nq_filings,
)
from app.utils.strings import format_value

FUND_CIK = "0001111111"
DENOMINATION = "Example Capital Management"


def _schedule_df(owner, owner_cik, issuer_cik="0009999999", shares=1000, cusip="CUSIP0001"):
    """
    Builds a minimal schedule-filing DataFrame as produced by the XML processor.
    """
    return pd.DataFrame(
        [
            {
                "Company": "Target Co",
                "CUSIP": cusip,
                "CIK": issuer_cik,
                "Shares": shares,
                "Owner_CIK": owner_cik,
                "Owner": owner,
                "Date": pd.Timestamp("2026-05-04"),
            }
        ]
    )


def _resolve_ticker(df):
    """
    Deterministic stand-in for TickerResolver: one ticker per CUSIP.
    """
    df["Ticker"] = df["CUSIP"].str.replace("CUSIP", "TICK", regex=False)
    return df


@patch("app.analysis.non_quarterly.open_issue")
@patch("app.analysis.non_quarterly.PriceFetcher.get_avg_price", return_value=10.0)
@patch(
    "app.stocks.ticker_resolver.TickerResolver.resolve_ticker",
    side_effect=_resolve_ticker,
)
@patch("app.analysis.non_quarterly.xml_to_dataframe_schedule")
class TestGetNonQuarterlyFilingsDataframe(unittest.TestCase):
    @staticmethod
    def _filing(date="2026-05-05", accepted="2026-05-05 10:00:00"):
        """
        Builds a raw filing dict as returned by the scraper.
        """
        return {
            "type": "SCHEDULE",
            "date": date,
            "accepted_on": accepted,
            "xml_content": b"<mock/>",
        }

    def test_denomination_match_is_case_insensitive(
        self, mock_xml, _mock_resolve, _mock_price, mock_issue
    ):
        """
        A filing whose Owner matches the fund denomination (any case) is kept
        and valued at price * shares.
        """
        mock_xml.return_value = _schedule_df(DENOMINATION.upper(), "0002222222")

        result = get_non_quarterly_filings_dataframe([self._filing()], DENOMINATION, FUND_CIK)

        assert result is not None
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["Shares"], 1000)
        self.assertEqual(result.iloc[0]["Value"], format_value(10000))
        mock_issue.assert_not_called()

    def test_cik_fallback_when_denomination_differs(
        self, mock_xml, _mock_resolve, _mock_price, mock_issue
    ):
        """
        When the Owner string does not match, the row is still kept if the
        Owner CIK matches the fund, without opening a GitHub issue.
        """
        mock_xml.return_value = _schedule_df("Some Other Legal Name", FUND_CIK)

        result = get_non_quarterly_filings_dataframe([self._filing()], DENOMINATION, FUND_CIK)

        assert result is not None
        self.assertEqual(len(result), 1)
        mock_issue.assert_not_called()

    def test_no_match_opens_issue_and_returns_none(
        self, mock_xml, _mock_resolve, _mock_price, mock_issue
    ):
        """
        When neither denomination nor CIK matches, a GitHub issue is opened
        and no DataFrame is returned.
        """
        mock_xml.return_value = _schedule_df("Some Other Legal Name", "0003333333")

        result = get_non_quarterly_filings_dataframe([self._filing()], DENOMINATION, FUND_CIK)

        self.assertIsNone(result)
        mock_issue.assert_called_once()

    def test_issuer_self_reference_is_skipped_without_issue(
        self, mock_xml, _mock_resolve, _mock_price, mock_issue
    ):
        """
        A filing about the fund's own shares (issuer CIK == fund CIK) is
        irrelevant: skipped silently, no GitHub issue.
        """
        mock_xml.return_value = _schedule_df(DENOMINATION, FUND_CIK, issuer_cik=FUND_CIK)

        result = get_non_quarterly_filings_dataframe([self._filing()], DENOMINATION, FUND_CIK)

        self.assertIsNone(result)
        mock_issue.assert_not_called()

    def test_amendments_deduplicated_by_acceptance_time(
        self, mock_xml, _mock_resolve, _mock_price, mock_issue
    ):
        """
        Two filings for the same Ticker and event Date keep only the most
        recently accepted one (amendment wins).
        """
        original = _schedule_df(DENOMINATION, FUND_CIK, shares=1000)
        amendment = _schedule_df(DENOMINATION, FUND_CIK, shares=750)
        mock_xml.side_effect = [original, amendment]

        result = get_non_quarterly_filings_dataframe(
            [
                self._filing(accepted="2026-05-05 10:00:00"),
                self._filing(accepted="2026-05-06 09:00:00"),
            ],
            DENOMINATION,
            FUND_CIK,
        )

        assert result is not None
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["Shares"], 750)
        mock_issue.assert_not_called()


class TestUpdateQuarterWithNqFilings(unittest.TestCase):
    @staticmethod
    def _quarter_df():
        """
        Builds a minimal 13F quarter DataFrame with two funds.
        """
        return pd.DataFrame(
            [
                {
                    "Fund": "Fund A",
                    "CUSIP": "CUSIP0001",
                    "Ticker": "TICK0001",
                    "Company": "ALPHA CO",
                    "Shares": 100,
                    "Delta_Shares": 10,
                    "Value_Num": 1000.0,
                    "Delta_Value_Num": 100.0,
                    "Delta": "+11.1%",
                },
                {
                    "Fund": "Fund B",
                    "CUSIP": "CUSIP0002",
                    "Ticker": "TICK0002",
                    "Company": "BETA CO",
                    "Shares": 50,
                    "Delta_Shares": 0,
                    "Value_Num": 500.0,
                    "Delta_Value_Num": 0.0,
                    "Delta": "NO CHANGE",
                },
            ]
        )

    @staticmethod
    def _nq_df(rows):
        """
        Builds the non-quarterly DataFrame returned by load_non_quarterly_data.
        """
        return pd.DataFrame(
            [
                {
                    "Fund": fund,
                    "CUSIP": cusip,
                    "Ticker": ticker,
                    "Company": company,
                    "Shares": shares,
                    "Value": value,
                    "Avg_Price": "10",
                    "Date": pd.Timestamp("2026-05-04"),
                    "Filing_Date": pd.Timestamp("2026-05-05"),
                }
                for fund, cusip, ticker, company, shares, value in rows
            ]
        )

    def test_existing_position_updated_with_nq_shares(self):
        """
        An NQ filing for a held CUSIP updates Shares and recomputes the deltas
        against the 13F baseline.
        """
        nq = self._nq_df([("Fund A", "CUSIP0001", "TICK0001", "Alpha Co", 150, "1.5K")])

        with patch("app.analysis.non_quarterly.load_non_quarterly_data", return_value=nq):
            result = update_quarter_with_nq_filings(self._quarter_df(), ["Fund A"])

        row = result[(result["Fund"] == "Fund A") & (result["CUSIP"] == "CUSIP0001")].iloc[0]
        self.assertEqual(row["Shares"], 150)
        self.assertEqual(row["Delta_Shares"], 50)
        self.assertEqual(row["Delta_Value_Num"], 500.0)
        self.assertEqual(row["Delta"], 50.0)

    def test_new_and_closed_positions_flagged(self):
        """
        An NQ-only CUSIP is flagged NEW; an NQ filing reporting zero shares on
        a held CUSIP is flagged CLOSE.
        """
        nq = self._nq_df(
            [
                ("Fund A", "CUSIP0003", "TICK0003", "Gamma Co", 200, "2K"),
                ("Fund A", "CUSIP0001", "TICK0001", "Alpha Co", 0, "0"),
            ]
        )

        with patch("app.analysis.non_quarterly.load_non_quarterly_data", return_value=nq):
            result = update_quarter_with_nq_filings(self._quarter_df(), ["Fund A"])

        new_row = result[(result["Fund"] == "Fund A") & (result["CUSIP"] == "CUSIP0003")].iloc[0]
        closed_row = result[(result["Fund"] == "Fund A") & (result["CUSIP"] == "CUSIP0001")].iloc[0]
        self.assertEqual(new_row["Delta"], "NEW")
        self.assertEqual(new_row["Shares"], 200)
        self.assertEqual(closed_row["Delta"], "CLOSE")
        self.assertEqual(closed_row["Shares"], 0)

    def test_fund_without_13f_keeps_only_nq_active_rows(self):
        """
        For a fund that did not file a 13F this quarter, stale carried-over
        positions are dropped and only NQ-active rows survive.
        """
        nq = self._nq_df([("Fund A", "CUSIP0001", "TICK0001", "Alpha Co", 150, "1.5K")])

        with patch("app.analysis.non_quarterly.load_non_quarterly_data", return_value=nq):
            result = update_quarter_with_nq_filings(
                self._quarter_df(), ["Fund A", "Fund B"], idx_13f_funds=["Fund A"]
            )

        self.assertIn("CUSIP0001", set(result["CUSIP"]))
        self.assertNotIn("CUSIP0002", set(result["CUSIP"]))


if __name__ == "__main__":
    unittest.main()
