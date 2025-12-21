from app.tickers.resolver import assign_cusip
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import pandas as pd
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


def _get_tag_text(element, tag_suffix):
    """
    Safely find a tag by its suffix and return its stripped text, or None.
    """
    if not element:
        return None
    tag = element.find(lambda t: t.name.endswith(tag_suffix))
    if tag:
        value_tag = tag.find('value')
        if value_tag:
            return value_tag.text.strip()
        else:
            return tag.text.strip()
    else:
        return None


def xml_to_dataframe_13f(xml_content):
    """
    Parses the XML content of a 13F filing and returns the data as a Pandas DataFrame.
    """
    soup_xml = BeautifulSoup(xml_content, "lxml")

    columns = [
        "Company",
        "CUSIP",
        "Value",
        "Shares",
        "Put/Call"
    ]

    data = []

    for info_table in soup_xml.find_all(lambda tag: tag.name.endswith('infotable')):
        company = _get_tag_text(info_table, 'nameofissuer')
        cusip = _get_tag_text(info_table, 'cusip')
        value = _get_tag_text(info_table, 'value')
        shares = _get_tag_text(info_table, 'sshprnamt')
        put_call = _get_tag_text(info_table, 'putcall') or ''

        data.append([company, cusip, value, shares, put_call])

    df = pd.DataFrame(data, columns=columns)

    # Filter out options to keep only shares
    df = df[df['Put/Call'] == ''].drop('Put/Call', axis=1)

    # Filter out 0 values
    df = df[(df['Value'] != "0") & (df['Shares'] != "0")]

    # Data cleaning
    df['Company'] = df['Company'].str.strip().str.replace(r'\s+', ' ', regex=True)
    df['CUSIP'] = df['CUSIP'].str.upper()
    df['Value'] = pd.to_numeric(df['Value'], errors='coerce')
    df['Shares'] = pd.to_numeric(df['Shares'], errors='coerce').astype(int)
    
    # --- Smart Value Scaling (Heuristic-based) ---
    # SEC rules for XML filings technically require full dollar amounts, but many funds still report in thousands, while others use full dollars.
    # THRESHOLD: If the median stock price in the portfolio is below $0.50, it is mathematically certain the filing is reported in thousands.
    # Most institutional holdings trade between $10 and $1000. In 'thousands' format, a $100 stock appears as $0.10.
    implied_prices = df['Value'] / df['Shares'].replace(0, pd.NA)
    median_price = float(implied_prices.median())
    PRICE_THRESHOLD = 0.50

    if median_price < PRICE_THRESHOLD:
        # Case: Filing in thousands -> Scale up to full dollars
        df['Value'] = df['Value'] * 1000
    else:
        # Case: Filing already in full dollars
        pass

    # Dedup by CUSIP
    df = df.groupby(['CUSIP'], as_index=False).agg({
        'Company': 'max',
        'Value': 'sum',
        'Shares': 'sum'
    })

    return df


def xml_to_dataframe_schedule(xml_content):
    """
    Parses the XML content of a Schedule 13G/D filing and returns the data as a Pandas DataFrame.
    """
    soup_xml = BeautifulSoup(xml_content, "lxml")

    columns = [
        "Company",
        "CUSIP",
        "CIK",
        "Shares",
        "Owner_CIK",
        "Owner",
        "Date"
    ]

    data = []

    form_data = soup_xml.find('formdata')
    company = _get_tag_text(form_data, 'issuername')
    cusip = _get_tag_text(form_data, 'issuercusip')
    cik = _get_tag_text(form_data, 'issuercik')
    date = _get_tag_text(form_data, 'dateofevent') or _get_tag_text(form_data, 'eventdaterequiresfilingthisstatement')

    for reporting_person in soup_xml.find_all('coverpageheaderreportingpersondetails') or soup_xml.find_all('reportingpersoninfo'):
        shares = _get_tag_text(reporting_person, 'aggregateamountowned') or \
                 _get_tag_text(reporting_person, 'reportingpersonbeneficiallyownedaggregatenumberofshares')
        owner_cik = _get_tag_text(reporting_person, 'rptownercik')
        owner_name = _get_tag_text(reporting_person, 'reportingpersonname')

        data.append([company, cusip, cik, shares, owner_cik, owner_name, date])

    df = pd.DataFrame(data, columns=columns)
    
    # Data cleaning
    df['Company'] = df['Company'].str.replace(r'\s+', ' ', regex=True)
    df['CUSIP'] = df['CUSIP'].str.upper()
    df['CIK'] = df['CIK'].str.strip()
    df['Shares'] = pd.to_numeric(df['Shares'], errors='coerce').fillna(0).astype(int)
    df['Owner_CIK'] = df['Owner_CIK'].str.strip()
    df['Owner'] = df['Owner'].str.upper()
    df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y', errors='coerce')

    return df


def xml_to_dataframe_4(xml_content):
    """
    Parses the XML content of a Form 4 filing and returns the data as a Pandas DataFrame.
    It correctly extracts the final share ownership for each reporting owner.
    """
    soup_xml = BeautifulSoup(xml_content, "lxml")

    columns = [
        "Company",
        "Ticker",
        "CIK",
        "Shares",
        "Owner_CIK",
        "Owner",
        "Date"
    ]
    data = []

    issuer = soup_xml.find('issuer')
    company = _get_tag_text(issuer, 'issuername')
    ticker = _get_tag_text(issuer, 'issuertradingsymbol')
    cik = _get_tag_text(issuer, 'issuercik')
    date = _get_tag_text(soup_xml, 'periodofreport')

    owner_shares = {}

    def process_item(item):
        """
        Helper to extract holding info from a transaction or holding tag.
        """
        shares_post = float(_get_tag_text(item, 'sharesownedfollowingtransaction'))
        ownership_nature = item.find('ownershipnature')
        direct_indirect = _get_tag_text(ownership_nature, 'directorindirectownership')
        nature_of_ownership = _get_tag_text(ownership_nature, 'natureofownership') or "Direct"
        
        key = (str(direct_indirect).strip().upper(), str(nature_of_ownership).strip().upper())
        owner_shares[key] = shares_post

    non_derivative_table = soup_xml.find('nonderivativetable')
    if non_derivative_table:
        for child in non_derivative_table.children:
            if child.name and 'nonderivativetransaction' in child.name:
                process_item(child)
            elif child.name and 'nonderivativeholding' in child.name:
                process_item(child)

    total_shares = int(sum(owner_shares.values()))

    for reporting_person in soup_xml.find_all('reportingowner'):
        owner_cik = _get_tag_text(reporting_person, 'rptownercik')
        owner_name = _get_tag_text(reporting_person, 'rptownername')

        data.append([company, ticker, cik, total_shares, owner_cik, owner_name, date])

    df = pd.DataFrame(data, columns=columns)

    # Data cleaning
    df['Company'] = df['Company'].str.replace(r'\s+', ' ', regex=True)
    df['Ticker'] = df['Ticker'].str.replace(r'[^a-zA-Z0-9]', '', regex=True).str.upper()
    df['CIK'] = df['CIK'].str.strip()
    df['Shares'] = pd.to_numeric(df['Shares'], errors='coerce').fillna(0).astype(int)
    df['Owner_CIK'] = df['Owner_CIK'].str.strip()
    df['Owner'] = df['Owner'].str.upper()
    df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d', errors='coerce')

    return assign_cusip(df)
