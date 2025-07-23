# SEC Python Web Scraper

This repository contains a Python script to scrape and compare the two most recent 13F filings for a given CIK from the SEC's [EDGAR](https://www.sec.gov/edgar/searchedgar/companysearch.html) database, and generates a .csv showing latest changes in holdings.

## Requirements

### Getting Started

1. Install the required packages: `pip install -r requirements.txt`
2. Create a `.env` file in the root directory of the project.
3. Add your Finnhub API key to the `.env` file in the following format:

    ```text
    FINNHUB_API_KEY="your_api_key_here"
    ```

4. Run the script: `python scraper.py`
5. When prompted, enter the 10-digit CIK number of a mutual fund (e.g., `0001067983` for Berkshire Hathaway Inc).

### Key Dependencies

- [Requests](https://2.python-requests.org/en/master/), Python library for making HTTP requests
- [lxml](https://lxml.de/), Python library for processing XML and HTML
- [Beautiful Soup](https://pypi.org/project/beautifulsoup4/), Python library for scraping information from Web pages
- [re](https://docs.python.org/3/library/re.html), Python module for using regular expressions
- [csv](https://docs.python.org/3/library/csv.html), Python module for parsing and writing CSV files
- [Finnhub-Stock-API](https://github.com/Finnhub-Stock-API/finnhub-python), for mapping CUSIPs to stock tickers.

## Contributors

- [Gary Pang](https://github.com/CodeWritingCow)
- [Alessandro Colace](https://github.com/dokson)

## References

- [SEC: Frequently Asked Questions About Form 13F](https://www.sec.gov/divisions/investment/13ffaq.htm)
