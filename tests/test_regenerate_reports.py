import unittest

from scripts.regenerate_reports import build_comparison_pairs, dedupe_filings_by_period


def _filing(reference_date, label=""):
    """
    Builds a minimal filing dict as produced by the scraper.
    """
    return {"reference_date": reference_date, "label": label, "xml_content": b"<mock/>"}


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


if __name__ == "__main__":
    unittest.main()
