from app.scraper.sec_scraper import (
    _create_search_url, _get_request, _get_accepted, _get_filing_date,
    _get_report_date, _get_primary_xml_url, _scrape_filing,
    fetch_latest_two_13f_filings, fetch_non_quarterly_after_date,
    get_latest_13f_filing_date, USER_AGENT, SEC_HOST
)
import unittest
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup
from tenacity import RetryError
import requests
import time


class TestSecScraper(unittest.TestCase):

    def setUp(self):
        # Patch time.sleep to speed up retries
        self.sleep_patcher = patch('time.sleep')
        self.mock_sleep = self.sleep_patcher.start()


    def tearDown(self):
        self.sleep_patcher.stop()


    @patch('app.scraper.sec_scraper.requests.get')
    def test_get_request_success(self, mock_get):
        """Test _get_request returns response on success."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        url = "http://test.com"
        response = _get_request(url)
        
        self.assertEqual(response, mock_response)
        mock_get.assert_called_with(url, headers={
            'User-Agent': USER_AGENT,
            'Accept-Encoding': 'gzip, deflate',
            'HOST': SEC_HOST,
        })


    @patch('app.scraper.sec_scraper.requests.get')
    def test_get_request_failure(self, mock_get):
        """Test _get_request raises RetryError on persistent failure."""
        mock_get.side_effect = requests.exceptions.RequestException("Error")
        
        url = "http://test.com"
        
        # tenacity raises RetryError after max attempts if retry_if_result returns True (for None)
        with self.assertRaises(RetryError):
            _get_request(url)


    def test_create_search_url(self):
        """Test _create_search_url generates correct URLs."""
        cik = "1234567890"
        
        # Test default 13F-HR
        expected_url = f'https://www.sec.gov/cgi-bin/browse-edgar?CIK={cik}&action=getcompany&type=13F-HR'
        self.assertEqual(_create_search_url(cik), expected_url)

        # Test with date
        date = "20230101"
        expected_url_date = f'https://www.sec.gov/cgi-bin/browse-edgar?CIK={cik}&action=getcompany&type=SCHEDULE&datea={date}'
        self.assertEqual(_create_search_url(cik, 'SCHEDULE', date), expected_url_date)


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
        soup = BeautifulSoup(html, 'html.parser')

        self.assertEqual(_get_accepted(soup), "2023-01-01 10:00:00")
        self.assertEqual(_get_filing_date(soup), "2023-01-02")
        self.assertEqual(_get_report_date(soup), "2022-12-31")
        
        # Test 13F-HR (index 3)
        # In our mock HTML, index 3 is target.xml
        self.assertEqual(_get_primary_xml_url(soup, '13F-HR'), 'https://www.sec.gov/Archives/edgar/data/123/000/target.xml')
        
        # Test SCHEDULE (index 1)
        # In our mock HTML, index 1 is xsl.xml
        self.assertEqual(_get_primary_xml_url(soup, 'SCHEDULE'), 'https://www.sec.gov/Archives/edgar/data/123/000/xsl.xml')


    @patch('app.scraper.sec_scraper._get_request')
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

        document_tag = {'href': '/report_page'}
        result = _scrape_filing(document_tag, '13F-HR')

        self.assertIsNotNone(result)
        self.assertEqual(result['date'], '2023-01-02')
        self.assertEqual(result['accepted_on'], '2023-01-01')
        self.assertEqual(result['type'], '13F-HR')
        self.assertEqual(result['reference_date'], '2022-12-31')
        self.assertEqual(result['xml_content'], b"<xml>content</xml>")


    @patch('app.scraper.sec_scraper._get_request')
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

        with patch('app.scraper.sec_scraper._scrape_filing') as mock_scrape:
            # Mock return values for the first 2 calls. 
            # Note: The code slices [offset:offset+2] BEFORE scraping. 
            # So it will only scrape doc1 and doc2.
            # We give them dates to verify sorting (doc1 is older, doc2 is newer).
            mock_scrape.side_effect = [
                {'id': 1, 'date': '2023-01-01'}, # doc1
                {'id': 2, 'date': '2023-01-05'}  # doc2
            ]

            filings = fetch_latest_two_13f_filings('CIK123')
            
            # Verify we only got 2 results
            self.assertEqual(len(filings), 2)
            
            # Verify sorting: newest date (2023-01-05) should be first
            self.assertEqual(filings[0]['date'], '2023-01-05')
            self.assertEqual(filings[1]['date'], '2023-01-01')
            
            # Verify we only attempted to scrape 2 times, not 4
            self.assertEqual(mock_scrape.call_count, 2)


    @patch('app.scraper.sec_scraper._get_request')
    def test_fetch_non_quarterly_after_date(self, mock_get_request):
        """Test fetch_non_quarterly_after_date aggregates filings."""
        # Mock search page responses for SCHEDULE and Form 4
        mock_response = MagicMock()
        mock_response.text = '<a id="documentsbutton" href="/doc">Format</a>'
        mock_get_request.return_value = mock_response

        with patch('app.scraper.sec_scraper._scrape_filing') as mock_scrape:
            mock_scrape.return_value = {'data': 'test'}
            
            filings = fetch_non_quarterly_after_date('CIK123', '2023-01-01')
            
            # Should call scrape for SCHEDULE and Form 4 (found 1 doc each in mock)
            self.assertEqual(len(filings), 2)

    @patch('app.scraper.sec_scraper._get_request')
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

        date = get_latest_13f_filing_date('CIK123')
        self.assertEqual(date, '2023-05-15')


if __name__ == '__main__':
    unittest.main()