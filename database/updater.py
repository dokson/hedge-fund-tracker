from app.analysis.non_quarterly import get_non_quarterly_filings_dataframe
from app.analysis.quarterly_report import generate_comparison
from app.scraper.sec_scraper import fetch_latest_two_13f_filings, fetch_non_quarterly_after_date, get_latest_13f_filing_date
from app.scraper.xml_processor import xml_to_dataframe_13f
from app.utils.console import horizontal_rule, print_centered, print_centered_table, select_fund, select_period
from app.utils.database import clean_stocks, get_funds_missing_quarters, delete_fund_from_database, load_hedge_funds, save_comparison, save_non_quarterly_filings, sort_stocks, update_ticker, update_ticker_for_cusip
from app.utils.readme import update_readme
from app.utils.strings import get_previous_quarter_end_date
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from tabulate import tabulate
import os


APP_NAME = "HEDGE FUND TRACKER - DATABASE UPDATER"


def exit():
    """
    0. Exits the application (after maintenance operations).

    This function cleans orphan CUSIPs, sorts the stock master file and updates the README with the latest data.
    """
    clean_stocks()
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
        
        target_date = get_previous_quarter_end_date(latest_date)
        target_date_prev = get_previous_quarter_end_date(target_date)

        found_previous = None
        fallback_previous = None

        # Exhaustive search: prioritized target_date, fallback target_date_prev
        while previous_filing:
            ref_date = previous_filing['reference_date']
            pub_date = previous_filing['date']
            
            if ref_date == target_date:
                found_previous = previous_filing
                break
            
            if ref_date == target_date_prev and not fallback_previous:
                fallback_previous = previous_filing
            
            # Smart stop: if published date is already older than the fallback reporting date, 
            # we can't possibly find a newer reporting period further down the list.
            if pub_date < target_date_prev:
                break
            
            offset += 1
            filings = fetch_latest_two_13f_filings(cik, offset)
            previous_filing = filings[1] if len(filings) == 2 else None

        previous_filing = found_previous or fallback_previous

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

    # Use 1 worker on GitHub Actions to stay within rate limits and have cleaner logs
    max_workers = 1 if os.getenv('GITHUB_ACTIONS') == 'true' else 5
    if max_workers == 1:
        print("Running sequentially (GitHub Actions detected).")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
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

    # Use 1 worker on GitHub Actions to stay within rate limits and have cleaner logs
    max_workers = 1 if os.getenv('GITHUB_ACTIONS') == 'true' else 5
    if max_workers == 1:
        print("Running sequentially (GitHub Actions detected).")

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
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


def run_ticker_update():
    """
    5. Updates a stock ticker across the entire database.
    
    This function prompts the user to enter an old ticker and a new ticker,
    then updates all occurrences in stocks.csv, all quarterly filings, and non-quarterly filings.
    """
    horizontal_rule()
    print_centered("TICKER UPDATE UTILITY")
    horizontal_rule()
    print("This will update a ticker across:")
    print("  - stocks.csv (master data file)")
    print("  - All filings")
    horizontal_rule()
    
    old_ticker = input("Enter the OLD ticker to replace: ").strip().upper()
    if not old_ticker:
        print("❌ Old ticker cannot be empty.")
        return
    
    new_ticker = input("Enter the NEW ticker: ").strip().upper()
    if not new_ticker:
        print("❌ New ticker cannot be empty.")
        return
    
    update_ticker(old_ticker, new_ticker)


def run_cusip_ticker_update():
    """
    6. Updates a stock ticker for a single CUSIP across the entire database.
    
    This function prompts the user to enter a CUSIP and a new ticker,
    then updates that specific CUSIP in stocks.csv, all quarterly filings, and non-quarterly filings.
    """
    horizontal_rule()
    print_centered("CUSIP TICKER UPDATE UTILITY")
    horizontal_rule()
    print("This will update the ticker for a single CUSIP across:")
    print("  - stocks.csv (master data file)")
    print("  - All filings")
    horizontal_rule()
    
    cusip = input("Enter the CUSIP: ").strip()
    if not cusip:
        print("❌ CUSIP cannot be empty.")
        return
    
    new_ticker = input("Enter the NEW ticker: ").strip().upper()
    if not new_ticker:
        print("❌ New ticker cannot be empty.")
        return
    
    update_ticker_for_cusip(cusip, new_ticker)
    

def run_delete_fund():
    """
    7. Deletes a hedge fund from the database and adds it to the excluded list.
    """
    selected_fund = select_fund("Select the hedge fund to DELETE:")
    if not selected_fund:
        return

    print(f"To confirm deletion of '{selected_fund['Fund']}', please enter its website URL.")
    url = input("Website URL (must start with 'http'): ").strip()
    
    if url.lower().startswith('http'):
        delete_fund_from_database(selected_fund, url=url)
    else:
        print("❌ Invalid URL or operation cancelled. Deletion aborted.")


def print_missing_quarters_report():
    """
    8. Shows funds with missing quarters.
    """
    horizontal_rule()
    print_centered("MISSING QUARTERS REPORT")
    horizontal_rule()
    
    missing_quarters = get_funds_missing_quarters()
    
    if not missing_quarters:
        print("✅ No funds with missing quarters found.")
        return

    data = [[fund, ", ".join(quarters)] for fund, quarters in missing_quarters.items()]
    
    print_centered_table(tabulate(data, headers=["Fund", "Missing Quarters"], tablefmt="psql", stralign="left"))
    horizontal_rule()


if __name__ == "__main__":
    actions = {
        '0': exit,
        '1': run_all_funds_report,
        '2': run_fetch_nq_filings,
        '3': run_fund_report,
        '4': run_manual_cik_report,
        '5': run_ticker_update,
        '6': run_cusip_ticker_update,
        '7': run_delete_fund,
        '8': print_missing_quarters_report
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
            print("5. Update a stock ticker across the entire database")
            print("6. Update a stock ticker for a single CUSIP")
            print("7. Delete a hedge fund from the database")
            print("8. Show funds with missing quarters")
            horizontal_rule()

            choice = input("Choose an option (0-8): ")
            action = actions.get(choice)
            if action:
                if action() is False:
                    break
            else:
                print("❌ Invalid selection. Try again.")
        except KeyboardInterrupt:
            print("\nOperation cancelled by user. Bye! 👋")
            break
