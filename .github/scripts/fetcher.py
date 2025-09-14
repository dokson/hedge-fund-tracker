import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from app.main import run_all_funds_report, run_fetch_latest_filings
from app.utils.database import sort_stocks


if __name__ == "__main__":
    print("::group::📅 Fetching 13F Reports")
    run_all_funds_report()
    print("::endgroup::✅ 13F reports fetched successfully.")

    print("::group::📜 Fetching Latest Non-Quarterly Filings")
    run_fetch_latest_filings()
    print("::endgroup::✅ Latest Non-Quarterly filings fetched successfully.")

    print("::notice title=Stocks Database Maintenance::🗃️ Sorting stocks database...")
    sort_stocks()
    print("✅ Stocks database sorted successfully.")
