import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from app.database import clean_stocks, sort_stocks
from app.utils.github import raised_alerts
from app.utils.run_summary import FetchRunSummary, render_markdown, write_step_summary
from database.updater import run_all_funds_report, run_fetch_nq_filings

if __name__ == "__main__":
    print("::group::📅 Fetching 13F Reports")
    reports_saved = run_all_funds_report()
    print("::endgroup::✅ 13F reports fetched successfully.")

    print("::group::📜 Fetching Non-Quarterly Filings")
    nq = run_fetch_nq_filings()
    print("::endgroup::✅ Non-Quarterly filings fetched successfully.")

    print("::notice title=Stocks Database Maintenance::🧹 Cleaning stocks database...")
    clean_stocks()
    print("::notice title=Stocks Database Maintenance::🗃️ Sorting stocks database...")
    sort_stocks()
    print("::notice title=Stocks Database Maintenance::✅ Stocks database maintenance completed.")

    write_step_summary(
        render_markdown(
            FetchRunSummary(
                funds=nq.funds,
                reports_saved=reports_saved,
                nq_rows_saved=nq.rows_saved,
                nq_failed_funds=nq.failed_funds,
                nq_saved=nq.saved,
                alerts=tuple(raised_alerts()),
            )
        )
    )
