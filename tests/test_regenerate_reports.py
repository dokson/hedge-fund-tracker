import unittest

from scripts.regenerate_reports import (
    build_comparison_pairs,
    collect_filings_until_floor,
    dedupe_filings_by_period,
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
