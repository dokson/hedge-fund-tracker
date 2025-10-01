from app.analysis.non_quarterly import get_non_quarterly_filings_dataframe
from app.analysis.quarterly_report import generate_comparison
from app.scraper.sec_scraper import fetch_latest_two_13f_filings, fetch_non_quarterly_after_date, get_latest_13f_filing_date
from app.scraper.xml_processor import xml_to_dataframe_13f
from app.utils.console import horizontal_rule, print_centered, select_fund, select_period
from app.utils.database import load_hedge_funds, save_comparison, save_non_quarterly_filings, sort_stocks


APP_NAME = "HEDGE FUND TRACKER - DATABASE UPDATER"


def exit():
    """
    0. Exit the application (after sorting stocks).
    """
    sort_stocks()
    print("Bye! 👋 Exited.")
    return False


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


def run_fetch_nq_filings():
    """
    2. Fetch latest non-quarterly filings for all known hedge funds and save to database.
    """
    hedge_funds = load_hedge_funds()
    total_funds = len(hedge_funds)
    print(f"Fetching Non Quarterly filings for all {total_funds} funds...")
    nq_filings = []

    def _fetch_nq(cik_to_process, fund_name, fund_denomination, latest_date):
        if not cik_to_process.strip():
            return
        filings = fetch_non_quarterly_after_date(cik_to_process, latest_date)
        if filings:
            filings_df = get_non_quarterly_filings_dataframe(filings, fund_denomination, cik_to_process)
            if filings_df is not None:
                filings_df.insert(0, 'Fund', fund_name)
                nq_filings.append(filings_df)

    for i, fund in enumerate(hedge_funds):
        print_centered(f"Processing {i + 1:2}/{total_funds}: {fund['Fund']}", "-")
        latest_13f_date = get_latest_13f_filing_date(fund['CIK'])
        _fetch_nq(fund['CIK'], fund['Fund'], fund['Denomination'], latest_13f_date)
        _fetch_nq(fund['CIKs'], fund['Fund'], fund['Denomination'], latest_13f_date)

    save_non_quarterly_filings(nq_filings)
    print_centered(f"All funds processed", "=")


def run_single_fund_report():
    """
    3. Generate latest report for a known hedge fund.
    """
    selected_fund = select_fund("Select the hedge fund for latest report 13F generation:")
    if selected_fund:
        process_fund(selected_fund)


def run_historical_fund_report():
    """
    4. Generate historical report for a known hedge fund.
    """
    selected_fund = select_fund("Select the hedge fund for historical report 13F generation:")
    if not selected_fund:
        return

    selected_period = select_period()
    if selected_period is not None:
        process_fund(selected_fund, offset=selected_period[0])


def run_manual_cik_report():
    """
    5. Manually enter a hedge fund CIK to generate latest report.
    """
    cik = input("Enter 10-digit CIK number: ").strip()
    process_fund({'CIK': cik})


if __name__ == "__main__":
    actions = {
        '0': exit,
        '1': run_all_funds_report,
        '2': run_fetch_nq_filings,
        '3': run_single_fund_report,
        '4': run_historical_fund_report,
        '5': run_manual_cik_report,
    }

    while True:
        try:
            horizontal_rule()
            print_centered(APP_NAME)
            horizontal_rule()
            print("0. Exit")
            print("1. Generate latest 13F reports for all known hedge funds")
            print("2. Fetch latest non-quarterly filings for all known hedge funds")
            print("3. Generate latest 13F report for a known hedge fund")
            print("4. Generate historical 13F report for a known hedge fund")
            print("5. Manually enter a hedge fund CIK to generate latest 13F report")
            horizontal_rule()

            choice = input("Choose an option (0-5): ")
            action = actions.get(choice)
            if action:
                if action() is False:
                    break
            else:
                print("❌ Invalid selection. Try again.")
        except KeyboardInterrupt:
            print("\nOperation cancelled by user. Bye! 👋")
            break
