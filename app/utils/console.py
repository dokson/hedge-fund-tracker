from tabulate import tabulate
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


def print_dataframe(dataframe, top_n, title, sort_by, cols, formatters={}):
    """
    Sorts, formats, and prints a DataFrame as a centered, responsive table in the console.

    Args:
        dataframe (pd.DataFrame): The DataFrame to display.
        top_n (int): The number of top rows to display.
        title (str): The title to be printed above the table.
        sort_by (str or list): The columns to sort the DataFrame by (in descending order).
        cols (list): The list of column names to include in the final output.
        formatters (dict, optional): A dictionary mapping column names to formatting functions.
                                     e.g., {'Value': format_value}
    """
    print("\n")
    print_centered(title, "-")

    display_df = dataframe.sort_values(by=sort_by, ascending=False).head(top_n).copy()
    
    for col, formatter in formatters.items():
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(formatter)

    num_cols = len(cols)

    print(display_df[cols].to_string(index=False, col_space=((get_terminal_width() - num_cols * 2) // num_cols), justify='center'))


def print_centered(title, fill_char=' '):
    """
    Prints a title centered within a line, padded with a fill character.
    e.g., '--- My Title ---'
    """
    print(f" {title} ".center(get_terminal_width(), fill_char))


def prompt_for_selection(items, text, display_func=None, num_columns=None):
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
        base_text = display_func(item) if display_func else str(item)
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
