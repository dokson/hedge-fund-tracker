from app.analysis.non_quarterly import update_quarter_with_nq_filings
from app.utils.database import get_last_quarter, get_last_quarter_for_fund, load_quarterly_data, load_stocks
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

    # Calculate 'Delta' based on aggregated values
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
    - Converts string-based numeric columns ('Value', 'Delta_Value', 'Portfolio%') to numeric types.
    - If the specified quarter is the most recent one, it integrates the latest non-quarterly filings (13D/G, Form 4) to provide an up-to-date view of holdings.

    Args:
        quarter (str, optional): The quarter to load, in 'YYYYQN' format. Defaults to the last available quarter.

    Returns:
        pd.DataFrame: A DataFrame containing the prepared quarterly data.
    """
    df_quarter = load_quarterly_data(quarter)

    df_quarter['Delta_Value_Num'] = get_numeric_series(df_quarter['Delta_Value'])
    df_quarter['Value_Num'] = get_numeric_series(df_quarter['Value'])
    df_quarter['Portfolio_Pct'] = get_percentage_number_series(df_quarter['Portfolio%'])

    # Identify if there are funds in the current DataFrame at their most recent filing quarter.
    # The update with non-quarterly data should only apply to them.
    funds_to_update = [fund for fund in df_quarter['Fund'].unique() if get_last_quarter_for_fund(fund) == quarter]

    if funds_to_update:
        df_quarter = update_quarter_with_nq_filings(df_quarter, funds_to_update)

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
    }
    return df_fund_quarter_with_flags.groupby(['Ticker', 'Company']).agg(**aggregation_rules).reset_index()


def _calculate_derived_metrics(df_analysis: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates derived metrics like Net_Buyers, Delta, and Buyer_Seller_Ratio.
    """
    df = df_analysis.copy()
    df['Net_Buyers'] = df['Buyer_Count'] - df['Seller_Count']
    df['Buyer_Seller_Ratio'] = np.where(df['Seller_Count'] > 0, df['Buyer_Count'] / df['Seller_Count'], np.inf)
    previous_total_value = np.where(df['Total_Value'] - df['Total_Delta_Value'] == 0, np.nan, df['Total_Value'] - df['Total_Delta_Value'])
    df['Delta'] = np.where((df_analysis['New_Holder_Count'] == df_analysis['Holder_Count']) & (df_analysis['Close_Count'] == 0), np.inf, df_analysis['Total_Delta_Value'] / previous_total_value * 100)
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
