import threading
import unittest
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup
from curl_cffi.requests.exceptions import HTTPError, RequestException
from prometheus_client import REGISTRY
from tenacity import wait_combine, wait_random

from app.scraper.sec_scraper import (
    _RETRY_ATTEMPTS,
    USER_AGENT,
    _attempt_request,
    _build_session,
    _get_accepted,
    _get_filing_date,
    _get_primary_xml_url,
    _get_report_date,
    _get_request,
    _get_session,
    _scrape_filing,
    close_session,
    complete_new_holdings,
    fetch_latest_two_13f_filings,
    fetch_non_quarterly_after_date,
    get_latest_13f_filing_date,
    reset_session,
    scraper_session,
)


class TestSecScraper(unittest.TestCase):
    def setUp(self):
        # Patch time.sleep to speed up retries
        self.sleep_patcher = patch("time.sleep")
        self.mock_sleep = self.sleep_patcher.start()

    def tearDown(self):
        self.sleep_patcher.stop()

    @patch("app.scraper.sec_scraper._rate_limiter")
    @patch("app.scraper.sec_scraper._get_session")
    def test_get_request_acquires_rate_limiter_and_returns_response(
        self, mock_get_session, mock_limiter
    ):
        """
        Each network call must acquire a token first so parallel workers stay
        within SEC EDGAR's per-host budget, then return the response fetched
        with the request timeout.
        """
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get_session.return_value.get.return_value = mock_response

        response = _get_request("http://test.com")

        self.assertIs(response, mock_response)
        mock_limiter.acquire.assert_called_once()
        mock_get_session.return_value.get.assert_called_with("http://test.com", timeout=15)

    def test_build_session_has_sec_headers(self):
        """
        A freshly built Session carries the SEC-required headers and no fixed Host:
        the filing lists come from data.sec.gov, the filings from www.sec.gov.
        """
        session = _build_session()
        try:
            self.assertEqual(session.headers["User-Agent"], USER_AGENT)
            self.assertEqual(session.headers["Accept-Encoding"], "gzip, deflate")
            self.assertNotIn("Host", session.headers)
        finally:
            session.close()

    def test_get_session_is_per_thread(self):
        """
        curl_cffi Sessions are not thread-safe, so _get_session must hand each
        thread its own instance and reuse it within the same thread.
        """
        reset_session()
        try:
            main_session = _get_session()
            self.assertIs(_get_session(), main_session)  # cached within the thread

            worker_session: dict[str, object] = {}

            def worker():
                worker_session["session"] = _get_session()

            t = threading.Thread(target=worker)
            t.start()
            t.join()

            self.assertIsNot(main_session, worker_session["session"])
        finally:
            reset_session()

    @patch("app.scraper.sec_scraper._get_session")
    def test_get_request_failure_returns_none_after_retries(self, mock_get_session):
        """
        Persistent failures must honor the documented None-on-error contract:
        callers never see tenacity's RetryError.
        """
        mock_get_session.return_value.get.side_effect = RequestException("Error")

        response = _get_request("http://test.com")

        self.assertIsNone(response)
        self.assertEqual(mock_get_session.return_value.get.call_count, _RETRY_ATTEMPTS)

    @patch("app.scraper.sec_scraper._get_session")
    def test_get_request_does_not_retry_permanent_4xx(self, mock_get_session):
        """
        A permanent HTTP error can never succeed on retry: one attempt, None.
        """
        error = HTTPError("404")
        error.response = MagicMock(status_code=404)
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = error
        mock_get_session.return_value.get.return_value = mock_response

        response = _get_request("http://test.com")

        self.assertIsNone(response)
        self.assertEqual(mock_get_session.return_value.get.call_count, 1)

    @patch("app.scraper.sec_scraper._get_session")
    def test_get_request_retries_transient_5xx(self, mock_get_session):
        """
        5xx responses are transient: retried up to the attempt cap, then None.
        """
        error = HTTPError("503")
        error.response = MagicMock(status_code=503)
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = error
        mock_get_session.return_value.get.return_value = mock_response

        response = _get_request("http://test.com")

        self.assertIsNone(response)
        self.assertEqual(mock_get_session.return_value.get.call_count, _RETRY_ATTEMPTS)

    @patch("app.scraper.sec_scraper._get_session")
    def test_scrape_filing_reads_the_header_page_when_both_index_pages_are_missing(
        self, mock_get_session
    ):
        """
        EDGAR's CDN at times answers 404 for both -index.htm and -index.html of a
        filing it still serves: the -index-headers.html page carries the same
        document links (relative) and the dates in SGML form.
        """
        folder = "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/"
        headers_page = (
            "<ACCEPTANCE-DATETIME>20260811171523\n"
            "CONFORMED SUBMISSION TYPE:\t13F-HR\n"
            "CONFORMED PERIOD OF REPORT:\t20260630\n"
            "FILED AS OF DATE:\t\t20260811\n"
            '<a href="xslX02/primary_doc.xml">'
            '<a href="primary_doc.xml">'
            '<a href="xsl/infotable.xml">'
            '<a href="infotable.xml">'
        )

        def respond(url, timeout):
            """
            Serves the header page and the table; every other URL is a 404.
            """
            response = MagicMock()
            if url.endswith("-index-headers.html"):
                response.text = headers_page
            elif url == folder + "infotable.xml":
                response.content = b"<informationTable/>"
            else:
                error = HTTPError("404")
                error.response = MagicMock(status_code=404)
                response.raise_for_status.side_effect = error
            return response

        mock_get_session.return_value.get.side_effect = respond

        result = _scrape_filing(
            {"href": "/Archives/edgar/data/1/000000000126000001/0000000001-26-000001-index.htm"},
            "13F-HR",
        )

        assert result is not None
        self.assertEqual(result["date"], "2026-08-11")
        self.assertEqual(result["reference_date"], "2026-06-30")
        self.assertEqual(result["accepted_on"], "2026-08-11 17:15:23")
        self.assertEqual(result["xml_content"], b"<informationTable/>")

    def test_retry_wait_uses_jitter(self):
        """
        The wait strategy must keep a random jitter component so retries 429'd
        together don't back off in lockstep and collide again.
        """
        wait = _attempt_request.retry.wait
        self.assertIsInstance(wait, wait_combine)
        self.assertTrue(any(isinstance(w, wait_random) for w in wait.wait_funcs))

    def test_html_parsing_helpers(self):
        """Test helper functions for parsing HTML soup."""
        # Updated mock HTML to reflect expected structure (label in one tag, value in next)
        html = """
        <div>Accepted</div>
        <div class="info">2023-01-01 10:00:00</div>
        <div>Filing Date</div>
        <div class="info">2023-01-02</div>
        <div>Period of Report</div>
        <div class="info">2022-12-31</div>
        <a href="/Archives/edgar/data/123/000/primary.xml">xml</a>
        <a href="/Archives/edgar/data/123/000/xsl.xml">xml</a>
        <a href="/Archives/edgar/data/123/000/other.xml">xml</a>
        <a href="/Archives/edgar/data/123/000/target.xml">xml</a>
        """
        soup = BeautifulSoup(html, "html.parser")

        self.assertEqual(_get_accepted(soup), "2023-01-01 10:00:00")
        self.assertEqual(_get_filing_date(soup), "2023-01-02")
        self.assertEqual(_get_report_date(soup), "2022-12-31")

        # Test 13F-HR (index 3)
        # In our mock HTML, index 3 is target.xml
        self.assertEqual(
            _get_primary_xml_url(soup, "13F-HR"),
            "https://www.sec.gov/Archives/edgar/data/123/000/target.xml",
        )

        # Test SCHEDULE (index 1)
        # In our mock HTML, index 1 is xsl.xml
        self.assertEqual(
            _get_primary_xml_url(soup, "SCHEDULE"),
            "https://www.sec.gov/Archives/edgar/data/123/000/xsl.xml",
        )

    def test_get_primary_xml_url_matches_uppercase_extension(self):
        """
        Some filers submit the information table with an uppercase .XML
        extension. The href regex must match case-insensitively, otherwise the
        link is dropped, the positional index shifts and the filing looks empty.
        """
        html = """
        <div>Filing Date</div>
        <div class="info">2023-01-02</div>
        <div>Period of Report</div>
        <div class="info">2022-12-31</div>
        <a href="/Archives/edgar/data/123/000/primary.XML">xml</a>
        <a href="/Archives/edgar/data/123/000/xsl.xml">xml</a>
        <a href="/Archives/edgar/data/123/000/other.XML">xml</a>
        <a href="/Archives/edgar/data/123/000/target.XML">xml</a>
        """
        soup = BeautifulSoup(html, "html.parser")

        self.assertEqual(
            _get_primary_xml_url(soup, "13F-HR"),
            "https://www.sec.gov/Archives/edgar/data/123/000/target.XML",
        )

    @patch("app.scraper.sec_scraper._get_request")
    def test_scrape_filing_success(self, mock_get_request):
        """Test _scrape_filing successfully extracts data."""
        # Mock report page response with correct structure
        report_html = """
        <div>Accepted</div>
        <div class="info">2023-01-01</div>
        <div>Filing Date</div>
        <div class="info">2023-01-02</div>
        <div>Period of Report</div>
        <div class="info">2022-12-31</div>
        <a href="/xml_link">xml</a>
        <a href="/xml_link">xml</a>
        <a href="/xml_link">xml</a>
        <a href="/target_xml">xml</a>
        """
        mock_report_response = MagicMock()
        mock_report_response.text = report_html

        # Mock XML response
        mock_xml_response = MagicMock()
        mock_xml_response.content = b"<xml>content</xml>"

        # Setup side effects for _get_request calls
        # First call for report page, second for XML
        mock_get_request.side_effect = [mock_report_response, mock_xml_response]

        document_tag = {"href": "/report_page"}
        result = _scrape_filing(document_tag, "13F-HR")

        self.assertIsNotNone(result)
        self.assertEqual(result["date"], "2023-01-02")
        self.assertEqual(result["accepted_on"], "2023-01-01")
        self.assertEqual(result["type"], "13F-HR")
        self.assertEqual(result["reference_date"], "2022-12-31")
        self.assertEqual(result["xml_content"], b"<xml>content</xml>")
        self.assertEqual(result["amendment_type"], "")
        self.assertEqual(mock_get_request.call_count, 2)

    @patch("app.scraper.sec_scraper._get_request")
    def test_scrape_filing_reads_an_amendments_type_from_its_cover_page(self, mock_get_request):
        """
        A 13F-HR/A also fetches its raw cover page (not the rendered one) for the amendment kind.
        """
        report_html = """
        <div>Form 13F-HR/A</div>
        <div>Filing Date</div><div class="info">2025-04-09</div>
        <div>Period of Report</div><div class="info">2024-12-31</div>
        <a href="/a/xslForm13F_X02/primary_doc.xml">xml</a>
        <a href="/a/primary_doc.xml">xml</a>
        <a href="/a/xslForm13F_X02/table.xml">xml</a>
        <a href="/a/table.xml">xml</a>
        """
        report, table, cover = MagicMock(), MagicMock(), MagicMock()
        report.text = report_html
        table.content = b"<informationTable/>"
        cover.content = (
            b"<amendmentInfo><amendmentType>NEW HOLDINGS</amendmentType></amendmentInfo>"
        )
        mock_get_request.side_effect = [report, table, cover]

        result = _scrape_filing({"href": "/report_page"}, "13F-HR")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["amendment_type"], "NEW HOLDINGS")
        self.assertTrue(mock_get_request.call_args_list[2].args[0].endswith("/a/primary_doc.xml"))

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_latest_two_13f_filings_takes_the_newest_accepted_13fs(self, mock_get_request):
        """
        The two newest 13F-HR filings by acceptance time are scraped, other forms are
        ignored, and each is read from its index page under the fund's CIK.
        """
        mock_get_request.return_value = _submissions(
            ("0000000001-26-000003", "13F-HR", "2026-08-14", "2026-08-14T09:00:00.000Z"),
            ("0000000001-26-000004", "SCHEDULE 13G", "2026-09-01", "2026-09-01T09:00:00.000Z"),
            ("0000000001-26-000001", "13F-HR", "2026-02-13", "2026-02-13T09:00:00.000Z"),
            ("0000000001-26-000005", "13F-HR/A", "2026-08-14", "2026-08-14T17:30:00.000Z"),
        )

        with patch("app.scraper.sec_scraper._scrape_filing") as mock_scrape:
            mock_scrape.side_effect = [{"id": 1}, {"id": 2}]
            filings = fetch_latest_two_13f_filings("0000000123")

        self.assertEqual(filings, [{"id": 1}, {"id": 2}])
        self.assertEqual(
            [c.args[0]["href"] for c in mock_scrape.call_args_list],
            [
                "/Archives/edgar/data/123/000000000126000005/0000000001-26-000005-index.htm",
                "/Archives/edgar/data/123/000000000126000003/0000000001-26-000003-index.htm",
            ],
        )
        self.assertEqual(
            mock_get_request.call_args.args[0],
            "https://data.sec.gov/submissions/CIK0000000123.json",
        )

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_latest_two_reads_an_older_page_when_the_offset_reaches_it(
        self, mock_get_request
    ):
        """
        The API's index only holds the latest filings: an offset past them continues on
        the older page the index lists.
        """
        older = MagicMock()
        older.json.return_value = _page(
            ("0000000001-24-000002", "13F-HR", "2024-11-14", "2024-11-14T09:00:00.000Z"),
            ("0000000001-24-000001", "13F-HR", "2024-08-14", "2024-08-14T09:00:00.000Z"),
        )
        mock_get_request.side_effect = lambda url, **_: (
            older
            if url.endswith("/CIK0000000123-submissions-001.json")
            else _submissions(
                ("0000000001-25-000001", "13F-HR", "2025-02-13", "2025-02-13T09:00:00.000Z"),
                files=[
                    {"name": "CIK0000000123-submissions-001.json", "filingTo": "2024-12-31"},
                ],
            )
        )

        with patch("app.scraper.sec_scraper._scrape_filing") as mock_scrape:
            mock_scrape.side_effect = lambda entry, *_args, **_kw: {"href": entry["href"]}
            filings = fetch_latest_two_13f_filings("0000000123", offset=1)

        assert filings is not None
        self.assertEqual(
            [f["href"].rsplit("/", 1)[1] for f in filings],
            ["0000000001-24-000002-index.htm", "0000000001-24-000001-index.htm"],
        )

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_latest_two_returns_none_when_a_windowed_filing_fails_to_scrape(
        self, mock_get_request
    ):
        """
        Two filings available but one fails to scrape (e.g. 429): return None,
        not a partial list, so the caller skips the fund instead of rewriting
        every position as NEW against an empty previous quarter.
        """
        mock_get_request.return_value = _submissions(
            ("0000000001-26-000002", "13F-HR", "2026-08-14", "2026-08-14T09:00:00.000Z"),
            ("0000000001-26-000001", "13F-HR", "2026-05-14", "2026-05-14T09:00:00.000Z"),
        )

        with patch("app.scraper.sec_scraper._scrape_filing") as mock_scrape:
            mock_scrape.side_effect = [{"id": 1, "date": "2023-06-30"}, None]

            self.assertIsNone(fetch_latest_two_13f_filings("0000000123"))

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_latest_two_returns_single_filing_when_only_one_exists(self, mock_get_request):
        """
        A genuinely new fund with a single 13F-HR is not an error: one available
        filing that scrapes cleanly returns a one-element list.
        """
        mock_get_request.return_value = _submissions(
            ("0000000001-26-000001", "13F-HR", "2026-05-14", "2026-05-14T09:00:00.000Z"),
        )

        with patch("app.scraper.sec_scraper._scrape_filing") as mock_scrape:
            mock_scrape.side_effect = [{"id": 1, "date": "2023-06-30"}]

            filings = fetch_latest_two_13f_filings("0000000123")

            assert filings is not None
            self.assertEqual(len(filings), 1)

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_latest_two_returns_none_when_the_listing_fails(self, mock_get_request):
        """
        A filing list EDGAR does not serve is an error, not a fund without filings.
        """
        mock_get_request.return_value = None

        self.assertIsNone(fetch_latest_two_13f_filings("0000000123"))

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_non_quarterly_lists_schedules_and_form_4s_filed_after_the_date(
        self, mock_get_request
    ):
        """
        Schedules 13D/G and Forms 4 filed after the start date are scraped, each with its
        type; a filing on the start date itself and forms such as 40-APP are not.
        """
        mock_get_request.return_value = _submissions(
            ("0000000001-26-000001", "SCHEDULE 13G/A", "2026-03-02", "2026-03-02T09:00:00.000Z"),
            ("0000000001-26-000002", "4", "2026-03-03", "2026-03-03T09:00:00.000Z"),
            ("0000000001-26-000003", "40-APP", "2026-03-04", "2026-03-04T09:00:00.000Z"),
            ("0000000001-26-000004", "13F-HR", "2026-03-05", "2026-03-05T09:00:00.000Z"),
            ("0000000001-26-000005", "4", "2026-03-01", "2026-03-01T09:00:00.000Z"),
        )

        with patch("app.scraper.sec_scraper._scrape_filing") as mock_scrape:
            mock_scrape.side_effect = lambda entry, filing_type, **_: {"type": filing_type}

            filings = fetch_non_quarterly_after_date("0000000123", "2026-03-01")

        self.assertEqual(filings, [{"type": "4"}, {"type": "SCHEDULE"}])

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_non_quarterly_skips_older_pages_before_the_start_date(self, mock_get_request):
        """
        Older pages hold nothing filed after the start date once their range ends before it:
        they are never downloaded.
        """
        mock_get_request.return_value = _submissions(
            files=[{"name": "CIK0000000123-submissions-001.json", "filingTo": "2025-12-31"}],
        )

        self.assertEqual(fetch_non_quarterly_after_date("0000000123", "2026-03-01"), [])
        self.assertEqual(mock_get_request.call_count, 1)

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_non_quarterly_returns_none_when_the_listing_fails(self, mock_get_request):
        """
        A failed listing request must surface as None, not as an empty or
        partial list the caller would save over the fund's existing rows.
        """
        mock_get_request.return_value = None

        self.assertIsNone(fetch_non_quarterly_after_date("0000000123", "2026-03-01"))

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_non_quarterly_returns_none_when_the_listing_is_not_json(self, mock_get_request):
        """
        A listing answered with something other than JSON (an error page) is a failure too.
        """
        mock_get_request.return_value.json.side_effect = ValueError("not JSON")

        self.assertIsNone(fetch_non_quarterly_after_date("0000000123", "2026-03-01"))

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_non_quarterly_returns_none_when_a_filing_request_fails(self, mock_get_request):
        """
        A filing whose report page cannot be downloaded must not be dropped
        silently: the whole fetch reports failure.
        """
        listing = _submissions(
            ("0000000001-26-000001", "SCHEDULE 13G", "2026-03-02", "2026-03-02T09:00:00.000Z"),
        )
        mock_get_request.side_effect = lambda url, **_: listing if "data.sec.gov" in url else None

        self.assertIsNone(fetch_non_quarterly_after_date("0000000123", "2026-03-01"))

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_non_quarterly_skips_a_filing_without_xml_document(self, mock_get_request):
        """
        A report page that downloads fine but has no XML document is a
        permanent property of that filing: it is skipped, not a failure.
        """
        listing = _submissions(
            ("0000000001-26-000001", "SCHEDULE 13G", "2026-03-02", "2026-03-02T09:00:00.000Z"),
        )
        report_page = MagicMock()
        report_page.text = "<div>Filing Date</div><div>2026-03-02</div>"
        mock_get_request.side_effect = lambda url, **_: (
            listing if "data.sec.gov" in url else report_page
        )

        self.assertEqual(fetch_non_quarterly_after_date("0000000123", "2026-03-01"), [])

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_non_quarterly_without_start_date_returns_none(self, mock_get_request):
        """
        A missing 13F baseline date (fund page unparseable) must degrade to
        None without firing any request, not crash on None.replace.
        """
        result = fetch_non_quarterly_after_date("0000000123", None)

        self.assertIsNone(result)
        mock_get_request.assert_not_called()

    @patch("app.scraper.sec_scraper._get_request")
    def test_get_latest_13f_filing_date(self, mock_get_request):
        """
        The filing date of the newest accepted 13F-HR or 13F-HR/A, other forms ignored.
        """
        mock_get_request.return_value = _submissions(
            ("0000000001-26-000001", "13F-HR", "2026-05-15", "2026-05-15T09:00:00.000Z"),
            ("0000000001-26-000002", "4", "2026-06-02", "2026-06-02T09:00:00.000Z"),
            ("0000000001-26-000003", "13F-HR/A", "2026-05-20", "2026-05-20T09:00:00.000Z"),
        )

        self.assertEqual(get_latest_13f_filing_date("0000000123"), "2026-05-20")


def _page(*filings):
    """
    The parallel arrays of a submissions API page for (accession, form, filed, accepted) rows.
    """
    return {
        "accessionNumber": [f[0] for f in filings],
        "form": [f[1] for f in filings],
        "filingDate": [f[2] for f in filings],
        "acceptanceDateTime": [f[3] for f in filings],
    }


def _submissions(*filings, files=()):
    """
    A mocked submissions API index response listing ``filings`` and its older ``files`` pages.
    """
    response = MagicMock()
    response.json.return_value = {"filings": {"recent": _page(*filings), "files": list(files)}}
    return response


class TestSecScraperLifecycle(unittest.TestCase):
    def tearDown(self):
        # Always rebuild after tests in this class so other tests get fresh state.
        reset_session()

    def test_close_session_closes_all_registered_sessions(self):
        """close_session() must close every per-thread session and clear the registry."""
        import app.scraper.sec_scraper as scraper

        s1, s2 = MagicMock(), MagicMock()
        with scraper._sessions_lock:
            scraper._sessions[:] = [s1, s2]

        close_session()

        s1.close.assert_called_once()
        s2.close.assert_called_once()
        self.assertEqual(scraper._sessions, [])

    def test_scraper_session_closes_even_when_body_raises(self):
        """
        The cleanup happens in a `finally` block, so an exception raised inside
        the `with` body must still close the sessions and then propagate.
        """
        import app.scraper.sec_scraper as scraper

        s = MagicMock()
        with scraper._sessions_lock:
            scraper._sessions[:] = [s]

        with self.assertRaises(RuntimeError), scraper_session():
            raise RuntimeError("boom")
        s.close.assert_called_once()


def _sec_requests(outcome: str) -> float:
    """
    Current value of the SEC request counter for ``outcome``.
    """
    return REGISTRY.get_sample_value("hft_sec_requests_total", {"outcome": outcome}) or 0.0


@patch("time.sleep")
@patch("app.scraper.sec_scraper._get_session")
class TestSecRequestMetrics(unittest.TestCase):
    def _respond_with_status(self, mock_get_session, status):
        """
        Make every request fail with HTTP ``status``.
        """
        error = HTTPError(str(status))
        error.response = MagicMock(status_code=status)
        mock_get_session.return_value.get.return_value.raise_for_status.side_effect = error

    def test_success_is_counted_ok(self, mock_get_session, _sleep):
        """
        A successful request increments the ok outcome.
        """
        mock_get_session.return_value.get.return_value.raise_for_status.return_value = None
        before = _sec_requests("ok")

        _get_request("http://test.com")

        self.assertEqual(_sec_requests("ok"), before + 1)

    def test_every_429_attempt_is_counted_rate_limited(self, mock_get_session, _sleep):
        """
        Each throttled attempt counts, so a retry storm is visible.
        """
        self._respond_with_status(mock_get_session, 429)
        before = _sec_requests("rate_limited")

        _get_request("http://test.com")

        self.assertEqual(_sec_requests("rate_limited"), before + _RETRY_ATTEMPTS)

    def test_other_failures_are_counted_error(self, mock_get_session, _sleep):
        """
        A permanent 4xx and a transport failure both count as errors.
        """
        self._respond_with_status(mock_get_session, 404)
        before = _sec_requests("error")

        _get_request("http://test.com")
        mock_get_session.return_value.get.side_effect = RequestException("down")
        _get_request("http://test.com")

        self.assertEqual(_sec_requests("error"), before + 1 + _RETRY_ATTEMPTS)


class TestCompleteNewHoldings(unittest.TestCase):
    """
    The updater completes a partial NEW HOLDINGS amendment with its period's report.
    """

    TABLE = '<ns1:informationTable xmlns:ns1="x">{}</ns1:informationTable>'
    ROW = "<ns1:infoTable><ns1:cusip>{}</ns1:cusip><ns1:value>{}</ns1:value></ns1:infoTable>"

    def filing(self, ref, published, cusip, value, kind=""):
        """
        A scraped filing with one row.
        """
        xml = self.TABLE.format(self.ROW.format(cusip, value)).encode()
        return {
            "reference_date": ref,
            "date": published,
            "xml_content": xml,
            "amendment_type": kind,
        }

    def test_an_original_is_returned_untouched_without_any_request(self):
        """
        Only NEW HOLDINGS amendments need their report.
        """
        original = self.filing("2024-12-31", "2025-02-14", "A", 500)
        with patch("app.scraper.sec_scraper._get_request") as mock_get:
            self.assertIs(complete_new_holdings("1", original), original)
        mock_get.assert_not_called()

    @patch("app.scraper.sec_scraper._scrape_filing")
    @patch("app.scraper.sec_scraper._get_request")
    def test_a_partial_amendment_is_merged_with_its_original(self, mock_get, mock_scrape):
        """
        The listing is walked back to the period's report, whose rows are kept.
        """
        added = self.filing("2024-12-31", "2025-04-09", "B", 20, "NEW HOLDINGS")
        mock_get.return_value = _submissions(
            *(
                (f"0000000001-25-00000{i}", "13F-HR", "2025-01-01", f"2025-01-0{i}T09:00:00Z")
                for i in range(4, 0, -1)
            )
        )
        mock_scrape.side_effect = [
            self.filing("2025-03-31", "2025-05-15", "Z", 1),
            added,
            self.filing("2024-12-31", "2025-02-14", "A", 500),
            self.filing("2024-09-30", "2024-11-14", "A", 400),
        ]

        merged = complete_new_holdings("1", added)

        self.assertIn(b"<ns1:cusip>A</ns1:cusip>", merged["xml_content"])
        self.assertIn(b"<ns1:cusip>B</ns1:cusip>", merged["xml_content"])
        self.assertEqual(mock_scrape.call_count, 4)


if __name__ == "__main__":
    unittest.main()
