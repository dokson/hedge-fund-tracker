import atexit
import os
import re
from contextlib import contextmanager
from typing import Any

import requests
from bs4 import BeautifulSoup
from tenacity import RetryError, retry, retry_if_result, stop_after_attempt, wait_exponential

from app.scraper.rate_limiter import RateLimiter
from app.utils.logger import get_logger, log_safe
from app.utils.strings import get_next_yyyymmdd_day

logger = get_logger(__name__)

# SEC EDGAR requires a custom User-Agent that identifies the application and provides a contact email.
# See: https://www.sec.gov/os/developer-support-policy
# Override the contact via SEC_USER_AGENT (e.g. when forking/deploying under a different contact).
USER_AGENT = os.environ.get("SEC_USER_AGENT", "Hedge Fund Tracker dok.son@msn.com")
SEC_HOST = "www.sec.gov"
SEC_URL = "https://" + SEC_HOST


def _build_session() -> requests.Session:
    """
    Builds a requests.Session pre-configured with SEC-required headers.
    """
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "HOST": SEC_HOST,
        }
    )
    return s


# Shared session + rate limiter: process-wide singletons.
# - requests.Session reuses TCP+TLS across parallel workers (thread-safe via urllib3 PoolManager).
# - SEC EDGAR fair-access policy caps clients at ~10 req/s per User-Agent; the token bucket
#   bounds requests across all worker threads regardless of pool size.
# Lifecycle: created at import, closed at interpreter exit via atexit. Use reset_session() in
# tests to drop and rebuild both singletons, or scraper_session() for a scoped override.
_session: requests.Session = _build_session()
_rate_limiter = RateLimiter(rate=9, capacity=9)


def close_session() -> None:
    """
    Closes the shared session, releasing pooled connections. Safe to call multiple times.
    """
    global _session
    try:
        _session.close()
    except Exception:
        logger.debug("Error closing shared SEC session", exc_info=True)


def reset_session() -> None:
    """
    Closes and rebuilds the shared session and rate limiter. Intended for test isolation.
    """
    global _session, _rate_limiter
    close_session()
    _session = _build_session()
    _rate_limiter = RateLimiter(rate=9, capacity=9)


@contextmanager
def scraper_session():
    """
    Context manager that ensures the shared session is closed on exit.

    Use around long-running batch jobs to guarantee connection cleanup:

        with scraper_session():
            fetch_latest_two_13f_filings(cik)
    """
    try:
        yield
    finally:
        close_session()


atexit.register(close_session)

FILING_SPECS: dict[str, dict[str, Any]] = {
    "13F-HR": {
        "xml_link_index": 3,
        "type_prefix": "13F-HR",
    },
    "SCHEDULE": {
        "xml_link_index": 1,
        "type_prefix": "SC",
    },
    "4": {
        "xml_link_index": 1,
        "type_prefix": "4",
        "type_reject": {"40-", "425"},
    },
}


@retry(
    retry=retry_if_result(lambda value: value is None),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    stop=stop_after_attempt(5),
    before_sleep=lambda rs: logger.progress(
        f"Retrying request for '{rs.args[0]}' in {rs.next_action.sleep:.0f}s... (Attempt #{rs.attempt_number})"  # type: ignore[union-attr]
    ),
)
def _get_request(url: str) -> requests.Response | None:
    """
    Sends a GET request to the specified URL via the shared Session.

    Rate-limited via a process-wide token bucket so parallel workers stay
    within SEC EDGAR's fair-access policy. Retries on failure via tenacity.

    Transient network errors (timeouts, connection resets, 5xx) are logged
    as warnings without a traceback since tenacity will retry them. Other
    RequestExceptions log a full traceback for diagnosis.
    """
    _rate_limiter.acquire()
    try:
        response = _session.get(url, timeout=15)
        response.raise_for_status()
        return response
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
        logger.warning(
            "Transient network error for %s: %s",
            log_safe(url, max_len=200),
            log_safe(exc.__class__.__name__),
        )
        return None
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status is not None and (status >= 500 or status == 429):
            logger.warning("Transient HTTP %s for %s", status, log_safe(url, max_len=200))
            return None
        logger.error("Request failed for %s", log_safe(url, max_len=200), exc_info=True)
        return None
    except requests.exceptions.RequestException:
        logger.error("Request failed for %s", log_safe(url, max_len=200), exc_info=True)
        return None


def _create_search_url(cik, filing_type="13F-HR", start_date=None, start_offset=0):
    """
    Creates the SEC EDGAR search URL for a given CIK and filing type.
    """
    search_url = (
        f"{SEC_URL}/cgi-bin/browse-edgar?CIK={cik}&action=getcompany&type={filing_type}&count=100"
    )

    if start_date:
        search_url += f"&datea={start_date}"

    if start_offset > 0:
        search_url += f"&start={start_offset}"

    return search_url


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


def _get_primary_xml_url(report_page_soup, filing_type):
    """
    Finds the link to the primary XML data file from the report page's soup.
    Uses the configuration based on filing type.
    """
    try:
        config = FILING_SPECS.get(filing_type)
        if config is None:
            return None
        tags = report_page_soup.find_all("a", attrs={"href": re.compile("xml")})

        xml_link_index = int(config["xml_link_index"])
        if len(tags) > xml_link_index:
            return SEC_URL + tags[xml_link_index].get("href")
    except Exception:
        logger.error("Error finding XML URL for filing type %s", filing_type, exc_info=True)
    return None


def _scrape_filing(document_tag, filing_type):
    """
    Processes a single filing document tag and extracts the XML content and metadata.

    Args:
        document_tag: BeautifulSoup tag for the document link
        filing_type: Type of filing being processed

    Returns:
        Dictionary with 'date' and 'xml_content' or None if processing fails
    """
    report_page_url = SEC_URL + document_tag["href"]
    try:
        report_page_response = _get_request(report_page_url)
        if not report_page_response:
            return None
    except RetryError:
        logger.error(
            "Failed to fetch report page %s after multiple retries.",
            log_safe(report_page_url, max_len=200),
            exc_info=True,
        )
        return None

    report_page_soup = BeautifulSoup(report_page_response.text, "html.parser")
    filing_date = _get_filing_date(report_page_soup)
    report_date = _get_report_date(report_page_soup)
    accepted = _get_accepted(report_page_soup)
    xml_url = _get_primary_xml_url(report_page_soup, filing_type)

    if not (filing_date and xml_url):
        logger.info(
            "Could not get metadata for report page %s", log_safe(report_page_url, max_len=200)
        )
        return None

    try:
        xml_response = _get_request(xml_url)
        if not xml_response:
            logger.info("Failed to download XML from %s", log_safe(xml_url, max_len=200))
            return None
    except RetryError:
        logger.error(
            "Failed to fetch XML file %s after multiple retries.",
            log_safe(xml_url, max_len=200),
            exc_info=True,
        )
        return None

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
    }


def fetch_latest_two_13f_filings(cik, offset=0):
    """
    Fetches the raw XML content and filing dates for the two most recent 13F-HR filings for a given CIK.
    Returns a list of dictionaries, or None if an error occurs.
    """
    search_url = _create_search_url(cik, "13F-HR")
    response = _get_request(search_url)

    if not response:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    document_tags = soup.find_all("a", id="documentsbutton")

    if not document_tags:
        logger.info("No 13F-HR filings found for CIK: %s", log_safe(cik))
        return None

    filings = []
    for tag in document_tags[offset : offset + 2]:
        filing_data = _scrape_filing(tag, "13F-HR")
        if filing_data:
            filings.append(filing_data)

    return filings


def fetch_non_quarterly_after_date(cik: str, start_date: str) -> list[dict] | None:
    """
    Fetches the raw content and filing dates for the latest schedule (13D/G) and Form 4 filings for a given CIK.
    Returns a list of dictionaries, or None if an error occurs.
    """
    filings: list[dict] = []
    yyyymmdd_date = start_date.replace("-", "")

    # Helper to fetch tags for a specific type with pagination
    def get_tags(filing_type):
        all_type_tags = []
        offset = 0
        while True:
            url = _create_search_url(cik, filing_type, get_next_yyyymmdd_day(yyyymmdd_date), offset)
            try:
                resp = _get_request(url)
                if not resp:
                    logger.error(
                        "Could not fetch %s filings for CIK %s (request failed at offset %d)",
                        filing_type,
                        log_safe(cik),
                        offset,
                    )
                    break
                soup = BeautifulSoup(resp.text, "html.parser")
                all_tags_on_page = soup.find_all("a", id="documentsbutton")

                if not all_tags_on_page:
                    break

                # Filter by filing type prefix to avoid EDGAR prefix-matching false positives
                # (e.g. searching for type=4 also returns 40-APP, 40-APP/A)
                spec = FILING_SPECS[filing_type]
                type_prefix = spec.get("type_prefix")
                type_reject = spec.get("type_reject", set())
                filtered_tags = []
                for tag in all_tags_on_page:
                    row = tag.find_parent("tr")
                    cells = row.find_all("td") if row else []
                    actual_type = cells[0].get_text(strip=True) if cells else ""
                    if type_prefix and not actual_type.startswith(type_prefix):
                        continue
                    if any(actual_type.startswith(r) for r in type_reject):
                        continue
                    filtered_tags.append(tag)
                all_type_tags.extend([(tag, filing_type) for tag in filtered_tags])

                # Pagination based on pre-filter count (EDGAR returns pages of 100)
                if len(all_tags_on_page) == 100:
                    offset += 100
                    if offset >= 500:  # Safety break to avoid infinite loops on extreme cases
                        logger.warning(
                            "Reached maximum pagination limit (500) for %s filings of CIK %s",
                            filing_type,
                            log_safe(cik),
                        )
                        break
                else:
                    break
            except Exception:
                logger.error(
                    "fetching %s filings for CIK %s at offset %d",
                    filing_type,
                    log_safe(cik),
                    offset,
                    exc_info=True,
                )
                break
        return all_type_tags

    all_tags = []
    all_tags.extend(get_tags("SCHEDULE"))
    all_tags.extend(get_tags("4"))

    if not all_tags:
        logger.info(
            "No non-quarterly filings found for CIK: %s after %s",
            log_safe(cik),
            log_safe(start_date),
        )
        return filings

    for tag, f_type in all_tags:
        filing_data = _scrape_filing(tag, f_type)
        if filing_data:
            filings.append(filing_data)

    return filings


def get_latest_13f_filing_date(cik: str) -> str | None:
    """
    Fetches and gets only the filing date of the most recent 13F-HR filing for a given CIK.

    Args:
        cik (str): The CIK of the hedge fund.

    Returns:
        str: The filing date in 'YYYY-MM-DD' format
    """
    search_url = _create_search_url(cik, "13F-HR")
    response = _get_request(search_url)

    if not response:
        logger.info(
            "Failed to get latest filing date for CIK %s because request failed.", log_safe(cik)
        )
        return None

    try:
        soup = BeautifulSoup(response.text, "html.parser")
        button = soup.find("a", id="documentsbutton")
        if not button:
            logger.info(
                "No 'documentsbutton' found for CIK %s on page %s",
                log_safe(cik),
                log_safe(search_url, max_len=200),
            )
            return None

        # The filing date is in the 4th <td> of the same <tr> as the button
        row = button.find_parent("tr")
        if row is None:
            return None
        return row.find_all("td")[3].text.strip()
    except (AttributeError, IndexError):
        logger.error(
            "Error parsing filing date for CIK %s. Page structure may have changed.",
            log_safe(cik),
            exc_info=True,
        )
        return None
