from app.analysis.non_quarterly import get_non_quarterly_filings_dataframe
from app.analysis.quarterly_report import generate_comparison
from app.scraper.sec_scraper import fetch_latest_two_13f_filings, fetch_non_quarterly_after_date, get_latest_13f_filing_date
from app.scraper.xml_processor import xml_to_dataframe_13f
from app.utils.console import horizontal_rule, print_centered, select_fund, select_period
from app.utils.database import load_hedge_funds, save_comparison, save_non_quarterly_filings, sort_stocks
from app.utils.readme import update_readme
from app.utils.strings import get_previous_quarter_end_date
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed


APP_NAME = "HEDGE FUND TRACKER - DATABASE UPDATER"


def exit():
    """
    0. Exits the application (after sorting stocks).

    This function sorts the stock master file and updates the README with the latest data.
    """
    sort_stocks()
    update_readme()
    print("Bye! 👋 Exited.")
    return False


def process_fund(fund_info, offset=0):
    """
    Fetches 13F filings for a single fund and generates a comparison report.

    This function retrieves the two most recent 13F filings for a given fund, accounting for an optional offset.
    It intelligently handles amendments by ensuring the comparison is made between two distinct reporting periods.
    The resulting comparison is then saved to the database.

    Args:
        fund_info (dict): A dictionary containing fund information, including 'CIK' and 'Fund' name.
        offset (int, optional): The number of filings to skip. Defaults to 0 (latest filing).
    """
    cik = fund_info.get('CIK')
    fund_name = fund_info.get('Fund') or fund_info.get('CIK')

    try:
        # Step 1: Fetch the primary filing for the given offset.
        filings = fetch_latest_two_13f_filings(cik, offset)
        latest_date = filings[0]['reference_date']
        dataframe_latest = xml_to_dataframe_13f(filings[0]['xml_content'])

        # Step 2: Find the filing for the immediately preceding quarter.
        # This loop skips amendments and ensures we are comparing against the correct previous period.
        previous_filing = filings[1] if len(filings) == 2 else None
        
        while previous_filing and previous_filing['reference_date'] != get_previous_quarter_end_date(latest_date):
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
    1. Generates and saves the latest 13F comparison reports for all known hedge funds.

    This function iterates through all funds listed in the database, processing them in parallel using a thread pool to fetch filings 
    and generate quarterly comparison reports.
    """
    hedge_funds = load_hedge_funds()
    total_funds = len(hedge_funds)
    print(f"Starting updating reports for all {total_funds} funds...")
    print("This will generate last vs previous quarter comparisons.")

    with ThreadPoolExecutor(max_workers=round(total_funds / 10)) as executor:
        futures = {executor.submit(process_fund, fund): fund for fund in hedge_funds}

        for i, future in enumerate(as_completed(futures)):
            fund = futures[future]
            print_centered(f"Processed {i + 1:2}/{total_funds}: {fund['Fund']}", "-")

    print_centered(f"All funds processed", "-")


def process_fund_nq(fund):
    """
    Fetches and processes non-quarterly (13D/G, Form 4) filings for a single fund.

    This function identifies the date of the fund's latest 13F filing and then searches for any non-quarterly filings submitted after that date.
    It handles funds with multiple associated CIKs.

    Args:
        fund (dict): A dictionary containing the fund's information, including 'CIK', 'CIKs', 'Fund' name, and 'Denomination'.

    Returns:
        tuple: A tuple containing the fund's name and a list of pandas DataFrames, where each DataFrame represents the processed non-quarterly filings.
               Returns an empty list if no new filings are found.
    """
    fund_results = []

    def _fetch_nq(cik_to_process, fund_name, fund_denomination, latest_date):
        if not cik_to_process or not cik_to_process.strip():
            return None
        
        filings = fetch_non_quarterly_after_date(cik_to_process, latest_date)
        if filings:
            filings_df = get_non_quarterly_filings_dataframe(filings, fund_denomination, cik_to_process)
            if filings_df is not None:
                filings_df = filings_df.copy()
                filings_df.insert(0, 'Fund', fund_name)
                return filings_df
        return None

    latest_13f_date = get_latest_13f_filing_date(fund['CIK'])
    
    result_cik = _fetch_nq(fund['CIK'], fund['Fund'], fund['Denomination'], latest_13f_date)
    if result_cik is not None:
        fund_results.append(result_cik)

    result_ciks = _fetch_nq(fund['CIKs'], fund['Fund'], fund['Denomination'], latest_13f_date)
    if result_ciks is not None:
        fund_results.append(result_ciks)
    
    return (fund['Fund'], fund_results)


def run_fetch_nq_filings():
    """
    2. Fetches and saves the latest non-quarterly filings for all known hedge funds.

    This function orchestrates the fetching of recent 13D/G and Form 4 filings for all funds in the database. 
    It uses a process pool for parallel execution and saves the consolidated results into a single database file.
    """
    hedge_funds = load_hedge_funds()
    total_funds = len(hedge_funds)
    print(f"Fetching Non Quarterly filings for all {total_funds} funds...")
    nq_filings = []
    completed_count = 0
    error_occurred = False

    with ProcessPoolExecutor(max_workers=round(total_funds / 10)) as executor:
        futures = {executor.submit(process_fund_nq, fund): fund for fund in hedge_funds}

        for future in as_completed(futures):
            fund = futures[future]
            completed_count += 1
            try:
                fund_name, results = future.result()
                if results:
                    nq_filings.extend(results)
                print_centered(f"Processed {completed_count:2}/{total_funds}: {fund_name}", "-")

            except Exception as e:
                if isinstance(e, TypeError) and "pickle" in str(e):
                    print_centered(f"❌ Pickle Error for {fund['Fund']}: retrying once in main thread...", "-")
                    try:
                        fund_name, results = process_fund_nq(fund)
                        if results:
                            nq_filings.extend(results)
                        print_centered(f"Successfully processed {fund_name} on retry", "-")
                        continue
                    except Exception as retry_e:
                        print_centered(f"❌ Retry failed for {fund['Fund']}: {retry_e}", "-")
                        e = retry_e
                
                print_centered(f"❌ Unrecoverable error processing {fund['Fund']}: {e}", "-")
                error_occurred = True
                break  # Exit the loop on unrecoverable error

    if error_occurred:
        print_centered("❌ Processing was halted due to an error. No filings were saved.")
        return

    save_non_quarterly_filings(nq_filings)
    print_centered(f"All funds processed - {len(nq_filings)} filing(s) saved", "-")


def run_fund_report():
    """
    3. Generates a 13F comparison report for a single, user-selected fund and period.

    This function prompts the user to choose a hedge fund from the known list and select a historical period (offset). 
    It then triggers the processing for that specific fund and period to generate and save a comparison report.
    """
    selected_fund = select_fund("Select the hedge fund for 13F report generation:")
    if not selected_fund:
        return

    selected_period = select_period()
    if selected_period is not None:
        process_fund(selected_fund, offset=selected_period[0])


def run_manual_cik_report():
    """
    4. Generates a 13F comparison report for a manually entered CIK.

    This function allows the user to input a 10-digit CIK directly and select a historical period (offset).
    It then triggers the processing for that CIK to generate and save a comparison report.
    """
    cik = input("Enter 10-digit CIK number: ").strip()
    if not cik:
        print("❌ CIK cannot be empty.")
        return

    selected_period = select_period()
    if selected_period is not None:
        process_fund({'CIK': cik}, offset=selected_period[0])


if __name__ == "__main__":
    actions = {
        '0': exit,
        '1': run_all_funds_report,
        '2': run_fetch_nq_filings,
        '3': run_fund_report,
        '4': run_manual_cik_report,
    }

    while True:
        try:
            horizontal_rule()
            print_centered(APP_NAME)
            horizontal_rule()
            print("0. Exit")
            print("1. Generate latest 13F reports for all known hedge funds")
            print("2. Fetch latest non-quarterly filings for all known hedge funds")
            print("3. Generate 13F report for a known hedge fund")
            print("4. Manually enter a hedge fund CIK to generate a 13F report")
            horizontal_rule()

            choice = input("Choose an option (0-4): ")
            action = actions.get(choice)
            if action:
                if action() is False:
                    break
            else:
                print("❌ Invalid selection. Try again.")
        except KeyboardInterrupt:
            print("\nOperation cancelled by user. Bye! 👋")
            break
