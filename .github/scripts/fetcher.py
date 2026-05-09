import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from app.utils.database import clean_stocks, sort_stocks
from database.GICS.updater import main as update_gics_hierarchy
from database.updater import run_all_funds_report, run_fetch_nq_filings

if __name__ == "__main__":
    print("::group::🗃️ Updating GICS Hierarchy")
    update_gics_hierarchy()
    print("::endgroup::✅ GICS hierarchy updated successfully.")

    print("::group::📅 Fetching 13F Reports")
    run_all_funds_report()
    print("::endgroup::✅ 13F reports fetched successfully.")

    print("::group::📜 Fetching Non-Quarterly Filings")
    run_fetch_nq_filings()
    print("::endgroup::✅ Non-Quarterly filings fetched successfully.")

    print("::notice title=Stocks Database Maintenance::🧹 Cleaning stocks database...")
    clean_stocks()
    print("::notice title=Stocks Database Maintenance::🗃️ Sorting stocks database...")
    sort_stocks()
    print("::notice title=Stocks Database Maintenance::✅ Stocks database maintenance completed.")
