from bs4 import BeautifulSoup
import csv
import os
import pandas as pd
import re
import requests

GICS_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/Global_Industry_Classification_Standard"


def scrape_gics_from_wikipedia():
    """
    Scrapes the Global Industry Classification Standard (GICS) hierarchy from Wikipedia.
    """
    print(f"🌐 Fetching GICS data from {GICS_WIKIPEDIA_URL}...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(GICS_WIKIPEDIA_URL, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error fetching Wikipedia page: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', {'class': 'wikitable'})
    
    if not table:
        print("❌ Could not find GICS table on Wikipedia page.")
        return None

    data = []
    # Using a slightly different approach to handle rowspans correctly in Python
    rows = table.find_all('tr')[1:] # Skip header
    
    # We need to keep track of active rowspans
    # Format: {column_index: [remaining_rows, value]}
    active_rowspans = {}

    for row_idx, tr in enumerate(rows):
        tds = tr.find_all(['td', 'th'])
        row_data = [None] * 8 # 8 columns in the GICS table
        
        td_idx = 0
        for col_idx in range(8):
            # Check if there's an active rowspan for this column
            if col_idx in active_rowspans and active_rowspans[col_idx][0] > 0:
                row_data[col_idx] = active_rowspans[col_idx][1]
                active_rowspans[col_idx][0] -= 1
            else:
                if td_idx < len(tds):
                    td = tds[td_idx]
                    text = td.get_text(separator=' ', strip=True)
                    # Fix ampersand spacing: "A&B" -> "A & B"
                    text = re.sub(r'\s*&\s*', ' & ', text)
                    # Fix comma spacing: "Word , Word" -> "Word, Word"
                    text = re.sub(r'\s*,\s*', ', ', text)
                    # Fix multiple spaces
                    text = re.sub(r'\s+', ' ', text).strip()
                    
                    row_data[col_idx] = text
                    
                    rowspan = int(td.get('rowspan', 1))
                    if rowspan > 1:
                        active_rowspans[col_idx] = [rowspan - 1, text]
                    
                    td_idx += 1

        # Only add if it's a sub-industry row (Sub-Industry Code is 8 digits)
        # Column mapping: 
        # 0: Sector Code, 1: Sector, 2: Group Code, 3: Group, 
        # 4: Industry Code, 5: Industry, 6: Sub-Industry Code, 7: Sub-Industry
        if row_data[6]:
            sub_industry_code = row_data[6].replace(" ", "")
            if re.match(r'^\d{8}$', sub_industry_code):
                data.append({
                    'Sector Code': row_data[0],
                    'Sector': row_data[1],
                    'Industry Group Code': row_data[2],
                    'Industry Group': row_data[3],
                    'Industry Code': row_data[4],
                    'Industry': row_data[5],
                    'Sub-Industry Code': row_data[6],
                    'Sub-Industry': row_data[7]
                })

    return pd.DataFrame(data)


def main():
    df = scrape_gics_from_wikipedia()
    
    if df is not None and not df.empty:
        # Determine the base path (relative to this script's location)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, 'hierarchy.csv')
        
        df.to_csv(output_path, index=False, quoting=csv.QUOTE_ALL)
        print(f"✅ GICS hierarchy saved to {output_path} ({len(df)} sub-industries)")
    else:
        print("❌ Failed to generate GICS hierarchy.")


if __name__ == "__main__":
    main()
