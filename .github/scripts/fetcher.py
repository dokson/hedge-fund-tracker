from app.main import run_all_funds_report, run_fetch_latest_schedules
from app.utils.database import sort_stocks
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))


if __name__ == "__main__":
    print("::group::📅 Fetching 13F Reports")
    run_all_funds_report()
    print("::endgroup::✅ 13F reports fetched successfully.")

    print("::group::📜 Fetching Latest Schedule Filings")
    run_fetch_latest_schedules()
    print("::endgroup::✅ Latest schedule filings fetched successfully.")

    print("::notice title=Stocks Database Maintenance::🗃️ Sorting stocks database...")
    sort_stocks()
    print("✅ Stocks database sorted successfully.")
