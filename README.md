# Hedge Fund Tracker

**Hedge Fund Tracker** is a Python tool designed for analysts, investors, and finance enthusiasts who want to monitor the investment strategies of major hedge funds. By analyzing public [13F filings](https://www.sec.gov/divisions/investment/13ffaq.htm) submitted to the [SEC](http://sec.gov/)'s [EDGAR](https://www.sec.gov/edgar/searchedgar/companysearch.html) database, this script provides a clear and detailed view of quarterly changes in hedge funds portfolios.

The goal is to transform raw [SEC](http://sec.gov/) data into clean CSV reports, highlighting the key moves of fund managers.

## Key Features

* **Comparative Analysis**: Automatically compares the last two 13F filings for each fund, highlighting **new** positions, **closed** positions, and percentage **changes** in existing holdings.
* **Historical Database**: Creates and maintains a local database of generated reports, organized by quarter (e.g., `database/2024Q1/`), allowing for historical and trend analysis.
* **Ticker Resolution**: Converts CUSIPs into familiar stock tickers (e.g., `AAPL`, `MSFT`) using the Finnhub API and a local caching system to optimize performance and reduce API calls.
* **Detailed Reports**: Generates an easy-to-read `.csv` file for each fund, with intuitively formatted data
* **Flexible Management**: Allows you to analyze all funds in a customizable list (`hedge_funds.csv`), a single fund of your choice, or a manually entered CIK via a command-line interface.
* **AI-Powered Analysis**: Utilizes Google's Generative AI to provide advanced analysis using latest 13F filings.

## Getting Started

This project uses `pipenv` for dependency management. If you don't have it, you can install it with `pip install pipenv`.

1. **Install dependencies:** Navigate to the project root and run the following command. This will create a virtual environment and install all required packages.

    ```bash
    pipenv install
    ```

    If the command above fails on Windows (e.g., with a "command not found" error), you can use the following alternative. It tells Python to execute the `pipenv` module directly, which works even if `pipenv` is not in your system's `PATH`.

    ```bash
    python -m pipenv install
    ```

2. **Create environment file:** Create a `.env` file in the root directory of the project.
3. **Add API Keys:** Add your Finnhub API key to the `.env` file. If you want to use the AI agent for advanced analysis, you must also add your Google API Key.

    ```text
    FINNHUB_API_KEY="your_api_key_here"
    GOOGLE_API_KEY="your_google_api_key_here"
    ```

4. **Run the script:** Execute within the project's virtual environment:

    ```bash
    pipenv run python -m app.main
    ```

    or

    ```bash
    python -m pipenv run python -m app.main
    ```

5. **Enter CIK:** When prompted, enter the 10-digit CIK number of a mutual fund (e.g., `0001067983` for Berkshire Hathaway Inc).

### Key Dependencies

* [Requests](https://2.python-requests.org/en/master/), Python library for making HTTP requests
* [Beautiful Soup](https://pypi.org/project/beautifulsoup4/), Python library for scraping information from Web pages
* [lxml](https://lxml.de/), Python library for processing XML and HTML
* [re](https://docs.python.org/3/library/re.html), Python module for using regular expressions
* [csv](https://docs.python.org/3/library/csv.html), Python module for parsing and writing CSV files
* [pandas](https://pandas.pydata.org/), Python tool used for analysis and for creating CSV reports.
* [python-dotenv](https://github.com/theskumar/python-dotenv), Python library for setting environment variables from a `.env` file
* [Finnhub-Stock-API](https://github.com/Finnhub-Stock-API/finnhub-python), Python library used for mapping CUSIPs to stock tickers.
* [FinanceDatabase](https://github.com/JerBouma/FinanceDatabase/), another Python library used for mapping CUSIPs to stock tickers when Finnhub fails or is unavailable.
* [Google Gen AI SDK](https://googleapis.github.io/python-genai/), Python client library for interacting with Google's Generative AI APIs.

## Acknowledgments

This project started as a fork of the [sec-web-scraper-13f](https://github.com/CodeWritingCow/sec-web-scraper-13f) by [Gary Pang](https://github.com/CodeWritingCow) that is a Python script to scrape the most recent 13F filing for a given CIK from the SEC's [EDGAR](https://www.sec.gov/edgar/searchedgar/companysearch.html) database. It has since evolved significantly into a comprehensive hedge fund tracker.

## References

* [SEC: Frequently Asked Questions About Form 13F](https://www.sec.gov/divisions/investment/13ffaq.htm)

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.
