# 📊 Hedge Fund Tracker

![repo size](https://img.shields.io/github/repo-size/dokson/hedge-fund-tracker)
[![last commit](https://img.shields.io/github/last-commit/dokson/hedge-fund-tracker)](https://github.com/dokson/hedge-fund-tracker/commits/master/)
[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/downloads/release/python-3130/)
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
# Add your API keys (FINNHUB, GOOGLE, GROQ, OPENROUTER) to the .env file

# Run the application
pipenv run python -m app.main
```

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **🆚 Comparative Analysis** | Combines quarterly (13F) and non-quarterly (13D/G, Form 4) filings for an up-to-date view |
| **📋 Detailed Reports** | Generates clear, console-based reports with intuitive formatting |
| **🗄️ Curated Database** | Includes list of top hedge funds and AI models, both easily editable via CSV files |
| **🔍 Ticker Resolution** | Converts CUSIPs to tickers using a smart fallback system (yfinance, Finnhub, FinanceDatabase) |
| **🤖 Multi-Provider AI Analysis** | Leverages different AI models to identify promising stocks based on filings |
| **🔀 Flexible Management** | Offers multiple analysis modes: all funds, a single fund and also custom CIKs |
| **⚙️ Automated Data Update** | Includes a GitHub Actions workflow to automatically fetch and commit the latest SEC filings |

## 📦 Installation

### Prerequisites

- [Python 3.13](https://www.python.org/downloads/release/python-3130/)+
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

    > **💡 Tip:** If `pipenv` is not found, you might need to use `python -m pipenv install`. This can happen if the user scripts directory is not in your system's PATH.

3. **🛠️ Configure environment:** Create a `.env` file in the root directory of the project and add your keys (Finnhub and Google API)

    ```bash
   # Create environment file
   cp .env.example .env
   
   # Edit .env file and add your API keys:
   # FINNHUB_API_KEY="your_finnhub_key"
   # GOOGLE_API_KEY="your_google_api_key"
   # GROQ_API_KEY="your_groq_api_key"
   # OPENROUTER_API_KEY="your_openrouter_api_key"
   ```

4. **▶️ Run the script:** Execute within the project's virtual environment:

    ```bash
    pipenv run python -m app.main
    ```

5. **📜 Choose an action:** Once the script starts, you'll see the main interactive menu for data analysis:

    ```txt
    ┌───────────────────────────────────────────────────────────────────────────────────┐
    │                                 Hedge Fund Tracker                                │
    ├───────────────────────────────────────────────────────────────────────────────────┤
    │  0. Exit                                                                          │
    │  1. View latest non-quarterly filings activity by funds (from 13D/G, Form 4)      │
    │  2. Analyze overall stock trends for a quarter                                    │
    │  3. Analyze a single fund's holdings for a quarter                                │
    │  4. Analyze a single stock for a quarter                                          │
    │  5. Find most promising stocks using an AI Analyst                                │
    └───────────────────────────────────────────────────────────────────────────────────┘
    ```

### Data Management

The data update operations (downloading and processing filings) are inside a dedicated script. This keeps the main application focused on analysis, while the updater handles populating and refreshing the database.

To run the data update operations, you need to use the `updater.py` script from the project root:

```bash
pipenv run python -m database.updater
```

This will open a separate menu for data management:

```txt
┌───────────────────────────────────────────────────────────────────────────────┐
│                     Hedge Fund Tracker - Database Updater                     │
├───────────────────────────────────────────────────────────────────────────────┤
│  0. Exit                                                                      │
│  1. Generate latest 13F reports for all known hedge funds                     │
│  2. Fetch latest non-quarterly filings for all known hedge funds              │
│  3. Generate latest 13F report for a known hedge fund                         │
│  4. Generate historical 13F report for a known hedge fund                     │
│  5. Manually enter a hedge fund CIK to generate latest 13F report             │
└───────────────────────────────────────────────────────────────────────────────┘
```

### API Configuration

The tool can utilize API keys for enhanced functionality, but all are optional:

| Service | Purpose | Get Free API Key |
|---------|---------|-------------|
| **[![Finnhub](https://github.com/user-attachments/assets/94465a7f-75e0-4a21-827c-511540c80cb3)](https://finnhub.io/) [Finnhub](https://finnhub.io/)** | [CUSIP](https://en.wikipedia.org/wiki/CUSIP) to [stock ticker](https://en.wikipedia.org/wiki/Ticker_symbol) conversion | [Finnhub Keys](https://finnhub.io/dashboard) |
| **[![Google AI Studio](https://github.com/user-attachments/assets/3b351d8e-d7f6-4337-9c2f-d2af77f30711)](https://aistudio.google.com/) [Google AI Studio](https://aistudio.google.com/)** | Access to [Google Gemini](https://gemini.google.com/) models | [AI Studio Keys](https://aistudio.google.com/app/apikey) |
| **[![Groq AI](https://github.com/user-attachments/assets/c56394b5-79f8-4c25-a24a-2e2a8bde829c)](https://console.groq.com/) [Groq AI](https://console.groq.com/)** | Access to various LLMs (e.g., OpenAI [gpt-oss](https://github.com/openai/gpt-oss), Meta [Llama](https://www.llama.com/), etc...) | [Groq Keys](https://console.groq.com/keys) |
| **[![OpenRouter](https://github.com/user-attachments/assets/0aae7c70-d6ab-4166-8052-d4b9e06b9bb3)](https://openrouter.ai/) [OpenRouter](https://openrouter.ai/)** | Access to various LLMs (e.g., xAI [grok](https://x.ai/news/grok-4-fast), NVIDIA [nemotron](https://build.nvidia.com/nvidia/nvidia-nemotron-nano-9b-v2/modelcard), etc...) | [OpenRouter Keys](https://openrouter.ai/settings/keys) |

> **💡 Note:** Ticker resolution primarily uses [yfinance](https://github.com/ranaroussi/yfinance), which is free and requires no API key. If that fails, the system falls back to [Finnhub](https://finnhub.io/) (if an API key is provided), with the final fallback being [FinanceDatabase](https://github.com/JerBouma/FinanceDatabase/).
>
> **💡 Note:** You do not need to use all the APIs. For the generative AI models ([Google AI Studio](https://aistudio.google.com/), [Groq AI](https://console.groq.com/), and [OpenRouter](https://openrouter.ai/)), you only need to create and use the API keys for the services you are interested in. For example, if you only want to use [xAI](https://x.ai/)'s models, you just need an [OpenRouter API key](https://openrouter.ai/settings/keys). It's also interesting to experiment with different models, as the heuristic results for selecting the top stocks each quarter can vary, although most top-performing stocks are consistently identified across all tested models. **All APIs used in this project are currently free.**

## 📁 Project Structure

```plaintext
hedge-fund-tracker/
├── 📁 .github/
│   ├── 📁 scripts/
│   │   └── 🐍 fetcher.py           # Daily script for data fetching (scheduled by workflows/daily-fetch.yml)
│   └── 📁 workflows/                # GitHub Actions for automation
│       ├── ⚙️ filings-fetch.yml    # GitHub Actions: Filings fetching job
│       └── ⚙️ python-tests.yml     # GitHub Actions: Unit tests
├── 📁 app/                          # Main application logic
│   └── ▶️ main.py                  # Main entry point for Data & AI analysis
├── 📁 database/                     # Data storage
│   ├── 📁 2025Q1/                  # Quarterly reports
│   │   ├── 📊 fund_1.csv           # Individual fund quarterly report
│   │   ├── 📊 fund_2.csv
│   │   └── 📊 fund_n.csv
│   ├── 📁 2025Q2/
│   ├── 📁 YYYYQN/
│   ├── 📝 hedge_funds.csv          # Curated hedge funds list -> EDIT THIS to add or remove funds to track
│   ├── 📝 models.csv               # LLMs list to use for AI Financial Analyst -> EDIT THIS to add or remove AI models
│   ├── 📊 non_quarterly.csv        # Stores latest 13D/G and Form 4 filings
│   ├── 📊 stocks.csv               # Master data for stocks (CUSIP-Ticker-Name)
│   └── ▶️ updater.py               # Main entry point for updating the database
├── 📁 tests/                        # Test suite
├── 📝 .env.example                 # Template for your API keys
├── ⛔ .gitignore                   # Git ignore rules
├── 🧾 LICENSE                      # MIT License
├── 🛠️ Pipfile                      # Project dependencies
├── 🔏 Pipfile.lock                 # Locked dependency versions
└── 📖 README.md                    # Project documentation (this file)
```

> **📝 Hedge Funds Configuration File:** `database/hedge_funds.csv` contains the list of hedge funds to monitor (CIK, name, manager) and can also be edited at runtime.
>
> **📝 LLMs Configuration File:** `database/models.csv` contains the list of available LLMs for AI analysis and can also be edited at runtime.

## 👨🏻‍💻 How This Tool Tracks Hedge Funds

This tracker leverages the following types of SEC filings to provide a comprehensive view of institutional activity.

- **📅 Quarterly 13F Filings**
  - Required for funds managing $100M+
  - Filed ***within 45 days*** of quarter-end
  - Shows ***portfolio snapshot*** on last day of quarter

- **📝 Non-Quarterly 13D/G Filings**
  - Required when acquiring 5%+ of company shares
  - Filed ***within 10 days*** of the transaction
  - Provides a ***timely view*** of significant investments

- **✍🏻 Non-Quarterly SEC Form 4 Insider Filings**
  - Filed by insiders (executives, directors) or large shareholders (>10%) when they trade company stocks
  - Must be filed ***within 2 business days*** of the transaction
  - Offers ***real-time insight*** into the actions of key individuals and institutions

## 🏢 Hedge Funds Selection

This tool tracks a curated list of the **150 of what I found to be the top-performing US hedge funds**, selected based on their performance over the last 3-5 years. This **selection** is the result of my own **methodology** designed to identify the **top percentile of institutional investors**. My *selection methodology* is detailed below.

### Selection Methodology

[Modern portfolio theory (MPT)](https://en.wikipedia.org/wiki/Modern_portfolio_theory) offers many methods for quantifying the [risk-return trade-off](https://en.wikipedia.org/wiki/Risk%E2%80%93return_spectrum), but they are often ill-suited for analyzing the limited data available in public filings. Consequently, the `hedge_funds.csv` was therefore generated using my own custom *selection algorithm* designed to identify top-performing funds while managing for [volatility](https://en.wikipedia.org/wiki/Volatility_(finance)).

> **Note**: The selection algorithm is external to this project and was used only to produce the curated `hedge_funds.csv` list.

My approach prioritizes high [cumulative returns](https://en.wikipedia.org/wiki/Rate_of_return) but also analyzes the path taken to achieve them: it penalizes [volatility](https://en.wikipedia.org/wiki/Volatility_(finance)), similar to the [Sharpe Ratio](https://en.wikipedia.org/wiki/Sharpe_ratio), but this penalty is dynamically adjusted based on performance consistency; likewise, [drawdowns](https://en.wikipedia.org/wiki/Drawdown_(economics)) are penalized, echoing the principle of the [Sterling Ratio](https://en.wikipedia.org/wiki/Sterling_ratio), but the penalty is intentionally dampened to avoid overly punishing funds that recover effectively from temporary downturns.

### List Management

The list of funds is dynamic. If a selected fund begins to underperform, I will consider replacing it. Similarly, I plan to eventually expand the list.

A good example of this selection process in action is *Liu Yijun*'s **Prime Capital Management** *(CIK: `0001448793`)*. Despite boasting a **3-Year Cumulative Return** of over **+165%** (as of the 2nd quarter of 2025), it was ultimately excluded for now due to the following *two factors*:

- **Inconsistent Path of Returns**: Most of its significant outperformance is concentrated in the last two years, which doesn't align with the methodology's preference for a more consistent, long-term track record.
- **Extreme Portfolio Concentration**: The portfolio consistently holds only 2-3 positions, making its performance statistically less relevant for aggregate analysis and potentially more volatile.

However, should it continue to significantly outperform the market in the coming quarters, its inclusion in the `hedge_funds.csv` will be reconsidered.

#### Notable Exclusions

Some famous names have to be excluded by design to enhance analysis quality:

- *Warren Buffett*'s [Berkshire Hathaway](https://www.berkshirehathaway.com/)
- *Ray Dalio*'s [Bridgewater Associates](https://www.bridgewater.com/)
- *Michael Burry*'s [Scion Asset Management](https://www.scionasset.com/)
- *Cathie Wood*'s [ARK Invest](https://www.ark-invest.com/)
- *Bill Ackman*'s [Pershing Square](https://pershingsquareholdings.com/)
- *Cliff Asness*'s [Aqr Capital Management](https://www.aqr.com/)
- *Murray Stahl*'s [Horizon Kinetics](https://horizonkinetics.com/)
- *Edward Mule*'s [Silver Point Capital](https://www.silverpointcapital.com/)
- *Paul Singer*'s [Elliot Investment](https://www.elliottmgmt.com/)
- *Daniel Loeb*'s [Third Point](https://www.thirdpoint.com/)
- *George Soros*'s [Soros Fund Management](https://sorosfundmgmt.com/)
- *Bill Gates*'s [Gates Foundation Trust](https://www.gatesfoundation.org/about/financials/foundation-trust)
- *Carl Icahn*'s [Icahn Enterprises](https://www.ielp.com/)
- *Lewis Sanders*'s [Sanders Capital](https://www.sanderscapital.com/)
- *Brad Gerstner*'s [Altimeter Capital Management](https://www.altimeter.com/)
- *Andreas Halvorsen*'s [Viking Global Investors](https://vikingglobal.com/)
- *David Lane*'s [Geode Capital Management](https://www.geodecapital.com/)
- *Robert Robotti*'s [Robotti Value Investors](https://www.robotti.com/)
- *Li Lu*'s [Himalaya Capital Management](https://www.himcap.com/)
- *Ken Fisher*'s [Fisher Asset Management](https://www.fisherinvestments.com/)
- *David Katz*'s [Matrix Asset Advisors](https://matrixassetadvisors.com/)
- *Joel Greenblatt*'s [Gotham Funds](https://www.gothamfunds.com/)
- *Barry Ritholtz*'s [Ritholtz Wealth Management](https://www.ritholtzwealth.com/)
- *Nathaniel August*'s [Mangrove Partners](https://mangrovepartners.com/)
- *James Oshaughnessy*'s [O'Shaughnessy Asset Management](https://www.osam.com/)
- *John Paulson*'s [Paulson & Co.](https://paulsonco.com/)
- *Pat Dorsey*'s [Dorsey Asset Management](https://dorseyasset.com/)
- *Jeremy Grantham*'s [GMO](https://www.gmo.com/)
- *Bill Nygren*'s [Harris Associates](https://harrisassoc.com/)
- *David Booth*'s [Dimensional Fund Advisors](https://www.dimensional.com/)
- *Robert Citrone*'s [Discovery Capital Management](https://discoverycapitalmanagement.com/)
- *Chris Hohn*'s [The Children's Investment](https://ciff.org/)
- *Stan Moss*'s [Polen Capital](https://www.polencapital.com/)
- *Sander Gerber*'s [Hudson Bay Capital Management](https://www.hudsonbaycapital.com/)
- *Bill Peckford*'s [Polar Asset Management](https://polaramp.com/)
- *Robert Atchison & Phillip Gross*'s [Adage Capital Partners](https://www.adagecapital.com/)
- [BlackRock](https://www.blackrock.com/)
- [State Street](https://statestreet.com/)
- [Jane Street](https://www.janestreet.com/)

#### Adding Custom Funds

Want to track additional funds? Simply edit `database/hedge_funds.csv` and add your preferred institutional investors. For example, to add [Berkshire Hathaway](https://www.berkshirehathaway.com/), [Pershing Square](https://pershingsquareholdings.com/) and [ARK-Invest](https://www.ark-invest.com/), you would add the following lines:

```csv
"CIK","Fund","Manager","Denomination"
"0001067983","Berkshire Hathaway","Warren Buffett","Berkshire Hathaway Inc."
"0001336528","Pershing Square","Bill Ackman","Pershing Square Capital Management, L.P."
"0001697748","ARK Invest","Cathie Wood","ARK Investment Management LLC"
```

> **💡 Note**: `hedge_funds.csv` currently includes **not only *traditional hedge funds*** but also **other institutional investors** *(private equity funds, large banks, VCs, pension funds, etc., that file 13F to the [SEC](http://sec.gov/))* selected from what I consider the **top 5%** of performers.

## 🧠 AI Models Selection

The **AI Financial Analyst**'s primary goal is to identify stocks with the highest growth potential based on hedge fund activity. It achieves this by calculating a **"Promise Score"** for each stock. This score is a weighted average of various metrics derived from 13F filings. The AI's first critical task is to act as a strategist, dynamically defining the heuristic by assigning the optimal weights for these metrics based on the market conditions of the selected quarter. Its second task is to provide quantitative scores (e.g., momentum, risk) for the top-ranked stocks.

The models included in `database/models.csv` have been selected because they have demonstrated the best performance and reliability for these specific tasks. Through experimentation, they have proven effective at interpreting the prompts and providing insightful, well-structured responses.

> **💡 Note** on Meta's [`llama-3.3-70b-versatile`](https://github.com/meta-llama/llama-models/blob/main/models/llama3_3/MODEL_CARD.md): while it can occasionally be less precise in defining the heuristic for the "Promise Score" compared to other top-tier models, it remains a valuable option. Its exceptional speed and lightweight nature make it ideal for rapid experimentation and iterative analysis, providing a useful trade-off between accuracy and performance. As the AI landscape evolves, it is expected that this model will eventually be replaced by newer alternatives that offer similar or better speed and efficiency.

### Adding Custom AI Models

You can easily add or change the AI models used for analysis by editing the `database/models.csv` file. This allows you to experiment with different Large Language Models (LLMs) from supported providers.

To add a new model, open `database/models.csv` and add a new row with the following columns:

- **ID**: The specific model identifier as required by the provider's API.
- **Description**: A brief, user-friendly description that will be displayed in the selection menu.
- **Client**: The provider of the model. Must be one of `Google`, `Groq`, or `OpenRouter`.

Here are the official model lists for each provider:

- [Google Gemini Models](https://ai.google.dev/gemini-api/docs/models)
- [Groq Available Models](https://console.groq.com/docs/models)
- [OpenRouter Available Models](https://openrouter.ai/models?order=newest&max_price=0)

## ⚠️ Limitations & Considerations

It's crucial to understand the inherent limitations of tracking investment strategies solely through SEC filings:

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| **🕒 Filing Delay** | Data can be 45+ days old | Focus on long-term strategies |
| **🧩 Incomplete Picture** | Only US long positions shown | Use as part of broader analysis |
| **📉 No Short Positions** | Missing hedge information | Consider reported positions carefully |
| **🌎 Limited Scope** | No non-US stocks or other assets | Supplement with additional data |

### A Truly Up-to-Date View

Many tracking websites rely solely on quarterly 13F filings, which means their data can be over 45 days old and miss many significant trades. Non-quarterly filings like 13D/G and Form 4 are often ignored because they are more complex to process and merge.

This tracker helps overcome that limitation by **integrating multiple filing types**. When analyzing the most recent quarter, the tool automatically incorporates the latest data from 13D/G and Form 4 filings. This means that the holdings, deltas, and portfolio percentages you see for the last quarter reflect not just the 13F snapshot, but also any significant trades that have occurred since. This ensures you have the most current and complete picture of institutional activity.

## ⚙️ Automation with GitHub Actions

This repository includes a [GitHub Actions](https://github.com/features/actions) workflow (`.github/workflows/filings-fetch.yml`) designed to keep your data effortlessly up-to-date by automatically fetching the latest SEC filings.

### How It Works

- **Scheduled Runs**: The workflow runs automatically every 5 hours *(from Monday to Saturday)* to check for **new 13F, 13D/G, and Form 4 filings** from the funds you are tracking (`hedge_funds.csv`).
- **Safe Branching Strategy**: Instead of committing directly to your main branch, the workflow pushes all new data to a dedicated branch named `automated/filings-fetch`.
- **User-Controlled Merging**: This approach gives you full control. You can review the changes committed by the bot and then merge them into your main branch whenever you're ready. This prevents unexpected changes and allows you to manage updates at your own pace.
- **Automated Alerts**: If the script encounters a non-quarterly filing where it cannot identify the fund owner based on your `hedge_funds.csv` configuration, it will automatically open a GitHub Issue in your repository, alerting you to a potential data mismatch that needs investigation.

### How to Enable It

1. **Fork the Repository**: Create your own [fork of this project](https://github.com/dokson/hedge-fund-tracker/fork) on GitHub.
2. **Enable Actions**: GitHub Actions are typically enabled by default on forked repositories. You can verify this under the *Actions* tab of your fork.
3. **Configure Secrets**: For the workflow to resolve tickers and create issues, you need to add your API keys as repository secrets. In your forked repository, you must add your `FINNHUB_API_KEY` as a repository secret. Go to `Settings` > `Secrets and variables` > `Actions` in your forked repository to add it.

## 🗃️ Technical Stack

| 🗂️ Category | 🦾 Technology |
|----------|------------|
| **Core** | [Python 3.13](https://www.python.org/downloads/release/python-3130/)+, [pipenv](https://pipenv.pypa.io/) |
| **Web Scraping** | [Requests](https://2.python-requests.org/en/master/), [Beautiful Soup](https://pypi.org/project/beautifulsoup4/), [lxml](https://lxml.de/) |
| **Config** | [python-dotenv](https://github.com/theskumar/python-dotenv) |
| **Data Processing** | [pandas](https://pandas.pydata.org/), [csv](https://docs.python.org/3/library/csv.html) |
| **Stocks Libraries** | [Finnhub-Stock-API](https://github.com/Finnhub-Stock-API/finnhub-python), [FinanceDatabase](https://github.com/JerBouma/FinanceDatabase/) |
| **Gen AI** | [Google Gen AI SDK](https://googleapis.github.io/python-genai/), [Groq](https://github.com/groq/groq-python), [OpenAI](https://github.com/openai/openai-python) |

## 🤝🏼 Contributing & Support

### 💬 Get Help

- **🆕 [Feature Requests](https://github.com/dokson/hedge-fund-tracker/issues/new?template=feature_request.md)**
- **🐛 [Bug Reports](https://github.com/dokson/hedge-fund-tracker/issues/new?template=bug_report.md)**

### ✍🏻 Feedback

I am continuously developing this tool and adding new features.
I welcome all feedback, so feel free to [contact me](https://github.com/dokson).

## 📚 References

- [SEC Developer Resources](https://www.sec.gov/about/developer-resources)
- [SEC: Frequently Asked Questions About Form 13F](https://www.sec.gov/rules-regulations/staff-guidance/division-investment-management-frequently-asked-questions/frequently-asked-questions-about-form-13f)
- [SEC: Guidance on Beneficial Ownership Reporting (Sections 13D/G)](https://www.sec.gov/rules-regulations/staff-guidance/compliance-disclosure-interpretations/exchange-act-sections-13d-13g-regulation-13d-g-beneficial-ownership-reporting)

## 🙏🏼 Acknowledgments

This project started as a fork of the [sec-web-scraper-13f](https://github.com/CodeWritingCow/sec-web-scraper-13f) by [Gary Pang](https://github.com/CodeWritingCow). The original tool was a Python script to scrape the most recent 13F filing for a given CIK from the [SEC](http://sec.gov/)'s [EDGAR](https://www.sec.gov/edgar/searchedgar/companysearch.html) database. It has since evolved significantly into a comprehensive hedge fund tracker.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
