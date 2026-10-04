import threading
import unittest
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup
from curl_cffi.requests.exceptions import HTTPError, RequestException
from prometheus_client import REGISTRY
from tenacity import wait_combine, wait_random

from app.scraper.sec_scraper import (
    _RETRY_ATTEMPTS,
    SEC_HOST,
    USER_AGENT,
    _attempt_request,
    _build_session,
    _create_search_url,
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
        """A freshly built Session must carry the SEC-required headers."""
        session = _build_session()
        try:
            self.assertEqual(session.headers["User-Agent"], USER_AGENT)
            self.assertEqual(session.headers["HOST"], SEC_HOST)
            self.assertEqual(session.headers["Accept-Encoding"], "gzip, deflate")
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

    def test_retry_wait_uses_jitter(self):
        """
        The wait strategy must keep a random jitter component so retries 429'd
        together don't back off in lockstep and collide again.
        """
        wait = _attempt_request.retry.wait
        self.assertIsInstance(wait, wait_combine)
        self.assertTrue(any(isinstance(w, wait_random) for w in wait.wait_funcs))

    def test_create_search_url(self):
        """Test _create_search_url generates correct URLs."""
        cik = "1234567890"

        # Test default 13F-HR
        expected_url = f"https://www.sec.gov/cgi-bin/browse-edgar?CIK={cik}&action=getcompany&type=13F-HR&count=100"
        self.assertEqual(_create_search_url(cik), expected_url)

        # Test with date
        date = "20230101"
        expected_url_date = f"https://www.sec.gov/cgi-bin/browse-edgar?CIK={cik}&action=getcompany&type=SCHEDULE&count=100&datea={date}"
        self.assertEqual(_create_search_url(cik, "SCHEDULE", date), expected_url_date)

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
    def test_fetch_latest_two_13f_filings(self, mock_get_request):
        """Test fetch_latest_two_13f_filings returns sorted list of top 2 filings from a larger list."""
        # Mock search page response with 4 filings
        search_html = """
        <a id="documentsbutton" href="/doc1">Format</a>
        <a id="documentsbutton" href="/doc2">Format</a>
        <a id="documentsbutton" href="/doc3">Format</a>
        <a id="documentsbutton" href="/doc4">Format</a>
        """
        mock_search_response = MagicMock()
        mock_search_response.text = search_html
        mock_get_request.return_value = mock_search_response

        with patch("app.scraper.sec_scraper._scrape_filing") as mock_scrape:
            # Mock return values for the first 2 calls.
            # Note: The code slices [offset:offset+2] BEFORE scraping.
            # So it will only scrape doc1 and doc2.
            # We give them dates to verify sorting (doc1 is older, doc2 is newer).
            mock_scrape.side_effect = [
                {"id": 1, "date": "2023-06-30"},  # last filing
                {"id": 2, "date": "2023-03-31"},  # second last filing
            ]

            filings = fetch_latest_two_13f_filings("CIK123")

            # Verify we only got 2 results
            assert filings is not None
            self.assertEqual(len(filings), 2)

            self.assertEqual(filings[0]["date"], "2023-06-30")
            self.assertEqual(filings[1]["date"], "2023-03-31")

            # Verify we only attempted to scrape 2 times, not 4
            self.assertEqual(mock_scrape.call_count, 2)

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_latest_two_returns_none_when_a_windowed_filing_fails_to_scrape(
        self, mock_get_request
    ):
        """
        Two filings available but one fails to scrape (e.g. 429): return None,
        not a partial list, so the caller skips the fund instead of rewriting
        every position as NEW against an empty previous quarter.
        """
        search_html = """
        <a id="documentsbutton" href="/doc1">Format</a>
        <a id="documentsbutton" href="/doc2">Format</a>
        """
        mock_search_response = MagicMock()
        mock_search_response.text = search_html
        mock_get_request.return_value = mock_search_response

        with patch("app.scraper.sec_scraper._scrape_filing") as mock_scrape:
            mock_scrape.side_effect = [{"id": 1, "date": "2023-06-30"}, None]

            filings = fetch_latest_two_13f_filings("CIK123")

            self.assertIsNone(filings)

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_latest_two_returns_single_filing_when_only_one_exists(self, mock_get_request):
        """
        A genuinely new fund with a single 13F-HR is not an error: one available
        tag that scrapes cleanly returns a one-element list.
        """
        mock_search_response = MagicMock()
        mock_search_response.text = '<a id="documentsbutton" href="/doc1">Format</a>'
        mock_get_request.return_value = mock_search_response

        with patch("app.scraper.sec_scraper._scrape_filing") as mock_scrape:
            mock_scrape.side_effect = [{"id": 1, "date": "2023-06-30"}]

            filings = fetch_latest_two_13f_filings("CIK123")

            assert filings is not None
            self.assertEqual(len(filings), 1)

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_non_quarterly_after_date(self, mock_get_request):
        """Test fetch_non_quarterly_after_date aggregates filings."""

        # Mock search page responses — must include <tr><td> with filing type for type filtering
        def make_response(filing_type_label):
            """
            Creates a mock response with the correct EDGAR table structure.
            """
            resp = MagicMock()
            resp.text = f'<tr><td>{filing_type_label}</td><td><a id="documentsbutton" href="/doc">Format</a></td></tr>'
            return resp

        mock_get_request.side_effect = [
            make_response("SC 13D"),  # SCHEDULE search
            make_response("4"),  # Form 4 search
        ]

        with patch("app.scraper.sec_scraper._scrape_filing") as mock_scrape:
            mock_scrape.return_value = {"data": "test"}

            filings = fetch_non_quarterly_after_date("CIK123", "2023-01-01")

            # Should call scrape for SCHEDULE and Form 4 (found 1 doc each in mock)
            assert filings is not None
            self.assertEqual(len(filings), 2)

    @staticmethod
    def _listing(*filing_type_labels):
        """
        Builds a mock EDGAR listing page with one documents button per filing type label.
        """
        resp = MagicMock()
        resp.text = "".join(
            f'<tr><td>{label}</td><td><a id="documentsbutton" href="/doc">Format</a></td></tr>'
            for label in filing_type_labels
        )
        return resp

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_non_quarterly_returns_none_when_a_listing_request_fails(self, mock_get_request):
        """
        A failed listing request must surface as None, not as an empty or
        partial list the caller would save over the fund's existing rows.
        """
        mock_get_request.side_effect = [self._listing("SC 13D"), None]

        with patch("app.scraper.sec_scraper._scrape_filing") as mock_scrape:
            mock_scrape.return_value = {"data": "test"}

            self.assertIsNone(fetch_non_quarterly_after_date("CIK123", "2023-01-01"))

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_non_quarterly_returns_none_when_a_listing_page_raises(self, mock_get_request):
        """
        An unexpected error while reading a listing page is a failure too.
        """
        mock_get_request.side_effect = RuntimeError("boom")

        self.assertIsNone(fetch_non_quarterly_after_date("CIK123", "2023-01-01"))

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_non_quarterly_returns_none_when_a_filing_request_fails(self, mock_get_request):
        """
        A filing whose report page cannot be downloaded must not be dropped
        silently: the whole fetch reports failure.
        """
        empty = MagicMock()
        empty.text = ""
        mock_get_request.side_effect = [self._listing("SC 13D"), empty, None]

        self.assertIsNone(fetch_non_quarterly_after_date("CIK123", "2023-01-01"))

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_non_quarterly_skips_a_filing_without_xml_document(self, mock_get_request):
        """
        A report page that downloads fine but has no XML document is a
        permanent property of that filing: it is skipped, not a failure.
        """
        empty = MagicMock()
        empty.text = ""
        report_page = MagicMock()
        report_page.text = "<div>Filing Date</div><div>2023-02-01</div>"
        mock_get_request.side_effect = [self._listing("SC 13D"), empty, report_page]

        self.assertEqual(fetch_non_quarterly_after_date("CIK123", "2023-01-01"), [])

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_non_quarterly_without_filings_returns_empty_list(self, mock_get_request):
        """
        Successful listings with no filings mean "nothing new", an empty list.
        """
        empty = MagicMock()
        empty.text = ""
        mock_get_request.return_value = empty

        self.assertEqual(fetch_non_quarterly_after_date("CIK123", "2023-01-01"), [])

    @patch("app.scraper.sec_scraper._get_request")
    def test_fetch_non_quarterly_without_start_date_returns_none(self, mock_get_request):
        """
        A missing 13F baseline date (fund page unparseable) must degrade to
        None without firing any request, not crash on None.replace.
        """
        result = fetch_non_quarterly_after_date("CIK123", None)  # type: ignore[arg-type]

        self.assertIsNone(result)
        mock_get_request.assert_not_called()

    @patch("app.scraper.sec_scraper._get_request")
    def test_get_latest_13f_filing_date(self, mock_get_request):
        """Test get_latest_13f_filing_date extracts date correctly."""
        html = """
        <tr>
            <td><a id="documentsbutton" href="/doc">Format</a></td>
            <td>Type</td>
            <td>Desc</td>
            <td>2023-05-15</td>
        </tr>
        """
        mock_response = MagicMock()
        mock_response.text = html
        mock_get_request.return_value = mock_response

        date = get_latest_13f_filing_date("CIK123")
        self.assertEqual(date, "2023-05-15")


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

    def test_reset_session_rebuilds_rate_limiter(self):
        """reset_session must replace _rate_limiter with a fresh instance and clear sessions."""
        import app.scraper.sec_scraper as scraper

        old_limiter = scraper._rate_limiter
        with scraper._sessions_lock:
            scraper._sessions[:] = [MagicMock()]

        reset_session()

        self.assertIsNot(scraper._rate_limiter, old_limiter)
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
        listing = MagicMock()
        listing.text = '<a id="documentsbutton" href="/1"></a>' * 4
        mock_get.return_value = listing
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
