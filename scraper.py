import pandas as pd
import finnhub
import requests
import re
import time
from bs4 import BeautifulSoup


def load_api_key_from_env(file_path='.env'):
    """Loads the Finnhub API key from a .env text file."""
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    if key.strip() == 'FINNHUB_API_KEY':
                        return value.strip().strip('"\'')
    except Exception as e:
        print(f"Error reading credential file '{file_path}': {e}")
    return None


FINNHUB_API_KEY = load_api_key_from_env()
if not FINNHUB_API_KEY:
    print("ERROR: Could not find FINNHUB_API_KEY. Please create a '.env' file with the line: FINNHUB_API_KEY=\"your_key_here\"")
    exit()

FINNHUB_CLIENT = finnhub.Client(api_key=FINNHUB_API_KEY)
FINNHUB_TIMEOUT = 0.1

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36'
SEC_URL = 'https://www.sec.gov'


def get_request(url):
    """
    Sends a GET request to the specified URL with custom headers.
    """
    headers = {
        'User-Agent': USER_AGENT,
        'Accept-Encoding': 'gzip, deflate, br',
        'HOST': 'www.sec.gov',
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None


def create_url(cik):
    """
    Creates the SEC EDGAR URL for a given CIK.
    """
    return f'{SEC_URL}/cgi-bin/browse-edgar?CIK={cik}&owner=exclude&action=getcompany&type=13F-HR'


def get_user_input():
    """
    Prompts the user for a 10-digit CIK number.
    """
    cik = input("Enter 10-digit CIK number: ")
    return cik


def get_filing_date(report_url):
    """
    Extracts the filing date from the report URL.
    """
    try:
        response = get_request(report_url)
        if response is None:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        filing_date_tag = soup.find('div', string=re.compile(r'Filing Date'))
        if filing_date_tag:
            filing_date = filing_date_tag.find_next().text.strip()
            return filing_date
        else:
            print(f"Filing date not found on page: {report_url}")
            return None
    except Exception as e:
        print(f"Error extracting filing date: {e}")
        return None


def scrape_company(requested_cik):
    """
    Scrapes the 13F reports for a given CIK from the SEC EDGAR database.
    """
    url = create_url(requested_cik)
    response = get_request(url)

    if response is None:
        return

    soup = BeautifulSoup(response.text, "html.parser")
    document_tags = soup.find_all('a', id="documentsbutton")

    if not document_tags:
        print(f"No documents found for CIK: {requested_cik}")
        return

    report_data = []
    filing_dates = []

    for i, tag in enumerate(document_tags[:2]):
        report_url = SEC_URL + tag['href']
        filing_date = get_filing_date(report_url)
        if filing_date:
            print(f"Scraping report for {filing_date}")
            filing_dates.append(filing_date)
            report_data.append(scrape_report_by_url(report_url))
        else:
            print(f"Could not determine filing date for {report_url}.")

    if len(report_data) == 2:
        generate_comparison(requested_cik, filing_dates, report_data[0], report_data[1])
    elif len(report_data) == 1:
        print("Only one report found, cannot generate comparison.")
    else:
        print("No reports found.")


def scrape_report_by_url(url):
    """
    Scrapes the 13F report from a given URL and saves the data to a CSV file.
    """
    response = get_request(url)
    if response is None:
        return

    soup = BeautifulSoup(response.text, "html.parser")
    tags = soup.findAll('a', attrs={'href': re.compile('xml')})
    xml_url = tags[3].get('href')

    response_xml = get_request(SEC_URL + xml_url)
    if response_xml is None:
        print(f"Failed to get XML response from {SEC_URL + xml_url}")
        return None

    soup_xml = BeautifulSoup(response_xml.content, "lxml")
    return xml_to_dataframe(soup_xml)


def xml_to_dataframe(soup_xml):
    """
    Parses the XML content and returns the data as a Pandas DataFrame.
    """
    columns = [
        "Name of Issuer",
        "CUSIP",
        "Value",
        "Shares",
        "Put/Call"
    ]

    data = []

    for info_table in soup_xml.find_all('infotable'):
        issuer = info_table.find('nameofissuer').text
        cusip = info_table.find('cusip').text
        value = info_table.find('value').text
        shares = info_table.find('sshprnamt').text
        put_call = info_table.find('putcall').text if info_table.find('putcall') else ''

        data.append([
            issuer,
            cusip,
            value,
            shares,
            put_call
        ])

    df = pd.DataFrame(data, columns=columns)

    # Filter out options to keep only shares
    df = df[df['Put/Call'] == ''].drop('Put/Call', axis=1)

    # Convert numeric columns and handle errors
    df['Shares'] = pd.to_numeric(df['Shares'], errors='coerce')
    df['Value'] = pd.to_numeric(df['Value'], errors='coerce')

    # Sum both value and shares by CUSIP
    df = df.groupby(['CUSIP', 'Name of Issuer'], as_index=False).agg({
        'Value': 'sum',
        'Shares': 'sum'
    })

    return df


def _find_ticker_in_finnhub_response(response_data):
    """
    Helper function to extract the ticker from Finnhub's symbol_lookup response.
    Prioritizes Common Stock/Equity.
    """
    if response_data and 'result' in response_data and len(response_data['result']) > 0:
        # Prioritize Common Stock/Equity for better accuracy
        for item in response_data['result']:
            if 'symbol' in item and 'type' in item and item['type'] in ['Common Stock', 'Equity', 'STOCK']:
                return item['symbol']
        # Fallback to the first result if no common stock is found
        if 'symbol' in response_data['result'][0]:
            return response_data['result'][0]['symbol']
    return None


def _finnhub_lookup_with_retry(query, max_retries=3, backoff_factor=1):
    """
    Performs a symbol lookup with the Finnhub API, with retries for 429 errors.
    """
    for attempt in range(max_retries):
        try:
            response = FINNHUB_CLIENT.symbol_lookup(query)
            time.sleep(FINNHUB_TIMEOUT)
            return response
        except finnhub.FinnhubAPIException as e:
            if '429' in str(e):
                if attempt < max_retries - 1:
                    wait_time = backoff_factor * (2 ** attempt)
                    print(
                        f"Finnhub API rate limit hit. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print(
                        f"Finnhub API rate limit hit. Max retries reached for query '{query}'.")
                    return None
            else:
                print(f"Finnhub API error for query '{query}': {e}")
                return None
        except Exception as e:
            print(
                f"An unexpected error occurred during Finnhub request for query '{query}': {e}")
            return None
    return None


def get_ticker_with_finnhub_fallback(cusip, issuer_name):
    """
    Attempts to get the ticker from Finnhub.io, first using the CUSIP,
    then falling back to the issuer name if the CUSIP finds nothing.
    Uses a retry mechanism for API rate limits.
    """
    # 1. Try with CUSIP
    response = _finnhub_lookup_with_retry(cusip)
    ticker = _find_ticker_in_finnhub_response(response)
    # 2. Fallback to full issuer name (truncated)
    if pd.isna(ticker) and issuer_name:
        response = _finnhub_lookup_with_retry(issuer_name[:20])
        ticker = _find_ticker_in_finnhub_response(response)
    # 3. Fallback to the first word of the issuer name
    if pd.isna(ticker) and issuer_name:
        first_word = issuer_name.split(' ')[0]
        # Block very common words
        if len(first_word) > 2 and first_word.lower() not in ['the', 'corp', 'inc', 'group', 'ltd', 'co']:
            response = _finnhub_lookup_with_retry(first_word)
            ticker = _find_ticker_in_finnhub_response(response)
    if pd.isna(ticker):
        print(
            f"Finnhub: No ticker found for CUSIP {cusip} / Issuer Name '{issuer_name}'.")
    return ticker


def get_cusip_to_ticker_mapping_finnhub_with_fallback(df_comparison):
    """
    Maps CUSIPs to tickers using Finnhub, with a fallback to the issuer name.
    Takes the entire comparison DataFrame as input to access both CUSIP and Name of Issuer.
    """
    mapped_tickers = pd.Series(
        index=df_comparison['CUSIP'].unique(), dtype=object)

    for index, row in df_comparison.iterrows():
        cusip = row['CUSIP']
        issuer_name = row['Name of Issuer']

        if cusip in mapped_tickers.index and pd.notna(mapped_tickers.loc[cusip]):
            continue

        ticker = get_ticker_with_finnhub_fallback(cusip, issuer_name)
        mapped_tickers.loc[cusip] = ticker

    return mapped_tickers


def generate_comparison(cik, filing_dates, df_recent, df_previous):
    """
    Generates a comparison report between the two DataFrames, calculating percentage change and indicating new positions.
    """
    df_recent = df_recent.set_index('CUSIP')
    df_previous = df_previous.set_index('CUSIP')

    df_comparison = df_recent.join(df_previous[['Shares']], lsuffix='_recent', rsuffix='_previous', how='left')
    df_comparison['Shares_previous'] = df_comparison['Shares_previous'].fillna(0)
    df_comparison['Percentage Change'] = ((df_comparison['Shares_recent'] - df_comparison['Shares_previous']) / df_comparison['Shares_previous']) * 100
    df_comparison['Percentage Change'] = df_comparison.apply(
        lambda row:
        'NEW' if row['Shares_previous'] == 0
        else 'NO CHANGE' if row['Shares_recent'] == row['Shares_previous']
        else '{:+.1f}%'.format(row['Percentage Change']),
        axis=1
    )

    df_comparison = df_comparison.reset_index()

    print(f"Getting Tickers from CUSIPs using Finnhub...")
    df_comparison['Ticker'] = df_comparison['CUSIP'].map(get_cusip_to_ticker_mapping_finnhub_with_fallback(df_comparison))

    df_comparison = df_comparison[['CUSIP', 'Ticker', 'Name of Issuer', 'Value', 'Shares_recent', 'Percentage Change']] \
        .rename(columns={'Shares_recent': 'Shares'}) \
        .sort_values(by='Value', ascending=False)

    # Save the comparison to CSV
    filename = f"{cik}_{filing_dates[0]}.csv"
    df_comparison.to_csv(filename, index=False)
    print(f"Created {filename}")


if __name__ == "__main__":
    requested_cik = get_user_input()
    scrape_company(requested_cik)
