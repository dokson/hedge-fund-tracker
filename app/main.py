from app.analysis.report import generate_comparison
from app.analysis.stocks import quarter_analysis
from app.scraper.sec_scraper import fetch_latest_two_13f_filings, fetch_schedule_filings_after_date
from app.scraper.xml_processor import xml_to_dataframe_13f
from app.utils.console import horizontal_rule, print_centered, print_dataframe, prompt_for_selection
from app.utils.database import get_all_quarters, load_hedge_funds, save_comparison, sort_stocks
from app.utils.strings import format_percentage, format_value

APP_NAME = "HEDGE FUND TRACKER"


def select_fund(text="Select the hedge fund:"):
    """
    Prompts the user to select a hedge fund.
    Returns selected fund info or None if cancelled/invalid.
    """
    return prompt_for_selection(
        load_hedge_funds(),
        text,
        display_func=lambda fund: f"{fund['Fund']} - {fund['Manager']}"
    )


def select_period():
    """
    Prompts the user to select a historical comparison period.
    Returns the selected offset integer or None if cancelled/invalid.
    """
    period_options = [
        (1, "Previous vs Two quarters back (Offset=1)"),
        (2, "Two vs Three quarters back (Offset=2)"),
        (3, "Three vs Four quarters back (Offset=3)"),
        (4, "Four vs Five quarters back (Offset=4)"),
        (5, "Five vs Six quarters back (Offset=5)"),
        (6, "Six vs Seven quarters back (Offset=6)"),
        (7, "Seven vs Eight quarters back (Offset=7: 2 years)")
    ]

    return prompt_for_selection(
        period_options,
        "Select offset for historical period comparison:",
        display_func=lambda option: option[1]
    )


def select_quarter():
    """
    Prompts the user to select an analysis quarter.
    Returns the selected quarter string (e.g., '2025Q1') or None if cancelled/invalid.
    """
    return prompt_for_selection(get_all_quarters(), "Select the quarter you want to analyze:")


def process_fund(fund_info, offset=0):
    """
    Processes a single fund: fetches filings and generates comparison.
    """
    cik = fund_info.get('CIK')
    fund_name = fund_info.get('Fund') or fund_info.get('CIK')

    try:
        filings = fetch_latest_two_13f_filings(cik, offset)

        dataframe_latest = xml_to_dataframe_13f(filings[0]['xml_content'])
        latest_date = filings[0]['date']

        # If processing the latest report, check for futher 13D/G filings
        if offset == 0:
            print("Checking for more recent 13D/G filings...")
            schedule_filings = fetch_schedule_filings_after_date(cik, latest_date)
            
            # TODO
            #if schedule_filings:
            #    schedule_filings_dataframe = get_latest_schedule_filings_dataframe(schedule_filings, fund_name, cik)
            #    original_rows = len(dataframe_latest)
            #    dataframe_latest = update_dataframe_with_schedule(dataframe_latest, schedule_filings_dataframe)
            #    new_rows = len(dataframe_latest)
            #    print(f"✅ Holdings updated with {new_rows - original_rows} changes from schedule filings.")

        dataframe_previous = xml_to_dataframe_13f(filings[1]['xml_content'])
        dataframe_comparison = generate_comparison(dataframe_latest, dataframe_previous)
        save_comparison(dataframe_comparison, latest_date, fund_name)
    except Exception as e:
        print(f"❌ An unexpected error occurred while processing {fund_name} (CIK = {cik}): {e}")


def run_all_funds_report():
    """
    1. Generate latest reports for all known hedge funds.
    """
    hedge_funds = load_hedge_funds()
    total_funds = len(hedge_funds)
    print(f"Starting updating reports for all {total_funds} funds...")
    print("This will generate last vs previous quarter comparisons.")
    for i, fund in enumerate(hedge_funds):
        print_centered(f"Processing {i + 1:2}/{total_funds}: {fund['Fund']}", "-")
        process_fund(fund)
    print_centered(f"All funds processed", "=")


def run_single_fund_report():
    """
    2. Generate latest report for a known hedge fund.
    """
    selected_fund = select_fund("Select the hedge fund for latest report generation:")
    if selected_fund:
        process_fund(selected_fund)


def run_historical_fund_report():
    """
    3. Generate historical report for a known hedge fund.
    """
    selected_fund = select_fund("Select the hedge fund for historical report generation:")
    if not selected_fund:
        return

    selected_period = select_period()
    if selected_period is not None:
        process_fund(selected_fund, offset=selected_period[0])


def run_manual_cik_report():
    """
    4. Manually enter a hedge fund CIK to generate latest report.
    """
    cik = input("Enter 10-digit CIK number: ").strip()
    process_fund({'CIK': cik})


def run_quarter_analysis():
    """
    5. Analyze stock trends for a quarter.
    """
    selected_quarter = select_quarter()
    if selected_quarter:
        df_analysis = quarter_analysis(selected_quarter)
        horizontal_rule('-')
        print("\n")
        print_centered(f"{selected_quarter} QUARTER ANALYSIS:")

        value = lambda x: format_value(int(x))
        percentage = lambda x: format_percentage(x)

        print_dataframe(df_analysis, 'Top 10 Buys (by Net # of Buyers)', ['Net_Buyers', 'Buyer_Count', 'Total_Delta_Value'], False, ['Ticker', 'Company', 'Net_Buyers', 'Buyer_Count', 'Seller_Count', 'Total_Value'], {'Total_Value': value})
        print_dataframe(df_analysis, 'Top 10 Buys (by Portfolio Impact %)', 'Total_Weighted_Delta_Pct', False, ['Ticker', 'Company', 'Total_Weighted_Delta_Pct', 'Holder_Count', 'Net_Buyers'], {'Total_Weighted_Delta_Pct': percentage})
        print_dataframe(df_analysis, 'Top 10 New Positions (by # of New Holders)', 'New_Holder_Count', False, ['Ticker', 'Company', 'New_Holder_Count', 'Total_Weighted_Delta_Pct'], {'Total_Weighted_Delta_Pct': percentage})
        print_dataframe(df_analysis, 'Top 10 Big Bets (by Max Portfolio %)', 'Max_Portfolio_Pct', False, ['Ticker', 'Company', 'Max_Portfolio_Pct', 'Holder_Count', 'Net_Buyers'], {'Max_Portfolio_Pct': percentage})
        print("\n")


def exit():
    """
    6. Exit the application (after sorting stocks).
    """
    sort_stocks()
    print("Bye! 👋 Exited.")
    return False


if __name__ == "__main__":
    actions = {
        '1': run_all_funds_report,
        '2': run_single_fund_report,
        '3': run_historical_fund_report,
        '4': run_manual_cik_report,
        '5': run_quarter_analysis,
        '6': exit,
    }

    while True:
        try:
            horizontal_rule()
            print_centered(APP_NAME)
            horizontal_rule()
            print("1. Generate latest reports for all known hedge funds (hedge_funds.csv)")
            print("2. Generate latest report for a known hedge fund (hedge_funds.csv)")
            print("3. Generate historical report for a known hedge fund (hedge_funds.csv)")
            print("4. Manually enter a hedge fund CIK number to generate latest report")
            print("5. Analyze stock trends for a quarter")
            print("6. Exit")
            horizontal_rule()

            main_choice = input("Choose an option (1-6): ")
            action = actions.get(main_choice)
            if action:
                if action() is False:
                    break
            else:
                print("❌ Invalid selection. Try again.")

        except KeyboardInterrupt:
            print("\nOperation cancelled by user. Bye! 👋")
            break
