from app.utils.database import get_all_quarters, load_hedge_funds, load_models
from tabulate import tabulate
from typing import Dict
import math
import shutil


def get_terminal_width(fallback=120):
    """
    Gets the width of terminal in characters.
    """
    return shutil.get_terminal_size(fallback=(fallback, 24)).columns


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
    print("\n")
 
    ascending = ascending_sort if isinstance(sort_by, list) else [ascending_sort] * len(sort_by) if isinstance(sort_by, list) else ascending_sort
    display_df = dataframe.sort_values(by=sort_by, ascending=ascending).head(top_n).copy()
 
    for col, formatter in formatters.items():
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(formatter)
 
    # If 'cols' is not specified, use all columns from the dataframe
    columns_to_show = cols if cols is not None else display_df.columns
    print_centered_table(tabulate(display_df[columns_to_show], headers="keys", tablefmt="psql", showindex=False, stralign="center", numalign="center"))


def prompt_for_selection(items, text, print_func=None, num_columns=None):
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

    Returns:
        The selected item from the list, or None if the selection is cancelled or invalid.
    """
    display_texts = []
    for i, item in enumerate(items):
        base_text = print_func(item) if print_func else str(item)
        display_texts.append(f"{i + 1}. {base_text}")

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
        choice = input(f"\nEnter a number (1-{len(items)}): ")
        selected_index = int(choice) - 1
        if 0 <= selected_index < len(items):
            return items[selected_index]
        else:
            print(f"❌ Invalid selection. Please enter a number between 1 and {len(items)}.")
            return None
    except ValueError:
        print(f"❌ Invalid input. Please enter a number between 1 and {len(items)}.")
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
        num_columns=2
    )


def select_quarter(text="Select the quarter"):
    """
    Prompts the user to select an analysis quarter.
    Returns the selected quarter string (e.g., '2025Q1').
    """
    return prompt_for_selection(get_all_quarters(), text)
