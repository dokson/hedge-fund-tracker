from app.ai.agent import AnalystAgent
from app.analysis.non_quarterly import get_nq_filings_info
from app.analysis.stocks import aggregate_quarter_by_fund, get_quarter_data, quarter_analysis, stock_analysis
from app.utils.console import horizontal_rule, print_centered, print_dataframe, select_ai_model, select_quarter
from app.utils.database import get_last_quarter, load_hedge_funds
from app.utils.strings import format_percentage, format_value, get_percentage_formatter, get_signed_perc_formatter, get_value_formatter
import numpy as np


APP_NAME = "HEDGE FUND TRACKER"


def run_view_nq_filings():
    """
    1. View latest filings activity from Schedules 13D/G and Form 4 filings.
    """
    nq_filings_df = get_nq_filings_info(aggregate_quarter_by_fund(get_quarter_data()))
    latest_n = 30

    print_dataframe(
        nq_filings_df, latest_n, title=f"LATEST {latest_n} 13D/G AND FORM 4 FILINGS", sort_by=['Date', 'Fund', 'Portfolio_Pct'],
        cols=['Date', 'Fund', 'Ticker', 'Shares', 'Delta_Shares', 'Delta', 'Avg_Price', 'Value', 'Portfolio_Pct'],
        formatters={'Delta': get_signed_perc_formatter(), 'Shares': get_value_formatter(), 'Delta_Shares': get_value_formatter(), 'Portfolio_Pct': get_percentage_formatter(),}
    )


def run_quarter_analysis():
    """
    2. Analyze stock trends for a quarter.
    """
    selected_quarter = select_quarter()
    if selected_quarter:
        df_analysis = quarter_analysis(selected_quarter)
        horizontal_rule('-')
        print_centered(f"{selected_quarter} QUARTER ANALYSIS:")
        horizontal_rule('-')

        top_n = 15
        print_dataframe(df_analysis, top_n, f'Top {top_n} Consensus Buys (by Net # of Buyers)', ['Net_Buyers', 'Buyer_Count', 'Total_Delta_Value'], ['Ticker', 'Company', 'Delta', 'Net_Buyers', 'Buyer_Count', 'Seller_Count', 'Holder_Count', 'Total_Delta_Value', 'Total_Value'], {'Delta': get_signed_perc_formatter(), 'Total_Delta_Value': get_value_formatter(), 'Total_Value': get_value_formatter()})
        print_dataframe(df_analysis, top_n, f'Top {top_n} New Consensus (by # of New Holders)', ['New_Holder_Count', 'Total_Delta_Value'], ['Ticker', 'Company', 'New_Holder_Count', 'Net_Buyers', 'Holder_Count', 'Delta', 'Total_Delta_Value', 'Total_Value'], {'Delta': get_signed_perc_formatter(), 'Total_Delta_Value': get_value_formatter(), 'Total_Value': get_value_formatter()})
        print_dataframe(df_analysis[(df_analysis['Delta'] != np.inf) & (df_analysis['Total_Delta_Value'] > 150_000_000)], top_n, f'Top {top_n} Increasing Positions (by Delta)', 'Delta', ['Ticker', 'Company', 'New_Holder_Count', 'Net_Buyers', 'Holder_Count', 'Delta', 'Total_Delta_Value', 'Total_Value'], {'Delta': get_signed_perc_formatter(), 'Total_Delta_Value': get_value_formatter(), 'Total_Value': get_value_formatter()})
        print_dataframe(df_analysis, top_n, f'Top {top_n} Big Bets (by Max Portfolio %)', 'Max_Portfolio_Pct', ['Ticker', 'Company', 'Max_Portfolio_Pct', 'Avg_Portfolio_Pct', 'Delta', 'Total_Delta_Value', 'Total_Value'], {'Max_Portfolio_Pct': get_percentage_formatter(), 'Avg_Portfolio_Pct': get_percentage_formatter(), 'Delta': get_signed_perc_formatter(), 'Total_Delta_Value': get_value_formatter(), 'Total_Value': get_value_formatter()})
        print_dataframe(df_analysis[(df_analysis['Holder_Count'] >= round(len(load_hedge_funds())/10))], top_n, f'Average {top_n} Stocks Portfolio', 'Avg_Portfolio_Pct', ['Ticker', 'Company', 'Avg_Portfolio_Pct', 'Max_Portfolio_Pct', 'Holder_Count', 'Delta'], {'Avg_Portfolio_Pct': get_percentage_formatter(), 'Max_Portfolio_Pct': get_percentage_formatter(), 'Delta': get_signed_perc_formatter()})
        print("\n")


def run_single_stock_analysis():
    """
    3. Analyze a single stock for a specific quarter.
    """
    selected_quarter = select_quarter()
    if selected_quarter:
        ticker = input("Enter stock ticker to analyze: ").strip().upper()
        if not ticker:
            print("❌ Ticker cannot be empty.")
            return
        
        df_analysis = stock_analysis(ticker, selected_quarter)

        if df_analysis.empty:
            print(f"❌ No data found for ticker {ticker} in quarter {selected_quarter}.")
            return
        
        horizontal_rule('-')
        print_centered(f"{ticker} ({df_analysis['Company'].iloc[0]}) - {selected_quarter} QUARTER ANALYSIS")
        horizontal_rule('-')

        total_value = df_analysis['Value'].sum()
        total_delta_value = df_analysis['Delta_Value'].sum()
        avg_percentage = df_analysis['Portfolio_Pct'].mean()
        max_percentage = df_analysis['Portfolio_Pct'].max()
        num_buyers = (df_analysis['Delta_Value'] > 0).sum()
        num_sellers = (df_analysis['Delta_Value'] < 0).sum()
        holder_count = (df_analysis['Delta'] != 'CLOSE').sum()
        new_holder_count = (df_analysis['Delta'].str.startswith('NEW')).sum()
        close_count = (df_analysis['Delta'] == 'CLOSE').sum()
        delta = total_delta_value / total_value * 100 if total_value != 0 else np.nan

        print("\n")
        print_centered(f"TOTAL HELD: {format_value(total_value)}")
        print_centered(f"DELTA VALUE: {format_value(total_delta_value)} / DELTA %: {"NEW" if holder_count == new_holder_count and close_count == 0 else format_percentage(delta, True)}")
        print_centered(f"AVG PTF %: {format_percentage(avg_percentage, decimal_places=2)} / MAX PTF %: {format_percentage(max_percentage)}")
        print_centered(f"HOLDERS: {len(df_analysis)}")
        print_centered(f"BUYERS: {num_buyers} ({new_holder_count} new) / SELLERS: {num_sellers} ({close_count} sold out)")
        print_centered(f"BUYER/SELLER RATIO: {format_value(num_buyers / num_sellers if num_sellers > 0 else float('inf'))}")

        print_dataframe(
            df_analysis, len(df_analysis), title=f'Holders by Shares', sort_by='Shares', 
            cols=['Fund', 'Portfolio_Pct', 'Shares', 'Value', 'Delta', 'Delta_Value'], 
            formatters={'Portfolio_Pct': get_percentage_formatter(), 'Shares': get_value_formatter(), 'Value': get_value_formatter(), 'Delta_Value': get_value_formatter()}
        )
        print("\n")


def run_ai_analyst():
    """
    4. Run AI Analyst
    """
    selected_model = select_ai_model()
    if not selected_model:
        return

    try:
        client_class = selected_model['Client']
        client = client_class(model=selected_model['ID'])
        print_centered(f"Starting AI Analysis using {selected_model['Description']}", "-")

        top_n = 30
        agent = AnalystAgent(get_last_quarter(), ai_client=client)
        scored_list = agent.generate_scored_list(top_n)
        title = f'Best {top_n} Promising Stocks according to {selected_model['Description']}'
        print_dataframe(scored_list, top_n, title=title, sort_by='Promise_Score', cols=['Ticker', 'Company', 'Industry', 'Promise_Score', 'Risk_Score', 'Low_Volatility_Score', 'Momentum_Score', 'Growth_Score'])
    except Exception as e:
        print(f"❌ An unexpected error occurred while running AI Financial Agent: {e}")


if __name__ == "__main__":
    actions = {
        '0': lambda: False,
        '1': run_view_nq_filings,
        '2': run_quarter_analysis,
        '3': run_single_stock_analysis,
        '4': run_ai_analyst,
    }

    while True:
        try:
            horizontal_rule()
            print_centered(APP_NAME)
            horizontal_rule()
            print("0. Exit")
            print("1. View latest non-quarterly filings activity (from Schedules 13D/G and Form 4)")
            print("2. Analyze stock trends for a quarter")
            print("3. Analyze a single stock for a quarter")
            print("4. Run AI Analyst for most promising stocks")
            horizontal_rule()

            main_choice = input("Choose an option (0-4): ")
            action = actions.get(main_choice)
            if action:
                if action() is False:
                    print("Bye! 👋 Exited.")
                    break
            else:
                print("❌ Invalid selection. Try again.")
        except KeyboardInterrupt:
            print("\nOperation cancelled by user. Bye! 👋")
            break
