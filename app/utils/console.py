LINE_LENGTH = 120


def horizontal_rule(char='='):
    """
    Prints a horizontal line of a given character.
    """
    print(char * LINE_LENGTH)


def print_dataframe(dataframe, top_n, title, sort_by, cols, formatters={}):
    print("\n")
    print_centered(title, "-")

    display_df = dataframe.sort_values(by=sort_by, ascending=False).head(top_n).copy()
    
    for col, formatter in formatters.items():
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(formatter)

    num_cols = len(cols)

    print(display_df[cols].to_string(index=False, col_space=((LINE_LENGTH - num_cols * 2) // num_cols), justify='center'))


def print_centered(title, fill_char=' '):
    """
    Prints a title centered within a line, padded with a fill character.
    e.g., '--- My Title ---'
    """
    print(f" {title} ".center(LINE_LENGTH, fill_char))


def prompt_for_selection(items, prompt, display_func=str):
    """
    Generic helper to prompt the user to select an item from a list.

    Args:
        items (list): The list of items to choose from.
        prompt (str): The prompt to display to the user.
        display_func (callable): A function to format each item for display.

    Returns:
        The selected item or None if cancelled/invalid.
    """
    print(prompt)
    for i, item in enumerate(items):
        print(f"  {i + 1:2}: {display_func(item)}")

    try:
        choice = input(f"\nEnter a number (1-{len(items)}): ")
        selected_index = int(choice) - 1
        if 0 <= selected_index < len(items):
            return items[selected_index]
        else:
            print("❌ Invalid selection.")
            return None
    except ValueError:
        print("❌ Invalid input. Please enter a number.")
        return None
