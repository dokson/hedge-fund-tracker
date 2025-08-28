from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import pandas as pd
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


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
        company = info_table.find(lambda tag: tag.name.endswith('nameofissuer')).text
        cusip = info_table.find(lambda tag: tag.name.endswith('cusip')).text
        value = info_table.find(lambda tag: tag.name.endswith('value')).text
        shares = info_table.find(lambda tag: tag.name.endswith('sshprnamt')).text
        put_call_tag = info_table.find(lambda tag: tag.name.endswith('putcall'))
        put_call = put_call_tag.text if put_call_tag else ''

        data.append([
            company,
            cusip,
            value,
            shares,
            put_call
        ])

    df = pd.DataFrame(data, columns=columns)

    # Filter out options to keep only shares
    df = df[df['Put/Call'] == ''].drop('Put/Call', axis=1)

    # Filter out 0 values
    df = df[(df['Value'] != "0") & (df['Shares'] != "0")]

    # Data cleaning
    df['CUSIP'] = df['CUSIP'].str.upper()
    df['Company'] = df['Company'].str.strip().str.replace(r'\s+', ' ', regex=True)
    df['Shares'] = pd.to_numeric(df['Shares'], errors='coerce')
    df['Value'] = pd.to_numeric(df['Value'], errors='coerce')
    
    # --- Smart Value Scaling ---
    # SEC 13F-HR rules state values are in full dollar amount. Some filings, however, report the thousands.
    # We use a dual-threshold heuristic to distinguish between the two formats.
    # We assume values are in thousands and should be scaled up ONLY IF:
    # 1. The largest single position is below a certain threshold (e.g., $1M). A value of 1M in thousands would be $1B, a rare single position.
    # 2. The total portfolio value is also below a threshold (e.g., $100M, the 13F filing minimum).
    # If either of these is false, we assume the values are already in full dollars and do not scale them.
    MAX_POSITION_THRESHOLD = 1_000_000
    TOTAL_VALUE_THRESHOLD = 100_000_000

    if not df.empty and df['Value'].max() < MAX_POSITION_THRESHOLD and df['Value'].sum() < TOTAL_VALUE_THRESHOLD:
        df['Value'] = df['Value'] * 1000
        
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
        "Shares",
        "Owner",
        "Date"
    ]

    data = []

    form_data = soup_xml.find('formdata')
    company = form_data.find(lambda tag: tag.name.endswith('issuername')).text
    cusip = form_data.find(lambda tag: tag.name.endswith('issuercusip')).text
    date_tag = form_data.find(lambda tag: tag.name.endswith('dateofevent'))
    date = date_tag.text if date_tag else form_data.find(lambda tag: tag.name.endswith('eventdaterequiresfilingthisstatement'))

    for reporting_person in soup_xml.find_all('coverpageheaderreportingpersondetails') or soup_xml.find_all('reportingpersoninfo'):
        shares_tag = reporting_person.find(lambda tag: tag.name.endswith('aggregateamountowned'))
        shares = shares_tag.text.strip() if shares_tag else reporting_person.find(lambda tag: tag.name.endswith('reportingpersonbeneficiallyownedaggregatenumberofshares'))
        cik_tag = reporting_person.find(lambda tag: tag.name.endswith('reportingpersoncik'))
        owner = cik_tag.text.strip() if cik_tag else reporting_person.find(lambda tag: tag.name.endswith('reportingpersonname')).text.strip()

        data.append([company, cusip, shares, owner, date])

    df = pd.DataFrame(data, columns=columns)
    
    # Data cleaning
    df['CUSIP'] = df['CUSIP'].str.upper()
    df['Company'] = df['Company'].str.replace(r'\s+', ' ', regex=True)
    df['Shares'] = pd.to_numeric(df['Shares'], errors='coerce').astype(int)
    df['Owner'] = df['Owner'].str.upper()
    df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y', errors='coerce')

    return df
