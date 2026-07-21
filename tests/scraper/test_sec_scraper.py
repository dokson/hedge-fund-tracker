import threading
import unittest
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup
from curl_cffi import requests
from curl_cffi.requests.exceptions import HTTPError, RequestException
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

    @patch("app.scraper.sec_scraper._get_session")
    def test_get_request_success(self, mock_get_session):
        """Test _get_request returns response on success."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get_session.return_value.get.return_value = mock_response

        url = "http://test.com"
        response = _get_request(url)

        self.assertEqual(response, mock_response)
        mock_get_session.return_value.get.assert_called_with(url, timeout=15)

    @patch("app.scraper.sec_scraper._rate_limiter")
    @patch("app.scraper.sec_scraper._get_session")
    def test_get_request_acquires_rate_limiter_before_request(self, mock_get_session, mock_limiter):
        """
        Each network call must acquire a token first so parallel workers stay
        within SEC EDGAR's per-host budget. Regression guard: if a future
        refactor drops the acquire() call, this test fails.
        """
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get_session.return_value.get.return_value = mock_response

        _get_request("http://test.com")

        mock_limiter.acquire.assert_called_once()

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

    def test_close_session_is_idempotent(self):
        """Calling close_session twice must not raise."""
        close_session()
        close_session()  # should not raise

    def test_reset_session_rebuilds_rate_limiter(self):
        """reset_session must replace _rate_limiter with a fresh instance and clear sessions."""
        import app.scraper.sec_scraper as scraper

        old_limiter = scraper._rate_limiter
        with scraper._sessions_lock:
            scraper._sessions[:] = [MagicMock()]

        reset_session()

        self.assertIsNot(scraper._rate_limiter, old_limiter)
        self.assertEqual(scraper._sessions, [])

    def test_scraper_session_closes_on_exit(self):
        """scraper_session() context manager must close registered sessions on exit."""
        import app.scraper.sec_scraper as scraper

        s = MagicMock()
        with scraper._sessions_lock:
            scraper._sessions[:] = [s]

        with scraper_session():
            pass
        s.close.assert_called_once()

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

    def test_reset_produces_a_usable_session(self):
        """
        After reset, _get_session() must return a live Session carrying the SEC
        headers, and _get_request must still wire through the rate limiter.
        """
        import app.scraper.sec_scraper as scraper

        reset_session()

        session = scraper._get_session()
        self.assertIsInstance(session, requests.Session)
        self.assertIn("User-Agent", session.headers)

        with (
            patch.object(scraper, "_get_session", return_value=MagicMock()) as mock_get_session,
            patch.object(scraper._rate_limiter, "acquire") as mock_acquire,
        ):
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_get_session.return_value.get.return_value = mock_response

            _get_request("http://test.com")

            mock_acquire.assert_called_once()
            mock_get_session.return_value.get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
