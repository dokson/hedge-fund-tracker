import requests
import re
from bs4 import BeautifulSoup

# Constants for SEC interaction
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36'
SEC_HOST = 'www.sec.gov'
SEC_URL = 'https://' + SEC_HOST


def _get_request(url):
    """Sends a GET request to the specified URL with custom headers."""
    headers = {
        'User-Agent': USER_AGENT,
        'Accept-Encoding': 'gzip, deflate, br',
        'HOST': SEC_HOST,
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"Request failed for {url}: {e}")
        return None


def _create_search_url(cik):
    """Creates the SEC EDGAR search URL for a given CIK."""
    return f'{SEC_URL}/cgi-bin/browse-edgar?CIK={cik}&owner=exclude&action=getcompany&type=13F-HR'


def _get_filing_date(report_page_soup):
    """Extracts the filing date from the report page's soup."""
    try:
        filing_date_tag = report_page_soup.find(
            'div', string=re.compile(r'Filing Date'))
        if filing_date_tag:
            return filing_date_tag.find_next().text.strip()
    except Exception as e:
        print(f"Error extracting filing date: {e}")
    return None


def _get_xml_url_from_report_page(report_page_soup):
    """Finds the link to the primary XML data file from the report page's soup."""
    try:
        # The primary XML is usually the 4th link matching this pattern
        tags = report_page_soup.findAll('a', attrs={'href': re.compile('xml')})
        if len(tags) > 3:
            return SEC_URL + tags[3].get('href')
    except Exception as e:
        print(f"Error finding XML URL: {e}")
    return None


def fetch_latest_two_filings(cik):
    """
    Fetches the raw XML content and filing dates for the two most recent 13F-HR filings for a given CIK.
    Returns a list of dictionaries, or None if an error occurs.
    """
    search_url = _create_search_url(cik)
    response = _get_request(search_url)
    if not response:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    document_tags = soup.find_all('a', id="documentsbutton")

    if not document_tags:
        print(f"No 13F-HR documents found for CIK: {cik}")
        return None

    filings = []
    for tag in document_tags[:2]:
        report_page_url = SEC_URL + tag['href']
        report_page_response = _get_request(report_page_url)
        if not report_page_response:
            continue

        report_page_soup = BeautifulSoup(report_page_response.text, "html.parser")
        filing_date = _get_filing_date(report_page_soup)
        xml_url = _get_xml_url_from_report_page(report_page_soup)

        if not (filing_date and xml_url):
            print(f"Could not get metadata for report page {report_page_url}")
            continue

        xml_response = _get_request(xml_url)
        if not xml_response:
            print(f"Failed to download XML from {xml_url}")
            continue

        filings.append({
            'date': filing_date,
            'xml_content': xml_response.content
        })
        print(f"Successfully scraped report for {filing_date}")

    return filings