from app.analysis.non_quarterly import update_quarter_with_nq_filings
from app.utils.database import get_last_quarter, get_last_quarter_for_fund, load_fund_data, load_non_quarterly_data, load_quarterly_data, load_stocks
from app.utils.pd import get_numeric_series, get_percentage_number_series
from app.utils.strings import format_percentage
import numpy as np
import pandas as pd


def aggregate_quarter_by_fund(df_quarter) -> pd.DataFrame:
    """
    Aggregates quarter fund holdings at the Ticker level.

    Args:
        df_quarter (pd.DataFrame): The DataFrame containing quarterly data.

    Returns:
        pd.DataFrame: An aggregated DataFrame.
    """
    df_stocks = load_stocks()

    # Drop company/ticker from quarterly data to use master data instead. 
    # This ensures consistency and correctly aggregates data for companies that may have multiple CUSIPs
    df_quarter = df_quarter.drop(columns=['Ticker', 'Company']).set_index('CUSIP').join(df_stocks[['Ticker', 'Company']], how='left').reset_index()

    df_fund_quarter = (
        df_quarter.groupby(['Fund', 'Ticker', 'Company'])
        .agg(
            Shares=('Shares', 'sum'),
            Delta_Shares=('Delta_Shares', 'sum'),
            Value=('Value_Num', 'sum'),
            Delta_Value=('Delta_Value_Num', 'sum'),
            Portfolio_Pct=('Portfolio_Pct', 'sum'),
        )
        .reset_index()
    )

    # If the sum of Portfolio_Pct is 0 but there are shares, it means the position is composed of <0.01% holdings
    # We assign a small non-zero value to represent this
    df_fund_quarter.loc[(df_fund_quarter['Portfolio_Pct'] == 0) & (df_fund_quarter['Shares'] > 0), 'Portfolio_Pct'] = 0.009

    # 1. Calculate Portfolio_Pct_Rank for each stock within each fund
    df_fund_quarter['Portfolio_Pct_Rank'] = df_fund_quarter.groupby('Fund')['Portfolio_Pct'].rank(ascending=False, method='min')

    # 2. Calculate Fund_Concentration_Ratio (Sum of Portfolio_Pct for top 10 holdings) for each fund
    concentration_map = df_fund_quarter[df_fund_quarter['Portfolio_Pct_Rank'] <= 10].groupby('Fund')['Portfolio_Pct'].sum().to_dict()
    df_fund_quarter['Fund_Concentration_Ratio'] = df_fund_quarter['Fund'].map(concentration_map)

    # 3. Calculate Shares_Delta_Pct (Velocity of accumulation)
    # We only care about existing positions to avoid inflating new entry numbers
    previous_shares = df_fund_quarter['Shares'] - df_fund_quarter['Delta_Shares']
    df_fund_quarter['Shares_Delta_Pct'] = np.where(
        (previous_shares > 0) & (df_fund_quarter['Shares'] > 0),
        (df_fund_quarter['Delta_Shares'] / previous_shares) * 100,
        0
    )

    # Calculate 'Delta' based on aggregated values (for display/legacy compatibility)
    df_fund_quarter['Delta'] = df_fund_quarter.apply(
        lambda row:
        'CLOSE' if row['Shares'] == 0
        else 'NO CHANGE' if row['Delta_Shares'] == 0
        else 'NEW' if row['Shares'] > 0 and row['Shares'] == row['Delta_Shares']
        else format_percentage(row['Delta_Shares'] / (row['Shares'] - row['Delta_Shares']) * 100, True),
        axis=1
    )

    return df_fund_quarter


def get_quarter_data(quarter=get_last_quarter()) -> pd.DataFrame:
    """
    Loads and prepares quarterly data for analysis.

    - Loads raw quarterly data from CSV files.
    - If the specified quarter is the most recent one, it integrates the latest non-quarterly filings (13D/G, Form 4).
    - If a fund has not yet filed for the current quarter but has non-quarterly data, it pulls its most recent previous 13F as a baseline.

    Args:
        quarter (str, optional): The quarter to load, in 'YYYYQN' format. Defaults to the last available quarter.

    Returns:
        pd.DataFrame: A DataFrame containing the prepared quarterly data.
    """
    df_quarter = load_quarterly_data(quarter)

    # Identify funds that have filed this quarter
    idx_13f_funds = df_quarter['Fund'].unique().tolist()
    funds_to_update = [fund for fund in idx_13f_funds if get_last_quarter_for_fund(fund) == quarter]

    # Include non quarterly data if it's the most recent quarter
    if quarter == get_last_quarter():
        nq_df = load_non_quarterly_data()
        if not nq_df.empty:
            for fund in nq_df['Fund'].unique().tolist():
                if fund not in funds_to_update:
                    # Fund has NQ data but no 13F for this quarter.
                    # We pull its last 13F to serve as a baseline for comparisons.
                    fund_last_quarter = get_last_quarter_for_fund(fund)
                    if fund_last_quarter and fund_last_quarter != quarter:
                        fund_base_df = load_fund_data(fund, fund_last_quarter)
                        if not fund_base_df.empty:
                            df_quarter = pd.concat([df_quarter, fund_base_df], ignore_index=True)
                    funds_to_update.append(fund)

    # Process numeric columns (handles both original and appended baseline data)
    df_quarter['Delta_Value_Num'] = get_numeric_series(df_quarter['Delta_Value'])
    df_quarter['Value_Num'] = get_numeric_series(df_quarter['Value'])
    df_quarter['Portfolio_Pct'] = get_percentage_number_series(df_quarter['Portfolio%'])

    if funds_to_update:
        df_quarter = update_quarter_with_nq_filings(df_quarter, funds_to_update, idx_13f_funds)

    return df_quarter


def _calculate_fund_level_flags(df_fund_quarter: pd.DataFrame) -> pd.DataFrame:
    """
    Adds boolean flags to the fund-level DataFrame to categorize fund activity for each stock.

    Args:
        df_fund_quarter (pd.DataFrame): DataFrame with fund-level holdings data.

    Returns:
        pd.DataFrame: The input DataFrame with added boolean columns for activity type (e.g., 'is_buyer', 'is_seller', 'is_new').
    """
    df = df_fund_quarter.copy()
    df['is_buyer'] = df['Delta_Value'] > 0
    df['is_seller'] = df['Delta_Value'] < 0
    df['is_holder'] = df['Shares'] > 0
    df['is_new'] = (df['Shares'] > 0) & (df['Shares'] == df['Delta_Shares'])
    df['is_closed'] = df['Shares'] == 0
    
    # High Conviction Signal: NEW position in Top 10 OR > 3% weighting
    df['is_high_conviction'] = df['is_new'] & ((df['Portfolio_Pct_Rank'] <= 10) | (df['Portfolio_Pct'] > 3.0))
    
    return df


def _aggregate_stock_data(df_fund_quarter_with_flags: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates fund-level data to the stock level.

    This function groups the data by stock and calculates summary statistics, such as total value, total delta value, and counts of different fund activities.

    Args:
        df_fund_quarter_with_flags (pd.DataFrame): DataFrame with fund-level data and activity flags.

    Returns:
        pd.DataFrame: An aggregated DataFrame with one row per stock, summarizing institutional activity.
    """
    aggregation_rules = {
        'Total_Value': ('Value', 'sum'),
        'Total_Delta_Value': ('Delta_Value', 'sum'),
        'Max_Portfolio_Pct': ('Portfolio_Pct', 'max'),
        'Avg_Portfolio_Pct': ('Portfolio_Pct', 'mean'),
        'Buyer_Count': ('is_buyer', 'sum'),
        'Seller_Count': ('is_seller', 'sum'),
        'Holder_Count': ('is_holder', 'sum'),
        'New_Holder_Count': ('is_new', 'sum'),
        'Close_Count': ('is_closed', 'sum'),
        'High_Conviction_Count': ('is_high_conviction', 'sum'),
        'Avg_Fund_Concentration': ('Fund_Concentration_Ratio', 'mean'),
    }
    
    df_agg = df_fund_quarter_with_flags.groupby(['Ticker', 'Company']).agg(**aggregation_rules).reset_index()

    # Calculate Avg_Ownership_Delta only for funds that increased their position (is_buyer)
    # but excluding NEW positions (to get a clean velocity of accumulation for existing holders)
    mask_accumulation = df_fund_quarter_with_flags['is_buyer'] & ~df_fund_quarter_with_flags['is_new']
    avg_delta_map = df_fund_quarter_with_flags[mask_accumulation].groupby(['Ticker'])['Shares_Delta_Pct'].mean().to_dict()
    df_agg['Ownership_Delta_Avg'] = df_agg['Ticker'].map(avg_delta_map).fillna(0)

    return df_agg


def _calculate_derived_metrics(df_analysis: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates derived metrics like Net_Buyers, Delta, and modern institutional KPIs.
    """
    df = df_analysis.copy()
    df['Net_Buyers'] = df['Buyer_Count'] - df['Seller_Count']
    df['Buyer_Seller_Ratio'] = np.where(df['Seller_Count'] > 0, df['Buyer_Count'] / df['Seller_Count'], np.inf)
    
    previous_total_value = np.where(df['Total_Value'] - df['Total_Delta_Value'] == 0, np.nan, df['Total_Value'] - df['Total_Delta_Value'])
    df['Delta'] = np.where((df_analysis['New_Holder_Count'] == df_analysis['Holder_Count']) & (df_analysis['Close_Count'] == 0), np.inf, df_analysis['Total_Delta_Value'] / previous_total_value * 100)
    
    # KPIs for AI Prompt Analysis
    df['Portfolio_Concentration_Avg'] = df['Avg_Fund_Concentration']
    
    return df


def quarter_analysis(quarter) -> pd.DataFrame:
    """
    Analyzes stock data for a given quarter to find the most popular, bought, and sold stocks.
    
    Args:
        quarter (str): The quarter in 'YYYYQN' format.

    Returns:
        pd.DataFrame: A DataFrame with aggregated stock analysis for the quarter
    """
    # Fund level calculation
    df_fund_quarter = aggregate_quarter_by_fund(get_quarter_data(quarter))
    df_fund_quarter_with_flags = _calculate_fund_level_flags(df_fund_quarter)
    df_analysis = _aggregate_stock_data(df_fund_quarter_with_flags)

    return _calculate_derived_metrics(df_analysis)


def stock_analysis(ticker, quarter):
    """
    Analyzes a single stock for a given quarter, returning a list of funds that hold it.
    
    Args:
        ticker (str): The stock ticker to analyze.
        quarter (str): The quarter in 'YYYYQN' format.

    Returns:
        pd.DataFrame: A DataFrame with fund-level details for the specified stock.
    """
    df_quarter = get_quarter_data(quarter)

    # Aggregates data for Ticker that may have multiple CUSIPs in the same hedge fund report
    return aggregate_quarter_by_fund(df_quarter[df_quarter['Ticker'] == ticker])


def fund_analysis(fund, quarter) -> pd.DataFrame:
    """
    Analyzes a single fund for a given quarter, returning its holdings.

    Args:
        fund (str): The fund to analyze.
        quarter (str): The quarter in 'YYYYQN' format.

    Returns:
        pd.DataFrame: A DataFrame with stock-level details for the specified fund.
    """
    df_quarter = get_quarter_data(quarter)
    df_fund_quarter = aggregate_quarter_by_fund(df_quarter)
    return df_fund_quarter[df_fund_quarter['Fund'] == fund]
