from .sec_scraper import fetch_latest_two_filings
from scraper.db.masterdata import load_hedge_funds, sort_stocks
from scraper.db.pd_helpers import coalesce
from scraper.ticker.resolver import get_ticker
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import pandas as pd
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


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

    # Cast numeric columns
    df['Shares'] = pd.to_numeric(df['Shares'], errors='coerce')
    df['Value'] = pd.to_numeric(df['Value'], errors='coerce')

    # Dedup by CUSIP
    df = df.groupby(['CUSIP'], as_index=False).agg({
        'Company': 'max',
        'Value': 'sum',
        'Shares': 'sum'
    })

    return df


def generate_comparison(fund_name, filing_dates, df_recent, df_previous):
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
        else '{:+.1f}%'.format(row['Delta%']),
        axis=1
    )

    total_portfolio_value = df_comparison['Value'].sum()
    df_comparison['Portfolio%'] = ((df_comparison['Value'] / total_portfolio_value) * 100).apply(lambda p: '<.01%' if 0 < p < 0.01 else f'{p:.2f}%')

    df_comparison['Ticker'] = df_comparison['CUSIP'].map(get_ticker(df_comparison))

    df_comparison = df_comparison[['CUSIP', 'Ticker', 'Company', 'Value', 'Portfolio%', 'Price_per_Share', 'Delta_Value', 'Delta']] \
        .sort_values(by=['Delta_Value', 'Value'], ascending=False)

    # Save the comparison to CSV
    filename = f"{fund_name.replace(' ', '_')}_{filing_dates[0]}.csv"
    df_comparison.to_csv(filename, index=False)
    print(f"Created {filename}")


def process_fund(fund_info):
    """
    Processes a single fund: fetches filings and generates comparison.
    """
    cik = fund_info.get('cik')
    fund_name = fund_info.get('hedge_fund') or fund_info.get('cik')
    try:
        filings = fetch_latest_two_filings(cik)
        filing_dates = [f['date'] for f in filings]
        df_recent = xml_to_dataframe(filings[0]['xml_content'])
        df_previous = xml_to_dataframe(filings[1]['xml_content'])
        generate_comparison(fund_name, filing_dates, df_recent, df_previous)
    except Exception as e:
        print(f"Error fetching filings: {e}")


if __name__ == "__main__":

     while True:
        print("\n--- Main Menu ---")
        print("1. Analyze a known investment fund (hedge_funds.csv)")
        print("2. Enter a CIK manually")
        print("3. Exit")
        choice = input("Choose an option (1-3): ")

        if choice == '1':
            hedge_funds = load_hedge_funds()
            hedge_funds_size = len(hedge_funds)
            print("Select the hedge fund you want to analyze:")
            for i, fund in enumerate(hedge_funds):
                print(f"  {i + 1}: {fund['hedge_fund']}")

            try:
                choice = input(f"\nEnter a number (1-{hedge_funds_size}): ")
                selected_index = int(choice) - 1
                if 0 <= selected_index < hedge_funds_size:
                    selected_fund = hedge_funds[selected_index]
                    process_fund(selected_fund)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input. Please enter a number.")
            except KeyboardInterrupt:
                print("Operation cancelled by user.")

        elif choice == '2':
            cik = get_user_input()
            process_fund({'cik': cik})
        
        elif choice == '3':
            print("Sorting stocks file by Ticker before exiting...")
            sort_stocks()
            print("Exit.")
            break

        else:
            print("Invalid choice. Try again.")