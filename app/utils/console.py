LINE_LENGTH = 90
DASH_LENGTH = 10


def horizontal_rule(char='='):
    """
    Prints a horizontal line of a given character.
    """
    print(char * LINE_LENGTH)


def print_dataframe(dataframe, title, sort_by, ascending, cols, formatters={}):
    print("\n")
    print_centered(title, "-")

    display_df = dataframe.sort_values(by=sort_by, ascending=ascending).head(10).copy()
    
    for col, formatter in formatters.items():
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(formatter)

    print(display_df[cols].to_string(index=False))


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
