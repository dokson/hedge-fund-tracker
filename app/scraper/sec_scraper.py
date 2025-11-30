from app.utils.strings import get_next_yyyymmdd_day
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, retry_if_result, wait_exponential, RetryError
import concurrent.futures
import requests
import re

# SEC EDGAR requires a custom User-Agent that identifies the application and provides a contact email.
# See: https://www.sec.gov/os/developer-support-policy
USER_AGENT = 'Hedge Fund Tracker dok.son@msn.com'
SEC_HOST = 'www.sec.gov'
SEC_URL = 'https://' + SEC_HOST

FILING_SPECS = {
    '13F-HR': {
        'xml_link_index': 3
    },
    'SCHEDULE': {
        'xml_link_index': 1
    },
    '4': {
        'xml_link_index': 1
    },
}


@retry(
    retry=retry_if_result(lambda value: value is None),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    stop=stop_after_attempt(5),
    before_sleep=lambda rs: print(f"Retrying request for '{rs.args[0]}' in {rs.next_action.sleep:.0f}s... (Attempt #{rs.attempt_number})")
)
def _get_request(url):
    """
    Sends a GET request to the specified URL with custom headers.
    Retries on failure.
    """
    headers = {
        'User-Agent': USER_AGENT,
        'Accept-Encoding': 'gzip, deflate',
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
    search_url = f'{SEC_URL}/cgi-bin/browse-edgar?CIK={cik}&action=getcompany&type={filing_type}'

    if start_date:
        search_url += f'&datea={start_date}'

    return search_url


def _get_accepted(report_page_soup):
    """
    Extracts the accepted time from the report page's soup.
    """
    try:
        filing_date_tag = report_page_soup.find('div', string=re.compile(r'Accepted'))
        if filing_date_tag:
            return filing_date_tag.find_next().text.strip()
    except Exception as e:
        print(f"Error extracting filing accepted time: {e}")
    return None


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


def _get_report_date(report_page_soup):
    """
    Extracts the report date from the report page's soup.
    """
    try:
        report_date_tag = report_page_soup.find('div', string=re.compile(r'Period of Report'))
        if report_date_tag:
            return report_date_tag.find_next().text.strip()
    except Exception as e:
        print(f"Error extracting report date: {e}")
    return None


def _get_primary_xml_url(report_page_soup, filing_type):
    """
    Finds the link to the primary XML data file from the report page's soup.
    Uses the configuration based on filing type.
    """
    try:
        config = FILING_SPECS.get(filing_type)      
        tags = report_page_soup.find_all('a', attrs={'href': re.compile('xml')})

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
    try:
        report_page_response = _get_request(report_page_url)
        if not report_page_response:
            return None
    except RetryError as e:
        print(f"❌ Failed to fetch report page {report_page_url} after multiple retries.")
        return None

    report_page_soup = BeautifulSoup(report_page_response.text, "html.parser")
    filing_date = _get_filing_date(report_page_soup)
    report_date = _get_report_date(report_page_soup)
    accepted = _get_accepted(report_page_soup)
    xml_url = _get_primary_xml_url(report_page_soup, filing_type)

    if not (filing_date and xml_url):
        print(f"Could not get metadata for report page {report_page_url}")
        return None

    try:
        xml_response = _get_request(xml_url)
        if not xml_response:
            print(f"Failed to download XML from {xml_url}")
            return None
    except RetryError as e:
        print(f"❌ Failed to fetch XML file {xml_url} after multiple retries.")
        return None

    print(f"Successfully scraped {filing_type} filing published on {filing_date}" + (f" (refering {report_date})" if filing_type == '13F-HR' else ""))
    return {
        'date': filing_date,
        'accepted_on': accepted,
        'type': filing_type,
        'reference_date': report_date,
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
        print(f"No 13F-HR filings found for CIK: {cik}")
        return None

    filings = []
    for tag in document_tags[offset:offset+2]:
        filing_data = _scrape_filing(tag, '13F-HR')
        if filing_data:
            filings.append(filing_data)

    return filings


def fetch_non_quarterly_after_date(cik: str, start_date: str) -> list[dict] | None:
    """
    Fetches the raw content and filing dates for the latest schedule (13D/G) and Form 4 filings for a given CIK.
    Returns a list of dictionaries, or None if an error occurs.
    """
    filings = []
    yyyymmdd_date = start_date.replace('-', '')

    # Helper to fetch tags for a specific type
    def get_tags(filing_type):
        url = _create_search_url(cik, filing_type, get_next_yyyymmdd_day(yyyymmdd_date))
        try:
            resp = _get_request(url)
            if not resp:
                print(f"❌ Could not fetch {filing_type} filings for CIK {cik} (request failed)")
                return []
            soup = BeautifulSoup(resp.text, "html.parser")
            return [(tag, filing_type) for tag in soup.find_all('a', id="documentsbutton")]
        except Exception as e:
            print(f"❌ Error fetching {filing_type} filings for CIK {cik}: {e}")
            return []

    all_tags = []
    all_tags.extend(get_tags('SCHEDULE'))
    all_tags.extend(get_tags('4'))

    if not all_tags:
        print(f"No non-quarterly filings found for CIK: {cik} after {start_date}")
        return filings

    # Parallel execution
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(_scrape_filing, tag, f_type) 
            for tag, f_type in all_tags
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                filings.append(result)

    return filings


def get_latest_13f_filing_date(cik: str) -> str:
    """
    Fetches and gets only the filing date of the most recent 13F-HR filing for a given CIK.

    Args:
        cik (str): The CIK of the hedge fund.

    Returns:
        str: The filing date in 'YYYY-MM-DD' format
    """
    search_url = _create_search_url(cik, '13F-HR')
    response = _get_request(search_url)

    if not response:
        print(f"Failed to get latest filing date for CIK {cik} because request failed.")
        return None

    try:
        soup = BeautifulSoup(response.text, "html.parser")
        button = soup.find('a', id="documentsbutton")
        if not button:
            print(f"No 'documentsbutton' found for CIK {cik} on page {search_url}")
            return None
        
        # The filing date is in the 4th <td> of the same <tr> as the button
        filing_date = button.find_parent('tr').find_all('td')[3].text.strip()
        return filing_date
    except (AttributeError, IndexError) as e:
        print(f"Error parsing filing date for CIK {cik}: {e}. Page structure may have changed.")
        return None
