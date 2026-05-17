import pandas as pd

from app.utils.database import load_gics_hierarchy
from app.utils.logger import get_logger

logger = get_logger(__name__)


def load_standard_sectors() -> pd.DataFrame:
    """
    Returns a DataFrame of unique GICS Sectors and their codes.

    Returns:
        pd.DataFrame: A DataFrame with columns 'Sector Code' and 'Sector'.
    """
    try:
        hierarchy_df = load_gics_hierarchy()
        if hierarchy_df.empty:
            return pd.DataFrame()
        return hierarchy_df[["Sector Code", "Sector"]].drop_duplicates().reset_index(drop=True)
    except Exception:
        logger.error("while loading standard sectors", exc_info=True)
        return pd.DataFrame()


def load_yf_sectors() -> pd.DataFrame:
    """
    Derives the sectors from the GICS hierarchy file formatted for yfinance.

    Returns:
        pd.DataFrame: A DataFrame with sector info (Key, Name).
    """
    try:
        # Extract unique sectors
        sectors = load_standard_sectors()

        # Mapping to yfinance keys (manual overrides where name doesn't match standard slug)
        yfinance_overrides = {
            "Information Technology": "technology",
            "Financials": "financial-services",
            "Health Care": "healthcare",
            "Utilities": "utilities",
            "Real Estate": "real-estate",
            "Communication Services": "communication-services",
            "Materials": "basic-materials",
            "Consumer Discretionary": "consumer-cyclical",
            "Consumer Staples": "consumer-defensive",
        }

        def get_yfinance_key(sector_name):
            if sector_name in yfinance_overrides:
                return yfinance_overrides[sector_name]
            return sector_name.lower().replace(" ", "-")

        sectors["Key"] = sectors["Sector"].apply(get_yfinance_key)

        return sectors.rename(columns={"Sector": "Name"}).reset_index(drop=True)
    except Exception:
        logger.error("while deriving yfinance sectors from hierarchy", exc_info=True)
        return pd.DataFrame()


def load_industry_groups() -> pd.DataFrame:
    """
    Returns a DataFrame of unique GICS Industry Groups and their codes.

    Returns:
        pd.DataFrame: A DataFrame with columns 'Industry Group Code' and 'Industry Group'.
    """
    try:
        hierarchy_df = load_gics_hierarchy()
        if hierarchy_df.empty:
            return pd.DataFrame()
        return (
            hierarchy_df[["Industry Group Code", "Industry Group"]]
            .drop_duplicates()
            .reset_index(drop=True)
        )
    except Exception:
        logger.error("while loading industry groups", exc_info=True)
        return pd.DataFrame()


def load_industries() -> pd.DataFrame:
    """
    Returns a DataFrame of unique GICS Industries and their codes.

    Returns:
        pd.DataFrame: A DataFrame with columns 'Industry Code' and 'Industry'.
    """
    try:
        hierarchy_df = load_gics_hierarchy()
        if hierarchy_df.empty:
            return pd.DataFrame()
        return hierarchy_df[["Industry Code", "Industry"]].drop_duplicates().reset_index(drop=True)
    except Exception:
        logger.error("while loading industries", exc_info=True)
        return pd.DataFrame()


def load_sub_industries() -> pd.DataFrame:
    """
    Returns a DataFrame of unique GICS Sub-Industries and their codes.

    Returns:
        pd.DataFrame: A DataFrame with columns 'Sub-Industry Code' and 'Sub-Industry'.
    """
    try:
        hierarchy_df = load_gics_hierarchy()
        if hierarchy_df.empty:
            return pd.DataFrame()
        return (
            hierarchy_df[["Sub-Industry Code", "Sub-Industry"]]
            .drop_duplicates()
            .reset_index(drop=True)
        )
    except Exception:
        logger.error("while loading sub-industries", exc_info=True)
        return pd.DataFrame()
