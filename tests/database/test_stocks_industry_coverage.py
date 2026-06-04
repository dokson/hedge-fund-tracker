"""
Ensures every row in database/stocks.csv carries a non-empty Industry value.

The Industry column is the single source of truth that feeds the Sector pill
(joined via sector_hierarchy.csv) and the industry filter on /stocks. A row
without an Industry would render as "—" everywhere and break the sector
heatmap.
"""

import csv
import unittest
from pathlib import Path

from app.database import DB_FOLDER


class TestStocksIndustryCoverage(unittest.TestCase):
    def test_every_stock_row_has_a_non_empty_industry(self):
        """
        Every data row in stocks.csv must have a non-empty `Industry` column.
        """
        path = Path(DB_FOLDER) / "stocks.csv"
        self.assertTrue(path.exists(), f"stocks.csv not found at {path}")

        missing: list[str] = []
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            self.assertIn(
                "Industry",
                reader.fieldnames or [],
                "stocks.csv must declare an 'Industry' column",
            )
            for line_no, row in enumerate(reader, start=2):
                industry = (row.get("Industry") or "").strip()
                if not industry:
                    ticker = row.get("Ticker", "?")
                    cusip = row.get("CUSIP", "?")
                    missing.append(f"  line {line_no}: CUSIP={cusip} Ticker={ticker}")

        if missing:
            self.fail(
                f"{len(missing)} stocks.csv row(s) have no Industry value. "
                "Run the industry backfill (yfinance → stocks.csv same-Company "
                "match → Groq LLM fallback) before committing:\n\n"
                + "\n".join(missing[:50])
                + ("\n  …" if len(missing) > 50 else "")
            )


if __name__ == "__main__":
    unittest.main()
