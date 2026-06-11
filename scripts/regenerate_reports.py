"""
Regenerates the per-fund quarterly comparison reports from EDGAR.

Unlike the incremental updater (which fetches the latest two filings), this
script walks each fund's 13F history once, deduplicates amendments per
reporting period (latest filed wins), rebuilds every comparison from
MIN_REFERENCE_DATE onwards and saves it over the existing CSV. Each filing is
downloaded exactly once per fund.

Run for all funds, or pass fund names for a partial run:
    pipenv run python -X utf8 scripts/regenerate_reports.py
    pipenv run python -X utf8 scripts/regenerate_reports.py Arena WT
"""

import sys
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup  # noqa: E402

from app.analysis.quarterly_report import generate_comparison  # noqa: E402
from app.database import (  # noqa: E402
    MIN_REFERENCE_DATE,
    clean_stocks,
    load_hedge_funds,
    save_comparison,
    sort_stocks,
)
from app.scraper.sec_scraper import (  # noqa: E402
    _create_search_url,
    _get_request,
    _scrape_filing,
    scraper_session,
)
from app.scraper.xml_processor import xml_to_dataframe_13f  # noqa: E402
from app.utils.strings import get_previous_quarter_end_date  # noqa: E402

# One quarter before MIN_REFERENCE_DATE: needed as the previous side of the
# oldest regenerated comparison.
FETCH_FLOOR = get_previous_quarter_end_date(MIN_REFERENCE_DATE)


def dedupe_filings_by_period(filings: list[dict]) -> list[dict]:
    """
    Keeps one filing per reporting period and orders them newest period first.

    EDGAR lists filings by publication date descending, so the first
    occurrence of a reference date is the most recently filed version — the
    amendment when one exists.
    """
    seen: dict[str, dict] = {}
    for filing in filings:
        ref = filing.get("reference_date")
        if ref and ref not in seen:
            seen[ref] = filing
    return sorted(seen.values(), key=lambda f: f["reference_date"], reverse=True)


def build_comparison_pairs(filings: list[dict], min_reference_date: str) -> list[tuple]:
    """
    Pairs each filing at or after the floor with its comparison baseline.

    The baseline is the immediately preceding quarter's filing, falling back
    to two quarters back when one is missing (mirroring the updater), or None.
    """
    by_ref = {f["reference_date"]: f for f in filings}
    pairs = []
    for filing in filings:
        ref = filing["reference_date"]
        if ref < min_reference_date:
            continue
        target = get_previous_quarter_end_date(ref)
        fallback = get_previous_quarter_end_date(target)
        pairs.append((filing, by_ref.get(target) or by_ref.get(fallback)))
    return pairs


def collect_filings_until_floor(filings: Iterable[dict | None]) -> list[dict]:
    """
    Consumes publication-ordered filings until one published before the floor.

    Stopping on the publication date (not the reporting period) is the only
    safe criterion: funds may publish filings for old periods late, placing
    them between recent quarters in the list, but a filing referring to a
    tracked period can never be published before the floor itself.
    """
    collected: list[dict] = []
    for filing in filings:
        if not filing or not filing.get("reference_date"):
            continue
        collected.append(filing)
        if filing.get("date", "") < FETCH_FLOOR:
            break
    return collected


def fetch_fund_filings(cik: str) -> list[dict]:
    """
    Scrapes a fund's 13F filings newest-published-first until the fetch floor.
    """
    response = _get_request(_create_search_url(cik, "13F-HR"))
    if not response:
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    def scrape_all() -> Iterator[dict | None]:
        """
        Yields each scraped filing from the fund's EDGAR listing, lazily.
        """
        for tag in soup.find_all("a", id="documentsbutton"):
            yield _scrape_filing(tag, "13F-HR")

    return collect_filings_until_floor(scrape_all())


def regenerate_fund(fund: dict) -> int:
    """
    Rebuilds and saves every comparison report for a single fund.

    Returns the number of quarters regenerated.
    """
    cik = str(fund.get("CIK") or "")
    fund_name = str(fund.get("Fund") or cik)

    filings = dedupe_filings_by_period(fetch_fund_filings(cik))
    pairs = build_comparison_pairs(filings, MIN_REFERENCE_DATE)

    # Oldest first: if multiple writes ever target the same quarter (e.g. a
    # future change weakening the dedupe), the newest version wins.
    regenerated = 0
    for current, previous in reversed(pairs):
        df_current = xml_to_dataframe_13f(current["xml_content"])
        df_previous = xml_to_dataframe_13f(previous["xml_content"]) if previous else None
        comparison = generate_comparison(df_current, df_previous)
        save_comparison(comparison, current["reference_date"], fund_name)
        regenerated += 1
    return regenerated


def main() -> None:
    """
    Regenerates reports for the selected funds (all when no names are given).
    """
    hedge_funds = load_hedge_funds()
    only = {name.lower() for name in sys.argv[1:]}
    if only:
        hedge_funds = [f for f in hedge_funds if (f.get("Fund") or "").lower() in only]
        missing = only - {(f.get("Fund") or "").lower() for f in hedge_funds}
        if missing:
            print(f"⚠️  Unknown fund name(s): {', '.join(sorted(missing))}")

    total = len(hedge_funds)
    print(f"Regenerating reports for {total} fund(s) from {MIN_REFERENCE_DATE} onwards...")

    failures = []
    with scraper_session(), ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(regenerate_fund, fund): fund for fund in hedge_funds}
        for i, future in enumerate(as_completed(futures)):
            fund = futures[future]
            try:
                count = future.result()
                print(f"--- {i + 1:3}/{total}: {fund['Fund']} ({count} quarter(s)) ---")
            except Exception as e:
                failures.append(fund["Fund"])
                print(f"❌ {i + 1:3}/{total}: {fund['Fund']} failed: {e}")

    clean_stocks()
    sort_stocks()

    if failures:
        print(f"❌ Completed with {len(failures)} failure(s): {', '.join(failures)}")
        sys.exit(1)
    print("✅ All funds regenerated.")


if __name__ == "__main__":
    main()
