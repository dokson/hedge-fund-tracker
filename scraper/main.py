from bs4 import BeautifulSoup
from .finnhub_client import get_cusip_to_ticker_mapping_finnhub_with_fallback
from .pandas import coalesce, pd
from .sec_scraper import fetch_latest_two_filings


def get_user_input():
    """
    Prompts the user for a 10-digit CIK number.
    """
    cik = input("Enter 10-digit CIK number: ")
    return cik


def xml_to_dataframe(xml_content):
    """
    Parses the XML content and returns the data as a Pandas DataFrame.
    """
    soup_xml = BeautifulSoup(xml_content, "xml")

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
    df_comparison['Value_previous'] = df_comparison['Value_previous'].fillna(0).astype('int64')

    df_comparison['Price_per_Share'] = (coalesce(df_comparison['Value_recent'] / df_comparison['Shares_recent'], df_comparison['Value_previous'] / df_comparison['Shares_previous'])).round(2)
    df_comparison['Delta_Shares'] = df_comparison['Shares_recent'] - df_comparison['Shares_previous']
    df_comparison['Delta_Value'] = (df_comparison['Delta_Shares'] * df_comparison['Price_per_Share']).fillna(0).astype(int)

    df_comparison['Delta_%'] = (df_comparison['Delta_Shares'] / df_comparison['Shares_previous']) * 100
    df_comparison['Delta_%'] = df_comparison.apply(
        lambda row: 
        'NEW' if row['Shares_previous'] == 0
        else 'CLOSE' if row['Shares_recent'] == 0
        else 'NO CHANGE' if row['Shares_recent'] == row['Shares_previous']
        else '{:+.1f}%'.format(row['Delta_%']),
        axis=1
    )

    df_comparison['Ticker'] = df_comparison['CUSIP'].map(get_cusip_to_ticker_mapping_finnhub_with_fallback(df_comparison))

    total_portfolio_value = df_comparison['Value_recent'].sum()

    df_comparison['Portfolio %'] = ((df_comparison['Value_recent'] / total_portfolio_value) * 100).apply(lambda p: '<.01%' if 0 < p < 0.01 else f'{p:.2f}%')

    df_comparison = df_comparison[['CUSIP', 'Ticker', 'Name of Issuer', 'Value_recent', 'Portfolio %', 'Price_per_Share', 'Delta_Value', 'Delta_%']] \
        .rename(columns={'Value_recent': 'Value'}) \
        .sort_values(by='Delta_Value', ascending=False)

    # Save the comparison to CSV
    filename = f"{cik}_{filing_dates[0]}.csv"
    df_comparison.to_csv(filename, index=False)
    print(f"Created {filename}")


if __name__ == "__main__":
    requested_cik = get_user_input()
    filings = fetch_latest_two_filings(requested_cik)
    
    if len(filings) == 2:
        filing_dates = [f['date'] for f in filings]
        df_recent = xml_to_dataframe(filings[0]['xml_content'])
        df_previous = xml_to_dataframe(filings[1]['xml_content'])

        generate_comparison(requested_cik, filing_dates, df_recent, df_previous)
    elif len(filings) == 1:
        print("Only one report found, cannot generate comparison.")
    else:
        print("No reports found.")
