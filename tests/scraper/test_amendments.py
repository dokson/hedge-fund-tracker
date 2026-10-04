"""
Tests for consolidating a 13F-HR/A "NEW HOLDINGS" amendment with the report it adds to.
"""

import unittest

from app.scraper.amendments import (
    amendment_type,
    consolidate_period,
    holdings_value,
    merge_new_holdings,
)


def info_table(*rows: tuple[str, int]) -> bytes:
    """
    An information table with one row per (CUSIP, value), namespaced as EDGAR serves it.
    """
    body = "".join(
        f"<ns1:infoTable><ns1:nameOfIssuer>X</ns1:nameOfIssuer><ns1:cusip>{c}</ns1:cusip>"
        f"<ns1:value>{v}</ns1:value><ns1:shrsOrPrnAmt><ns1:sshPrnamt>1</ns1:sshPrnamt>"
        f"</ns1:shrsOrPrnAmt></ns1:infoTable>"
        for c, v in rows
    )
    return f'<?xml version="1.0"?><ns1:informationTable xmlns:ns1="x">{body}</ns1:informationTable>'.encode()


def filing(ref: str, published: str, xml: bytes, kind: str = "") -> dict:
    """
    A scraped filing as the scraper returns it.
    """
    return {"reference_date": ref, "date": published, "xml_content": xml, "amendment_type": kind}


ORIGINAL = filing("2024-12-31", "2025-02-14", info_table(("A", 300), ("B", 200)))


class TestCoverPage(unittest.TestCase):
    """
    The amendment type is read from the filing's cover page.
    """

    def test_reads_the_amendment_type(self):
        """
        The cover page names the amendment kind.
        """
        cover = b"<edgarSubmission><coverPage><isAmendment>true</isAmendment><amendmentInfo><amendmentType>NEW HOLDINGS</amendmentType></amendmentInfo></coverPage></edgarSubmission>"
        self.assertEqual(amendment_type(cover), "NEW HOLDINGS")

    def test_an_original_has_no_amendment_type(self):
        """
        An original report carries no amendment block.
        """
        self.assertEqual(amendment_type(b"<edgarSubmission><coverPage/></edgarSubmission>"), "")


class TestMergeNewHoldings(unittest.TestCase):
    """
    A partial amendment's rows join the report they add to.
    """

    def test_rows_of_both_reports_are_kept(self):
        """
        The merged table holds the original rows and the added ones.
        """
        merged = merge_new_holdings(ORIGINAL["xml_content"], info_table(("C", 50)))
        self.assertEqual(holdings_value(merged), 550)
        self.assertIn(b"<ns1:cusip>C</ns1:cusip>", merged)
        self.assertTrue(merged.rstrip().endswith(b"</ns1:informationTable>"))


class TestConsolidatePeriod(unittest.TestCase):
    """
    One report per period, with partial amendments merged in.
    """

    def test_a_partial_new_holdings_amendment_is_merged_into_its_report(self):
        """
        A few added rows complete the original instead of replacing it.
        """
        partial = filing("2024-12-31", "2025-04-09", info_table(("C", 50)), "NEW HOLDINGS")
        (out,) = consolidate_period([partial, ORIGINAL])
        self.assertEqual(holdings_value(out["xml_content"]), 550)
        self.assertEqual(out["date"], "2025-04-09")

    def test_a_full_report_labelled_new_holdings_replaces_the_original(self):
        """
        An amendment carrying the whole book is a restatement whatever its label.
        """
        full = filing(
            "2024-12-31", "2025-04-09", info_table(("A", 310), ("B", 210)), "NEW HOLDINGS"
        )
        (out,) = consolidate_period([full, ORIGINAL])
        self.assertEqual(holdings_value(out["xml_content"]), 520)

    def test_a_restatement_replaces_the_original(self):
        """
        The latest restatement wins, as before.
        """
        restated = filing("2024-12-31", "2025-04-09", info_table(("A", 100)), "RESTATEMENT")
        (out,) = consolidate_period([restated, ORIGINAL])
        self.assertIs(out, restated)

    def test_new_holdings_without_its_original_is_kept_as_filed(self):
        """
        With nothing to merge into, the amendment is all there is.
        """
        partial = filing("2024-12-31", "2025-04-09", info_table(("C", 50)), "NEW HOLDINGS")
        (out,) = consolidate_period([partial])
        self.assertIs(out, partial)

    def test_two_partial_amendments_both_join_the_original(self):
        """
        Successive additions accumulate.
        """
        first = filing("2024-12-31", "2025-03-01", info_table(("C", 50)), "NEW HOLDINGS")
        second = filing("2024-12-31", "2025-04-09", info_table(("D", 20)), "NEW HOLDINGS")
        (out,) = consolidate_period([second, first, ORIGINAL])
        self.assertEqual(holdings_value(out["xml_content"]), 570)

    def test_periods_are_kept_apart_newest_first(self):
        """
        Other periods pass through, ordered newest reporting period first.
        """
        older = filing("2024-09-30", "2024-11-14", info_table(("A", 1)))
        out = consolidate_period([ORIGINAL, older])
        self.assertEqual([f["reference_date"] for f in out], ["2024-12-31", "2024-09-30"])


if __name__ == "__main__":
    unittest.main()
