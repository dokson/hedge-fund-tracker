"""
Generate the manifests of the logos uploaded to Cloudinary by hand, read by the frontend:
- app/frontend/src/data/curatedFavicons.json: fund hosts with a favicon in funds/favicons/
- app/frontend/src/data/curatedLogos.json: tickers with a company logo in stocks/logos/

The frontend only requests a curated asset its manifest lists: requesting one that does not
exist logs a 404 in the browser console before the next source is tried. Rerun after uploading
or deleting one (needs CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET):
    pipenv run gen-logos
"""

import json
import os
import sys
from pathlib import Path

from curl_cffi import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.utils.logger import get_logger  # noqa: E402

logger = get_logger(__name__)

DATA = ROOT / "app" / "frontend" / "src" / "data"
# Mirrors CLOUDINARY_CLOUD_NAME in app/frontend/src/lib/config.ts.
CLOUDINARY_CLOUD_NAME = "dskksi2dd"
# Cloudinary folder → the manifest listing the names (file name without extension) it holds.
MANIFESTS = {
    "funds/favicons/": DATA / "curatedFavicons.json",
    "stocks/logos/": DATA / "curatedLogos.json",
}


def list_png_names(folder: str, auth: tuple[str, str]) -> list[str]:
    """
    The names of the PNG images uploaded under ``folder``, sorted, through the Admin API.
    """
    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/resources/image/upload"
    names: list[str] = []
    cursor: str | None = None
    while True:
        params = {"prefix": folder, "max_results": "500"}
        if cursor:
            params["next_cursor"] = cursor
        response = requests.get(url, params=params, auth=auth, timeout=30)
        response.raise_for_status()
        page = response.json()
        names += [
            resource["public_id"].removeprefix(folder)
            for resource in page.get("resources", [])
            if resource.get("format") == "png"
        ]
        cursor = page.get("next_cursor")
        if not cursor:
            return sorted(names)


def main() -> None:
    """
    Write one manifest per Cloudinary folder of curated logos.
    """
    key, secret = os.environ.get("CLOUDINARY_API_KEY"), os.environ.get("CLOUDINARY_API_SECRET")
    if not key or not secret:
        sys.exit("CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET are required (see .env).")
    for folder, manifest in MANIFESTS.items():
        names = list_png_names(folder, (key, secret))
        manifest.write_text(json.dumps(names, indent=2) + "\n", encoding="utf-8", newline="\n")
        logger.success("%d curated logos in %s: wrote %s", len(names), folder, manifest.name)


if __name__ == "__main__":
    main()
