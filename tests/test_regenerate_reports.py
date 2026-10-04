import unittest
from unittest.mock import patch

from scripts.regenerate_reports import (
    build_comparison_pairs,
    collect_filings_until_floor,
    dedupe_filings_by_period,
    regenerate_fund,
)


def _filing(reference_date: str, label: str = "", published: str | None = None) -> dict:
    """
    Builds a minimal filing dict as produced by the scraper.
    """
    return {
        "reference_date": reference_date,
        "date": published or reference_date,
        "label": label,
        "xml_content": b"<mock/>",
    }


class TestCollectFilingsUntilFloor(unittest.TestCase):
    def test_late_published_old_periods_do_not_stop_the_walk(self):
        """
        A fund can publish filings for old periods late (in a batch), placing
        them between recent quarters in EDGAR's publication-ordered list. The
        walk must continue past them: only a publication date older than the
        floor proves no further useful filing exists.
        """
        listing = iter(
            [
                _filing("2025-06-30", "q2", published="2025-07-29"),
                _filing("2024-09-30", "old", published="2025-05-12"),
                _filing("2024-06-30", "old", published="2025-05-12"),
                _filing("2024-03-31", "old", published="2025-05-12"),
                _filing("2025-03-31", "q1", published="2025-05-09"),
                _filing("2024-12-31", "q4", published="2025-02-12"),
            ]
        )

        collected = collect_filings_until_floor(listing)

        labels = [f["label"] for f in collected]
        self.assertIn("q1", labels)
        self.assertIn("q4", labels)

    def test_walk_stops_after_publication_before_floor(self):
        """
        Once a filing was published before the floor, no later-listed filing
        can refer to a tracked period: the walk stops without consuming more.
        """
        consumed: list[str] = []

        def listing():
            for filing in [
                _filing("2025-03-31", "q1", published="2025-05-09"),
                _filing("2024-09-30", "pre-floor", published="2024-11-12"),
                _filing("2024-06-30", "beyond", published="2024-08-12"),
            ]:
                consumed.append(filing["label"])
                yield filing

        collect_filings_until_floor(listing())

        self.assertNotIn("beyond", consumed)


class TestDedupeFilingsByPeriod(unittest.TestCase):
    def test_amendment_wins_over_original(self):
        """
        EDGAR lists filings newest-filed first: with two filings for the same
        period, the first occurrence (the amendment) must be kept.
        """
        filings = [
            _filing("2026-03-31", "amendment"),
            _filing("2026-03-31", "original"),
            _filing("2025-12-31", "q4"),
        ]

        deduped = dedupe_filings_by_period(filings)

        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["label"], "amendment")

    def test_a_partial_new_holdings_amendment_completes_the_original(self):
        """
        A NEW HOLDINGS amendment adds its rows to the period's report instead of replacing it.
        """
        table = '<ns1:informationTable xmlns:ns1="x">{}</ns1:informationTable>'
        row = "<ns1:infoTable><ns1:cusip>{}</ns1:cusip><ns1:value>{}</ns1:value></ns1:infoTable>"
        original = _filing("2024-12-31", "original")
        original["xml_content"] = table.format(row.format("A", 500)).encode()
        added = _filing("2024-12-31", "added", published="2025-04-09")
        added["xml_content"] = table.format(row.format("B", 20)).encode()
        added["amendment_type"] = "NEW HOLDINGS"

        (kept,) = dedupe_filings_by_period([added, original])

        self.assertIn(b"<ns1:cusip>A</ns1:cusip>", kept["xml_content"])
        self.assertIn(b"<ns1:cusip>B</ns1:cusip>", kept["xml_content"])

    def test_sorted_by_reference_date_descending(self):
        """
        Output is ordered newest reporting period first regardless of the
        publication order in the input.
        """
        filings = [
            _filing("2025-12-31"),
            _filing("2026-03-31"),
            _filing("2025-09-30"),
        ]

        deduped = dedupe_filings_by_period(filings)

        self.assertEqual(
            [f["reference_date"] for f in deduped],
            ["2026-03-31", "2025-12-31", "2025-09-30"],
        )


class TestBuildComparisonPairs(unittest.TestCase):
    def test_consecutive_quarters_paired(self):
        """
        Each regenerated quarter is compared against the immediately
        preceding one when available.
        """
        filings = dedupe_filings_by_period(
            [_filing("2026-03-31"), _filing("2025-12-31"), _filing("2025-09-30")]
        )

        pairs = build_comparison_pairs(filings, "2025-09-30")

        self.assertEqual(len(pairs), 3)
        self.assertEqual(pairs[0][0]["reference_date"], "2026-03-31")
        self.assertEqual(pairs[0][1]["reference_date"], "2025-12-31")
        self.assertEqual(pairs[1][1]["reference_date"], "2025-09-30")
        self.assertIsNone(pairs[2][1])

    def test_gap_falls_back_to_two_quarters_back(self):
        """
        When a fund skipped a quarter, the comparison falls back to the
        filing from two quarters earlier, mirroring the updater.
        """
        filings = dedupe_filings_by_period([_filing("2026-03-31"), _filing("2025-09-30")])

        pairs = build_comparison_pairs(filings, "2026-03-31")

        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0][1]["reference_date"], "2025-09-30")

    def test_older_filings_used_as_previous_but_not_regenerated(self):
        """
        Filings older than the floor are not regenerated themselves but still
        serve as the previous side of newer comparisons.
        """
        filings = dedupe_filings_by_period([_filing("2025-03-31"), _filing("2024-12-31")])

        pairs = build_comparison_pairs(filings, "2025-03-31")

        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0][0]["reference_date"], "2025-03-31")
        self.assertEqual(pairs[0][1]["reference_date"], "2024-12-31")


class TestRegenerateFundAppliesFilingCorrections(unittest.TestCase):
    @patch("scripts.regenerate_reports.save_comparison")
    @patch("scripts.regenerate_reports.generate_comparison")
    @patch("scripts.regenerate_reports.xml_to_dataframe_13f")
    @patch("scripts.regenerate_reports.load_split_factors", return_value={})
    @patch("scripts.regenerate_reports.corrections_for")
    @patch("scripts.regenerate_reports.fetch_fund_filings")
    def test_each_filing_is_parsed_with_its_own_corrections(
        self, mock_fetch, mock_corrections, _mock_registry, mock_xml, _mock_cmp, _mock_save
    ):
        """
        Both the current and the previous filing get the corrections of their quarter.
        """
        mock_fetch.return_value = [_filing("2026-03-31"), _filing("2025-12-31")]
        mock_corrections.side_effect = lambda fund, quarter: {("X", fund): quarter}

        regenerate_fund({"CIK": "0000000001", "Fund": "Tester"})

        passed = [call.kwargs.get("corrections") for call in mock_xml.call_args_list]
        self.assertIn({("X", "Tester"): "2026Q1"}, passed)
        self.assertIn({("X", "Tester"): "2025Q4"}, passed)


class TestRegenerateFundAppliesSplits(unittest.TestCase):
    @patch("scripts.regenerate_reports.save_comparison")
    @patch("scripts.regenerate_reports.generate_comparison")
    @patch("scripts.regenerate_reports.xml_to_dataframe_13f")
    @patch("scripts.regenerate_reports.load_split_factors")
    @patch("scripts.regenerate_reports.fetch_fund_filings")
    def test_each_quarter_gets_its_own_split_factors(
        self, mock_fetch, mock_registry, mock_xml, mock_comparison, _mock_save
    ):
        mock_fetch.return_value = [
            _filing("2026-06-30"),
            _filing("2026-03-31"),
            _filing("2025-12-31"),
        ]
        mock_registry.return_value = {
            "2026Q2": {"146869102": 5.0},
            "2025Q4": {"64110L106": 10.0},
        }

        regenerate_fund({"CIK": "0000000001", "Fund": "Tester"})

        applied = [call.args[2] for call in mock_comparison.call_args_list]
        self.assertIn({"146869102": 5.0}, applied)
        # 2026Q1 has no split on record and must be compared untouched.
        self.assertIn({}, applied)

    @patch("scripts.regenerate_reports.save_comparison")
    @patch("scripts.regenerate_reports.generate_comparison")
    @patch("scripts.regenerate_reports.xml_to_dataframe_13f")
    @patch("scripts.regenerate_reports.load_split_factors")
    @patch("scripts.regenerate_reports.fetch_fund_filings")
    def test_a_skipped_quarter_compounds_the_splits_it_spans(
        self, mock_fetch, mock_registry, mock_xml, mock_comparison, _mock_save
    ):
        # No 2026Q1 filing, so 2026Q2 is compared against 2025Q4 and both
        # quarters' splits sit between the two filings.
        mock_fetch.return_value = [_filing("2026-06-30"), _filing("2025-12-31")]
        mock_registry.return_value = {
            "2026Q1": {"64110L106": 2.0},
            "2026Q2": {"64110L106": 3.0},
        }

        regenerate_fund({"CIK": "0000000001", "Fund": "Tester"})

        applied = [call.args[2] for call in mock_comparison.call_args_list]
        self.assertIn({"64110L106": 6.0}, applied)


if __name__ == "__main__":
    unittest.main()
