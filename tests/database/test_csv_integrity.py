"""
Recursive CSV integrity check for every .csv file under database/.

A row is considered malformed when:
  * its column count does not match the header
  * any cell still contains a stray double-quote character (proper CSV
    escaping would have doubled it inside a quoted value, so a surviving
    `"` after csv.reader processing signals a broken row)
"""

import csv
import unittest
from pathlib import Path

from app.database import DB_FOLDER


class TestCsvIntegrity(unittest.TestCase):
    def test_all_database_csv_files_are_well_formed(self):
        """
        Every CSV under database/ must parse cleanly: each data row's column
        count matches the header and no cell carries a surviving '"' that
        indicates broken escaping.
        """
        db_root = Path(DB_FOLDER)
        csv_paths = sorted(db_root.rglob("*.csv"))
        self.assertGreater(len(csv_paths), 0, "No CSV files found under database/")

        issues: list[str] = []
        for path in csv_paths:
            relative = path.relative_to(db_root)
            try:
                with path.open(encoding="utf-8", newline="") as f:
                    reader = csv.reader(f)
                    try:
                        header = next(reader)
                    except StopIteration:
                        issues.append(f"  {relative} → empty file (no header)")
                        continue
                    expected_cols = len(header)

                    for line_no, row in enumerate(reader, start=2):
                        if len(row) != expected_cols:
                            issues.append(
                                f"  {relative}:{line_no} → {len(row)} columns "
                                f"(expected {expected_cols}): {row[:5]}"
                            )
                            continue
                        for col_idx, cell in enumerate(row):
                            if '"' in cell:
                                issues.append(
                                    f"  {relative}:{line_no} col {header[col_idx]!r} → "
                                    f"stray quote in value: {cell[:60]!r}"
                                )
                                break
            except UnicodeDecodeError as exc:
                issues.append(f"  {relative} → UTF-8 decode error: {exc}")

        if issues:
            self.fail(
                f"Found {len(issues)} malformed rows across "
                f"{len(csv_paths)} CSV files under database/:\n\n"
                + "\n".join(issues[:50])
                + ("\n  …" if len(issues) > 50 else "")
            )


if __name__ == "__main__":
    unittest.main()
