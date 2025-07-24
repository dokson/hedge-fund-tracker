import pandas as pd
import requests
import re

from bs4 import BeautifulSoup
from .finnhub_client import get_cusip_to_ticker_mapping_finnhub_with_fallback

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


def generate_comparison(cik, filing_dates, df_recent, df_previous):
    """
    Generates a comparison report between the two DataFrames, calculating percentage change and indicating new positions.
    """
    df_comparison = pd.merge(
        df_recent,
        df_previous,
        on=['CUSIP', 'Name of Issuer'],
        how='outer',
        suffixes=('_recent', '_previous')
    )

    df_comparison['Shares_recent'] = df_comparison['Shares_recent'].fillna(0).astype('int64')
    df_comparison['Shares_previous'] = df_comparison['Shares_previous'].fillna(0).astype('int64')
    df_comparison['Value_recent'] = df_comparison['Value_recent'].fillna(0).astype('int64')
    df_comparison['Percentage Change'] = ((df_comparison['Shares_recent'] - df_comparison['Shares_previous']) / df_comparison['Shares_previous']) * 100
    df_comparison['Percentage Change'] = df_comparison.apply(
        lambda row:
        'NEW' if row['Shares_previous'] == 0
        else 'CLOSE' if row['Shares_recent'] == 0
        else 'NO CHANGE' if row['Shares_recent'] == row['Shares_previous']
        else '{:+.1f}%'.format(row['Percentage Change']),
        axis=1
    )

    print(f"Getting Tickers from CUSIPs using Finnhub...")
    df_comparison['Ticker'] = df_comparison['CUSIP'].map(get_cusip_to_ticker_mapping_finnhub_with_fallback(df_comparison))

    df_comparison = df_comparison[['CUSIP', 'Ticker', 'Name of Issuer', 'Value_recent', 'Shares_recent', 'Percentage Change']] \
        .rename(columns={'Shares_recent': 'Shares', 'Value_recent': 'Value'}) \
        .sort_values(by='Value', ascending=False)

    # Save the comparison to CSV
    filename = f"{cik}_{filing_dates[0]}.csv"
    df_comparison.to_csv(filename, index=False)
    print(f"Created {filename}")


if __name__ == "__main__":
    requested_cik = get_user_input()
    scrape_company(requested_cik)
