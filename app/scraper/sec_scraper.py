import atexit
import os
import re
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from itertools import islice
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests
from curl_cffi.requests import exceptions as curl_exc
from tenacity import retry, retry_if_result, stop_after_attempt, wait_exponential, wait_random

from app.scraper.amendments import NEW_HOLDINGS, amendment_type, consolidate_period
from app.scraper.rate_limiter import RateLimiter
from app.utils.logger import get_logger, log_safe
from app.utils.metrics import SEC_REQUESTS

logger = get_logger(__name__)

# SEC EDGAR requires a custom User-Agent that identifies the application and provides a contact email.
# See: https://www.sec.gov/os/developer-support-policy
# Override the contact via SEC_USER_AGENT (e.g. when forking/deploying under a different contact).
USER_AGENT = os.environ.get("SEC_USER_AGENT", "Hedge Fund Tracker dok.son@msn.com")
SEC_HOST = "www.sec.gov"
SEC_URL = "https://" + SEC_HOST
# EDGAR's JSON API: the filing lists come from here, the filings themselves from SEC_URL.
DATA_SEC_URL = "https://data.sec.gov"


def _build_session() -> requests.Session:
    """
    Builds a Session pre-configured with the SEC-required headers.
    """
    session = requests.Session()
    # No fixed Host header: curl derives it from each URL, and requests go to two SEC hosts.
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"})
    return session


# Per-thread sessions + a process-wide rate limiter.
# - curl_cffi Sessions wrap a single libcurl handle and are NOT thread-safe, so each
#   worker thread owns its own (database.updater fans fetches across a ThreadPoolExecutor).
#   Each session reuses TCP+TLS for its thread; instances are tracked so close_session()
#   can release them all.
# - SEC EDGAR fair-access policy caps clients at ~10 req/s per User-Agent; the token bucket
#   bounds requests across all worker threads regardless of how many sessions exist.
# Lifecycle: sessions are created lazily on first use per thread, closed at interpreter exit
# via atexit. Use reset_session() in tests to drop them and rebuild the rate limiter, or
# scraper_session() for a scoped override.
_thread_local = threading.local()
_sessions: list[requests.Session] = []
_sessions_lock = threading.Lock()
_rate_limiter = RateLimiter(rate=9, capacity=9)


def _get_session() -> requests.Session:
    """
    Returns the calling thread's Session, creating it on first use.

    curl_cffi Sessions are not thread-safe, so each thread owns its own. New
    instances are registered so close_session() can release every thread's
    connections at shutdown.
    """
    session: requests.Session | None = getattr(_thread_local, "session", None)
    if session is None:
        session = _build_session()
        _thread_local.session = session
        with _sessions_lock:
            _sessions.append(session)
    return session


def close_session() -> None:
    """
    Closes every Session created across all threads, releasing pooled
    connections. Safe to call multiple times.
    """
    with _sessions_lock:
        sessions = list(_sessions)
        _sessions.clear()
    for session in sessions:
        try:
            session.close()
        except Exception:
            logger.debug("Error closing a SEC session", exc_info=True)
    # Drop the current thread's reference so the next call rebuilds it. Other
    # threads' references go stale but point at already-closed sessions.
    if hasattr(_thread_local, "session"):
        del _thread_local.session


def reset_session() -> None:
    """
    Closes all sessions and rebuilds the rate limiter. Intended for test isolation.
    """
    global _rate_limiter
    close_session()
    _rate_limiter = RateLimiter(rate=9, capacity=9)


@contextmanager
def scraper_session():
    """
    Context manager that ensures all sessions are closed on exit.

    Use around long-running batch jobs to guarantee connection cleanup:

        with scraper_session():
            fetch_latest_two_13f_filings(cik)
    """
    try:
        yield
    finally:
        close_session()


atexit.register(close_session)

# The EDGAR form names each filing type covers, and the position of its data document among
# the XML links of the filing's index page.
FILING_SPECS: dict[str, dict[str, Any]] = {
    "13F-HR": {
        "xml_link_index": 3,
        "forms": frozenset({"13F-HR", "13F-HR/A"}),
    },
    "SCHEDULE": {
        "xml_link_index": 1,
        "forms": frozenset({"SCHEDULE 13D", "SCHEDULE 13D/A", "SCHEDULE 13G", "SCHEDULE 13G/A"}),
    },
    "4": {
        "xml_link_index": 1,
        "forms": frozenset({"4", "4/A"}),
    },
}


class _PermanentHTTPError(Exception):
    """
    Non-retryable HTTP failure (4xx other than 429): retrying cannot succeed.
    """

    def __init__(self, status: int | None):
        """
        Keeps the HTTP status so callers can tell a missing page from a refused one.
        """
        super().__init__(f"HTTP {status}")
        self.status = status


class _FilingRequestError(Exception):
    """
    A filing's report page or XML document could not be downloaded.
    """


class _ListingError(Exception):
    """
    A page of a fund's filing list could not be downloaded or read from EDGAR.
    """


# The random term desynchronizes retries so requests 429'd together by SEC (a
# shared cloud IP fails in bursts) don't back off in lockstep and collide again.
_RETRY_ATTEMPTS = 5


@retry(
    retry=retry_if_result(lambda value: value is None),
    wait=wait_exponential(multiplier=1, min=2, max=8) + wait_random(0, 3),
    stop=stop_after_attempt(_RETRY_ATTEMPTS),
    retry_error_callback=lambda rs: None,
    before_sleep=lambda rs: logger.progress(
        "Retrying request for '%s' in %.0fs... (Attempt #%d)",
        log_safe(rs.args[0], max_len=200),
        rs.next_action.sleep,  # type: ignore[union-attr]
        rs.attempt_number,
    ),
)
def _attempt_request(url: str) -> requests.Response | None:
    """
    Single rate-limited GET attempt, retried by tenacity while it returns None.

    Transient failures (timeouts, connection resets, 5xx, 429) return None so
    tenacity retries them; exhaustion maps to None via retry_error_callback.
    Permanent HTTP errors raise _PermanentHTTPError to stop retrying at once;
    _get_request logs them, since a missing index page may still be recovered.
    """
    _rate_limiter.acquire()
    try:
        response = _get_session().get(url, timeout=15)
        response.raise_for_status()
        SEC_REQUESTS.labels(outcome="ok").inc()
        return response
    except (curl_exc.Timeout, curl_exc.ConnectionError) as exc:
        SEC_REQUESTS.labels(outcome="error").inc()
        logger.warning(
            "Transient network error for %s: %s",
            log_safe(url, max_len=200),
            log_safe(exc.__class__.__name__),
        )
        return None
    except curl_exc.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        SEC_REQUESTS.labels(outcome="rate_limited" if status == 429 else "error").inc()
        if status is not None and (status >= 500 or status == 429):
            logger.warning("Transient HTTP %s for %s", status, log_safe(url, max_len=200))
            return None
        raise _PermanentHTTPError(status) from exc
    except curl_exc.RequestException:
        SEC_REQUESTS.labels(outcome="error").inc()
        logger.error("Request failed for %s", log_safe(url, max_len=200), exc_info=True)
        return None


def _get_request(url: str, *, missing_ok: bool = False) -> requests.Response | None:
    """
    Sends a GET request to the specified URL via the shared Session.

    Rate-limited via a process-wide token bucket so parallel workers stay
    within SEC EDGAR's fair-access policy. Retries transient failures via
    tenacity and always returns None on error — callers never see an
    exception from this function.

    ``missing_ok`` reports a 404 as progress rather than an error, for a page
    the caller can still find under another name.
    """
    try:
        return _attempt_request(url)
    except _PermanentHTTPError as exc:
        if missing_ok and exc.status == 404:
            logger.progress("EDGAR has no %s", log_safe(url, max_len=200))
        else:
            logger.error("Request failed for %s", log_safe(url, max_len=200), exc_info=True)
        return None


def _get_accepted(report_page_soup):
    """
    Extracts the accepted time from the report page's soup.
    """
    try:
        filing_date_tag = report_page_soup.find("div", string=re.compile(r"Accepted"))
        if filing_date_tag:
            return filing_date_tag.find_next().text.strip()
    except Exception:
        logger.error("Error extracting filing accepted time", exc_info=True)
    return None


def _get_filing_date(report_page_soup):
    """
    Extracts the filing date from the report page's soup.
    """
    try:
        filing_date_tag = report_page_soup.find("div", string=re.compile(r"Filing Date"))
        if filing_date_tag:
            return filing_date_tag.find_next().text.strip()
    except Exception:
        logger.error("Error extracting filing date", exc_info=True)
    return None


def _get_report_date(report_page_soup):
    """
    Extracts the report date from the report page's soup.
    """
    try:
        report_date_tag = report_page_soup.find("div", string=re.compile(r"Period of Report"))
        if report_date_tag:
            return report_date_tag.find_next().text.strip()
    except Exception:
        logger.error("Error extracting report date", exc_info=True)
    return None


def _get_primary_xml_url(report_page_soup, filing_type, page_url=SEC_URL):
    """
    Finds the link to the primary XML data file from the report page's soup.
    Uses the configuration based on filing type; links resolve against ``page_url``.
    """
    try:
        config = FILING_SPECS.get(filing_type)
        if config is None:
            return None
        tags = report_page_soup.find_all("a", attrs={"href": re.compile("xml", re.IGNORECASE)})

        xml_link_index = int(config["xml_link_index"])
        if len(tags) > xml_link_index:
            return urljoin(page_url, tags[xml_link_index].get("href"))
    except Exception:
        logger.error("Error finding XML URL for filing type %s", filing_type, exc_info=True)
    return None


def _get_cover_page_url(report_page_soup: BeautifulSoup, page_url: str = SEC_URL) -> str | None:
    """
    The raw (not XSL-rendered) 13F cover page linked from the report page, if any.
    """
    for tag in report_page_soup.find_all(
        "a", attrs={"href": re.compile(r"primary_doc\.xml$", re.I)}
    ):
        href = tag.get("href")
        if isinstance(href, str) and "xsl" not in href.lower():
            return urljoin(page_url, href)
    return None


def _get_header_dates(headers_page: str) -> tuple[str | None, str | None, str | None]:
    """
    Filing date, period of report and accepted time from a filing's SGML header
    page, in the formats the index page shows them (YYYY-MM-DD, YYYY-MM-DD HH:MM:SS).
    """

    def field(pattern: str) -> str | None:
        """
        The first digits captured by ``pattern``, or None.
        """
        match = re.search(pattern, headers_page)
        return match.group(1) if match else None

    filed = field(r"FILED AS OF DATE:\s*(\d{8})")
    period = field(r"CONFORMED PERIOD OF REPORT:\s*(\d{8})")
    accepted = field(r"ACCEPTANCE-DATETIME(?:>|&gt;)(\d{14})")

    def iso(digits: str | None, source: str, target: str) -> str | None:
        """
        ``digits`` reformatted from ``source`` to ``target``, or None.
        """
        return datetime.strptime(digits, source).strftime(target) if digits else None

    return (
        iso(filed, "%Y%m%d", "%Y-%m-%d"),
        iso(period, "%Y%m%d", "%Y-%m-%d"),
        iso(accepted, "%Y%m%d%H%M%S", "%Y-%m-%d %H:%M:%S"),
    )


def _get_report_page(index_url: str) -> tuple[str, str] | None:
    """
    A filing's report page as (url, text), or None when it cannot be downloaded.

    EDGAR publishes the index of a filing as -index.htm and -index.html, and its
    CDN at times answers 404 for one or both while the -index-headers.html
    page (the SGML header, with the same document links) is served.
    """
    candidates = [index_url]
    if index_url.endswith("-index.htm"):
        stem = index_url.removesuffix(".htm")
        candidates += [stem + ".html", stem + "-headers.html"]
    for position, url in enumerate(candidates):
        response = _get_request(url, missing_ok=position < len(candidates) - 1)
        if response:
            return url, response.text
    return None


def _scrape_filing(entry, filing_type, *, raise_on_request_error=False):
    """
    Processes a single filing of a listing and extracts the XML content and metadata.

    Args:
        entry: the filing's listing entry; its ``href`` is the filing's index page
        filing_type: Type of filing being processed
        raise_on_request_error: raise _FilingRequestError when a download fails,
            so callers can tell a transient failure from a filing without XML

    Returns:
        Dictionary with 'date' and 'xml_content' or None if processing fails
    """
    report_page_url = SEC_URL + entry["href"]
    report_page = _get_report_page(report_page_url)
    if not report_page:
        if raise_on_request_error:
            raise _FilingRequestError(report_page_url)
        return None

    page_url, page_text = report_page
    report_page_soup = BeautifulSoup(page_text, "html.parser")
    if page_url.endswith("-headers.html"):
        filing_date, report_date, accepted = _get_header_dates(page_text)
    else:
        filing_date = _get_filing_date(report_page_soup)
        report_date = _get_report_date(report_page_soup)
        accepted = _get_accepted(report_page_soup)
    xml_url = _get_primary_xml_url(report_page_soup, filing_type, page_url)

    if not (filing_date and xml_url):
        logger.info(
            "Could not get metadata for report page %s", log_safe(report_page_url, max_len=200)
        )
        return None

    xml_response = _get_request(xml_url)
    if not xml_response:
        logger.info("Failed to download XML from %s", log_safe(xml_url, max_len=200))
        if raise_on_request_error:
            raise _FilingRequestError(xml_url)
        return None

    kind = ""
    if filing_type == "13F-HR" and "13F-HR/A" in page_text:
        cover_url = _get_cover_page_url(report_page_soup, page_url)
        cover_response = _get_request(cover_url) if cover_url else None
        if cover_url and not cover_response and raise_on_request_error:
            raise _FilingRequestError(cover_url)
        kind = amendment_type(cover_response.content) if cover_response else ""

    if filing_type == "13F-HR":
        logger.info(
            "Successfully scraped %s filing published on %s (refering %s)",
            filing_type,
            filing_date,
            report_date,
        )
    else:
        logger.info("Successfully scraped %s filing published on %s", filing_type, filing_date)
    return {
        "date": filing_date,
        "accepted_on": accepted,
        "type": filing_type,
        "reference_date": report_date,
        "xml_content": xml_response.content,
        "amendment_type": kind,
    }


def _get_submissions_page(name: str) -> dict[str, Any]:
    """
    One page of EDGAR's submissions API (the CIK's index, or one of its older pages).
    """
    response = _get_request(f"{DATA_SEC_URL}/submissions/{name}")
    if not response:
        raise _ListingError(name)
    try:
        return response.json()
    except ValueError as exc:
        raise _ListingError(name) from exc


def _list_filings(
    cik: str, filing_types: tuple[str, ...], filed_after: str | None = None
) -> Iterator[dict[str, str]]:
    """
    A CIK's filings of the given types, newest accepted first, as ``{"href", "type",
    "filing_date"}`` entries whose ``href`` is the filing's index page; only those filed after
    ``filed_after`` (YYYY-MM-DD) when given.

    Read from EDGAR's submissions API rather than the browse-edgar pages, which answer 503
    for minutes at a time under load. The API's index holds the last year (at least 1000
    filings); older filings sit in further pages, downloaded only when the walk reaches them.
    Ordered by acceptance time, so filings published the same day keep their real order.
    Raises _ListingError when a page cannot be downloaded.
    """
    form_types = {
        form: filing_type
        for filing_type in filing_types
        for form in FILING_SPECS[filing_type]["forms"]
    }
    number = int(cik)

    def entries(page: dict[str, list[str]]) -> Iterator[dict[str, str]]:
        """
        The page's filings of the wanted forms, newest accepted first.
        """
        rows = zip(
            page["accessionNumber"],
            page["form"],
            page["filingDate"],
            page["acceptanceDateTime"],
            strict=True,
        )
        for accession, form, filed, _ in sorted(rows, key=lambda row: row[3], reverse=True):
            if form in form_types and (filed_after is None or filed > filed_after):
                folder = accession.replace("-", "")
                yield {
                    "href": f"/Archives/edgar/data/{number}/{folder}/{accession}-index.htm",
                    "type": form_types[form],
                    "filing_date": filed,
                }

    index = _get_submissions_page(f"CIK{number:010d}.json")
    yield from entries(index["filings"]["recent"])
    older = sorted(index["filings"].get("files", []), key=lambda f: f["filingTo"], reverse=True)
    for page in older:
        if filed_after is not None and page["filingTo"] <= filed_after:
            return
        yield from entries(_get_submissions_page(page["name"]))


def fetch_latest_two_13f_filings(cik, offset=0):
    """
    Fetches the raw XML content and filing dates for the two most recent 13F-HR filings for a given CIK.
    Returns a list of dictionaries, or None if an error occurs.
    """
    try:
        entries = list(islice(_list_filings(cik, ("13F-HR",)), offset + 2))
    except _ListingError:
        logger.warning("Could not list the 13F filings of CIK %s.", log_safe(cik))
        return None

    if not entries:
        logger.info("No 13F-HR filings found for CIK: %s", log_safe(cik))
        return None

    filings = []
    for entry in entries[offset:]:
        filing_data = _scrape_filing(entry, "13F-HR")
        if filing_data is None:
            # A partial list would make the caller compare against an empty previous
            # quarter and rewrite every position as NEW; signal an error instead.
            logger.warning(
                "Could not scrape a 13F-HR filing for CIK %s; skipping to avoid a degraded comparison.",
                log_safe(cik),
            )
            return None
        filings.append(filing_data)

    return filings


def complete_new_holdings(cik: str, filing: dict[str, Any]) -> dict[str, Any]:
    """
    A partial NEW HOLDINGS amendment merged with the report it adds to, found
    by walking the fund's 13F listing back to the amendment's period; any other
    filing is returned as is (see app.scraper.amendments).
    """
    if filing.get("amendment_type") != NEW_HOLDINGS:
        return filing

    versions = [filing]
    try:
        for entry in _list_filings(cik, ("13F-HR",)):
            scraped = _scrape_filing(entry, "13F-HR")
            if not scraped or scraped.get("date", "") > filing["date"]:
                continue
            same = scraped["xml_content"] == filing["xml_content"]
            if scraped.get("reference_date") == filing["reference_date"] and not same:
                versions.append(scraped)
            if scraped.get("date", "") < filing["reference_date"]:
                break
    except _ListingError:
        logger.warning(
            "Could not list 13F filings for CIK %s; NEW HOLDINGS amendment kept as filed.",
            log_safe(cik),
        )
        return filing
    return consolidate_period(versions)[0]


def fetch_non_quarterly_after_date(cik: str, start_date: str | None) -> list[dict] | None:
    """
    Fetches the raw content and filing dates for the latest schedule (13D/G) and Form 4 filings for a given CIK.
    Returns a list of dictionaries (empty when nothing was filed), or None when no start date is
    available or any listing or filing request fails: a partial list would be saved over the
    fund's existing rows, so failure must be distinguishable from "no filings".
    """
    if not start_date:
        logger.warning(
            "No 13F baseline date available for CIK %s: skipping non-quarterly fetch.",
            log_safe(cik),
        )
        return None

    try:
        entries = list(_list_filings(cik, ("SCHEDULE", "4"), filed_after=start_date))
    except _ListingError:
        logger.warning("Could not list the non-quarterly filings of CIK %s.", log_safe(cik))
        return None

    if not entries:
        logger.info(
            "No non-quarterly filings found for CIK: %s after %s",
            log_safe(cik),
            log_safe(start_date),
        )
        return []

    filings: list[dict] = []
    for entry in entries:
        try:
            filing_data = _scrape_filing(entry, entry["type"], raise_on_request_error=True)
        except _FilingRequestError:
            logger.warning(
                "Could not download a %s filing for CIK %s; skipping the fetch to keep existing data.",
                entry["type"],
                log_safe(cik),
            )
            return None
        if filing_data:
            filings.append(filing_data)

    return filings


def get_latest_13f_filing_date(cik: str) -> str | None:
    """
    The filing date (YYYY-MM-DD) of the CIK's most recent 13F-HR, or None when it has none
    or its filing list cannot be downloaded.
    """
    try:
        latest = next(_list_filings(cik, ("13F-HR",)), None)
    except _ListingError:
        logger.info(
            "Failed to get latest filing date for CIK %s because request failed.", log_safe(cik)
        )
        return None
    return latest["filing_date"] if latest else None
