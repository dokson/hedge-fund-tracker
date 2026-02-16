from app.ai.agent import AnalystAgent
from app.analysis.performance_evaluator import PerformanceEvaluator
from app.analysis.stocks import aggregate_quarter_by_fund, fund_analysis, get_quarter_data, quarter_analysis, stock_analysis
from app.stocks.libraries.yfinance import YFinance
from app.stocks.price_fetcher import PriceFetcher
from app.utils.console import horizontal_rule, print_centered, print_dataframe, print_fund, select_ai_model, select_fund, select_quarter
from app.utils.database import count_funds_in_quarter, get_all_quarters, get_last_quarter, get_most_recent_quarter, load_non_quarterly_data
from app.utils.strings import format_percentage, format_value, get_percentage_formatter, get_price_formatter, get_signed_perc_formatter, get_string_formatter, get_value_formatter
import numpy as np
import pandas as pd

APP_NAME = "HEDGE FUND TRACKER"


def run_view_nq_filings():
    """
    1. View latest filings activity from Schedules 13D/G and Form 4 filings.
    """
    non_quarterly_filings_df = load_non_quarterly_data().set_index(['Fund', 'Ticker'])

    # Load the last two quarters is sufficient to find the most recent 13F for each fund
    latest_quarter_data = [aggregate_quarter_by_fund(get_quarter_data(quarter)) for quarter in get_all_quarters()[:2]]
    latest_quarter_data_per_fund = pd.concat(latest_quarter_data).drop_duplicates(subset=['Fund', 'Ticker'], keep='first')
    latest_quarter_data_per_fund.set_index(['Fund', 'Ticker'], inplace=True)

    nq_filings_df = non_quarterly_filings_df.join(latest_quarter_data_per_fund, how='inner', rsuffix='_quarter').reset_index()
    nq_filings_df = nq_filings_df[nq_filings_df['Delta_Shares'] != 0]

    # Filter filings from the last 30 days (interesting_day_range)
    interesting_day_range = 30
    subset_df = nq_filings_df[pd.to_datetime(nq_filings_df['Date']) >= pd.Timestamp.now().normalize() - pd.Timedelta(days=interesting_day_range)].copy()
    tickers = subset_df['Ticker'].unique().tolist()
    # Fetch current prices and industry info
    stock_info = YFinance.get_stocks_info(tickers)

    # Ensure numeric types and calculate the percentage change
    subset_df['Avg_Price'] = pd.to_numeric(subset_df['Avg_Price'], errors='coerce')
    subset_df['Current_Price'] = subset_df['Ticker'].map(lambda t: stock_info.get(t, {}).get('price') or PriceFetcher.get_current_price(t))
    subset_df['Sector'] = subset_df['Ticker'].map(lambda t: stock_info.get(t, {}).get('sector'))
    subset_df['Price_Var%'] = ((subset_df['Current_Price'] - subset_df['Avg_Price']) / subset_df['Avg_Price']) * 100
    
    print_dataframe(
        subset_df, len(subset_df), title=f"LAST {interesting_day_range} DAYS 13D/G AND FORM 4 FILINGS", sort_by=['Date', 'Fund'],
        cols=['Date', 'Fund', 'Ticker', 'Company', 'Sector', 'Delta', 'Avg_Price', 'Current_Price', 'Price_Var%', 'Value'],
        formatters={
            'Company': get_string_formatter(25),
            'Avg_Price': get_price_formatter(),
            'Current_Price': get_price_formatter(),
            'Price_Var%': get_signed_perc_formatter()
        }
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
        min_holder_threshold = round(count_funds_in_quarter(selected_quarter) / 10)

        print_dataframe(
            df_analysis,
            top_n,
            f'Top {top_n} Consensus Buys (by Net # of Buyers)',
            ['Net_Buyers', 'Buyer_Count', 'Total_Delta_Value'],
            ['Ticker', 'Company', 'Delta', 'Net_Buyers', 'Buyer_Count', 'Seller_Count', 'Holder_Count', 'Total_Delta_Value'],
            {'Company': get_string_formatter(30), 'Delta': get_signed_perc_formatter(), 'Total_Delta_Value': get_value_formatter()}
        )
        print_dataframe(
            df_analysis,
            top_n,
            f'Top {top_n} New Consensus (by # of New Holders)',
            ['New_Holder_Count', 'Total_Delta_Value'],
            ['Ticker', 'Company', 'New_Holder_Count', 'Net_Buyers', 'Holder_Count', 'Delta', 'Total_Delta_Value', 'Total_Value'],
            {'Delta': get_signed_perc_formatter(), 'Total_Delta_Value': get_value_formatter(), 'Total_Value': get_value_formatter()}
        )
        print_dataframe(
            df_analysis[(df_analysis['Delta'] != np.inf) & (df_analysis['Holder_Count'] >= min_holder_threshold)],
            top_n,
            f'Top {top_n} Increasing Positions (by Delta)',
            'Delta',
            ['Ticker', 'Company', 'New_Holder_Count', 'Net_Buyers', 'Holder_Count', 'Delta', 'Total_Delta_Value', 'Total_Value'],
            {'Company': get_string_formatter(35), 'Delta': get_signed_perc_formatter(), 'Total_Delta_Value': get_value_formatter(), 'Total_Value': get_value_formatter()}
        )
        print_dataframe(
            df_analysis,
            top_n,
            f'Top {top_n} Big Bets (by Max Portfolio %)',
            'Max_Portfolio_Pct',
            ['Ticker', 'Company', 'Max_Portfolio_Pct', 'Avg_Portfolio_Pct', 'Delta', 'Total_Delta_Value', 'Total_Value'],
            {'Max_Portfolio_Pct': get_percentage_formatter(), 'Avg_Portfolio_Pct': get_percentage_formatter(), 'Delta': get_signed_perc_formatter(), 'Total_Delta_Value': get_value_formatter(), 'Total_Value': get_value_formatter()}
        )
        print_dataframe(
            df_analysis[df_analysis['Holder_Count'] >= min_holder_threshold],
            top_n,
            f'Average {top_n} Stocks Portfolio',
            'Avg_Portfolio_Pct',
            ['Ticker', 'Company', 'Avg_Portfolio_Pct', 'Max_Portfolio_Pct', 'Holder_Count', 'Delta'],
            {'Avg_Portfolio_Pct': get_percentage_formatter(), 'Max_Portfolio_Pct': get_percentage_formatter(), 'Delta': get_signed_perc_formatter()}
        )
        print("\n")


def run_fund_analysis():
    """
    3. Analyze a single fund for a quarter.
    """
    selected_fund = select_fund()
    if selected_fund:
        selected_quarter = select_quarter(fund_name=selected_fund['Fund'])
        if not selected_quarter:
            return

        df_fund = fund_analysis(selected_fund['Fund'], selected_quarter)
        if df_fund.empty:
            print(f"❌ No data available for {print_fund(selected_fund)} in quarter {selected_quarter}.")
            return

        horizontal_rule('-')
        print_centered(f"{print_fund(selected_fund).upper()} - {selected_quarter} QUARTER ANALYSIS")
        horizontal_rule('-')

        total_value = df_fund['Value'].sum()
        num_positions = (df_fund['Value'] > 0).sum()
        new_positions = (df_fund['Delta'].str.startswith('NEW')).sum()
        close_positions = (df_fund['Delta'] == 'CLOSE').sum()

        print("\n")
        print_centered(f"TOTAL VALUE: {format_value(total_value)}")
        print_centered(f"POSITIONS: {num_positions}")
        print_centered(f"NEW: {new_positions} / CLOSED: {close_positions}")

        top_n = 10
        columns = ['Ticker', 'Company', 'Portfolio_Pct', 'Value', 'Delta', 'Delta_Value']
        formatters = {
            'Company': get_string_formatter(35),
            'Portfolio_Pct': get_percentage_formatter(),
            'Value': get_value_formatter(),
            'Delta_Value': get_value_formatter()
        }

        if len(df_fund) >= 2 * top_n:
            print_dataframe(df_fund, top_n, title=f'Top {top_n} Holdings by Portfolio %', sort_by='Portfolio_Pct', cols=columns, formatters=formatters)
            print_dataframe(df_fund, top_n, title=f'Top {top_n} Value Increases', sort_by='Delta_Value', cols=columns, formatters=formatters)
            print_dataframe(df_fund.sort_values(by='Delta_Value', ascending=True), top_n, title=f'Top {top_n} Value Decreases', sort_by='Delta_Value', cols=columns, formatters=formatters, ascending_sort=True)
        else:
            print_dataframe(df_fund, len(df_fund), title='Portfolio (sorted by %)', sort_by='Portfolio_Pct', cols=columns, formatters=formatters)


def run_stock_analysis():
    """
    4. Analyze a single stock for a specific quarter.
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
        previous_total_value = total_value - total_delta_value
        delta = total_delta_value / previous_total_value * 100 if previous_total_value != 0 else np.nan

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
            formatters={
                'Portfolio_Pct': get_percentage_formatter(),
                'Shares': get_value_formatter(),
                'Value': get_value_formatter(),
                'Delta_Value': get_value_formatter()
            }
        )


def run_performance_evaluation():
    """
    5. Evaluate fund performance (Holding-Based Return).
    """
    selected_fund = select_fund()
    if selected_fund:
        selected_quarter = select_quarter(fund_name=selected_fund['Fund'], require_previous=True)
        if not selected_quarter:
            return

        result = PerformanceEvaluator.calculate_quarterly_performance(selected_fund['Fund'], selected_quarter)
        
        if "error" in result:
            print(f"❌ {result['error']}")
            return

        horizontal_rule('-')
        print_centered(f"{selected_fund['Fund'].upper()} - {selected_quarter} PERFORMANCE EVALUATION (HBR)")
        horizontal_rule('-')

        print("\n")
        print_centered(f"Portfolio Return: {format_percentage(result['portfolio_return'], show_sign=True, decimal_places=2)}")
        print_centered(f"Start Value: {format_value(result['start_value'])}")
        print_centered(f"End Value: {format_value(result['end_value'])}")
        
        formatters = {
            'Company': get_string_formatter(40),
            'Weight': get_percentage_formatter(),
            'Return': get_signed_perc_formatter(),
            'Weighted_Return': get_signed_perc_formatter()
        }
        cols = ['Ticker', 'Company', 'Weight', 'Return', 'Weighted_Return']

        if result['top_contributors']:
            df_contrib = pd.DataFrame(result['top_contributors'])
            print_dataframe(df_contrib, len(df_contrib), title="Top Contributors (by Impact)", sort_by='Weighted_Return', cols=cols, formatters=formatters)
        
        if result['top_detractors']:
            df_detract = pd.DataFrame(result['top_detractors'])
            print_dataframe(df_detract, len(df_detract), title="Top Detractors (by Impact)", sort_by='Weighted_Return', cols=cols, formatters=formatters, ascending_sort=True)


def run_ai_analyst():
    """
    6. Run AI Analyst
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
        if not scored_list.empty:
            title = f'Best {top_n} Promising Stocks according to {selected_model["Description"]}'
            
            # Remove "Score" suffix from headers and format scores
            rename_map = {
                'Promise_Score': 'Promise',
                'Risk_Score': 'Risk',
                'Low_Volatility_Score': 'Volatility',
                'Momentum_Score': 'Momentum',
                'Growth_Score': 'Growth'
            }
            scored_list = scored_list.rename(columns=rename_map)
            
            print_dataframe(
                scored_list,
                top_n,
                title=title,
                sort_by='Promise',
                cols=['Ticker', 'Company', 'Industry', 'Promise', 'Risk', 'Volatility', 'Momentum', 'Growth'],
                formatters={'Company': get_string_formatter(35), 'Industry': get_string_formatter(30)}
            )


    except Exception as e:
        print(f"❌ An unexpected error occurred while running AI Financial Agent: {e}")


def run_ai_due_diligence():
    """
    7. Run AI Due Diligence on a stock
    """
    selected_model = select_ai_model()
    if not selected_model:
        return

    ticker = input("Enter stock ticker to analyze: ").strip().upper()
    if not ticker:
        print("❌ Ticker cannot be empty.")
        return

    try:
        client_class = selected_model['Client']
        client = client_class(model=selected_model['ID'])
        print_centered(f"Starting AI Due Diligence using {selected_model['Description']}", "-")

        last_available_quarter = get_last_quarter()
        analysis_quarter = get_most_recent_quarter(ticker)

        if not analysis_quarter:
            print(f"❌ No recent data found for ticker {ticker} (last two quarters).")
            return
        elif analysis_quarter != last_available_quarter:
            print(f"🚨 Warning: Data for {ticker} not found in the latest quarter ({last_available_quarter}). Using data from {analysis_quarter} instead.")

        agent = AnalystAgent(analysis_quarter, ai_client=client)
        analysis = agent.run_stock_due_diligence(ticker)

        if analysis:
            horizontal_rule()
            print_centered(f"AI-POWERED DUE DILIGENCE: {analysis.get('ticker')} ({analysis.get('company')})")
            horizontal_rule()

            thesis_map = {"Bullish": "🟢", "Neutral": "🟡", "Bearish": "🔴"}
            analysis_data = analysis.get('analysis', {})

            # Define the order and content for display
            display_sections = {
                "Business Summary": (analysis_data.get("business_summary"), None),
                "Financial Health": (analysis_data.get("financial_health"), analysis_data.get("financial_health_sentiment")),
                "Valuation": (analysis_data.get("valuation"), analysis_data.get("valuation_sentiment")),
                "Growth VS Risks": (analysis_data.get("growth_vs_risks"), analysis_data.get("growth_vs_risks_sentiment")),
                "Institutional Sentiment": (analysis_data.get("institutional_sentiment"), analysis_data.get("institutional_sentiment_sentiment")),
            }

            for title, (content, sentiment) in display_sections.items():
                if content:
                    indicator = thesis_map.get(sentiment, "📋")
                    print(f"\n{indicator} {title.upper()}")
                    print(content)

            thesis_info = analysis.get('investment_thesis', {})
            overall_sentiment = thesis_info.get("overall_sentiment")
            print(f"\n{thesis_map.get(overall_sentiment)} OVERALL")
            print(f"Sentiment: {overall_sentiment}")
            print(f"Thesis: {thesis_info.get('thesis')}")

            target_price = thesis_info.get('price_target')
            target_price = str(target_price).replace('$', '').replace(',', '') if target_price else None
            current_price = analysis.get('current_price')

            potential_upside_str = ""
            if target_price and current_price:
                try:
                    target_price_val = float(target_price)
                    potential_upside = ((target_price_val - current_price) / current_price) * 100
                    potential_upside_str = f" ({format_percentage(potential_upside, True)})"
                except (ValueError, TypeError):
                    pass # Ignore if conversion fails
            
            print(f"Target Price (3 months): {target_price or 'N/A'}{potential_upside_str}")
    except Exception as e:
        print(f"❌ An unexpected error occurred while running AI Due Diligence: {e}")


if __name__ == "__main__":
    actions = {
        '0': lambda: False,
        '1': run_view_nq_filings,
        '2': run_quarter_analysis,
        '3': run_fund_analysis,
        '4': run_stock_analysis,
        '5': run_performance_evaluation,
        '6': run_ai_analyst,
        '7': run_ai_due_diligence,
    }

    while True:
        try:
            horizontal_rule()
            print_centered(APP_NAME)
            horizontal_rule()
            print("0. Exit")
            print("1. View latest non-quarterly filings activity by funds (from 13D/G, Form 4)")
            print("2. Analyze overall hedge-funds stock trends for a quarter")
            print("3. Analyze a specific fund's quarterly portfolio")
            print("4. Analyze a specific stock's activity for a quarter")
            print("5. Evaluate a fund's performance (Holding-Based Return)")
            print("6. Run AI Analyst to find most promising stocks")
            print("7. Run AI Due Diligence on a stock")
            horizontal_rule()

            main_choice = input("Choose an option (0-7): ")
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
