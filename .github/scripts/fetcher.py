import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from app.main import run_all_funds_report, run_fetch_latest_schedules

if __name__ == "__main__":
    print("::group::🚀 Starting 13F filing fetch")
    run_all_funds_report()
    print("::endgroup:: ✅ 13F filing fetch completed.")

    print("::group::🚀 Starting schedule filing fetch")
    run_fetch_latest_schedules()
    print("::endgroup:: ✅ Schedule filing fetch completed.")
