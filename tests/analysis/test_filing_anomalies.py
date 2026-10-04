"""
Tests for the detector of filed rows whose price does not fit their CUSIP.
"""

import unittest

import pandas as pd

from app.analysis.filing_anomalies import (
    CusipAnomaly,
    CusipAnomalyDetector,
    FiledRow,
    closed_from_quarter_file,
    render_anomalies_markdown,
    rows_from_quarter_file,
)

DETECTOR = CusipAnomalyDetector()


def row(
    fund: str,
    cusip: str,
    price: float,
    quarter: str = "2026Q2",
    shares: float = 1000.0,
    delta: str = "",
) -> FiledRow:
    """
    A filed row; the company name is carried for the report only.
    """
    return FiledRow(
        quarter=quarter,
        fund=fund,
        cusip=cusip,
        company="ANY NAME",
        price=price,
        shares=shares,
        delta=delta,
    )


def holders(cusip: str, price: float, quarter: str = "2026Q2") -> list[FiledRow]:
    """
    Three funds reporting a security at the same price.
    """
    return [row(f"Fund{i}", cusip, price, quarter) for i in range(3)]


class TestAgainstTheFunds(unittest.TestCase):
    """
    A row is judged only against the other funds' price for the same CUSIP.
    """

    def test_flags_a_row_priced_unlike_every_other_holder(self):
        """
        An ETF filed under another fund's CUSIP at a twentieth of its price is flagged.
        """
        rows = [*holders("QQQ1", 736.0), row("Ratan", "QQQ1", 31.6)]
        anomalies = DETECTOR.detect(rows)
        self.assertEqual([(a.fund, a.cusip) for a in anomalies], [("Ratan", "QQQ1")])
        self.assertAlmostEqual(anomalies[0].reference_price, 736.0)

    def test_consistent_prices_are_not_flagged(self):
        """
        Small differences between filings are normal.
        """
        rows = [*holders("QQQ1", 736.0), row("Other", "QQQ1", 740.0)]
        self.assertEqual(DETECTOR.detect(rows), [])

    def test_a_gap_of_forty_percent_is_flagged(self):
        """
        The other holders all report one price; 44% away is another security.
        """
        rows = [*holders("JCI", 105.7), row("Talaria", "JCI", 152.7)]
        self.assertEqual(len(DETECTOR.detect(rows)), 1)

    def test_the_funds_own_history_is_never_a_reference(self):
        """
        A jump from the fund's previous quarter is a genuine move as often as not.
        """
        rows = [
            row("Segra", "URG1", 1.79, "2025Q3", shares=26_262_623),
            row("Segra", "URG1", 161.33, "2025Q4", shares=1000),
        ]
        self.assertEqual(DETECTOR.detect(rows), [])

    def test_too_few_holders_means_no_verdict(self):
        """
        Two funds disagreeing do not say which one is wrong.
        """
        rows = [row("A", "X1", 10.0), row("B", "X1", 100.0)]
        self.assertEqual(DETECTOR.detect(rows), [])

    def test_min_reporters_is_configurable(self):
        """
        A looser detector accepts a two-fund consensus.
        """
        rows = [row("A", "QQQ1", 736.0), row("B", "QQQ1", 736.0), row("Ratan", "QQQ1", 31.6)]
        self.assertEqual(len(CusipAnomalyDetector(min_reporters=2).detect(rows)), 1)


class TestAutomaticCorrection(unittest.TestCase):
    """
    A flagged row is moved to the one CUSIP whose price it matches, among the
    filing's other flagged CUSIPs and the positions the filing closes.
    """

    def test_a_position_filed_under_a_neighbours_cusip_returns_home(self):
        """
        A position filed under another issuer's CUSIP, while its own reads as closed.
        """
        rows = [
            *holders("JCI", 80.0, "2025Q1"),
            *holders("JNJ", 165.0, "2025Q1"),
            row("Talaria", "JCI", 165.8, "2025Q1", shares=483_200, delta="NEW"),
        ]
        anomalies = DETECTOR.detect(rows, closed={("Talaria", "2025Q1"): {"JNJ": 559_800}})
        self.assertEqual(
            [(a.fund, a.cusip, a.correct_cusip) for a in anomalies], [("Talaria", "JCI", "JNJ")]
        )
        self.assertIn("JNJ", anomalies[0].note)

    def test_a_rotated_cusip_column_is_put_back(self):
        """
        Three rows shifted by one CUSIP each go back to their own.
        """
        rows = [
            *holders("URG", 1.40, "2025Q4"),
            *holders("VST", 161.0, "2025Q4"),
            *holders("NKLR", 4.62, "2025Q4"),
            row("Segra", "NKLR", 1.39, "2025Q4"),
            row("Segra", "URG", 161.33, "2025Q4"),
            row("Segra", "VST", 4.62, "2025Q4"),
        ]
        fixes = {(a.cusip, a.correct_cusip) for a in DETECTOR.detect(rows)}
        self.assertEqual(fixes, {("NKLR", "URG"), ("URG", "VST"), ("VST", "NKLR")})

    def test_two_matching_candidates_mean_no_correction(self):
        """
        When the price fits two closed positions, nothing is guessed.
        """
        rows = [
            *holders("JCI", 80.0, "2025Q1"),
            *holders("JNJ", 165.0, "2025Q1"),
            *holders("PG", 166.0, "2025Q1"),
            row("Talaria", "JCI", 165.8, "2025Q1", delta="NEW"),
        ]
        closed = {("Talaria", "2025Q1"): {"JNJ": 1000, "PG": 1000}}
        self.assertIsNone(DETECTOR.detect(rows, closed=closed)[0].correct_cusip)

    def test_no_matching_candidate_leaves_the_row_open(self):
        """
        Without a candidate at the filed price the anomaly is only reported.
        """
        rows = [*holders("QQQ1", 736.0), row("Ratan", "QQQ1", 31.6)]
        self.assertIsNone(DETECTOR.detect(rows)[0].correct_cusip)


class TestMatcherSafeguards(unittest.TestCase):
    """
    A correction needs evidence beyond a loosely similar price.
    """

    def test_a_loose_price_match_is_not_enough(self):
        """
        A rotation whose prices fit only within 40% is left open.
        """
        rows = [
            *holders("A1", 10.0),
            *holders("B1", 100.0),
            row("F", "A1", 140.0),
            row("F", "B1", 14.0),
        ]
        self.assertTrue(all(a.correct_cusip is None for a in DETECTOR.detect(rows)))

    def test_a_chain_that_does_not_close_is_left_open(self):
        """
        Rows matching one another's prices without forming a cycle are not moved.
        """
        rows = [
            *holders("A1", 10.0),
            *holders("B1", 100.0),
            row("F", "A1", 100.0),
            row("F", "B1", 1000.0),
        ]
        self.assertTrue(all(a.correct_cusip is None for a in DETECTOR.detect(rows)))

    def test_a_closed_position_needs_a_similar_share_count(self):
        """
        A closed position held in very different size is a coincidence, not the row.
        """
        rows = [
            *holders("JCI", 80.0, "2025Q1"),
            *holders("JNJ", 165.0, "2025Q1"),
            row("Talaria", "JCI", 165.8, "2025Q1", shares=483_200, delta="NEW"),
        ]
        anomalies = DETECTOR.detect(rows, closed={("Talaria", "2025Q1"): {"JNJ": 8_000}})
        self.assertIsNone(anomalies[0].correct_cusip)

    def test_a_continuing_position_is_never_moved_to_a_closed_cusip(self):
        """
        A row the fund already held under its CUSIP is not a misfiled new one: in
        a filing that closes hundreds of positions, one priced alike is chance.
        """
        rows = [
            *holders("MSTR", 404.0, "2025Q2"),
            *holders("OTHER", 99.0, "2025Q2"),
            row("Big", "MSTR", 100.2, "2025Q2", shares=264_599, delta="+1172.1%"),
        ]
        anomalies = DETECTOR.detect(rows, closed={("Big", "2025Q2"): {"OTHER": 250_000}})
        self.assertIsNone(anomalies[0].correct_cusip)

    def test_a_closed_position_must_match_closely(self):
        """
        Same-date prices of one security agree; a 10% gap is a coincidence.
        """
        rows = [*holders("PLTR", 133.0), *holders("MMM", 127.0), row("A", "PLTR", 115.6)]
        detector = CusipAnomalyDetector(price_tolerance=0.1)
        anomalies = detector.detect(rows, closed={("A", "2026Q2"): {"MMM": 1000}})
        self.assertIsNone(anomalies[0].correct_cusip)

    def test_a_closed_position_without_a_funds_price_is_no_candidate(self):
        """
        A candidate too few funds hold has no price to match against.
        """
        rows = [*holders("JCI", 80.0), row("B", "JNJ", 165.0), row("A", "JCI", 165.8)]
        anomalies = DETECTOR.detect(rows, closed={("A", "2026Q2"): {"JNJ": 1000}})
        self.assertIsNone(anomalies[0].correct_cusip)


class TestRestatement(unittest.TestCase):
    """
    A row the other funds contradict, with no CUSIP to move to, is restated at
    their price: its value by default, its share count on a registered split basis.
    """

    def test_a_mis_valued_row_keeps_its_shares_and_takes_the_funds_price(self):
        """
        Value and Delta_Value are recomputed at the funds' price; shares stay as filed.
        """
        filed = FiledRow(
            "2025Q2", "Ratan", "FXI", "ANY", 368.0, 15_000, delta_shares=15_000, delta="NEW"
        )
        (a,) = DETECTOR.detect([*holders("FXI", 36.8, "2025Q2"), filed])
        self.assertEqual(a.kind, "value")
        assert a.restated is not None
        self.assertEqual(a.restated.shares, 15_000)
        self.assertAlmostEqual(a.restated.value, 552_000)
        self.assertAlmostEqual(a.restated.delta_value, 552_000)
        self.assertEqual(a.restated.delta, "NEW")

    def test_shares_on_a_registered_split_basis_are_restated(self):
        """
        A ratio equal to the CUSIP's split factor means the share count is on the other basis.
        """
        filed = FiledRow(
            "2026Q1", "Blue", "BKNG", "ANY", 168.24, 17_000, delta_shares=17_000, delta="NEW"
        )
        detector = CusipAnomalyDetector(split_factors={"BKNG": {25.0}})
        (a,) = detector.detect([*holders("BKNG", 4206.0, "2026Q1"), filed])
        self.assertEqual(a.kind, "shares")
        assert a.restated is not None
        self.assertEqual((a.restated.shares, a.restated.delta_shares), (680, 680))
        self.assertAlmostEqual(a.restated.value, 168.24 * 17_000)
        self.assertEqual(a.restated.delta, "NEW")

    def test_a_share_restatement_carries_into_the_next_filing(self):
        """
        The next comparison was made against the wrong share count; its delta follows.
        """
        filed = FiledRow(
            "2026Q1", "Blue", "BKNG", "ANY", 168.24, 17_000, delta_shares=17_000, delta="NEW"
        )
        detector = CusipAnomalyDetector(
            split_factors={"BKNG": {25.0}}, split_factors_fn=lambda _p, _c: {"BKNG": 25.0}
        )
        rows = [*holders("BKNG", 4206.0, "2026Q1"), filed, row("Blue", "OTHER", 10.0, "2026Q2")]
        closed = {("Blue", "2026Q2"): {"BKNG": 425_000.0}}
        carried = [a for a in detector.detect(rows, closed=closed) if a.kind == "carried"]
        self.assertEqual([(a.quarter, a.cusip) for a in carried], [("2026Q2", "BKNG")])
        assert carried[0].restated is not None
        self.assertEqual(carried[0].restated.shares, 0)
        self.assertEqual(carried[0].restated.delta_shares, -17_000)
        self.assertEqual(carried[0].restated.delta, "CLOSE")

    def test_a_cusip_correction_is_not_restated(self):
        """
        A row moved to its real CUSIP keeps the filed numbers.
        """
        rows = [
            *holders("JCI", 80.0, "2025Q1"),
            *holders("JNJ", 165.0, "2025Q1"),
            row("Talaria", "JCI", 165.8, "2025Q1", shares=483_200, delta="NEW"),
        ]
        (a,) = DETECTOR.detect(rows, closed={("Talaria", "2025Q1"): {"JNJ": 559_800}})
        self.assertEqual((a.kind, a.restated), ("cusip", None))


def anomaly(fund: str) -> CusipAnomaly:
    """
    A report entry for the rendering tests.
    """
    return CusipAnomaly(
        quarter="2025Q4",
        fund=fund,
        cusip="91688R108",
        filed_company="VISTRA | CORP",
        filed_price=161.33,
        reference_price=1.79,
    )


class TestRowsFromQuarterFile(unittest.TestCase):
    """
    A saved quarter CSV becomes priced rows.
    """

    def test_reads_price_and_shares_and_skips_totals_and_closed_rows(self):
        """
        Value strings are parsed; the Total line and zero-share rows carry no price.
        """
        df = pd.DataFrame(
            {
                "CUSIP": ["AAA", "BBB", "Total"],
                "Company": ["ALPHA", "BETA", ""],
                "Shares": ["1000", "0", ""],
                "Value": ["161.33K", "0", "161.33K"],
            }
        )
        rows = rows_from_quarter_file("2025Q4", "Segra", df)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].cusip, rows[0].shares), ("AAA", 1000.0))
        self.assertAlmostEqual(rows[0].price, 161.33)


class TestClosedFromQuarterFile(unittest.TestCase):
    """
    The positions a saved filing closes are the matcher's candidates.
    """

    def test_reads_the_close_rows(self):
        """
        Rows marked CLOSE, with the share count the fund held before.
        """
        df = pd.DataFrame(
            {
                "CUSIP": ["G51502105", "478160104", "Total"],
                "Delta_Shares": ["483200", "-559800", ""],
                "Delta": ["NEW", "CLOSE", ""],
            }
        )
        self.assertEqual(closed_from_quarter_file(df), {"478160104": 559_800.0})


class TestMarkdown(unittest.TestCase):
    """
    The run summary lists the anomalies in one table.
    """

    def test_lists_every_anomaly_in_order(self):
        """
        One table, ordered by quarter and fund.
        """
        md = render_anomalies_markdown([anomaly("Zeta"), anomaly("Alpha")])
        self.assertLess(md.index("Alpha"), md.index("Zeta"))
        self.assertNotIn("To verify", md)

    def test_filed_names_are_escaped(self):
        """
        A filed name cannot break the Markdown table.
        """
        self.assertIn(r"VISTRA \| CORP", render_anomalies_markdown([anomaly("A")]))

    def test_no_anomalies_says_so(self):
        """
        A clean database gets one line.
        """
        self.assertIn("No price anomalies", render_anomalies_markdown([]))


if __name__ == "__main__":
    unittest.main()
