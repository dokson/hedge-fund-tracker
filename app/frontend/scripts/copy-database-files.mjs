/**
 * Pure data module: the canonical list of CSV files that the GH Pages static
 * build copies from /database/ into /dist/database/. Imported by both
 * copy-database.mjs (the actual script) and copy-database.test.ts (regression
 * guard that asserts the list stays in sync with dataService.ts fetches).
 *
 * Kept side-effect free so the test can import it without running the build.
 */
export const staticFiles = [
  "hedge_funds.csv",
  "excluded_hedge_funds.csv",
  "stocks.csv",
  "non_quarterly.csv",
  "models.csv",
  "sector_hierarchy.csv",
];
