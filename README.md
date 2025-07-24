# SEC Python Web Scraper

This repository contains a Python script to scrape and compare the two most recent 13F filings for a given CIK from the SEC's [EDGAR](https://www.sec.gov/edgar/searchedgar/companysearch.html) database, and generates a .csv showing latest changes in holdings.

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
3. **Add API Key:** Add your Finnhub API key to the `.env` file in the following format:

    ```text
    FINNHUB_API_KEY="your_api_key_here"
    ```

4. **Run the script:** Execute the scraper within the project's virtual environment:

    ```bash
    pipenv run python -m scraper.main
    ```

    or

    ```bash
    python -m pipenv run python -m scraper.main
    ```

5. **Enter CIK:** When prompted, enter the 10-digit CIK number of a mutual fund (e.g., `0001067983` for Berkshire Hathaway Inc).

### Key Dependencies

- [Requests](https://2.python-requests.org/en/master/), Python library for making HTTP requests
- [lxml](https://lxml.de/), Python library for processing XML and HTML
- [Beautiful Soup](https://pypi.org/project/beautifulsoup4/), Python library for scraping information from Web pages
- [re](https://docs.python.org/3/library/re.html), Python module for using regular expressions
- [csv](https://docs.python.org/3/library/csv.html), Python module for parsing and writing CSV files
- [Finnhub-Stock-API](https://github.com/Finnhub-Stock-API/finnhub-python), for mapping CUSIPs to stock tickers.

## Acknowledgments

This project is a fork of the original [sec-web-scraper-13f](https://github.com/CodeWritingCow/sec-web-scraper-13f) created by [Gary Pang](https://github.com/CodeWritingCow).

This version has been modified and updated by [Alessandro Colace](https://github.com/dokson).

## References

- [SEC: Frequently Asked Questions About Form 13F](https://www.sec.gov/divisions/investment/13ffaq.htm)

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.
