from .sec_scraper import fetch_latest_two_filings
from scraper.db.masterdata import load_hedge_funds, sort_stocks
from scraper.db.pd_helpers import coalesce
from scraper.string_utils import format_percentage, format_value, get_quarter
from scraper.ticker.resolver import resolve_ticker
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from pathlib import Path
import pandas as pd
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

OUTPUT_FOLDER = '/database'


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

    df_comparison = pd.concat([df_comparison, total_row], ignore_index=True)

    # Save the comparison to CSV
    quarter_folder = Path(OUTPUT_FOLDER) / get_quarter(filing_dates[0])
    quarter_folder.mkdir(parents=True, exist_ok=True)
    
    filename = quarter_folder / f"{fund_name.replace(' ', '_')}.csv"
    df_comparison.to_csv(filename, index=False)
    print(f"Created {filename}")


def process_fund(fund_info):
    """
    Processes a single fund: fetches filings and generates comparison.
    """
    cik = fund_info.get('CIK')
    fund_name = fund_info.get('Fund') or fund_info.get('CIK')
    try:
        filings = fetch_latest_two_filings(cik)
        filing_dates = [f['date'] for f in filings]
        df_recent = xml_to_dataframe(filings[0]['xml_content'])
        df_previous = xml_to_dataframe(filings[1]['xml_content'])
        generate_comparison(fund_name, filing_dates, df_recent, df_previous)
    except Exception as e:
        print(f"An unexpected error occurred while processing {fund_name} (CIK: {cik}): {e}")


if __name__ == "__main__":

     while True:
        print("\n--- Main Menu ---")
        print("1. Generate latest reports for all known hedge funds (hedge_funds.csv)")
        print("2. Update the latest report for a known hedge fund (hedge_funds.csv)")
        print("3. Manually enter a hedge fund CIK number to get latest its filings and generate a report")
        print("4. Exit")
        choice = input("Choose an option (1-4): ")

        if choice == '1':
            hedge_funds = load_hedge_funds()
            total_funds = len(hedge_funds)
            print(f"Starting update reports for all {total_funds} funds...")
            for i, fund in enumerate(hedge_funds):
                print(f"\n--- Processing {i + 1:2}/{total_funds}: {fund['Fund']} - {fund['Manager']} ---")
                process_fund(fund)
            print("--- All funds processed. ---")

        elif choice == '2':
            hedge_funds = load_hedge_funds()
            total_funds = len(hedge_funds)
            print("Select the hedge fund you want to update:")
            for i, fund in enumerate(hedge_funds):
                print(f"  {i + 1:2}: {fund['Fund']} - {fund['Manager']}")

            try:
                choice = input(f"\nEnter a number (1-{total_funds}): ")
                selected_index = int(choice) - 1
                if 0 <= selected_index < total_funds:
                    selected_fund = hedge_funds[selected_index]
                    process_fund(selected_fund)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input. Please enter a number.")
            except KeyboardInterrupt:
                print("Operation cancelled by user.")

        elif choice == '3':
            cik = get_user_input()
            process_fund({'CIK': cik})
        
        elif choice == '4':
            print("Sorting stocks file by Ticker before exiting...")
            sort_stocks()
            print("Exit.")
            break

        else:
            print("Invalid choice. Try again.")