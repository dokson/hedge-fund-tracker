from scraper.db.pd_helpers import coalesce
from scraper.string_utils import format_percentage, format_value
from scraper.ticker.resolver import resolve_ticker
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import pandas as pd
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

OUTPUT_FOLDER = './database'


def xml_to_dataframe_13f(xml_content):
    """
    Parses the XML content and returns the data as a Pandas DataFrame.
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
    Parses the XML content and returns the data as a Pandas DataFrame.
    """
    soup_xml = BeautifulSoup(xml_content, "lxml")

    columns = [
        "Company",
        "CUSIP",
        "Shares",
        "Owner"
    ]

    data = []

    for info_share in soup_xml.find_all(lambda tag: tag.name.endswith('formdata')):
        company = info_share.find('issuername').text
        cusip = info_share.find('issuercusip').text

        for reporting_person in soup_xml.find_all(lambda tag: tag.name.endswith('reportingpersoninfo')):
            owner = reporting_person.find('reportingpersoncik').text
            shares = reporting_person.find('sharedvotingpower').text

            data.append([
                company,
                cusip,
                shares,
                owner
            ])

    df = pd.DataFrame(data, columns=columns)

    # Data cleaning
    df['CUSIP'] = df['CUSIP'].str.upper()
    df['Company'] = df['Company'].str.strip().str.replace(r'\s+', ' ', regex=True)
    df['Shares'] = pd.to_numeric(df['Shares'], errors='coerce')
    df['Owner'] = df['Owner'].str.upper()

    return df


def generate_comparison(df_recent, df_previous):
    """
    Generates a comparison report between the two DataFrames, calculating percentage change and indicating new positions.
    """
    df_comparison = pd.merge(
        df_recent,
        df_previous,
        on=['CUSIP'],
        how='outer',
        suffixes=('_recent', '_previous')
    )

    df_comparison['Company'] = coalesce(df_comparison['Company_recent'], df_comparison['Company_previous'])

    df_comparison['Shares_recent'] = df_comparison['Shares_recent'].fillna(0).astype('int64')
    df_comparison['Shares_previous'] = df_comparison['Shares_previous'].fillna(0).astype('int64')
    df_comparison['Value'] = df_comparison['Value_recent'].fillna(0).astype('int64')
    df_comparison['Value_previous'] = df_comparison['Value_previous'].fillna(0).astype('int64')

    df_comparison['Price_per_Share'] = (coalesce(df_comparison['Value'] / df_comparison['Shares_recent'], df_comparison['Value_previous'] / df_comparison['Shares_previous'])).round(2)
    df_comparison['Delta_Shares'] = df_comparison['Shares_recent'] - df_comparison['Shares_previous']
    df_comparison['Delta_Value'] = (df_comparison['Delta_Shares'] * df_comparison['Price_per_Share']).fillna(0).astype(int)

    df_comparison['Delta%'] = (df_comparison['Delta_Shares'] / df_comparison['Shares_previous']) * 100

    df_comparison['Delta'] = df_comparison.apply(
        lambda row: 
        'NEW' if row['Shares_previous'] == 0
        else 'CLOSE' if row['Shares_recent'] == 0
        else 'NO CHANGE' if row['Shares_recent'] == row['Shares_previous']
        else format_percentage(row['Delta%'], True),
        axis=1
    )

    total_portfolio_value = df_comparison['Value'].sum()
    previous_portfolio_value = df_comparison['Value_previous'].sum()
    total_delta_value = total_portfolio_value - previous_portfolio_value
    total_delta = (total_delta_value / previous_portfolio_value) * 100
    
    df_comparison['Portfolio%'] = ((df_comparison['Value'] / total_portfolio_value) * 100).apply(format_percentage)
    df_comparison = resolve_ticker(df_comparison)

    df_comparison = df_comparison[['CUSIP', 'Ticker', 'Company', 'Value', 'Portfolio%', 'Delta_Value', 'Delta']] \
        .sort_values(by=['Delta_Value', 'Value'], ascending=False)

    df_comparison['Value'] = df_comparison['Value'].apply(format_value)
    df_comparison['Delta_Value'] = df_comparison['Delta_Value'].apply(format_value)

    # Add grand total row
    total_row = pd.DataFrame([{
        'CUSIP': 'Total', 
        'Ticker': '', 
        'Company': '',
        'Value': format_value(total_portfolio_value),
        'Portfolio%': format_percentage(100),
        'Delta_Value': format_value(total_delta_value),
        'Delta': format_percentage(total_delta, True)
    }])

    return pd.concat([df_comparison, total_row], ignore_index=True)
