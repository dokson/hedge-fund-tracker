# 📊 Hedge Fund Tracker

![repo size](https://img.shields.io/github/repo-size/dokson/hedge-fund-tracker)
[![last commit](https://img.shields.io/github/last-commit/dokson/hedge-fund-tracker)](https://github.com/dokson/hedge-fund-tracker/commits/master/)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License: MIT](https://img.shields.io/github/license/dokson/hedge-fund-tracker)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/dokson/hedge-fund-tracker/pulls)
![GitHub stars](https://img.shields.io/github/stars/dokson/hedge-fund-tracker.svg?style=social&label=Star)

> **Track hedge fund portfolios and investment strategies using [SEC](http://sec.gov/) filings**

A comprehensive Python tool for analyzing hedge fund portfolio changes, built for financial analysts, investors, and finance enthusiasts who want to monitor institutional investment strategies through public [SEC](http://sec.gov/) filings.

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/dokson/hedge-fund-tracker.git
cd hedge-fund-tracker

# Install dependencies
pipenv install

# Set up environment variables
cp .env.example .env
# Add your FINNHUB_API_KEY and GOOGLE_API_KEY to the .env file

# Run the application
pipenv run python -m app.main
```

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **🆚 Comparative Analysis** | Compare quarterly 13F filings to identify new positions, closures, and changes |
| **📋 Detailed Reports** | Generate clean CSV reports with intuitive formatting |
| **🗄️ Historical Database** | Maintain organized quarterly reports for trend analysis |
| **🔍 Ticker Resolution** | Convert CUSIPs to stock tickers using Finnhub API with smart caching |
| **🤖 AI-Powered Analysis** | Get insights using Google's Generative AI on latest filings |
| **🔀 Flexible Management** | Analyze all funds, single funds, or custom CIKs |

## 📦 Installation

### Prerequisites

- [Python 3.12](https://www.python.org/downloads/release/python-3120/)+
- [pipenv](https://pipenv.pypa.io/) (install with `pip install pipenv`)

1. **📥 Clone and navigate:**

   ```bash
   git clone https://github.com/dokson/hedge-fund-tracker.git
   cd hedge-fund-tracker
   ```

2. **📲 Install dependencies:** Navigate to the project root and run the following command. This will create a virtual environment and install all required packages.

    ```bash
    pipenv install
    ```

    *On Windows, if the above fails: (e.g., with a "command not found" error), you can use the following alternative.*

    ```bash
    python -m pipenv install
    ```

3. **🛠️ Configure environment:** Create a `.env` file in the root directory of the project and add your keys (Finnhub and Google API)

    ```bash
   # Create environment file
   cp .env.example .env
   
   # Edit .env file and add your API keys:
   # FINNHUB_API_KEY="your_finnhub_key"
   # GOOGLE_API_KEY="your_google_key"
   ```

4. **▶️ Run the script:** Execute within the project's virtual environment:

    ```bash
    pipenv run python -m app.main
    ```

    *or on Windows, if the above fails:*

    ```bash
    python -m pipenv run python -m app.main
    ```

5. **📜 Choose an action:** Once the script starts, you'll see the following interactive menu:

    ```txt
    ┌───────────────────────────────────────────────────────────────────────────────┐
    │                               Hedge Fund Tracker                              │
    │                                                                               │
    │  1. Generate latest reports for all known hedge funds (hedge_funds.csv)       │
    │  2. Generate latest report for a known hedge fund (hedge_funds.csv)           │
    │  3. Generate historical report for a known hedge fund (hedge_funds.csv)       │
    │  4. Fetch latest schedule filings for a known hedge fund (hedge_funds.csv)    |
    │  5. Manually enter a hedge fund CIK number to generate latest report          │
    │  6. Analyze stock trends for a quarter                                        │
    │  7. Analyze a single stock for a quarter                                      │
    │  8. Run AI Analyst for most promising stocks                                  │
    └───────────────────────────────────────────────────────────────────────────────┘
    ```

### API Configuration

The tool requires API keys for full functionality:

| Service | Purpose | Required | Get API Key |
|---------|---------|----------|-------------|
| **☁️ [Finnhub](https://finnhub.io/)** | CUSIP to stock ticker conversion | **Optional**: for fetching new filings and updating data | [Get Free API Key](https://finnhub.io/dashboard) |
| **🤖 [Google AI Studio](https://aistudio.google.com/)** | AI-powered analysis | **Optional**: enables advanced AI financial analyst features | [Get Free API Key](https://aistudio.google.com/app/apikey) |

> **💡 Note:** Without [Finnhub](https://finnhub.io/) API Key, it falls back to the local [FinanceDatabase](https://github.com/JerBouma/FinanceDatabase/) for ticker resolution (though this may be less accurate for some securities).

## 📁 Project Structure

```plaintext
hedge-fund-tracker/
├── 📁 .github/
│   ├── 📁 scripts/
│   │   └── 📄 fetcher.py           # Daily fetching job (scheduled by workflows/daily-fetch.yml)
│   └── 📁 workflows/
│       ├── 📄 daily-fetch.yml      # GitHub Actions: Daily fetching job
│       └── 📄 python-tests.yml     # GitHub Actions: Unit tests
│
├── 📁 app/                          # Main application package
│   └── 📄 main.py                  # Entry point and CLI interface
│
├── 📁 database/                     # Data storage
│   ├── 📁 2025Q1/                  # Quarterly reports
│   │   ├── 📄 fund_1.csv           # Individual fund quarterly report
│   │   ├── 📄 fund_2.csv
│   │   └── 📄 fund_n.csv
│   ├── 📁 2025Q2/
│   ├── 📁 YYYYQN/
│   ├── 📄 hedge_funds.csv          # Curated hedge funds list
│   ├── 📄 latest_filings.csv       # Latest schedule filings
│   └── 📄 stocks.csv               # Stocks masterdata (CUSIP-Ticker-Name)
│
├── 📁 tests/                        # Test suite
│
├── 📄 .env.example                 # Environment variables template
├── 📄 .gitignore                   # Git ignore rules
├── 📄 LICENSE                      # MIT License
├── 📄 Pipfile                      # pipenv dependencies
├── 📄 Pipfile.lock                 # Locked dependency versions
└── 📄 README.md                    # Project documentation (this file)
```

> **📝 Hedge Funds Configuration File:** `database/hedge_funds.csv` contains the list of hedge funds to monitor (CIK, name, manager) and can be also edited at runtime.

## 👨🏻‍💻 How This Tool Tracks Hedge Funds

This tracker leverages two key SEC filing types:

- **📅 Quarterly 13F Filings**
  - Required for funds managing $100M+
  - Filed within 45 days of quarter-end
  - Shows portfolio snapshot on last day of quarter

- **📝 Schedules (Non-Quarterly) 13D/G Filings**
  - Required when acquiring 5%+ of company shares
  - Filed within 10 days of transaction
  - Provides timely view of significant investments

### 🏢 A Note on Fund Selection

This tool is configured to monitor a **curated list of top-performing investment funds, identified based on their performance over the last 3-5 years**. The goal is to focus on a select group representing what I consider the **top percentile of institutional investors**.

#### Notable Exclusions

Some famous names have to be excluded by design to enhance analysis quality:

- *Warren Buffett*'s [Berkshire Hathaway](https://www.berkshirehathaway.com/)
- *Ray Dalio*'s [Bridgewater Associates](https://www.bridgewater.com/)
- *Cathie Wood*'s [ARK Invest](https://www.ark-invest.com/)
- *Bill Ackman*'s [Pershing Square](https://pershingsquareholdings.com/)
- *Cliff Asness*'s [Aqr Capital Management](https://www.aqr.com/)
- *Murray Stahl*'s [Horizon Kinetics](https://horizonkinetics.com/)
- *Paul Singer*'s [Elliot Investment](https://www.elliottmgmt.com/)
- *Daniel Loeb*'s [Third Point](https://www.thirdpoint.com/)
- *George Soros*'s [Soros Fund Management](https://sorosfundmgmt.com/)
- *Bill Gates*'s [Gates Foundation Trust](https://www.gatesfoundation.org/about/financials/foundation-trust)
- *Carl Icahn*'s [Icahn Enterprises](https://www.ielp.com/)
- *Lewis Sanders*'s [Sanders Capital](https://www.sanderscapital.com/)
- *Brad Gerstner*'s [Altimeter Capital Management](https://www.altimeter.com/)
- *Andreas Halvorsen*s [Viking Global Investors](https://vikingglobal.com/)
- *David Lane*'s [Geode Capital Management](https://www.geodecapital.com/)
- *Robert Robotti*'s [Robotti Value Investors](https://www.robotti.com/)
- *Li Lu*'s [Himalaya Capital Management](https://www.himcap.com/)
- *Ken Fisher*'s [Fisher Asset Management](https://www.fisherinvestments.com/)
- *David Katz*'s [Matrix Asset Advisors](https://matrixassetadvisors.com/)
- *Bill Nygren*'s [Harris Associates](https://harrisassoc.com/)
- *David Booth*'s [Dimensional Fund Advisors](https://www.dimensional.com/)
- *Chris Hohn*'s [The Children's Investment](https://ciff.org/)
- *Robert Atchinson & Phillip Gross*' [Adage Capital Partners](https://www.adagecapital.com/)
- [BlackRock](https://www.blackrock.com/)
- [State Street](https://statestreet.com/)
- [Jane Street](https://www.janestreet.com/)

#### Adding Custom Funds

Want to track additional funds? Simply edit `hedge_funds.csv` and add your preferred institutional investors. For example, to add [Berkshire Hathaway](https://www.berkshirehathaway.com/), [Pershing Square](https://pershingsquareholdings.com/) and [ARK-Invest](https://www.ark-invest.com/), you would add the following lines:

```csv
"CIK","Fund","Manager","Denomination"
"0001067983","Berkshire Hathaway","Warren Buffett","Berkshire Hathaway Inc."
"0001336528","Pershing Square","Bill Ackman","Pershing Square Capital Management, L.P."
"0001697748","ARK Invest","Cathie Wood","ARK Investment Management LLC"
```

> **💡 Note**: `hedge_funds.csv` currently includes **not only *traditional hedge funds*** but also **other institutional investors** *(private equity funds, large banks, VCs, pension funds, etc., that file 13F to the [SEC](http://sec.gov/))* selected from what I consider the **top 5%** of performers.

## ⚠️ Limitations & Considerations

It's crucial to understand the inherent limitations of tracking investment strategies solely through SEC filings:

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| **🕒 Filing Delay** | Data can be 45+ days old | Focus on long-term strategies |
| **🧩 Incomplete Picture** | Only US long positions shown | Use as part of broader analysis |
| **📉 No Short Positions** | Missing hedge information | Consider reported positions carefully |
| **🌎 Limited Scope** | No non-US stocks or other assets | Supplement with additional data |

## 🗃️ Technical Stack

| 🗂️ Category | 🦾 Technology |
|----------|------------|
| **Core** | [Python 3.12](https://www.python.org/downloads/release/python-3120/)+, [pipenv](https://pipenv.pypa.io/) |
| **Web Scraping** | [Requests](https://2.python-requests.org/en/master/), [Beautiful Soup](https://pypi.org/project/beautifulsoup4/), [lxml](https://lxml.de/) |
| **Config** | [python-dotenv](https://github.com/theskumar/python-dotenv) |
| **Data Processing** | [pandas](https://pandas.pydata.org/), [csv](https://docs.python.org/3/library/csv.html) |
| **Stocks Libraries** | [Finnhub-Stock-API](https://github.com/Finnhub-Stock-API/finnhub-python), [FinanceDatabase](https://github.com/JerBouma/FinanceDatabase/) |
| **Gen AI** | [Google Gen AI SDK](https://googleapis.github.io/python-genai/) |

## 🤝🏼 Contributing & Support

### 💬 Get Help

- **🆕 [Feature Requests](https://github.com/dokson/hedge-fund-tracker/issues/new?template=feature_request.md)**
- **🐛 [Bug Reports](https://github.com/dokson/hedge-fund-tracker/issues/new?template=bug_report.md)**

### ✍🏻 Feedback

I am continuously developing and trying to expand the functionalities and features to add to this tool.
I welcome all feedback, so feel free to [contact me](https://github.com/dokson).

## 📚 References

- [SEC Developer Resources](https://www.sec.gov/about/developer-resources)
- [SEC: Frequently Asked Questions About Form 13F](https://www.sec.gov/rules-regulations/staff-guidance/division-investment-management-frequently-asked-questions/frequently-asked-questions-about-form-13f)
- [SEC: Guidance on Beneficial Ownership Reporting (Sections 13D/G)](https://www.sec.gov/rules-regulations/staff-guidance/compliance-disclosure-interpretations/exchange-act-sections-13d-13g-regulation-13d-g-beneficial-ownership-reporting)

## 🙏🏼 Acknowledgments

This project started as a fork of the [sec-web-scraper-13f](https://github.com/CodeWritingCow/sec-web-scraper-13f) by [Gary Pang](https://github.com/CodeWritingCow) that is a Python script to scrape the most recent 13F filing for a given CIK from the [SEC](http://sec.gov/)'s [EDGAR](https://www.sec.gov/edgar/searchedgar/companysearch.html) database. It has since evolved significantly into a comprehensive hedge fund tracker.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
