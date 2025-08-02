from .sec_scraper import fetch_latest_two_13f_filings
from .pandas_processor import xml_to_dataframe_13f, generate_comparison
from scraper.db.masterdata import load_hedge_funds, save_comparison, sort_stocks

LINE_LENGTH=75
DASH_LENGTH=5


def process_fund(fund_info, offset=0):
    """
    Processes a single fund: fetches filings and generates comparison.
    """
    cik = fund_info.get('CIK')
    fund_name = fund_info.get('Fund') or fund_info.get('CIK')
    try:
        filings = fetch_latest_two_13f_filings(cik, offset)
        filing_dates = [f['date'] for f in filings]
        df_recent = xml_to_dataframe_13f(filings[0]['xml_content'])
        df_previous = xml_to_dataframe_13f(filings[1]['xml_content'])
        
        df_comparison = generate_comparison(df_recent, df_previous)
        save_comparison(df_comparison, filing_dates[0], fund_name)
    except Exception as e:
        print(f"An unexpected error occurred while processing {fund_name}: {e}")


def select_fund():
    """
    Fund selection.
    Returns selected fund info or None if cancelled/invalid.
    """
    hedge_funds = load_hedge_funds()
    total_funds = len(hedge_funds)
    
    print("Select the hedge fund:")
    for i, fund in enumerate(hedge_funds):
        print(f"  {i + 1:2}: {fund['Fund']} - {fund['Manager']}")

    try:
        choice = input(f"\nEnter a number (1-{total_funds}): ")
        selected_index = int(choice) - 1
        if 0 <= selected_index < total_funds:
            return hedge_funds[selected_index]
        else:
            print("❌ Invalid selection.")
            return None
    except ValueError:
        print("❌ Invalid input. Please enter a number.")
        return None
    except KeyboardInterrupt:
        print("❌ Operation cancelled by user.")
        return None


if __name__ == "__main__":

    while True:
        print("\n" + "="*LINE_LENGTH)
        print(" "*int((LINE_LENGTH-16)/2) + "HEDGE FUND TRACKER")
        print("="*LINE_LENGTH)
        print("1. Generate latest reports for all known hedge funds (hedge_funds.csv)")
        print("2. Generate latest report for a known hedge fund (hedge_funds.csv)")
        print("3. Generate historical report for a known hedge fund (hedge_funds.csv)")
        print("4. Manually enter a hedge fund CIK number to generate latest report")
        print("5. Exit")
        print("="*LINE_LENGTH)

        offset_input = input("Choose an option (1-5): ")

        if offset_input == '1':
            hedge_funds = load_hedge_funds()
            total_funds = len(hedge_funds)
            print(f"Starting updating reports for all {total_funds} funds...")
            print("This will generate last vs previous quarter comparisons.")
            for i, fund in enumerate(hedge_funds):
                print("\n")
                print("-"*DASH_LENGTH + f" Processing {i + 1:2}/{total_funds}: {fund['Fund']} - {fund['Manager']} " + "-"*DASH_LENGTH)
                process_fund(fund)
            print("-"*DASH_LENGTH + "All funds processed." + "-"*DASH_LENGTH)

        elif offset_input == '2':
            print("Select the hedge fund for latest report generation:")
            selected_fund = select_fund()
            if selected_fund:
                process_fund(selected_fund)

        elif offset_input == '3':
            print("Select the hedge fund for historical report generation:")
            selected_fund = select_fund()
            if not selected_fund:
                continue

            print("Select historical period comparison:")
            print("  1: Previous vs Two quarters back")
            print("  2: Two vs Three quarters back")
            print("  3: Three vs Four quarters back")
            print("  4: Four vs Five quarters back")
            print("  5: Five vs Six quarters back")
            print("  6: Six vs Seven quarters back")
            print("  7: Seven vs Eight quarters back (2 years)")

            try:
                offset_input = input("Enter offset number (1-7): ").strip()
                offset = int(offset_input)

                if 1 <= offset <= 7:
                    process_fund(selected_fund, offset)
                else:
                    print("❌ Offset must be positive and must not go back further than 2 years.")
            except ValueError:
                print("❌ Invalid input. Please enter a number.")

        elif offset_input == '4':
            cik = input("Enter 10-digit CIK number: ")
            process_fund({'CIK': cik})
        
        elif offset_input == '5':
            sort_stocks()
            print("Exit.")
            break

        else:
            print("❌ Invalid choice. Try again.")
