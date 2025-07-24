import unittest
from scraper.sec_scraper import _create_search_url
from unittest.mock import patch

class TestSecScraper(unittest.TestCase):

    def test_create_url(self):
        cik = "1234567890"
        expected_url = f'https://www.sec.gov/cgi-bin/browse-edgar?CIK={cik}&owner=exclude&action=getcompany&type=13F-HR'
        self.assertEqual(_create_search_url(cik), expected_url)

if __name__ == '__main__':
    unittest.main()