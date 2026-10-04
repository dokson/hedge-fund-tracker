"""
Tests for the filing review register (database/filing_anomalies.csv): detector
anomalies and the owner's decisions on them, in one file.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app.analysis.filing_anomalies import CusipAnomaly, Restatement
from app.database.filing_anomalies import (
    COLUMNS,
    apply_restatements,
    check_filings,
    corrections_for,
    merge_anomalies,
    save_filing_anomalies,
)


def anomaly(quarter: str, fund: str, cusip: str, company: str) -> CusipAnomaly:
    """
    One detector finding.
    """
    return CusipAnomaly(
        quarter=quarter,
        fund=fund,
        cusip=cusip,
        filed_company=company,
        filed_price=10.0,
        reference_price=1.0,
    )


def register(*rows: dict[str, str]) -> pd.DataFrame:
    """
    A register frame with every column, blanks where a row leaves one out.
    """
    return pd.DataFrame([{c: r.get(c, "") for c in COLUMNS} for r in rows], columns=COLUMNS)


CORRECTED = {
    "Quarter": "2025Q4",
    "Fund": "Segra",
    "Filed_CUSIP": "91688R108",
    "Filed_Company": "VISTRA CORP",
    "Status": "auto-corrected",
    "CUSIP": "92840M102",
}
DISMISSED = {
    "Quarter": "2026Q2",
    "Fund": "IMC",
    "Filed_CUSIP": "05988J103",
    "Filed_Company": "BANDWIDTH INC",
    "Status": "dismissed",
    "Note": "real move",
}


class TestMergeAnomalies(unittest.TestCase):
    """
    A scan adds and refreshes open findings but never touches a decision.
    """

    def test_new_findings_are_added_as_open(self):
        """
        A first scan fills the register with open rows.
        """
        merged = merge_anomalies(
            register(), [anomaly("2026Q2", "Ratan", "46090E103", "iShares China")]
        )
        self.assertEqual(merged["Status"].tolist(), ["open"])

    def test_decided_rows_survive_even_when_no_longer_detected(self):
        """
        A corrected row stops being anomalous once applied: it must not be dropped.
        """
        merged = merge_anomalies(register(CORRECTED, DISMISSED), [])
        self.assertEqual(sorted(merged["Status"]), ["auto-corrected", "dismissed"])
        self.assertEqual(
            merged.loc[merged["Status"] == "auto-corrected", "CUSIP"].item(), "92840M102"
        )

    def test_a_dismissed_finding_does_not_come_back(self):
        """
        Re-detecting a dismissed row keeps the owner's decision and note.
        """
        merged = merge_anomalies(
            register(DISMISSED),
            [anomaly("2026Q2", "IMC", "05988J103", "BANDWIDTH INC")],
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged["Status"].item(), "dismissed")
        self.assertEqual(merged["Note"].item(), "real move")

    def test_open_rows_no_longer_detected_are_dropped(self):
        """
        An undecided finding that disappeared (e.g. the fund amended) leaves the register.
        """
        stale = {**DISMISSED, "Status": "open", "Note": ""}
        self.assertTrue(merge_anomalies(register(stale), []).empty)

    def test_funds_no_longer_tracked_leave_the_register(self):
        """
        A fund removed from hedge_funds.csv takes every row with it, decided ones included.
        """
        merged = merge_anomalies(
            register(CORRECTED, DISMISSED),
            [anomaly("2026Q2", "Ratan", "X", "N")],
            tracked={"IMC", "Ratan"},
        )
        self.assertEqual(sorted(merged["Fund"]), ["IMC", "Ratan"])

    def test_without_a_tracked_list_nothing_is_dropped(self):
        """
        An unreadable fund list must not wipe the register.
        """
        self.assertEqual(len(merge_anomalies(register(CORRECTED, DISMISSED), [], tracked=set())), 2)

    def test_order_is_stable(self):
        """
        Same content, same row order: the committed file only changes with the findings.
        """
        found = [anomaly("2026Q1", "B", "X", "N"), anomaly("2025Q4", "A", "Y", "M")]
        first = merge_anomalies(register(), found)
        second = merge_anomalies(register(), list(reversed(found)))
        pd.testing.assert_frame_equal(first, second)
        self.assertEqual(first["Fund"].tolist(), ["A", "B"])


RESTATED = Restatement(
    shares=1000, value=36_800.0, delta_shares=1000, delta_value=36_800.0, delta="NEW"
)


class TestRestatementsInTheRegister(unittest.TestCase):
    """
    A restated finding is recorded with the figures the analysis uses.
    """

    def test_a_restated_finding_is_auto_corrected_with_its_figures(self):
        """
        Kind and the restated figures land in the register.
        """
        found = CusipAnomaly(
            **{
                **anomaly("2025Q2", "R", "FXI", "ETF").__dict__,
                "kind": "value",
                "restated": RESTATED,
            }
        )
        merged = merge_anomalies(register(), [found])
        row = merged.iloc[0]
        self.assertEqual((row["Status"], row["Kind"]), ("auto-corrected", "value"))
        self.assertEqual((row["Shares"], row["Value"], row["Delta"]), ("1000", "36800", "NEW"))

    def test_carried_rows_are_rebuilt_on_every_scan(self):
        """
        A carried delta follows its restatement: gone when the scan no longer yields it.
        """
        carried = CusipAnomaly(
            **{**anomaly("2026Q2", "B", "X", "N").__dict__, "kind": "carried", "restated": RESTATED}
        )
        merged = merge_anomalies(register(), [carried])
        self.assertEqual(merged["Status"].tolist(), ["carried"])
        self.assertTrue(merge_anomalies(merged, []).empty)

    def test_cusip_corrections_without_a_kind_read_as_cusip(self):
        """
        Rows written before kinds existed keep working.
        """
        merged = merge_anomalies(register(CORRECTED), [])
        self.assertEqual(merged["Kind"].tolist(), ["cusip"])


class TestApplyRestatements(unittest.TestCase):
    """
    The analysis loaders read restated figures on top of the faithful CSVs.
    """

    def setUp(self):
        """
        A register restating one row of a two-row filing.
        """
        self.register = register(
            {
                "Quarter": "2025Q2",
                "Fund": "R",
                "Filed_CUSIP": "FXI",
                "Filed_Company": "ETF",
                "Status": "auto-corrected",
                "Kind": "value",
                "Shares": "1000",
                "Value": "36800",
                "Delta_Shares": "1000",
                "Delta_Value": "36800",
                "Delta": "NEW",
            }
        )

    def frame(self) -> pd.DataFrame:
        """
        The filing as saved: the mis-valued row at ten times its price.
        """
        return pd.DataFrame(
            {
                "CUSIP": ["FXI", "AAA"],
                "Shares": [1000, 500],
                "Delta_Shares": [1000, 0],
                "Value": ["368K", "63.2K"],
                "Delta_Value": ["368K", "0"],
                "Delta": ["NEW", "NO CHANGE"],
                "Portfolio%": ["85.34%", "14.66%"],
                "Fund": ["R", "R"],
            }
        )

    def test_restated_row_takes_the_register_figures(self):
        """
        Value fields come from the register; the other row keeps its filed figures.
        """
        out = apply_restatements(self.frame(), "2025Q2", self.register)
        self.assertEqual(out.loc[0, "Value"], "36.8K")
        self.assertEqual(out.loc[1, "Value"], "63.2K")

    def test_portfolio_weights_are_recomputed_for_the_filing(self):
        """
        The filing total changes, so every row's weight follows.
        """
        out = apply_restatements(self.frame(), "2025Q2", self.register)
        self.assertEqual(out["Portfolio%"].tolist(), ["36.8%", "63.2%"])

    def test_columns_read_as_numbers_take_numbers(self):
        """
        A filing whose values all parse as integers keeps numeric columns.
        """
        frame = self.frame().assign(Value=[368_000, 63_200], Delta_Value=[0, 0])
        out = apply_restatements(frame, "2025Q2", self.register)
        self.assertEqual(out.loc[0, "Value"], 36_800)
        self.assertEqual(out.loc[0, "Delta_Value"], 36_800)

    def test_other_quarters_and_funds_are_untouched(self):
        """
        Only the restated filing changes.
        """
        frame = self.frame()
        pd.testing.assert_frame_equal(apply_restatements(frame, "2025Q3", self.register), frame)


class TestSharedRestatementFixture(unittest.TestCase):
    """
    The Python loader and its TypeScript mirror read the register identically,
    pinned by tests/fixtures/restatement_cases.json.
    """

    def test_python_matches_the_shared_cases(self):
        """
        Every expected figure comes out of apply_restatements.
        """
        from app.utils.pd import get_numeric_series

        case = json.loads(
            (Path(__file__).parents[1] / "fixtures" / "restatement_cases.json").read_text(
                encoding="utf-8"
            )
        )
        holdings = pd.DataFrame(case["holdings"]).assign(Fund=case["fund"])
        out = apply_restatements(holdings, case["quarter"], pd.DataFrame(case["register"]))
        for expected, (_, got) in zip(case["expected"], out.iterrows(), strict=True):
            with self.subTest(cusip=expected["cusip"]):
                self.assertEqual(got["CUSIP"], expected["cusip"])
                self.assertEqual(int(got["Shares"]), expected["shares"])
                self.assertEqual(int(got["Delta_Shares"]), expected["deltaShares"])
                value, delta_value = get_numeric_series(
                    pd.Series([got["Value"], got["Delta_Value"]])
                )
                self.assertAlmostEqual(
                    value, expected["value"], delta=abs(expected["value"]) * 0.005
                )
                self.assertAlmostEqual(
                    delta_value, expected["deltaValue"], delta=abs(expected["deltaValue"]) * 0.005
                )
                self.assertEqual(got["Delta"], expected["delta"])
                self.assertAlmostEqual(
                    float(got["Portfolio%"].rstrip("%")), expected["portfolioPct"], places=1
                )


class TestRegisterOnDisk(unittest.TestCase):
    """
    Saving merges into the file; the parser reads its corrected rows.
    """

    def setUp(self):
        """
        Point the database at a temporary folder holding one decided row.
        """
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        register(CORRECTED).to_csv(self.folder / "filing_anomalies.csv", index=False)
        self.patcher = patch("app.database.DB_FOLDER", str(self.folder))
        self.patcher.start()

    def tearDown(self):
        """
        Restore the database folder.
        """
        self.patcher.stop()
        self.tmp.cleanup()

    def test_corrections_for_reads_only_corrected_rows_of_that_filing(self):
        """
        Corrected rows only, keyed by filed CUSIP and upper-cased filed name.
        """
        self.assertEqual(
            corrections_for("Segra", "2025Q4"), {("91688R108", "VISTRA CORP"): "92840M102"}
        )
        self.assertEqual(corrections_for("Segra", "2026Q1"), {})

    def test_save_keeps_decisions_and_adds_findings(self):
        """
        A scan written to disk preserves the corrected row.
        """
        save_filing_anomalies([anomaly("2026Q2", "Ratan", "46090E103", "iShares China")])
        saved = pd.read_csv(self.folder / "filing_anomalies.csv", dtype=str, keep_default_na=False)
        self.assertEqual(sorted(saved["Status"]), ["auto-corrected", "open"])

    def test_hand_corrections_apply_and_survive_a_scan(self):
        """
        A row corrected by hand is applied like an automatic one and never rewritten.
        """
        manual = {**CORRECTED, "Quarter": "2026Q2", "Status": "corrected"}
        register(CORRECTED, manual).to_csv(self.folder / "filing_anomalies.csv", index=False)
        self.assertEqual(
            corrections_for("Segra", "2026Q2"), {("91688R108", "VISTRA CORP"): "92840M102"}
        )
        save_filing_anomalies([])
        saved = pd.read_csv(self.folder / "filing_anomalies.csv", dtype=str, keep_default_na=False)
        self.assertEqual(sorted(saved["Status"]), ["auto-corrected", "corrected"])

    def test_check_filings_scans_and_saves(self):
        """
        One call scans the database and folds the findings into the register.
        """
        found = [anomaly("2026Q2", "Ratan", "46090E103", "iShares China")]
        with patch("app.database.filing_anomalies.scan_database", return_value=found):
            self.assertEqual(check_filings(), found)
        saved = pd.read_csv(self.folder / "filing_anomalies.csv", dtype=str, keep_default_na=False)
        self.assertEqual(len(saved), 2)

    def test_the_quarter_loaders_read_restated_figures(self):
        """
        Both loaders apply the register on top of the saved filing.
        """
        from app.database.quarters import load_fund_data, load_quarterly_data

        (self.folder / "2025Q2").mkdir()
        TestApplyRestatements.frame(TestApplyRestatements()).drop(columns="Fund").to_csv(
            self.folder / "2025Q2" / "R.csv", index=False
        )
        TestApplyRestatements.setUp(holder := TestApplyRestatements())
        holder.register.to_csv(self.folder / "filing_anomalies.csv", index=False)
        quarter = load_quarterly_data("2025Q2")
        fund = load_fund_data("R", "2025Q2")
        self.assertEqual(quarter.loc[quarter["CUSIP"] == "FXI", "Value"].item(), "36.8K")
        self.assertEqual(fund.loc[fund["CUSIP"] == "FXI", "Value"].item(), "36.8K")

    def test_save_keeps_only_tracked_funds(self):
        """
        The register on disk follows hedge_funds.csv.
        """
        pd.DataFrame([{"CIK": "1", "Fund": "Ratan"}]).to_csv(
            self.folder / "hedge_funds.csv", index=False
        )
        saved = save_filing_anomalies([anomaly("2026Q2", "Ratan", "46090E103", "iShares China")])
        self.assertEqual(saved["Fund"].tolist(), ["Ratan"])

    def test_missing_register_means_no_corrections(self):
        """
        A database without the file behaves exactly as before.
        """
        (self.folder / "filing_anomalies.csv").unlink()
        self.assertEqual(corrections_for("Segra", "2025Q4"), {})


if __name__ == "__main__":
    unittest.main()
