from app.ai.agent import AnalystAgent
from app.analysis.quarterly_report import generate_comparison
from app.analysis.schedules import get_latest_schedule_filings_dataframe
from app.analysis.stocks import quarter_analysis, stock_analysis
from app.scraper.sec_scraper import get_latest_13f_filing_date, fetch_latest_two_13f_filings, fetch_schedule_filings_after_date
from app.scraper.xml_processor import xml_to_dataframe_13f
from app.utils.console import horizontal_rule, print_centered, print_dataframe, prompt_for_selection
from app.utils.database import get_all_quarters, get_last_quarter, load_hedge_funds, save_comparison, save_latest_schedule_filings, sort_stocks
from app.utils.strings import format_percentage, format_value, get_percentage_formatter, get_signed_perc_formatter, get_value_formatter
import numpy as np


APP_NAME = "HEDGE FUND TRACKER"


def select_fund(text="Select the hedge fund:"):
    """
    Prompts the user to select a hedge fund, displaying them in columns.
    Returns selected fund info or None if cancelled/invalid.
    """
    return prompt_for_selection(
        load_hedge_funds(),
        text,
        display_func=lambda fund: f"{fund['Fund']} - {fund['Manager']}",
        num_columns=-1
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
        display_func=lambda option: option[1],
        num_columns=2
    )


def select_quarter():
    """
    Prompts the user to select an analysis quarter.
    Returns the selected quarter string (e.g., '2025Q1') or None if cancelled/invalid.
    """
    return prompt_for_selection(get_all_quarters(), "Select the quarter you want to analyze:")


def process_fund(fund_info, offset=0):
    """
    Processes a single fund: fetches filings and generates a comparison report.
    It ensures the comparison is between two different reporting periods, skipping over any amendments for the same period.
    """
    cik = fund_info.get('CIK')
    fund_name = fund_info.get('Fund') or fund_info.get('CIK')

    try:
        # Step 1: Fetch the primary filing for the given offset.
        filings = fetch_latest_two_13f_filings(cik, offset)
        latest_date = filings[0]['reference_date']
        dataframe_latest = xml_to_dataframe_13f(filings[0]['xml_content'])

        # Step 2: Find the first valid preceding filing for comparison.
        # This loop correctly is needed to handle amendments (13F-HR/A) with earlier reference dates.
        previous_filing = filings[1] if len(filings) == 2 else None
        
        while previous_filing and latest_date <= previous_filing['reference_date']:
            offset += 1
            filings = fetch_latest_two_13f_filings(cik, offset)
            previous_filing = filings[1] if len(filings) == 2 else None

        dataframe_previous = xml_to_dataframe_13f(previous_filing['xml_content']) if previous_filing else None
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


def run_fetch_latest_schedules():
    """
    4. Fetch latest schedule filings for all known hedge funds and save to database.
    """
    hedge_funds = load_hedge_funds()
    total_funds = len(hedge_funds)
    print(f"Starting updating reports for all {total_funds} funds...")
    latest_schedules = []

    for i, fund in enumerate(hedge_funds):
        print_centered(f"Processing {i + 1:2}/{total_funds}: {fund['Fund']}", "-")
        cik = fund.get('CIK')
        fund_denomination = fund.get('Denomination')

        schedule_filings = fetch_schedule_filings_after_date(cik, get_latest_13f_filing_date(cik))

        if schedule_filings:
            schedule_filings_dataframe = get_latest_schedule_filings_dataframe(schedule_filings, fund_denomination, cik)
            if schedule_filings_dataframe is not None and not schedule_filings_dataframe.empty:
                schedule_filings_dataframe.insert(0, 'Fund', fund.get('Fund'))
                latest_schedules.append(schedule_filings_dataframe)
    
    save_latest_schedule_filings(latest_schedules)
    print_centered(f"All funds processed", "=")


def run_manual_cik_report():
    """
    5. Manually enter a hedge fund CIK to generate latest report.
    """
    cik = input("Enter 10-digit CIK number: ").strip()
    process_fund({'CIK': cik})


def run_quarter_analysis():
    """
    6. Analyze stock trends for a quarter.
    """
    selected_quarter = select_quarter()
    if selected_quarter:
        df_analysis = quarter_analysis(selected_quarter)
        horizontal_rule('-')
        print_centered(f"{selected_quarter} QUARTER ANALYSIS:")
        horizontal_rule('-')

        top_n = 15
        print_dataframe(df_analysis, top_n, f'Top {top_n} Consensus Buys (by Net # of Buyers)', ['Net_Buyers', 'Buyer_Count', 'Total_Delta_Value'], ['Ticker', 'Company', 'Delta', 'Net_Buyers', 'Buyer_Count', 'Seller_Count', 'Holder_Count', 'Total_Delta_Value', 'Total_Value'], {'Delta': get_signed_perc_formatter(), 'Total_Delta_Value': get_value_formatter(), 'Total_Value': get_value_formatter()})
        print_dataframe(df_analysis, top_n, f'Top {top_n} New Consensus (by # of New Holders)', ['New_Holder_Count', 'Total_Delta_Value'], ['Ticker', 'Company', 'New_Holder_Count', 'Net_Buyers', 'Holder_Count', 'Delta', 'Total_Delta_Value', 'Total_Value'], {'Delta': get_signed_perc_formatter(), 'Total_Delta_Value': get_value_formatter(), 'Total_Value': get_value_formatter()})
        print_dataframe(df_analysis[(df_analysis['Delta'] != np.inf) & (df_analysis['Total_Delta_Value'] > 150_000_000)], top_n, f'Top {top_n} Increasing Positions (by Delta)', 'Delta', ['Ticker', 'Company', 'New_Holder_Count', 'Net_Buyers', 'Holder_Count', 'Delta', 'Total_Delta_Value', 'Total_Value'], {'Delta': get_signed_perc_formatter(), 'Total_Delta_Value': get_value_formatter(), 'Total_Value': get_value_formatter()})
        print_dataframe(df_analysis, top_n, f'Top {top_n} Big Bets (by Max Portfolio %)', 'Max_Portfolio_Pct', ['Ticker', 'Company', 'Max_Portfolio_Pct', 'Avg_Portfolio_Pct', 'Delta', 'Total_Delta_Value', 'Total_Value'], {'Max_Portfolio_Pct': get_percentage_formatter(), 'Avg_Portfolio_Pct': get_percentage_formatter(), 'Delta': get_signed_perc_formatter(), 'Total_Delta_Value': get_value_formatter(), 'Total_Value': get_value_formatter()})
        print_dataframe(df_analysis[(df_analysis['Holder_Count'] >= round(len(load_hedge_funds())/10))], top_n, f'Average {top_n} Stocks Portfolio', 'Avg_Portfolio_Pct', ['Ticker', 'Company', 'Avg_Portfolio_Pct', 'Max_Portfolio_Pct', 'Holder_Count', 'Delta'], {'Avg_Portfolio_Pct': get_percentage_formatter(), 'Max_Portfolio_Pct': get_percentage_formatter(), 'Delta': get_signed_perc_formatter()})
        print("\n")


def run_single_stock_analysis():
    """
    7. Analyze a single stock for a specific quarter.
    """
    selected_quarter = select_quarter()
    if selected_quarter:
        ticker = input("Enter stock ticker to analyze: ").strip().upper()
        if not ticker:
            print("❌ Ticker cannot be empty.")
            return
        
        df_analysis = stock_analysis(ticker, selected_quarter)

        if df_analysis.empty:
            print(f"❌ No data found for ticker {ticker} in quarter {selected_quarter}.")
            return
        
        horizontal_rule('-')
        print_centered(f"{ticker} ({df_analysis['Company'].iloc[0]}) - {selected_quarter} QUARTER ANALYSIS")
        horizontal_rule('-')

        total_value = df_analysis['Value'].sum()
        total_delta_value = df_analysis['Delta_Value'].sum()
        avg_percentage = df_analysis['Portfolio_Pct'].mean()
        max_percentage = df_analysis['Portfolio_Pct'].max()
        num_buyers = (df_analysis['Delta_Value'] > 0).sum()
        num_sellers = (df_analysis['Delta_Value'] < 0).sum()
        holder_count = (df_analysis['Delta'] != 'CLOSE').sum()
        new_holder_count = (df_analysis['Delta'].str.startswith('NEW')).sum()
        close_count = (df_analysis['Delta'] == 'CLOSE').sum()
        delta = total_delta_value / total_value * 100 if total_value != 0 else np.nan

        print("\n")
        print_centered(f"TOTAL HELD: {format_value(total_value)}")
        print_centered(f"DELTA VALUE: {format_value(total_delta_value)} / DELTA %: {"NEW" if holder_count == new_holder_count and close_count == 0 else format_percentage(delta, True)}")
        print_centered(f"AVG PTF %: {format_percentage(avg_percentage, decimal_places=2)} / MAX PTF %: {format_percentage(max_percentage)}")
        print_centered(f"HOLDERS: {len(df_analysis)}")
        print_centered(f"BUYERS: {num_buyers} ({new_holder_count} new) / SELLERS: {num_sellers} ({close_count} sold out)")
        print_centered(f"BUYER/SELLER RATIO: {format_value(num_buyers / num_sellers if num_sellers > 0 else float('inf'))}")

        print_dataframe(df_analysis, len(df_analysis), f'Holders by Shares', 'Shares', ['Fund', 'Portfolio_Pct', 'Shares', 'Value', 'Delta', 'Delta_Value'], {'Portfolio_Pct': get_percentage_formatter(), 'Shares': get_value_formatter(), 'Value': get_value_formatter(), 'Delta_Value': get_value_formatter()})
        print("\n")


def run_ai_analyst():
    """
    8. Run AI Analyst
    """
    try:
        top_n = 30
        agent = AnalystAgent(get_last_quarter())
        scored_list = agent.generate_scored_list(top_n)
        print_dataframe(scored_list, top_n, title=f'Best {top_n} Promising Stocks (according to the AI Analyst)', sort_by='Promise_Score', cols=['Ticker', 'Company', 'Industry', 'Promise_Score', 'Risk_Score', 'Low_Volatility_Score', 'Momentum_Score', 'Growth_Score'])
    except Exception as e:
        print(f"❌ An unexpected error occurred while running AI Financial Agent: {e}")


def exit():
    """
    9. Exit the application (after sorting stocks).
    """
    sort_stocks()
    print("Bye! 👋 Exited.")
    return False


if __name__ == "__main__":
    actions = {
        '1': run_all_funds_report,
        '2': run_single_fund_report,
        '3': run_historical_fund_report,
        '4': run_fetch_latest_schedules,
        '5': run_manual_cik_report,
        '6': run_quarter_analysis,
        '7': run_single_stock_analysis,
        '8': run_ai_analyst,
        '9': exit
    }

    while True:
        try:
            horizontal_rule()
            print_centered(APP_NAME)
            horizontal_rule()
            print("1. Generate latest reports for all known hedge funds (hedge_funds.csv)")
            print("2. Generate latest report for a known hedge fund (hedge_funds.csv)")
            print("3. Generate historical report for a known hedge fund (hedge_funds.csv)")
            print("4. Fetch latest schedule filings for a known hedge fund (hedge_funds.csv)")
            print("5. Manually enter a hedge fund CIK number to generate latest report")
            print("6. Analyze stock trends for a quarter")
            print("7. Analyze a single stock for a quarter")
            print("8. Run AI Analyst for most promising stocks")
            print("9. Exit")
            horizontal_rule()

            main_choice = input("Choose an option (1-9): ")
            action = actions.get(main_choice)
            if action:
                if action() is False:
                    break
            else:
                print("❌ Invalid selection. Try again.")

        except KeyboardInterrupt:
            print("\nOperation cancelled by user. Bye! 👋")
            break
