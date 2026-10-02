import tempfile
import unittest
from pathlib import Path

from app.utils.run_summary import FetchRunSummary, render_markdown, write_step_summary


class TestRenderMarkdown(unittest.TestCase):
    def test_counts_table_lists_every_metric(self):
        """
        The table carries funds, 13F comparisons, rows saved, failures and alerts.
        """
        summary = FetchRunSummary(
            funds=120,
            reports_saved=37,
            nq_rows_saved=12,
            nq_failed_funds=("Fund B", "Fund A"),
            alerts=("Ticker not found for CUSIP 'X'",),
        )

        markdown = render_markdown(summary)

        self.assertIn("| Funds processed | 120 |", markdown)
        self.assertIn("| 13F comparisons written | 37 |", markdown)
        self.assertIn("| Non-quarterly filing rows saved | 12 |", markdown)
        self.assertIn("| Non-quarterly fetches failed (existing rows kept) | 2 |", markdown)
        self.assertIn("| Unidentified filers / unresolved identifiers | 1 |", markdown)

    def test_failed_funds_are_listed_sorted(self):
        """
        The funds whose rows were carried over are listed by name, sorted.
        """
        summary = FetchRunSummary(
            funds=2, reports_saved=0, nq_rows_saved=0, nq_failed_funds=("Fund B", "Fund A")
        )

        markdown = render_markdown(summary)

        self.assertLess(markdown.index("- Fund A"), markdown.index("- Fund B"))

    def test_clean_run_has_no_detail_sections(self):
        """
        Without failures or alerts only the table is rendered.
        """
        markdown = render_markdown(FetchRunSummary(funds=3, reports_saved=3, nq_rows_saved=0))

        self.assertNotIn("###", markdown)
        self.assertNotIn("not saved", markdown)

    def test_unsaved_non_quarterly_file_is_flagged(self):
        """
        A run that left non_quarterly.csv untouched says so explicitly.
        """
        summary = FetchRunSummary(funds=3, reports_saved=3, nq_rows_saved=0, nq_saved=False)

        self.assertIn("not saved", render_markdown(summary))

    def test_alerts_are_deduplicated_in_order(self):
        """
        The same alert raised twice in a run is listed once, first occurrence first.
        """
        summary = FetchRunSummary(funds=1, reports_saved=0, nq_rows_saved=0, alerts=("b", "a", "b"))

        markdown = render_markdown(summary)

        self.assertEqual(markdown.count("- b"), 1)
        self.assertLess(markdown.index("- b"), markdown.index("- a"))
        self.assertIn("| Unidentified filers / unresolved identifiers | 2 |", markdown)

    def test_external_strings_cannot_break_the_markdown(self):
        """
        Pipes, markup and newlines in a fund name are escaped or stripped.
        """
        summary = FetchRunSummary(
            funds=1,
            reports_saved=0,
            nq_rows_saved=0,
            nq_failed_funds=("A|B <img>\n## Fake",),
        )

        markdown = render_markdown(summary)

        self.assertIn(r"- A\|B \<img\>\#\# Fake", markdown)
        self.assertNotIn("\n## Fake", markdown)


class TestWriteStepSummary(unittest.TestCase):
    def test_noop_outside_github_actions(self):
        """
        Without GITHUB_STEP_SUMMARY nothing is written and False is returned.
        """
        self.assertFalse(write_step_summary("x", env={}))

    def test_appends_to_the_step_summary_file(self):
        """
        The markdown is appended (the runner may already hold earlier content) with LF endings.
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.md"
            path.write_bytes(b"earlier\n")

            written = write_step_summary("## Run\nline", env={"GITHUB_STEP_SUMMARY": str(path)})

            self.assertTrue(written)
            self.assertEqual(path.read_bytes(), b"earlier\n## Run\nline\n")

    def test_unwritable_summary_does_not_raise(self):
        """
        A bad summary path must never fail the fetch run itself.
        """
        missing = str(Path(tempfile.gettempdir()) / "no-such-dir-hft" / "summary.md")

        with self.assertLogs("app.utils.run_summary", level="WARNING"):
            self.assertFalse(write_step_summary("x", env={"GITHUB_STEP_SUMMARY": missing}))


if __name__ == "__main__":
    unittest.main()
