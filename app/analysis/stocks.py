from app.utils.database import get_all_quarter_files
from app.utils.strings import format_percentage, format_value, get_numeric
from pathlib import Path
import pandas as pd


def _load_quarter_data(quarter):
    """
    Loads all fund comparison data for a given quarter (e.g., '2025Q1').

    Args:
        quarter (str): The quarter in 'YYYYQN' format.

    Returns:
        pd.DataFrame: A concatenated DataFrame of all fund data for the quarter
    """
    all_fund_data = []

    for file_path in get_all_quarter_files(quarter):
        fund_name = Path(file_path).stem
        
        df = pd.read_csv(file_path)

        total_row = df[df['CUSIP'] == 'Total']
        if total_row.empty:
            continue

        total_portfolio_value = get_numeric(total_row['Value'].iloc[0])

        df_stocks = df[df['CUSIP'] != 'Total'].copy()

        df_stocks.loc[:, 'Delta_Value_Num'] = df_stocks['Delta_Value'].apply(get_numeric)
        df_stocks.loc[:, 'Value_Num'] = df_stocks['Value'].apply(get_numeric)
        df_stocks.loc[:, 'Weighted_Delta_Pct'] = (df_stocks['Delta_Value_Num'] / total_portfolio_value) * 100
        df_stocks.loc[:, 'Fund'] = fund_name

        all_fund_data.append(df_stocks)

    return pd.concat(all_fund_data, ignore_index=True)


def analyze_quarter(quarter):
    """
    Analyzes stock data for a given quarter to find the most popular, bought, and sold stocks.
    
    Args:
        quarter (str): The quarter in 'YYYYQN' format.
    """
    df_quarter = _load_quarter_data(quarter)
    if df_quarter is None:
        return

    aggregation = {
        'Value_Num': 'sum',
        'Delta_Value_Num': 'sum',
        'Weighted_Delta_Pct': 'sum',
        'Fund': pd.Series.nunique,
        'CUSIP': [
            ('buyers', lambda x: (df_quarter.loc[x.index, 'Delta_Value_Num'] > 0).sum()),
            ('sellers', lambda x: (df_quarter.loc[x.index, 'Delta_Value_Num'] < 0).sum())
        ]
    }

    df_analysis = df_quarter.groupby(['CUSIP', 'Ticker', 'Company']).agg(aggregation).reset_index()
    df_analysis.columns = ['_'.join(col).strip('_') for col in df_analysis.columns.values]
    
    df_analysis.rename(columns={
        'Value_Num_sum': 'Total_Value',
        'Delta_Value_Num_sum': 'Total_Delta_Value',
        'Weighted_Delta_Pct_sum': 'Total_Weighted_Delta_Pct',
        'Fund_nunique': 'Holder_Count',
        'CUSIP_buyers': 'Buyer_Count',
        'CUSIP_sellers': 'Seller_Count'
    }, inplace=True)

    df_analysis['Net_Buyers'] = df_analysis['Buyer_Count'] - df_analysis['Seller_Count']

    print("\n" + "="*80)
    print(f"Stock Analysis for Quarter: {quarter}")
    print("="*80)

    def display_report(title, df, sort_by, ascending, cols, formatters):
        print(f"\n--- {title} ---\n")
        display_df = df.sort_values(by=sort_by, ascending=ascending).head(10)
        for col, formatter in formatters.items():
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(formatter)
        print(display_df[cols].to_string(index=False))

    value = lambda x: format_value(int(x))
    percentage = lambda x: format_percentage(x)
    
    cols_absolute = ['Ticker', 'Company', 'Total_Value', 'Total_Delta_Value', 'Holder_Count']
    formatters_abs = {'Total_Value': value, 'Total_Delta_Value': value}
    
    cols_weighted = ['Ticker', 'Company', 'Total_Weighted_Delta_Pct', 'Holder_Count', 'Net_Buyers']
    formatters_wgt = {'Total_Weighted_Delta_Pct': percentage}

    # Display reports
    display_report("Top 10 Buys (by Absolute Dollar Value)", df_analysis, 'Total_Delta_Value', False, cols_absolute, formatters_abs)
    display_report("Top 10 Sells (by Absolute Dollar Value)", df_analysis, 'Total_Delta_Value', True, cols_absolute, formatters_abs)
    display_report("Top 10 Buys (by Portfolio Impact %)", df_analysis, 'Total_Weighted_Delta_Pct', False, cols_weighted, formatters_wgt)
    display_report("Top 10 Sells (by Portfolio Impact %)", df_analysis, 'Total_Weighted_Delta_Pct', True, cols_weighted, formatters_wgt)
    display_report("Most Widely Held Stocks (by # of Funds)", df_analysis, ['Holder_Count', 'Total_Value'], False, ['Ticker', 'Company', 'Holder_Count', 'Net_Buyers', 'Total_Value'], {'Total_Value': value})
    display_report("Highest Conviction Buys (by Net # of Buyers)", df_analysis, ['Net_Buyers', 'Total_Delta_Value'], False, ['Ticker', 'Company', 'Net_Buyers', 'Buyer_Count', 'Seller_Count'], {})
