import os
from app.main import run_fetch_latest_schedules

if __name__ == "__main__":
    is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'

    if is_github_actions:
        print("::group::🚀 Starting daily schedule filing fetch")

    run_fetch_latest_schedules()

    if is_github_actions:
        print("::endgroup:: ✅ Daily schedule filing fetch completed.")
