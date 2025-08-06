from app.utils.strings import get_next_yyyymmdd_day
from bs4 import BeautifulSoup
import requests
import re

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36'
SEC_HOST = 'www.sec.gov'
SEC_URL = 'https://' + SEC_HOST

FILING_SPECS = {
    '13F-HR': {
        'xml_link_index': 3
    },
    'SCHEDULE': {
        'xml_link_index': 1
    }
}


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


def _create_search_url(cik, filing_type='13F-HR', start_date=None):
    """
    Creates the SEC EDGAR search URL for a given CIK and filing type.
    """
    search_url = f'{SEC_URL}/cgi-bin/browse-edgar?CIK={cik}&owner=exclude&action=getcompany&type={filing_type}'

    if start_date:
        search_url += f'&datea={start_date}'

    return search_url


def _get_filing_date(report_page_soup):
    """
    Extracts the filing date from the report page's soup.
    """
    try:
        filing_date_tag = report_page_soup.find('div', string=re.compile(r'Filing Date'))
        if filing_date_tag:
            return filing_date_tag.find_next().text.strip()
    except Exception as e:
        print(f"Error extracting filing date: {e}")
    return None


def _get_primary_xml_url(report_page_soup, filing_type):
    """
    Finds the link to the primary XML data file from the report page's soup.
    Uses the configuration based on filing type.
    """
    try:
        config = FILING_SPECS.get(filing_type)      
        tags = report_page_soup.findAll('a', attrs={'href': re.compile('xml')})

        xml_link_index = config['xml_link_index']
        if len(tags) > xml_link_index:
            return SEC_URL + tags[xml_link_index].get('href')
    except Exception as e:
        print(f"Error finding XML URL for filing type {filing_type}: {e}")
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
    report_page_url = SEC_URL + document_tag['href']
    report_page_response = _get_request(report_page_url)
    if not report_page_response:
        return None

    report_page_soup = BeautifulSoup(report_page_response.text, "html.parser")
    filing_date = _get_filing_date(report_page_soup)
    xml_url = _get_primary_xml_url(report_page_soup, filing_type)

    if not (filing_date and xml_url):
        print(f"Could not get metadata for report page {report_page_url}")
        return None

    xml_response = _get_request(xml_url)
    if not xml_response:
        print(f"Failed to download XML from {xml_url}")
        return None

    print(f"Successfully scraped {filing_type} report for {filing_date}")
    return {
        'date': filing_date,
        'xml_content': xml_response.content
    }


def fetch_latest_two_13f_filings(cik, offset=0):
    """
    Fetches the raw XML content and filing dates for the two most recent 13F-HR filings for a given CIK.
    Returns a list of dictionaries, or None if an error occurs.
    """
    search_url = _create_search_url(cik, '13F-HR')
    response = _get_request(search_url)
    if not response:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    document_tags = soup.find_all('a', id="documentsbutton")

    if not document_tags:
        print(f"No 13F-HR documents found for CIK: {cik}")
        return None

    filings = []
    for tag in document_tags[offset:offset+2]:
        filing_data = _scrape_filing(tag, '13F-HR')
        if filing_data:
            filings.append(filing_data)

    return filings


def fetch_schedule_filings_after_date(cik, start_date):
    """
    Fetches the raw content and filing dates for the latest schedule filings for a given CIK.
    Returns a list of dictionaries, or None if an error occurs.
    """
    yyyymmdd_date = start_date.replace('-', '')
    search_url = _create_search_url(cik, 'SCHEDULE', get_next_yyyymmdd_day(yyyymmdd_date))
    response = _get_request(search_url)
    if not response:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    document_tags = soup.find_all('a', id="documentsbutton")

    if not document_tags:
        print(f"No schedule documents found for CIK: {cik}")
        return None

    filings = []
    for tag in document_tags:
        filing_data = _scrape_filing(tag, 'SCHEDULE')
        if filing_data:
            filings.append(filing_data)

    return filings
