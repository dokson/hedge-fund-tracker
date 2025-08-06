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

    # Data cleaning
    df['CUSIP'] = df['CUSIP'].str.upper()
    df['Company'] = df['Company'].str.strip().str.replace(r'\s+', ' ', regex=True)
    df['Shares'] = pd.to_numeric(df['Shares'], errors='coerce')
    df['Value'] = pd.to_numeric(df['Value'], errors='coerce')

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
        "Owner"
    ]

    data = []

    form_data = soup_xml.find('formdata')
    company = form_data.find(lambda tag: tag.name.endswith('issuername')).text
    cusip = form_data.find(lambda tag: tag.name.endswith('issuercusip')).text

    for reporting_person in soup_xml.find_all('coverpageheaderreportingpersondetails') or soup_xml.find_all('reportingpersoninfo'):
        shares = reporting_person.find(lambda tag: tag.name.endswith('sharedvotingpower')).text.strip()
        cik_tag = reporting_person.find(lambda tag: tag.name.endswith('reportingpersoncik'))
        owner = cik_tag.text.strip() if cik_tag else reporting_person.find(lambda tag: tag.name.endswith('reportingpersonname')).text.strip()

        data.append([company, cusip, shares, owner])

    df = pd.DataFrame(data, columns=columns)
    
    # Data cleaning
    df['CUSIP'] = df['CUSIP'].str.upper()
    df['Company'] = df['Company'].str.replace(r'\s+', ' ', regex=True)
    df['Shares'] = pd.to_numeric(df['Shares'], errors='coerce').astype(int)
    df['Owner'] = df['Owner'].str.upper()

    return df
