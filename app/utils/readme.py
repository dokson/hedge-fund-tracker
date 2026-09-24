import re
from pathlib import Path

import pandas as pd

from app.database import DB_FOLDER
from app.database import EXCLUDED_HEDGE_FUNDS_FILE as EXCLUDED_FILENAME
from app.utils.logger import get_logger
from app.utils.pd import atomic_write_text

logger = get_logger(__name__)

EXCLUDED_HEDGE_FUNDS_FILE = f"{DB_FOLDER}/{EXCLUDED_FILENAME}"
README_FILE = "./README.md"
README_DISPLAY_LIMIT = 60


def generate_excluded_funds_list() -> str | None:
    """
    Generates a markdown list of the first N excluded funds from a CSV file.
    """
    try:
        df = pd.read_csv(EXCLUDED_HEDGE_FUNDS_FILE, keep_default_na=False)

        markdown_list = []
        # Iterate over the first N funds defined by README_DISPLAY_LIMIT
        for row in df.head(README_DISPLAY_LIMIT).itertuples():
            manager = row.Manager
            fund = row.Fund
            url = row.URL

            if manager and manager != fund:
                markdown_list.append(f"- _{manager!s}_'s [{fund!s}]({url!s})")
            else:
                markdown_list.append(f"- [{fund!s}]({url!s})")

        if len(df) > README_DISPLAY_LIMIT:
            file_path = EXCLUDED_HEDGE_FUNDS_FILE.replace("./", "")
            markdown_list.append(
                f"- and many more... (see [`{file_path}`](/{file_path}) for the full list)"
            )

        return "\n".join(markdown_list)
    except FileNotFoundError:
        logger.error("%s was not found.", EXCLUDED_HEDGE_FUNDS_FILE, exc_info=True)
        return None


def update_readme() -> None:
    """
    Updates the README.md file with the list of excluded funds.
    """
    content = generate_excluded_funds_list()
    if content is not None:
        try:
            with Path(README_FILE).open(encoding="utf-8", newline="") as f:
                readme_text = f.read()

            newline = "\r\n" if "\r\n" in readme_text else "\n"
            block = newline.join(content.splitlines())
            new_readme_text = re.sub(
                r"(<!-- EXCLUDED_FUNDS_LIST_START -->)(.*?)(<!-- EXCLUDED_FUNDS_LIST_END -->)",
                lambda m: f"{m.group(1)}{newline}{block}{newline}{m.group(3)}",
                readme_text,
                flags=re.DOTALL,
            )

            atomic_write_text(README_FILE, new_readme_text)
        except FileNotFoundError:
            logger.error("%s was not found.", README_FILE, exc_info=True)
