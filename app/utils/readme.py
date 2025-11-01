import pandas as pd
import re

README_FILE = './README.md'
EXCLUDED_HEDGE_FUNDS_FILE = './database/excluded_hedge_funds.csv'


def generate_excluded_funds_list() -> str | None:
    """
    Generates a markdown list of excluded funds from a CSV file.
    """
    try:
        df = pd.read_csv(EXCLUDED_HEDGE_FUNDS_FILE, keep_default_na=False)
        
        markdown_list = []
        for _, row in df.iterrows():
            manager = row['Manager']
            fund = row['Fund']
            url = row['URL']
            
            if manager and manager != fund:
                markdown_list.append(f"- *{manager}*'s [{fund}]({url})")
            else:
                markdown_list.append(f"- [{fund}]({url})")
        
        return "\n".join(markdown_list)
    except FileNotFoundError:
        print(f"❌ Error: {EXCLUDED_HEDGE_FUNDS_FILE} was not found.")
        return None


def update_readme() -> None:
    """
    Updates the README.md file with the list of excluded funds.
    """
    content = generate_excluded_funds_list()
    if content is not None:
        try:
            with open(README_FILE, 'r', encoding='utf-8') as f:
                readme_text = f.read()
    
            new_readme_text = re.sub(r'(<!-- EXCLUDED_FUNDS_LIST_START -->)(.*?)(<!-- EXCLUDED_FUNDS_LIST_END -->)',
                                     f'\\1\n{content}\n\\3', readme_text, flags=re.DOTALL)
    
            with open(README_FILE, 'w', encoding='utf-8') as f:
                f.write(new_readme_text)
        except FileNotFoundError:
            print(f"❌ Error: {README_FILE} was not found.")
