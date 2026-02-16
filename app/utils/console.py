from app.utils.database import get_all_quarters, get_quarters_for_fund, load_hedge_funds, load_models
from app.utils.strings import get_previous_quarter
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from tabulate import tabulate
from typing import Dict
import math
import os
import shutil
import sys


# Ensure UTF-8 encoding for stdout and stderr, especially on Windows
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, Exception):
        pass
if sys.stderr.encoding.lower() != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, Exception):
        pass


@contextmanager
def silence_output():
    """
    Context manager to silence stdout and stderr.
    Useful for suppressing verbose output from third-party libraries.
    """
    with open(os.devnull, 'w') as devnull:
        with redirect_stderr(devnull), redirect_stdout(devnull):
            yield


def get_terminal_width(fallback=110):
    """
    Gets the width of terminal in characters with a small buffer.
    """
    try:
        # Prefer environment variable if set, otherwise use shutil
        width = int(os.environ.get('COLUMNS', shutil.get_terminal_size(fallback=(fallback, 24)).columns))
        # Use a safe buffer (subtract 2) to account for some terminal borders/margins
        return max(width - 2, 40)
    except Exception:
        return fallback


def horizontal_rule(char='='):
    """
    Prints a horizontal line of a given character.
    """
    print(char * get_terminal_width())


def print_centered(title, fill_char=' '):
    """
    Prints a title centered within a line, padded with a fill character.
    """
    print(f" {title} ".center(get_terminal_width(), fill_char))


def print_centered_table(table):
    """
    Prints a screen centered table
    """
    for line in table.splitlines():
        print_centered(line)


def print_dataframe(dataframe, top_n, title, sort_by, cols=None, formatters={}, ascending_sort=False):
    """
    Sorts, formats, and prints a DataFrame as a centered, responsive table in the console.

    Args:
        dataframe (pd.DataFrame): The DataFrame to display.
        top_n (int): The number of top rows to display.
        title (str): The title to be printed above the table.
        sort_by (str or list): The columns to sort the DataFrame by (in descending order).
        cols (list, optional): The list of column names to include in the final output.
                               If None, all columns are displayed. Defaults to None.
        formatters (dict, optional): A dictionary mapping column names to formatting functions.
                                     e.g., {'Value': format_value}
        ascending_sort (bool, optional): Whether to sort in ascending order. Defaults to False.
    """
    print("\n")
    print_centered(title, "-")

    ascending = ascending_sort if isinstance(sort_by, list) else [ascending_sort] * len(sort_by) if isinstance(sort_by, list) else ascending_sort
    display_df = dataframe.sort_values(by=sort_by, ascending=ascending).head(top_n).copy()
 
    for col, formatter in formatters.items():
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(formatter)
 
    # If 'cols' is not specified, use all columns from the dataframe
    columns_to_show = cols if cols is not None else display_df.columns
    print_centered_table(tabulate(display_df[columns_to_show], headers="keys", tablefmt="psql", showindex=False, stralign="center", numalign="center"))


def prompt_for_selection(items, text, print_func=None, num_columns=None, start_index=1):
    """
    Prompts the user to select an item from a list, with optional multi-column display.

    Args:
        items (list): The list of items to choose from.
        text (str): The prompt text to display to the user.
        display_func (callable, optional): A function to format each item for display. Defaults to str().
        num_columns (int, optional): Controls the display format.
            - If None (default): Displays a simple, single-column list.
            - If -1: Displays a multi-column grid, dynamically calculating the number of columns to fit the terminal width.
            - If a positive integer (e.g., 3): Displays a multi-column grid with that specific number of columns.
        start_index (int, optional): The starting number for the selection list. Defaults to 1.

    Returns:
        The selected item from the list, or None if the selection is cancelled or invalid.
    """
    display_texts = []
    for i, item in enumerate(items):
        display_number = i + start_index
        base_text = print_func(item) if print_func else str(item).replace(f"Offset={i}", f"Offset={display_number}")
        display_texts.append(f"{display_number}. {base_text}")

    print(text + "\n")

    if not num_columns:
        num_columns = 1
    elif num_columns == -1:
        terminal_width = get_terminal_width()
        # Find the longest item name to estimate column width
        max_item_width = max(len(s) for s in display_texts) if display_texts else 0
        # Calculate columns, ensuring at least 1, with 2 spaces for padding
        num_columns = max(1, terminal_width // (max_item_width + 2))

    num_rows = math.ceil(len(display_texts) / num_columns)
    padded_items = display_texts + [''] * (num_rows * num_columns - len(display_texts))

    table_data = []
    for i in range(num_rows):
        row = [padded_items[j * num_rows + i] for j in range(num_columns)]
        table_data.append(row)
    
    print(tabulate(table_data, tablefmt="plain"))

    try:
        prompt_text = f"\nEnter a number ({start_index}-{len(items) + start_index - 1}): "
        choice = input(prompt_text)
        selected_index = int(choice) - start_index
        if 0 <= selected_index < len(items):
            return items[selected_index]
        else:
            print(f"❌ Invalid selection. Please enter a number between {start_index} and {len(items) + start_index - 1}.")
            return None
    except ValueError:
        print(f"❌ Invalid input. Please enter a number.")
        return None


def select_ai_model(text="Select the AI model"):
    """
    Prompts the user to select an AI model for the analysis.
    Returns the selected model.
    """
    return prompt_for_selection(load_models(), text, print_func=lambda model: model['Description'])


def print_fund(fund_info: Dict) -> str:
    """
    Formats fund information into a 'Fund (Manager)' string.

    Args:
        fund_info (Dict): A dictionary containing fund details like 'Fund' and 'Manager'.

    Returns:
        str: A formatted string, e.g., "Fund Name (Manager Name)".
    """
    return f"{fund_info.get('Fund')} ({fund_info.get('Manager')})"


def select_fund(text="Select the hedge fund:"):
    """
    Prompts the user to select a hedge fund, displaying them in columns.
    Returns selected fund info.
    """
    return prompt_for_selection(
        load_hedge_funds(),
        text,
        print_func=print_fund,
        num_columns=-1
    )


def select_period(text="Select offset:"):
    """
    Prompts the user to select a historical comparison period.
    Returns the selected offset integer.
    """
    period_options = [
        (0, "Latest vs Previous quarter"),
        (1, "Previous vs Two quarters back (Offset=1)"),
        (2, "Two vs Three quarters back (Offset=2)"),
        (3, "Three vs Four quarters back (Offset=3)"),
        (4, "Four vs Five quarters back (Offset=4)"),
        (5, "Five vs Six quarters back (Offset=5)"),
        (6, "Six vs Seven quarters back (Offset=6)"),
        (7, "Seven vs Eight quarters back (Offset=7: 2 years)")
    ]

    return prompt_for_selection(
        period_options,
        text,
        print_func=lambda option: option[1],
        num_columns=2,
        start_index=0
    )


def select_quarter(text="Select the quarter", fund_name=None, require_previous=False):
    """
    Prompts the user to select an analysis quarter.
    Optionally filters by fund availability and ensures a previous quarter exists for comparison.

    Args:
        text (str): The prompt text.
        fund_name (str, optional): If provided, filters to quarters where this fund has data.
        require_previous (bool): If True, only quarters that have a previous quarter's data
                                 (based on fund_name or general availability) are shown.

    Returns:
        str: The selected quarter string (e.g., '2025Q1').
    """
    if fund_name:
        available_quarters = get_quarters_for_fund(fund_name)
    else:
        available_quarters = get_all_quarters()

    if require_previous:
        # Filter to quarters Q where Q-1 also exists in available_quarters
        available_quarters = [
            q for q in available_quarters
            if get_previous_quarter(q) in available_quarters
        ]

    if not available_quarters:
        print(f"❌ No valid quarters found for processing{f' (Fund: {fund_name})' if fund_name else ''}.")
        return None

    return prompt_for_selection(available_quarters, text)
