"""
Scan the saved 13F filings for rows priced unlike their CUSIP and update the
register database/filing_anomalies.csv, auto-correcting the unambiguous ones;
then warn about tracked funds with no 13F saved for some quarter.

Corrections take effect when the filing is parsed again:
    pipenv run check-filings
    pipenv run regenerate <fund ...>
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import get_funds_missing_quarters  # noqa: E402
from app.database.filing_anomalies import check_filings  # noqa: E402
from app.utils.logger import get_logger, log_safe  # noqa: E402

logger = get_logger(__name__)

if __name__ == "__main__":
    check_filings()
    for fund, quarters in sorted(get_funds_missing_quarters().items()):
        logger.warning("%s has no 13F saved for %s", log_safe(fund), ", ".join(quarters))
