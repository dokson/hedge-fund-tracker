"""
Ranks excluded hedge fund managers by Wikipedia pageviews over the last 12 months.

By default runs in dry-run mode and prints the ranking. Pass --apply to rewrite
database/excluded_hedge_funds.csv so the top N managers (by pageviews) appear
first, followed by all remaining rows sorted alphabetically by Fund name.

For each row, resolves the manager name to a Wikipedia article via the
MediaWiki search API, filtering to pages whose extract mentions finance-related
keywords (investor, hedge fund, financier, businessman, asset manager, etc.).
Rows with multiple managers ("A & B") sum the views of all resolved managers.

Usage (dry-run):
    pipenv run python -X utf8 scripts/rank_excluded_funds_by_popularity.py

Apply changes to the CSV:
    pipenv run python -X utf8 scripts/rank_excluded_funds_by_popularity.py --apply

Options:
    --top N          Override how many rows pin to the top (default: README_DISPLAY_LIMIT).
    --workers K      Parallel HTTP workers (default: 8).
"""

import argparse
import csv
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from urllib.parse import quote

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import DB_FOLDER, EXCLUDED_HEDGE_FUNDS_FILE  # noqa: E402
from app.utils.readme import README_DISPLAY_LIMIT  # noqa: E402

CACHE_DIR = ROOT / "__wikicache__"
CACHE_DIR.mkdir(exist_ok=True)
RESOLVE_CACHE_FILE = CACHE_DIR / "wiki_resolve.json"
PAGEVIEWS_CACHE_FILE = CACHE_DIR / "wiki_pageviews.json"
_cache_lock = threading.Lock()


def _load_cache(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cache(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


_RESOLVE_CACHE: dict = _load_cache(RESOLVE_CACHE_FILE)
_PAGEVIEWS_CACHE: dict = _load_cache(PAGEVIEWS_CACHE_FILE)

WIKI_API = "https://en.wikipedia.org/w/api.php"
PAGEVIEWS_API = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
    "/en.wikipedia.org/all-access/user/{title}/monthly/{start}/{end}"
)
USER_AGENT = "hedge-fund-tracker/1.0 (https://github.com/alecolace/hedge-fund-tracker)"

FINANCE_TERMS = (
    "investor",
    "hedge fund",
    "financier",
    "businessman",
    "asset manager",
    "investment",
    "portfolio manager",
    "fund manager",
    "billionaire",
    "venture capital",
    "private equity",
    "chief executive",
    "ceo",
    "founder",
    "trader",
    "wall street",
)

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})


class TransientHTTPError(Exception):
    """
    Raised on HTTP responses that should be retried (5xx, 429, network errors).
    """


@retry(
    retry=retry_if_exception_type((TransientHTTPError, requests.RequestException)),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(5),
    reraise=True,
)
def _http_get_json(url: str, params: dict | None = None) -> dict | None:
    """
    GETs JSON with retries on transient failures. Returns None on 404
    (non-existent article) so callers can distinguish "no data" from "throttled".
    """
    r = session.get(url, params=params, timeout=20)
    if r.status_code == 404:
        return None
    if r.status_code >= 500 or r.status_code == 429:
        raise TransientHTTPError(f"{r.status_code} on {r.url}")
    r.raise_for_status()
    return r.json()


def split_managers(raw: str) -> list[str]:
    """
    Splits a manager cell like "Paul Marshall & Ian Wace" into individual names.
    """
    parts = re.split(r"\s*(?:&|,| and )\s*", raw)
    return [p.strip() for p in parts if p.strip()]


NICKNAME_VARIANTS: dict[str, tuple[str, ...]] = {
    "bill": ("bill", "william"),
    "william": ("bill", "william", "will"),
    "bob": ("bob", "robert", "rob"),
    "rob": ("rob", "robert", "bob"),
    "robert": ("robert", "rob", "bob"),
    "steve": ("steve", "steven", "stephen"),
    "steven": ("steve", "steven", "stephen"),
    "stephen": ("steve", "steven", "stephen"),
    "mike": ("mike", "michael"),
    "michael": ("mike", "michael"),
    "chris": ("chris", "christopher"),
    "christopher": ("chris", "christopher"),
    "ken": ("ken", "kenneth"),
    "kenneth": ("ken", "kenneth"),
    "ron": ("ron", "ronald"),
    "ronald": ("ron", "ronald"),
    "tim": ("tim", "timothy"),
    "timothy": ("tim", "timothy"),
    "dan": ("dan", "daniel"),
    "daniel": ("dan", "daniel"),
    "dave": ("dave", "david"),
    "david": ("dave", "david"),
    "jim": ("jim", "james"),
    "james": ("jim", "james"),
    "jeff": ("jeff", "jeffrey"),
    "jeffrey": ("jeff", "jeffrey"),
    "tom": ("tom", "thomas"),
    "thomas": ("tom", "thomas"),
    "rich": ("rich", "richard", "rick"),
    "richard": ("rich", "richard", "rick"),
    "joe": ("joe", "joseph"),
    "joseph": ("joe", "joseph"),
    "greg": ("greg", "gregory"),
    "gregory": ("greg", "gregory"),
    "alec": ("alec", "alexander", "alex"),
    "alex": ("alec", "alexander", "alex"),
    "alexander": ("alec", "alexander", "alex"),
    "fred": ("fred", "frederick", "alfred"),
    "matt": ("matt", "matthew"),
    "matthew": ("matt", "matthew"),
    "andy": ("andy", "andrew"),
    "andrew": ("andy", "andrew"),
    "nick": ("nick", "nicholas"),
    "nicholas": ("nick", "nicholas"),
    "tony": ("tony", "anthony"),
    "anthony": ("tony", "anthony"),
}


def _name_tokens(name: str) -> list[str]:
    """
    Returns lowercased name tokens with length >= 2, e.g. ['ben', 'horowitz'].
    """
    return [t.lower() for t in re.split(r"[\s.]+", name) if len(t) >= 2]


def _title_matches_name(title: str, name: str) -> bool:
    """
    The article title must contain the manager's surname (last name token) and,
    if the name has >= 2 tokens, a nickname-aware variant of the first token.
    """
    tokens = _name_tokens(name)
    if not tokens:
        return False
    title_low = title.lower()
    if tokens[-1] not in title_low:
        return False
    if len(tokens) >= 2:
        variants = NICKNAME_VARIANTS.get(tokens[0], (tokens[0],))
        if not any(v in title_low for v in variants):
            return False
    return True


_SUFFIX_RE = re.compile(r"\b(sr|jr|ii|iii|iv)\b\.?", re.IGNORECASE)


def _cache_get(cache: dict, key: str) -> tuple[bool, object]:
    """
    Returns (present, value). `present=False` means the key has never been resolved.
    """
    with _cache_lock:
        if key in cache:
            return True, cache[key]
    return False, None


def _cache_set(cache: dict, path: Path, key: str, value: object) -> None:
    with _cache_lock:
        cache[key] = value
        _save_cache(path, cache)


def resolve_wikipedia_title(name: str) -> str | None:
    """
    Returns the canonical Wikipedia title for a manager, or None if no
    finance-related article matching the manager's name is found.
    Cached on disk; cached "no match" results are reused on subsequent runs.
    """
    cache_key = f"manager::{name}"
    present, cached = _cache_get(_RESOLVE_CACHE, cache_key)
    if present:
        return cached  # type: ignore[return-value]

    try:
        data = _http_get_json(
            WIKI_API,
            params={
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": name,
                "srlimit": 8,
            },
        )
        hits = (data or {}).get("query", {}).get("search", [])
    except Exception:
        return None  # transient failure: don't poison the cache

    resolved: str | None = None
    candidates: list[tuple[int, int, int, str]] = []
    for idx, hit in enumerate(hits):
        title = hit["title"]
        if not _title_matches_name(title, name):
            continue
        snippet = re.sub(r"<[^>]+>", "", hit.get("snippet", "")).lower()
        finance_hits = sum(1 for term in FINANCE_TERMS if term in snippet)
        if finance_hits == 0:
            continue
        has_suffix = 1 if _SUFFIX_RE.search(title.lower()) else 0
        candidates.append((-finance_hits, has_suffix, idx, title))
    if candidates:
        candidates.sort()
        resolved = candidates[0][3]
    else:
        for hit in hits:
            title = hit["title"]
            if not _title_matches_name(title, name):
                continue
            try:
                data = _http_get_json(
                    f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
                )
            except Exception:
                continue
            if not data:
                continue
            extract = (data.get("extract") or "").lower()
            if any(term in extract for term in FINANCE_TERMS):
                resolved = title
                break

    _cache_set(_RESOLVE_CACHE, RESOLVE_CACHE_FILE, cache_key, resolved)
    return resolved


def resolve_fund_title(fund_name: str, denomination: str) -> str | None:
    """
    Falls back to resolving the firm's Wikipedia page (e.g. "State Street
    Corporation", "Janus Henderson") when the manager has no usable page.
    The matched title must share a distinctive token with the fund or
    denomination, to avoid latching onto unrelated firms surfaced by search.
    """
    stoplist = {
        "capital",
        "fund",
        "funds",
        "group",
        "investment",
        "investments",
        "management",
        "partners",
        "advisors",
        "asset",
        "trust",
        "company",
        "holdings",
        "corp",
        "corporation",
        "llc",
        "inc",
        "ltd",
        "limited",
        "global",
        "financial",
        "associates",
        "lp",
        "company.",
    }
    all_fund_tokens = {
        t.lower() for t in re.split(r"[\s.,&]+", f"{fund_name} {denomination}") if len(t) >= 4
    }
    fund_tokens = {t for t in all_fund_tokens if t not in stoplist}
    if not fund_tokens:
        return None
    token_patterns = [re.compile(rf"\b{re.escape(t)}\b") for t in fund_tokens]
    cache_key = f"firm::{fund_name}::{denomination}"
    present, cached = _cache_get(_RESOLVE_CACHE, cache_key)
    if present:
        return cached  # type: ignore[return-value]

    resolved: str | None = None
    for candidate in (fund_name, denomination):
        if not candidate or resolved:
            continue
        try:
            data = _http_get_json(
                WIKI_API,
                params={
                    "action": "query",
                    "format": "json",
                    "list": "search",
                    "srsearch": candidate,
                    "srlimit": 5,
                },
            )
            hits = (data or {}).get("query", {}).get("search", [])
        except Exception:
            return None  # transient: skip caching
        for hit in hits:
            title = hit["title"]
            title_low = title.lower()
            if title_low.startswith("list of") or "(disambiguation)" in title_low:
                continue
            if not any(p.search(title_low) for p in token_patterns):
                continue
            # Reject titles that introduce tokens absent from the firm name —
            # e.g. "Berkshire Hathaway" or "Berkshire Partners" must not match
            # "Berkshire Capital Holdings Inc" just because they share "berkshire".
            # Compare against the full token set (stoplist words included) so
            # that "partners" / "hathaway" are detected as foreign.
            title_tokens = {t.lower() for t in re.split(r"[\s.,&]+", title) if len(t) >= 4}
            if title_tokens - all_fund_tokens:
                continue
            snippet = re.sub(r"<[^>]+>", "", hit.get("snippet", "")).lower()
            if any(term in snippet for term in FINANCE_TERMS):
                resolved = title
                break
    _cache_set(_RESOLVE_CACHE, RESOLVE_CACHE_FILE, cache_key, resolved)
    return resolved


def fetch_pageviews(title: str, start: str, end: str) -> int:
    """
    Returns total monthly pageviews for a Wikipedia article between start and end.
    Dates must be in YYYYMMDD format. Results are cached per (title, start, end).
    """
    cache_key = f"{title}::{start}::{end}"
    present, cached = _cache_get(_PAGEVIEWS_CACHE, cache_key)
    if present:
        return cast(int, cached)

    url = PAGEVIEWS_API.format(title=quote(title, safe=""), start=start, end=end)
    try:
        data = _http_get_json(url)
    except Exception:
        return 0  # transient: do not cache so a later run can retry
    if data is None:
        _cache_set(_PAGEVIEWS_CACHE, PAGEVIEWS_CACHE_FILE, cache_key, 0)
        return 0
    views = sum(int(item.get("views", 0)) for item in data.get("items", []))
    _cache_set(_PAGEVIEWS_CACHE, PAGEVIEWS_CACHE_FILE, cache_key, views)
    return views


def score_row(row: dict, start: str, end: str) -> tuple[int, list[str]]:
    """
    Resolves and scores a single row. Returns (total_views, [titles_used]).
    If no manager has a usable Wikipedia page, falls back to the firm/fund page.
    """
    managers = split_managers(row.get("Manager", ""))
    total = 0
    titles: list[str] = []
    for m in managers:
        title = resolve_wikipedia_title(m)
        if not title:
            continue
        views = fetch_pageviews(title, start, end)
        total += views
        titles.append(f"{title}={views}")
        time.sleep(0.05)
    if not titles:
        firm_title = resolve_fund_title(row.get("Fund", ""), row.get("Denomination", ""))
        if firm_title:
            views = fetch_pageviews(firm_title, start, end)
            total += views
            titles.append(f"[firm]{firm_title}={views}")
    return total, titles


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true", help="Rewrite the CSV with the new order")
    p.add_argument("--top", type=int, default=README_DISPLAY_LIMIT)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument(
        "--no-cache", action="store_true", help="Ignore on-disk cache and refetch everything"
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.no_cache:
        _RESOLVE_CACHE.clear()
        _PAGEVIEWS_CACHE.clear()
    csv_path = ROOT / DB_FOLDER.lstrip("./") / EXCLUDED_HEDGE_FUNDS_FILE

    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    end_dt = datetime.now(UTC).replace(day=1) - timedelta(days=1)
    start_dt = (end_dt.replace(day=1) - timedelta(days=365)).replace(day=1)
    start = start_dt.strftime("%Y%m%d")
    end = end_dt.strftime("%Y%m%d")
    print(f"Pageviews window: {start} -> {end}")
    print(f"Resolving {len(rows)} managers (workers={args.workers})...")

    results: list[tuple[int, list[str], dict]] = [(0, [], r) for r in rows]
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, (views, titles) in enumerate(ex.map(lambda r: score_row(r, start, end), rows)):
            results[i] = (views, titles, rows[i])
            if (i + 1) % 25 == 0:
                print(f"  ...{i + 1}/{len(rows)}")

    results.sort(key=lambda x: x[0], reverse=True)

    print()
    print(f"{'#':>3}  {'Views':>10}  {'Fund':<40}  {'Manager':<35}  Wiki")
    print("-" * 130)
    for i, (views, titles, row) in enumerate(results[: args.top], start=1):
        wiki = ", ".join(titles) if titles else "—"
        print(f"{i:>3}  {views:>10}  {row['Fund'][:40]:<40}  {row['Manager'][:35]:<35}  {wiki}")

    no_match = [r for v, _t, r in results if v == 0]
    print(f"\n{len(no_match)} managers without a finance-related Wikipedia match.")

    if args.apply:
        top_rows = [r for _, _, r in results[: args.top]]
        tail_rows = sorted(
            (r for _, _, r in results[args.top :]),
            key=lambda r: r.get("Fund", "").lower(),
        )
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(top_rows + tail_rows)
        print(f"\nApplied: rewrote {csv_path} with new top {args.top}.")

        from app.utils.readme import update_readme

        update_readme()
        print("README excluded-funds section regenerated.")
    else:
        print("\nDry-run: pass --apply to rewrite the CSV.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
