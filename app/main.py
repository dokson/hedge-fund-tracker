from app.analysis.report import generate_comparison
from app.analysis.stocks import quarter_analysis
from app.scraper.sec_scraper import fetch_latest_two_13f_filings
from app.scraper.xml_processor import xml_to_dataframe_13f
from app.utils.database import get_all_quarters, load_hedge_funds, save_comparison, sort_stocks
from app.utils.strings import format_percentage, format_value

APP_NAME = "HEDGE FUND TRACKER"
LINE_LENGTH=90
DASH_LENGTH=10

def horizontal_rule(char='='):
    print(char*LINE_LENGTH)


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
        print("\n❌ Operation cancelled by user.")
        return None


def select_quarter():
    """
    Lists available quarters from the database folder and prompts the user to select one.
    Returns the selected quarter string (e.g., '2025Q1') or None if cancelled/invalid.
    """
    try:
        quarters = get_all_quarters()
            
        print("Select the quarter you want to analyze:")
        for i, quarter in enumerate(quarters):
            print(f"  {i + 1}: {quarter}")
            
        choice = input(f"Select the quarter (1-{len(quarters)}): ")
        selected_index = int(choice) - 1
        
        if 0 <= selected_index < len(quarters):
            return quarters[selected_index]
        else:
            print("❌ Invalid selection.")
            return None
    except ValueError:
        print("❌ Invalid input. Please enter a number.")
        return None
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user.")
        return None


def process_fund(fund_info, offset=0):
    """
    Processes a single fund: fetches filings and generates comparison.
    """
    try:
        cik = fund_info.get('CIK')
        fund_name = fund_info.get('Fund') or fund_info.get('CIK')
        filings = fetch_latest_two_13f_filings(cik, offset)

        dataframe_latest = xml_to_dataframe_13f(filings[0]['xml_content'])
        dataframe_previous = xml_to_dataframe_13f(filings[1]['xml_content'])

        dataframe_comparison = generate_comparison(dataframe_latest, dataframe_previous)
        latest_date = [f['date'] for f in filings][0]
        save_comparison(dataframe_comparison, latest_date, fund_name)
    except Exception as e:
        print(f"An unexpected error occurred while processing fund (CIK = {cik}): {e}")


def display_analysis(dataframe, title, sort_by, ascending, cols, formatters=None):
    if formatters is None:
        formatters = {}

    print("\n" + "-"*int((LINE_LENGTH-len(title)-2)/2) + f" {title} " + "-"*int((LINE_LENGTH-len(title)-2)/2) + "\n")

    display_df = dataframe.sort_values(by=sort_by, ascending=ascending).head(10).copy()
    
    for col, formatter in formatters.items():
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(formatter)

    print(display_df[cols].to_string(index=False))
    

if __name__ == "__main__":

    while True:
        try:
            horizontal_rule()
            print(" "*int((LINE_LENGTH-len(APP_NAME))/2) + APP_NAME)
            horizontal_rule()
            print("1. Generate latest reports for all known hedge funds (hedge_funds.csv)")
            print("2. Generate latest report for a known hedge fund (hedge_funds.csv)")
            print("3. Generate historical report for a known hedge fund (hedge_funds.csv)")
            print("4. Manually enter a hedge fund CIK number to generate latest report")
            print("5. Analyze stock trends for a quarter")
            print("6. Exit")
            horizontal_rule()

            main_choice = input("Choose an option (1-6): ")

            if main_choice == '1':
                hedge_funds = load_hedge_funds()
                total_funds = len(hedge_funds)
                print(f"Starting updating reports for all {total_funds} funds...")
                print("This will generate last vs previous quarter comparisons.")
                for i, fund in enumerate(hedge_funds):
                    print("\n")
                    print("-"*DASH_LENGTH + f" Processing {i + 1:2}/{total_funds}: {fund['Fund']} - {fund['Manager']} " + "-"*DASH_LENGTH)
                    process_fund(fund)
                print("-"*DASH_LENGTH + "All funds processed." + "-"*DASH_LENGTH)

            elif main_choice == '2':
                print("Select the hedge fund for latest report generation:")
                selected_fund = select_fund()
                if selected_fund:
                    process_fund(selected_fund)

            elif main_choice == '3':
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

            elif main_choice == '4':
                cik = input("Enter 10-digit CIK number: ")
                process_fund({'CIK': cik})
            
            elif main_choice == '5':
                selected_quarter = select_quarter()
                if selected_quarter:
                    df_analysis  = quarter_analysis(selected_quarter)
                    horizontal_rule('-')
                    print(f"Stock Analysis for Quarter: {selected_quarter}")

                    value = lambda x: format_value(int(x))
                    percentage = lambda x: format_percentage(x)

                    display_analysis(df_analysis, 'Top 10 Buys (by Portfolio Impact %)', 'Total_Weighted_Delta_Pct', False, ['Ticker', 'Company', 'Total_Weighted_Delta_Pct', 'Holder_Count', 'Net_Buyers'], {'Total_Weighted_Delta_Pct': percentage})
                    display_analysis(df_analysis, 'Top 10 Sells (by Portfolio Impact %)', 'Total_Weighted_Delta_Pct', True, ['Ticker', 'Company', 'Total_Weighted_Delta_Pct', 'Holder_Count', 'Net_Buyers'], {'Total_Weighted_Delta_Pct': percentage})
                    display_analysis(df_analysis, 'Most Widely Held Stocks (by # of Funds)', ['Holder_Count', 'Total_Value'], False, ['Ticker', 'Company', 'Holder_Count', 'Net_Buyers', 'Total_Value'], {'Total_Value': value})
                    display_analysis(df_analysis, 'Highest Conviction Buys (by Net # of Buyers)', ['Net_Buyers', 'Buyer_Count', 'Total_Delta_Value'], False, ['Ticker', 'Company', 'Net_Buyers', 'Buyer_Count', 'Seller_Count'])

            elif main_choice == '6':
                sort_stocks()
                print("Bye! 👋 Exited.")
                break

            else:
                print("❌ Invalid selection. Try again.")

        except KeyboardInterrupt:
            print("\nBye! 👋")
            break
