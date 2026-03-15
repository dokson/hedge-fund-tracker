# 📊 Hedge Fund Tracker

[![repo views](https://komarev.com/ghpvc/?username=dokson&repo=hedge-fund-tracker&label=views&color=orange)](https://github.com/dokson/hedge-fund-tracker)
[![repo size](https://img.shields.io/github/repo-size/dokson/hedge-fund-tracker)](https://github.com/dokson/hedge-fund-tracker/tree/master)
[![last commit](https://img.shields.io/github/last-commit/dokson/hedge-fund-tracker)](https://github.com/dokson/hedge-fund-tracker/commits/master/)
[![latest release](https://img.shields.io/github/v/release/dokson/hedge-fund-tracker?label=version&color=green)](https://github.com/dokson/hedge-fund-tracker/releases)
[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3130/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![License](https://img.shields.io/badge/license-Source%20Available-blue)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/dokson/hedge-fund-tracker.svg?style=social&label=Star)](https://github.com/dokson/hedge-fund-tracker/stargazers)
[![GitHub watchers](https://img.shields.io/github/watchers/dokson/hedge-fund-tracker.svg)](https://github.com/dokson/hedge-fund-tracker/watchers)
[![GitHub forks](https://img.shields.io/github/forks/dokson/hedge-fund-tracker.svg)](https://github.com/dokson/hedge-fund-tracker/network/members)

**If this tool is helping you, please ⭐ the repo!** It really helps discoverability.

> **SEC 13F Filing Tracker | Institutional Portfolio Analysis | AI-Powered Stock Research**

A comprehensive **Python tool** for tracking **hedge fund portfolios** through **SEC filings** (13F, 13D/G, Form 4). Transform raw [SEC EDGAR](https://www.sec.gov/edgar) data into actionable **investment insights**. Built for **financial analysts**, **quantitative traders**, and **retail investors** seeking to analyze **institutional investor strategies**, **portfolio changes**, and discover **stock opportunities** by following elite fund managers.

**Keywords**: SEC filings tracker, 13F analysis, hedge fund portfolio, institutional investors, stock research, investment intelligence, CUSIP converter, financial data scraper, AI stock analysis

## ⫶☰ Table of Contents

- [📊 Hedge Fund Tracker](#-hedge-fund-tracker)
  - [🚀 Quick Start](#-quick-start)
  - [✨ Key Features](#-key-features)
  - [📦 Installation](#-installation)
    - [Prerequisites](#prerequisites)
    - [Data Management](#data-management)
    - [Database Updater](#database-updater)
    - [GICS Classification](#gics-classification)
    - [API Configuration](#api-configuration)
  - [📁 Project Structure](#-project-structure)
  - [👨🏻‍💻 How This Tool Tracks Hedge Funds](#-how-this-tool-tracks-hedge-funds)
  - [🏢 Hedge Funds Selection](#-hedge-funds-selection)
    - [Selection Methodology](#selection-methodology)
    - [List Management](#list-management)
      - [Notable Exclusions](#notable-exclusions)
      - [Adding Custom Funds](#adding-custom-funds)
  - [🧠 AI Models Selection](#-ai-models-selection)
    - [Adding Custom AI Models](#adding-custom-ai-models)
  - [⚠️ Limitations & Considerations](#-limitations--considerations)
    - [A Truly Up-to-Date View](#a-truly-up-to-date-view)
  - [⚙️ Automation with GitHub Actions](#-automation-with-github-actions)
    - [How It Works](#how-it-works)
    - [How to Enable It](#how-to-enable-it)
  - [🗃️ Technical Stack](#-technical-stack)
  - [🤝🏼 Contributing & Support](#-contributing--support)
    - [💬 Loved it? Help it grow](#-loved-it-help-it-grow)
    - [✍🏻 Feedback](#-feedback)
  - [📚 References](#-references)
  - [🙏🏼 Acknowledgments](#-acknowledgments)
  - [📄 License](#-license)

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/dokson/hedge-fund-tracker.git
cd hedge-fund-tracker

# Install Python dependencies
pipenv install

# Install and build the React frontend
cd app/frontend && npm install && npm run build && cd ../..

# Run the application (opens web UI in your browser)
pipenv run python -m app.main
```

## ✨ Key Features

| Feature | Description |
| :--- | :--- |
| **🌐 Modern Web UI** | Premium React-based platform with real-time SSE streaming for AI tasks, native Dark Mode, and responsive design. |
| **📊 Visual Analytics** | Interactive charts (Recharts) to track institutional holdings, sectoral trends, and quarterly portfolio evolutions. |
| **🆚 Comparative Analysis** | Combines quarterly (13F) and non-quarterly (13D/G, Form 4) filings for an up-to-date view. |
| **📋 Comprehensive Reports** | High-fidelity analysis pages for both investment funds (portfolios) and specific stocks (tickers). |
| **🔍 Smart Ticker Resolution** | Multi-fallback system (yfinance, Finnhub, FinanceDatabase) to resolve CUSIPs into actionable stock symbols. |
| **🤖 AI Financial Analyst** | Leverages top-tier LLMs to calculate "Promise Scores" and perform deep due diligence on high-conviction opportunities. |
| **⚙️ Automated Data Pipeline** | Scheduled GitHub Actions to fetch, process, and commit the latest SEC filings directly to your repository. |
| **🌐 GitHub Pages Demo** | Static deployment with bundled data — all analysis features work without a backend. |
| **⭐ Personalized Watchlist** | Star your favorite funds or stocks for quick access and personalized tracking across the platform. |
| **🗃️ GICS Hierarchy** | Autonomous parser to build a granular [GICS](https://www.msci.com/indexes/index-resources/gics) classification database. |

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

3. **🔨 Build the frontend:** Build the React interface (required once before first run):

   ```bash
   cd app/frontend && npm install && npm run build && cd ../..
   ```

4. **▶️ Run the application:** Execute within the project's virtual environment:

   ```bash
   pipenv run python -m app.main
   ```

   This starts a FastAPI server on `http://localhost:8000` and opens the **web UI** in your browser automatically.

   > **⚠️ Note on CLI mode (Legacy):** The terminal CLI is a **deprecated version** of the tool, built before the development of the modern Web UI. While still functional, it requires a manual `.env` configuration. This file is **automatically generated** the first time you launch the Web UI. So, if you still wish to use the "old school" CLI, just run:
   >
   > ```bash
   > pipenv run python -m app.main --cli
   > ```

### Data Management

The data update operations (downloading and processing filings) are inside a dedicated script. This keeps the main application focused on analysis, while the updater handles populating and refreshing the database.

To run the data update operations, you need to use the `updater.py` script from the project root:

```bash
pipenv run python -m database.updater
```

### Database Updater

The `updater.py` script includes semi-automated maintenance tasks:

- **Sorting**: Upon exit (option `0`), the script automatically sorts the `database/stocks.csv` file by ticker to maintain performance and prevent Git diff noise.
- **Auto-Documentation**: This README's excluded funds section is synchronized whenever the database is refreshed manually.

This will open a separate menu for data management:

```txt
┌───────────────────────────────────────────────────────────────────────────────┐
│                     Hedge Fund Tracker - Database Updater                     │
├───────────────────────────────────────────────────────────────────────────────┤
│  0. Exit                                                                      │
│  1. Generate latest 13F reports for all known hedge funds                     │
│  2. Fetch latest non-quarterly filings for all known hedge funds              │
│  3. Generate 13F report for a known hedge fund                                │
│  4. Manually enter a hedge fund CIK to generate a 13F report                  │
└───────────────────────────────────────────────────────────────────────────────┘
```

### GICS Classification

The project includes an **autonomous GICS (Global Industry Classification Standard) parser** (`database/gics/updater.py`). Originally developed by [MSCI](https://www.msci.com/) and [S&P](https://www.spglobal.com/), it scrapes Wikipedia to build a full hierarchy of 163 sub-industries. This provides the AI Analyst with granular industry context while remaining independent of third-party libraries.

### API Configuration

The tool can utilize API keys for enhanced functionality, but all are optional:

| Service | Purpose | Get Free API Key |
| :--- | :--- | :--- |
| **[![Finnhub](https://github.com/user-attachments/assets/94465a7f-75e0-4a21-827c-511540c80cb3)](https://finnhub.io/) [Finnhub](https://finnhub.io/)** | [CUSIP](https://en.wikipedia.org/wiki/CUSIP) to [stock ticker](https://en.wikipedia.org/wiki/Ticker_symbol) conversion | [Finnhub Keys](https://finnhub.io/dashboard) |
| **[![GitHub Models](https://github.com/user-attachments/assets/3e8ca2f8-1bb0-4ec3-9374-d6106499adde)](https://github.com/marketplace/models) [GitHub Models](https://github.com/marketplace/models)** | Access to top-tier models (e.g., [xAI Grok-3](https://x.ai/news/grok-3), [OpenAI GPT-5](https://openai.com/en-US/gpt-5/), etc...) | [GitHub Tokens](https://github.com/settings/personal-access-tokens/new?description=Used+to+call+GitHub+Models+APIs+to+easily+run+LLMs%3A+https%3A%2F%2Fdocs.github.com%2Fgithub-models%2Fquickstart%23step-2-make-an-api-call&name=GitHub+Models+token&user_models=read) |
| **[![Google AI Studio](https://github.com/user-attachments/assets/3b351d8e-d7f6-4337-9c2f-d2af77f30711)](https://aistudio.google.com/) [Google AI Studio](https://aistudio.google.com/)** | Access to [Google Gemini](https://gemini.google.com/) models | [AI Studio Keys](https://aistudio.google.com/app/apikey) |
| **[![Groq AI](https://github.com/user-attachments/assets/c56394b5-79f8-4c25-a24a-2e2a8bde829c)](https://console.groq.com/) [Groq AI](https://console.groq.com/)** | Access to various LLMs (e.g., OpenAI [gpt-oss](https://github.com/openai/gpt-oss), Meta [Llama](https://www.llama.com/), etc...) | [Groq Keys](https://console.groq.com/keys) |
| **[![Hugging Face](https://github.com/user-attachments/assets/b4f22e8b-6c6e-4e28-91ca-e2bc9b89837f)](https://huggingface.co/) [Hugging Face](https://huggingface.co/)** | Access to open weights models (e.g., [DeepSeek R1](https://huggingface.co/deepseek-ai/DeepSeek-R1), [Kimi-Linear-48B](https://huggingface.co/moonshotai/Kimi-Linear-48B-A3B-Instruct), etc...) | [HF Tokens](https://huggingface.co/settings/tokens) |
| **[![OpenRouter](https://github.com/user-attachments/assets/0aae7c70-d6ab-4166-8052-d4b9e06b9bb3)](https://openrouter.ai/) [OpenRouter](https://openrouter.ai/)** | Access to various LLMs (e.g., [Claude 4.5 Opus](https://www.anthropic.com/news/claude-4-5-opus), [GLM 4.5 Air](https://chatglm.cn/), etc...) | [OpenRouter Keys](https://openrouter.ai/settings/keys) |

> **💡 Note:** Ticker resolution primarily uses [yfinance](https://github.com/ranaroussi/yfinance), which is free and requires no API key. If that fails, the system falls back to [Finnhub](https://finnhub.io/) (if an API key is provided), with the final fallback being [FinanceDatabase](https://github.com/JerBouma/FinanceDatabase/).
>
> **💡 Note:** You don't need to use all the APIs. For the generative AI models ([Google AI Studio](https://aistudio.google.com/), [GitHub Models](https://github.com/marketplace/models), [Groq AI](https://console.groq.com/), [Hugging Face](https://huggingface.co/models), and [OpenRouter](https://openrouter.ai/)), you only need the API keys for the services you plan to use.
> For instance, if you want to experiment with models like [OpenAI](https://openai.com/) [GPT-4o mini](https://platform.openai.com/docs/models/gpt-4o-mini), you just need a [GitHub Token](https://github.com/settings/tokens). Experimenting with different models is encouraged, as the quality of AI-generated analysis, both for identifying promising stocks and for conducting due diligence, can vary. However, top-performing stocks are typically identified consistently across all tested models. **All APIs used in this project are currently free (with GitHub Models providing a generous free tier for developers).**

## 📁 Project Structure

```plaintext
hedge-fund-tracker/
├── 📁 .github/
│   ├── 📁 scripts/
│   │   └── 🐍 fetcher.py           # Daily script for data fetching (scheduled by workflows/daily-fetch.yml)
│   └── 📁 workflows/                # GitHub Actions for automation
│       ├── ⚙️ deploy-pages.yml     # GitHub Actions: Deploy to GitHub Pages
│       ├── ⚙️ filings-fetch.yml    # GitHub Actions: Filings fetching job
│       └── ⚙️ python-tests.yml     # GitHub Actions: Unit tests
├── 📁 app/                          # Main application logic
│   ├── 📁 frontend/                 # React + Vite web UI
│   │   ├── 📁 public/               # Static assets (404.html, logo.png)
│   │   ├── 📁 scripts/              # copy-database.mjs (bundles CSVs for GH Pages)
│   │   ├── 📁 src/
│   │   │   ├── 📁 components/       # Shared UI components (ModelSelector, TerminalOutput, FeatureNotAvailable, etc.)
│   │   │   ├── 📁 lib/              # config.ts (IS_GH_PAGES_MODE), dataService.ts (CSV I/O), aiClient.ts (SSE)
│   │   │   └── 📁 pages/            # AIRanking, AIDueDiligence, FundsConfig, AISettings, DatabaseOperations
│   │   ├── 📦 package.json
│   │   └── ⚙️ vite.config.ts
│   ├── 🐍 server.py                 # FastAPI server (serves frontend + all API endpoints)
│   └── ▶️ main.py                  # Entry point: web server (default) or CLI (--cli)
├── 📁 database/                     # Data storage
│   ├── 📁 2025Q1/                  # Quarterly reports
│   │   ├── 📊 fund_1.csv           # Individual fund quarterly report
│   │   ├── 📊 fund_2.csv
│   │   └── 📊 fund_n.csv
│   ├── 📁 YYYYQN/
│   ├── 📁 GICS/
│   │   ├── 🗃️ hierarchy.csv        # Full GICS hierarchy
│   │   └── ▶️ updater.py           # GICS updater script
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
  - Filed **_within 45 days_** of quarter-end
  - Shows **_portfolio snapshot_** on last day of quarter

- **📝 Non-Quarterly 13D/G Filings**
  - Required when acquiring 5%+ of company shares
  - Filed **_within 10 days_** of the transaction
  - Provides a **_timely view_** of significant investments

- **✍🏻 Non-Quarterly SEC Form 4 Insider Filings**
  - Filed by insiders (executives, directors) or large shareholders (>10%) when they trade company stocks
  - Must be filed **_within 2 business days_** of the transaction
  - Offers **_real-time insight_** into the actions of key individuals and institutions

## 🏢 Hedge Funds Selection

This tool tracks a curated list of **what I found to be the top-performing institutional investors that file with the U.S. SEC**, _identified_ based on their performance over the last 3-5 years. This **curation** is the result of my own **methodology** designed to identify the **top percentile of global investment funds**. My _selection methodology_ is detailed below.

### Selection Methodology

[Modern portfolio theory (MPT)](https://en.wikipedia.org/wiki/Modern_portfolio_theory) offers many methods for quantifying the [risk-return trade-off](https://en.wikipedia.org/wiki/Risk%E2%80%93return_spectrum), but they are often ill-suited for analyzing the limited data available in public filings. Consequently, the `hedge_funds.csv` was therefore generated using my own custom _selection algorithm_ designed to identify top-performing funds while managing for [volatility](<https://en.wikipedia.org/wiki/Volatility_(finance)>).

> **Note**: The selection algorithm is external to this project and was used only to produce the curated `hedge_funds.csv` list.

My approach prioritizes high [cumulative returns](https://en.wikipedia.org/wiki/Rate_of_return) but also analyzes the path taken to achieve them: it penalizes [volatility](<https://en.wikipedia.org/wiki/Volatility_(finance)>), similar to the [Sharpe Ratio](https://en.wikipedia.org/wiki/Sharpe_ratio), but this penalty is dynamically adjusted based on performance consistency; likewise, [drawdowns](<https://en.wikipedia.org/wiki/Drawdown_(economics)>) are penalized, echoing the principle of the [Sterling Ratio](https://en.wikipedia.org/wiki/Sterling_ratio), but the penalty is intentionally dampened to avoid overly punishing funds that recover effectively from temporary downturns.

### List Management

The list of hedge funds is actively managed to maintain its quality; funds that underperform may be replaced, while new top performers are periodically added.

However, despite their strong performance, several funds with portfolios predominantly focused on **Healthcare** and **Biotech**, such as **[Nextech Invest](https://www.nextechinvest.com/)**, **[Enavate Sciences](https://enavatesciences.com/)**, **[Caligan Partners](https://www.caliganpartners.com/)**, and **[Boxer Capital Management](https://www.boxercap.com/)**, have been intentionally excluded. These funds invest in highly specialized sectors where I lack the necessary expertise. Consequently, I consider them too risky for my personal investment profile, given the complexity and volatility inherent in biotech and healthcare ventures.

#### Notable Exclusions

The quality of the output analysis is directly tied to the quality of the input data. To enhance the accuracy of the insights and opportunities identified, many popular high-profile funds have been intentionally excluded by design (the list below is automatically managed and capped to 50 funds, but you can see the full list in `excluded_hedge_funds.csv`):

<!-- EXCLUDED_FUNDS_LIST_START -->

- _Warren Buffett_'s [Berkshire Hathaway](https://www.berkshirehathaway.com/)
- _Ken Griffin_'s [Citadel Advisors](https://www.citadel.com/)
- _Ray Dalio_'s [Bridgewater Associates](https://www.bridgewater.com/)
- _Michael Burry_'s [Scion Asset Management](https://www.scionasset.com/)
- _Peter Thiel_'s [Thiel Macro](https://www.linkedin.com/company/thiel-macro)
- _Cathie Wood_'s [ARK Invest](https://www.ark-invest.com/)
- _Bill Ackman_'s [Pershing Square](https://pershingsquareholdings.com/)
- _Dmitry Balyasny_'s [Balyasny Asset Management](https://www.bamfunds.com/)
- _Alec Litowitz_'s [Magnetar Capital](https://www.magnetar.com/)
- _Cliff Asness_'s [AQR Capital Management](https://www.aqr.com/)
- _David Tepper_'s [Appaloosa](https://www.appaloosawm.com/)
- _Israel Englander_'s [Millennium Management](https://www.mlp.com/)
- _Frank Sands_'s [Sands Capital Management](https://www.sandscapital.com/)
- _Murray Stahl_'s [Horizon Kinetics](https://horizonkinetics.com/)
- _Edward Mule_'s [Silver Point Capital](https://www.silverpointcapital.com/)
- _David Abrams_'s [Abrams Capital Management](https://www.abramscapital.com/)
- _Jeffrey Ubben_'s [ValueAct Capital](https://valueact.com/)
- _Paul Singer_'s [Elliott Investment](https://www.elliottmgmt.com/)
- _Chris Hohn_'s [The Children's Investment](https://ciff.org/)
- _Daniel Loeb_'s [Third Point](https://www.thirdpoint.com/)
- _Boaz Weinstein_'s [Saba Capital](https://www.sabacapital.com/)
- _William Huffman_'s [Nuveen](https://www.nuveen.com/)
- _George Soros_'s [Soros Fund Management](https://sorosfundmgmt.com/)
- _Bill Gates_'s [Gates Foundation Trust](https://www.gatesfoundation.org/about/financials/foundation-trust)
- _Carl Icahn_'s [Icahn Enterprises](https://www.ielp.com/)
- _Dev Kantesaria_'s [Valley Forge Capital Management](https://www.valleyforgecapital.com/)
- _Lewis Sanders_'s [Sanders Capital](https://www.sanderscapital.com/)
- _Brad Gerstner_'s [Altimeter Capital Management](https://www.altimeter.com/)
- _Andreas Halvorsen_'s [Viking Global Investors](https://vikingglobal.com/)
- _Paul Tudor Jones_'s [Tudor Investment Corporation](https://www.tudorfunds.com/)
- _Chris Davis_'s [Davis Advisors](https://davisfunds.com/)
- _Paul Isaac_'s [Arbiter Partners](https://arbiterpartners.net/)
- _Robert Robotti_'s [Robotti Value Investors](https://www.robotti.com/)
- _Jim Cracchiolo_'s [Ameriprise Financial](https://www.ameriprise.com/)
- _Li Lu_'s [Himalaya Capital Management](https://www.himcap.com/)
- _Francis Chou_'s [Chou Associates](https://www.choufunds.com/)
- _Anand Parekh_'s [Alyeska Investment Group](https://alyeskagroup.com/)
- _Ken Fisher_'s [Fisher Asset Management](https://www.fisherinvestments.com/)
- _David Katz_'s [Matrix Asset Advisors](https://matrixassetadvisors.com/)
- _Lee Ainslie_'s [Maverick Capital](https://www.maverickcap.com/)
- _Joel Greenblatt_'s [Gotham Funds](https://www.gothamfunds.com/)
- _Barry Ritholtz_'s [Ritholtz Wealth Management](https://www.ritholtzwealth.com/)
- _Robert Pitts_'s [Steadfast Capital Management](https://www.steadfast.com/)
- _John Paulson_'s [Paulson & Co.](https://paulsonco.com/)
- _Jeremy Grantham_'s [GMO](https://www.gmo.com/)
- _Paul Marshall & Ian Wace_'s [Marshall Wace](https://www.mwam.com/)
- _Seymour Kaufman_'s [Crosslink Capital](https://www.crosslinkcapital.com/)
- _Mario Gabelli_'s [GAMCO Investors](https://gabelli.com/)
- _John Overdeck_'s [Two Sigma](https://www.twosigma.com/)
- _Richard Pzena_'s [Pzena Investment Management](https://www.pzena.com/)
- and many more... (see [`database/excluded_hedge_funds.csv`](/database/excluded_hedge_funds.csv) for the full list)
<!-- EXCLUDED_FUNDS_LIST_END -->

> **💡 Note**: For convenience, key information for these funds, including their CIKs, is maintained in the `database/excluded_hedge_funds.csv` file.

#### Adding Custom Funds

Want to track additional funds? Simply edit `database/hedge_funds.csv` and add your preferred institutional investors. For example, to add [Berkshire Hathaway](https://www.berkshirehathaway.com/), [Pershing Square](https://pershingsquareholdings.com/) and [ARK-Invest](https://www.ark-invest.com/), you would add the following lines:

```csv
"CIK","Fund","Manager","Denomination","CIKs"
"0001067983","Berkshire Hathaway","Warren Buffett","Berkshire Hathaway Inc",""
"0001336528","Pershing Square","Bill Ackman","Pershing Square Capital Management, L.P.",""
"0001697748","ARK Invest","Cathie Wood","ARK Investment Management LLC",""
```

> **💡 Note**: `hedge_funds.csv` currently includes **not only _traditional hedge funds_** but also **other institutional investors** _(private equity funds, large banks, VCs, pension funds, etc., that file 13F to the [SEC](http://sec.gov/))_ selected from what I consider the **top 5%** of performers.
>
> If you wish to track any of the **Notable Exclusions** hedge funds, you can copy the relevant rows from `excluded_hedge_funds.csv` into `hedge_funds.csv`.

##### **Columns for Custom Funds:**

- **`Denomination`**: This is the exact legal name used by the fund in its filings. It is **essential** for accurately processing non-quarterly filings (13D/G, Form 4) as the scraper uses it to identify the fund's specific transactions within complex filing documents.
- **`CIKs`** _(optional)_: A comma-separated list of additional CIKs. This field is used to track filings from related entities or subsidiaries. Some investment firms have complex structures where different legal entities file separately (e.g., a management company and a holding company).

  _Example:_ [Jeffrey Ubben](https://en.wikipedia.org/wiki/Jeffrey_W._Ubben)'s [ValueAct Holdings _(CIK = `0001418814`)_](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001418814) also has filings under [ValueAct Capital Management _(CIK = `0001418812`)_](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001418812). By adding `0001418812` to the `CIKs` column, the tool aggregates **non-quarterly filings** from both entities for a complete view.

  ```csv
  "CIK","Fund","Manager","Denomination","CIKs"
  "0001418814","ValueAct","Jeffrey Ubben","ValueAct Holdings, L.P.","0001418812"
  ```

## 🧠 AI Models Selection

The **AI Financial Analyst**'s primary goal is to identify stocks with the highest growth potential based on hedge fund activity. It achieves this by calculating a **"Promise Score"** for each stock. This score is a weighted average of various metrics derived from 13F filings. The AI's first critical task is to act as a strategist, dynamically defining the heuristic by assigning the optimal weights for these metrics based on the market conditions of the selected quarter. Its second task is to provide quantitative scores (e.g., momentum, risk) for the top-ranked stocks.

The models included in `database/models.csv` have been selected because they have demonstrated the best performance and reliability for these specific tasks. Through experimentation, they have proven effective at interpreting the prompts and providing insightful, well-structured responses.

### Adding Custom AI Models

You can easily add or change the AI models used for analysis by editing the `database/models.csv` file. This allows you to experiment with different Large Language Models (LLMs) from supported providers.

To add a new model, open `database/models.csv` and add a new row with the following columns:

- **ID**: The specific model identifier as required by the provider's API.
- **Description**: A brief, user-friendly description that will be displayed in the selection menu.
- **Client**: The provider of the model. Must be one of `GitHub`, `Google`, `Groq`, `HuggingFace`, or `OpenRouter`.

Here are the official model lists for each provider:

- [GitHub Models](https://github.com/marketplace/models)
- [Google Gemini Models](https://ai.google.dev/gemini-api/docs/models)
- [Groq Models](https://console.groq.com/docs/models)
- [HuggingFace Models](https://huggingface.co/models)
- [OpenRouter Free Models](https://openrouter.ai/models?order=newest&max_price=0)

## ⚠️ Limitations & Considerations

It's crucial to understand the inherent limitations of tracking investment strategies solely through SEC filings:

| Limitation | Impact | Mitigation |
| :--- | :--- | :--- |
| **🕒 Filing Delay** | Data can be 45+ days old | Focus on long-term strategies |
| **🧩 Incomplete Picture** | Only US long positions shown | Use as part of broader analysis |
| **📉 No Short Positions** | Missing hedge information | Consider reported positions carefully |
| **🌎 Limited Scope** | No non-US stocks or other assets | Supplement with additional data |

### A Truly Up-to-Date View

Many tracking websites rely solely on quarterly 13F filings, which means their data can be over 45 days old and miss many significant trades. Non-quarterly filings like 13D/G and Form 4 are often ignored because they are more complex to process and merge.

This tracker helps overcome that limitation by **integrating multiple filing types**. When analyzing the most recent quarter, the tool automatically incorporates the latest data from 13D/G and Form 4 filings. As a result, the holdings, deltas, and portfolio percentages reflect not just the static 13F snapshot, but also any significant trades that have occurred since. This provides a more dynamic and complete picture of institutional activity.

## 🌐 GitHub Pages Deployment

The frontend can be deployed as a **static demo on GitHub Pages** — no Python backend required. AI features and data updates are disabled in this mode, but all core analysis pages work with bundled data.

**Live demo**: `https://{username}.github.io/hedge-fund-tracker/`

### What's Available in GitHub Pages Mode

| Page | Status |
| :--- | :--- |
| Dashboard (Latest Filings) | Fully functional |
| Quarterly Trends | Fully functional |
| Hedge Fund Portfolios | Fully functional |
| Stocks Browser | Fully functional |
| Funds Config | Read-only (data visible, no edits) |
| AI Ranking | Disabled (requires local backend) |
| AI Due Diligence | Disabled (requires local backend) |
| AI Settings | Hidden |
| Database Operations | Hidden |

### How to Deploy

1. **Fork the repository** on GitHub
2. **Enable GitHub Pages**: Go to Settings > Pages > Source: **"GitHub Actions"**
3. **Push to `master`** — the deploy workflow (`.github/workflows/deploy-pages.yml`) runs automatically

The build step (`npm run build:gh-pages`) bundles all CSV data into `dist/database/` so the static site is fully self-contained.

### Local Development

For full functionality (AI analysis, data updates, file editing), run locally:

```bash
pipenv install
cd app/frontend && npm install && npm run build && cd ../..
pipenv run python -m app.main
```

## ⚙️ Automation with GitHub Actions

This repository includes a [GitHub Actions](https://github.com/features/actions) workflow (`.github/workflows/filings-fetch.yml`) designed to keep your data effortlessly up-to-date by automatically fetching the latest SEC filings.

### How It Works

- **Scheduled Runs**: The workflow runs automatically to check for **new 13F, 13D/G, and Form 4 filings** from the funds you are tracking (`hedge_funds.csv`). It runs four times a day from Monday to Friday (at 01:30, 13:30, 17:30, and 21:30 UTC) and once on Saturday (at 04:00 UTC).
- **Safe Branching Strategy**: Instead of committing directly to your main branch, the workflow pushes all new data to a dedicated branch named `automated/filings-fetch`.
- **GitHub Pages Deploy**: A separate workflow (`.github/workflows/deploy-pages.yml`) automatically rebuilds and deploys the static frontend to GitHub Pages whenever frontend or database files change on `master`.
- **User-Controlled Merging**: This approach gives you full control. You can review the changes committed by the bot and then merge them into your main branch whenever you're ready. This prevents unexpected changes and allows you to manage updates at your own pace.
- **Automated Alerts**: If the script encounters a non-quarterly filing where it cannot identify the fund owner based on your `hedge_funds.csv` configuration, it will automatically open a GitHub Issue in your repository, alerting you to a potential data mismatch that needs investigation.

### How to Enable It

1. **Fork the Repository**: Create your own [fork of this project](https://github.com/dokson/hedge-fund-tracker/fork) on GitHub.
2. **Enable Actions**: GitHub Actions are typically enabled by default on forked repositories. You can verify this under the _Actions_ tab of your fork.
3. **Configure Secrets**: For the workflow to resolve tickers and create issues, you need to add your API keys as repository secrets. In your forked repository, you must add your `FINNHUB_API_KEY` as a repository secret. Go to `Settings` > `Secrets and variables` > `Actions` in your forked repository to add it.

## 🗃️ Technical Stack

| 🗂️ Category | 🦾 Technology |
| :--- | :--- |
| **Core** | [Python 3.13](https://www.python.org/downloads/release/python-3130/)+, [pipenv](https://pipenv.pypa.io/) |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/), [uvicorn](https://www.uvicorn.org/) |
| **Frontend** | [React 18](https://react.dev/), [Vite](https://vitejs.dev/), [TypeScript](https://www.typescriptlang.org/), [Tailwind CSS](https://tailwindcss.com/) |
| **UI Components** | [shadcn/ui](https://ui.shadcn.com/), [Radix UI](https://www.radix-ui.com/), [Lucide](https://lucide.dev/), [Sonner](https://sonner.emilkowal.ski/) |
| **Data Viz & State** | [Recharts](https://recharts.github.io/), [TanStack Query v5](https://tanstack.com/query/latest) |
| **Web Scraping** | [Requests](https://2.python-requests.org/en/master/), [Beautiful Soup 4](https://pypi.org/project/beautifulsoup4/), [lxml](https://lxml.de/) |
| **Reliability** | [Tenacity](https://github.com/jd/tenacity), [Python-Dotenv](https://github.com/theskumar/python-dotenv) |
| **Stocks Data** | [yfinance](https://github.com/ranaroussi/yfinance), [Finnhub-Stock-API](https://github.com/Finnhub-Stock-API/finnhub-python), [FinanceDatabase](https://github.com/JerBouma/FinanceDatabase/) |
| **Gen AI** | [python-toon](https://github.com/xaviviro/python-toon), [Google AI SDK](https://googleapis.github.io/python-genai/), [OpenAI SDK](https://github.com/openai/openai-python) |

## 🤝🏼 Contributing & Support

### 💬 Loved it? Help it grow

- **🐛 [Bug Reports](https://github.com/dokson/hedge-fund-tracker/issues/new?template=bug_report.md)**
- **🆕 [Feature Requests](https://github.com/dokson/hedge-fund-tracker/issues/new?template=feature_request.md)**
- **🔀 [Fork & PR](https://github.com/dokson/hedge-fund-tracker/fork)**
- **🔁 [Share on X](https://x.com/intent/post?text=Have%20a%20look%20at%20https%3A%2F%2Fgithub.com%2Fdokson%2Fhedge-fund-tracker%2F%20by%20%40alecolace) or [LinkedIn](https://www.linkedin.com/sharing/share-offsite/?url=https://github.com/dokson/hedge-fund-tracker/)**

### ✍🏻 Feedback

This tool is in active development, and your input is valuable.
If you have any suggestions or ideas for new features, please feel free to [get in touch](https://github.com/dokson).

## 📚 References

- [SEC Developer Resources](https://www.sec.gov/about/developer-resources)
- [SEC: Frequently Asked Questions About Form 13F](https://www.sec.gov/rules-regulations/staff-guidance/division-investment-management-frequently-asked-questions/frequently-asked-questions-about-form-13f)
- [SEC: Guidance on Beneficial Ownership Reporting (Sections 13D/G)](https://www.sec.gov/rules-regulations/staff-guidance/compliance-disclosure-interpretations/exchange-act-sections-13d-13g-regulation-13d-g-beneficial-ownership-reporting)
- [Wikipedia: Global Industry Classification Standard](https://en.wikipedia.org/wiki/Global_Industry_Classification_Standard)
- [MSCI: Global Industry Classification Standard (GICS)](https://www.msci.com/indexes/index-resources/gics)
- [S&P Global: GICS Structure & Methodology](https://www.spglobal.com/spdji/en/documents/methodologies/methodology-gics.pdf)
- [CUSIP (Committee on Uniform Security Identification Procedures)](https://en.wikipedia.org/wiki/CUSIP)
- [Modern Portfolio Theory (MPT)](https://en.wikipedia.org/wiki/Modern_portfolio_theory)

## 🙏🏼 Acknowledgments

This project began as a fork of [sec-web-scraper-13f](https://github.com/CodeWritingCow/sec-web-scraper-13f) by [Gary Pang](https://github.com/CodeWritingCow). The original tool provided a solid foundation for scraping 13F filings from the [SEC](http://sec.gov/)'s [EDGAR](https://www.sec.gov/edgar/searchedgar/companysearch.html) database. It has since been significantly re-architected and expanded into a comprehensive analysis platform, incorporating multiple filing types, AI-driven insights, and automated data management.

## 📄 License

This project uses a **dual license**:

- **Original work** (Gary Pang's [sec-web-scraper-13f](https://github.com/CodeWritingCow/sec-web-scraper-13f)): MIT License.
- **All new work** (everything added by Alessandro Colace): Copyright © 2025 Alessandro Colace — All Rights Reserved. Personal and educational use is permitted; redistribution and commercial use require written permission.

See the [LICENSE](LICENSE) file for the full terms.
