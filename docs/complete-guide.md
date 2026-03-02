---
title: The Complete Guide to SEC Filings in Python (2026)
description: The definitive guide to working with SEC EDGAR filings in Python. Free, no API key required. Financial statements, insider trading, 13F holdings, XBRL, and more.
---

# The Complete Guide to SEC Filings in Python

*Last updated: February 2026*

Every public company in the United States is required to file financial reports with the Securities and Exchange Commission (SEC). These filings — annual reports (10-K), quarterly reports (10-Q), current event reports (8-K), insider trading disclosures (Form 4), institutional holdings (13F), and dozens more — are all publicly available through the SEC's EDGAR database.

EDGAR contains over 20 million filings going back to 1994. It's the single richest source of corporate financial data in the world, and it's completely free.

EdgarTools is a Python library that turns EDGAR's raw data into structured Python objects you can analyze immediately. No API key, no paid subscription, no rate-limited trial. Just `pip install edgartools` and you have access to financial statements, insider trades, institutional holdings, fund portfolios, proxy statements, and more — all as native Python objects with built-in analysis methods.

```python
from edgar import Company

income = Company("AAPL").get_filings(form="10-K")[0].obj().financials.income_statement()
print(income)
```

That's a complete Apple income statement in three lines. This guide shows you everything else you can do.

---

## Table of Contents

- [Installation](#installation)
- [Finding Companies](#finding-companies)
- [Working with Filings](#working-with-filings)
- [Financial Statements](#financial-statements)
- [Company Facts](#company-facts)
- [Insider Trading](#insider-trading)
- [Institutional Holdings (13F)](#institutional-holdings-13f)
- [Investment Funds](#investment-funds)
- [Current Filings](#current-filings)
- [AI and MCP Integration](#ai-and-mcp-integration)
- [EdgarTools vs Alternatives](#edgartools-vs-alternatives)
- [Resources](#resources)

---

## Installation

```bash
pip install edgartools
```

The SEC requires all API users to identify themselves. Set your identity once per session:

```python
from edgar import set_identity
set_identity("Your Name your.email@example.com")
```

You can also set the `EDGAR_IDENTITY` environment variable so you don't need to call this in every script.

!!! tip "Wrong package?"
    If you see `ImportError: cannot import name 'get_filings' from 'edgar'`, you may have the wrong `edgar` package installed:
    ```bash
    pip uninstall edgar && pip install edgartools
    ```

[:material-notebook: Open in Colab](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/01_getting_started.ipynb){ .md-button }

---

## Finding Companies

Look up any public company by ticker symbol, CIK number, or name:

```python
from edgar import Company

apple = Company("AAPL")        # By ticker
microsoft = Company("MSFT")    # Another ticker
berkshire = Company(1067983)    # By CIK number
```

The `Company` object gives you access to metadata, filings, financials, and facts — all from a single entry point:

```python
company = Company("AAPL")
company.name                # 'APPLE INC'
company.cik                 # 320193
company.sic_code            # '3571'
company.sic_description     # 'Electronic Computers'
company.shares_outstanding  # 15115785000.0
company.public_float        # 2899948348000.0
```

From a `Company` object you can get filings, financials, facts, and more — it's the starting point for most analysis workflows in edgartools.

[:material-notebook: Open in Colab](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/sec-company-data-python.ipynb){ .md-button }

---

## Working with Filings

### Get a Company's Filings

Every company's full filing history is available:

```python
filings = Company("MSFT").get_filings()          # All filings
tenks = Company("MSFT").get_filings(form="10-K")  # Just 10-Ks
```

### Filter and Search

Narrow results by date, form type, or other criteria:

```python
filings = Company("TSLA").get_filings(form="10-K")
recent = filings.head(5)            # Most recent 5
filing = filings[0]                 # Latest filing
```

### Open and Read Filings

Once you have a filing, you can open it in your browser, extract clean text for NLP, or convert it to markdown:

```python
filing = Company("AAPL").get_filings(form="10-K")[0]

filing.open()        # Open in your browser
text = filing.text() # Get clean text content
md = filing.markdown() # Get markdown version
html = filing.html()   # Get raw HTML
```

The `text()` method strips all HTML formatting and returns clean, readable text — useful for NLP pipelines, RAG systems, and text analysis.

### Typed Data Objects

The real power of edgartools is `filing.obj()` — it converts raw filings into structured Python objects with properties, methods, and DataFrames:

```python
tenk = filing.obj()  # Returns a TenK object

# Access sections
tenk.business_description
tenk.risk_factors
tenk.mda  # Management Discussion & Analysis

# Access financials
tenk.financials.income_statement()
tenk.financials.balance_sheet()
tenk.financials.cash_flow_statement()

# Auditor and corporate structure
tenk.auditor                               # AuditorInfo (name, PCAOB ID, location)
tenk.subsidiaries                          # SubsidiaryList from Exhibit 21

# XBRL report pages (statements, notes, details)
tenk.reports                               # Reports from FilingSummary.xml
```

EdgarTools provides typed data objects for 17+ filing types including 10-K, 10-Q, 8-K, 13F, Form 4, DEF 14A, N-PORT, N-MFP, Form D, Form C, and more. See the full list in the [Filing Types](data-objects.md) documentation.

[:material-notebook: Open in Colab](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/download-10k-annual-report-python.ipynb){ .md-button }

---

## Financial Statements

### From a Single Filing

Extract income statements, balance sheets, and cash flow statements from any 10-K or 10-Q:

```python
from edgar import Company

tenk = Company("AAPL").get_filings(form="10-K")[0].obj()

income = tenk.financials.income_statement()
balance = tenk.financials.balance_sheet()
cashflow = tenk.financials.cash_flow_statement()
```

### Convert to DataFrames

Every statement converts to a pandas DataFrame for analysis:

```python
df = income.to_dataframe()
```

### Multi-Period Analysis

Get financial data across multiple years using the XBRL stitching API:

```python
from edgar import Company

company = Company("MSFT")
financials = company.get_financials()

# Multi-year income statement
income = financials.income_statement()

# Multi-year balance sheet
balance = financials.balance_sheet()
```

[:material-notebook: Open in Colab](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/financial-statements-sec-python.ipynb){ .md-button }
&nbsp;
[:material-notebook: Multi-Period Analysis](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/XBRL2-StitchingStatements.ipynb){ .md-button }

---

## Company Facts

Track individual financial metrics across a company's entire filing history using the SEC's XBRL facts database:

```python
from edgar import Company

facts = Company("GOOG").get_facts()

# Get specific metrics
facts.get_revenue()              # Latest annual revenue
facts.get_net_income()           # Latest net income
facts.get_total_assets()         # Latest total assets
facts.get_shareholders_equity()  # Latest equity
```

Query any XBRL concept:

```python
# Get a specific concept's value
facts.get_concept("AccountsPayableCurrent")

# Time series for any metric
facts.time_series("Revenues")
```

[:material-notebook: Open in Colab](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/extract-revenue-earnings-python.ipynb){ .md-button }

---

## Insider Trading

Track insider buying and selling through SEC Form 4 filings:

```python
from edgar import Company

form4s = Company("TSLA").get_filings(form="4").head(5)
for f in form4s:
    ownership = f.obj()
    print(ownership)
```

Each Form 4 filing is parsed into an `Ownership` object with structured transaction details — who traded, how many shares, at what price, and whether it was a buy or sell.

Convert transactions to a DataFrame for analysis across multiple filings:

```python
import pandas as pd

form4s = Company("NVDA").get_filings(form="4").head(20)
transactions = pd.concat([f.obj().to_dataframe().fillna('') for f in form4s])
```

This gives you a single DataFrame of all insider transactions, ready for filtering by insider name, transaction type, or date range.

[:material-notebook: Open in Colab](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/insider-trading-sec-form4-python.ipynb){ .md-button }

---

## Institutional Holdings (13F)

See what hedge funds and institutional investors are holding. Every institutional manager with $100M+ in assets must file quarterly 13F reports:

```python
from edgar import Company

# Citadel Advisors' latest 13F
thirteenf = Company(1423053).get_filings(form="13F-HR")[0].obj()
print(thirteenf.holdings)  # Full portfolio as DataFrame
```

Compare holdings quarter-over-quarter:

```python
thirteenf.compare_holdings()     # NEW, CLOSED, INCREASED, DECREASED
thirteenf.holding_history(periods=4)  # Multi-quarter trends
```

[:material-notebook: Open in Colab](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/13f-institutional-holdings-python.ipynb){ .md-button }

---

## Investment Funds

### Mutual Fund & ETF Holdings (N-PORT)

Analyze complete portfolio holdings from monthly N-PORT filings:

```python
from edgar import Company

fund = Company("VANGUARD INDEX FUNDS")
nport = fund.get_filings(form="NPORT-P")[0].obj()
nport.investments  # Full holdings
```

### Money Market Funds (N-MFP)

```python
mmf = fund.get_filings(form="N-MFP2")[0].obj()
```

### Executive Compensation and Proxy Statements

Parse DEF 14A proxy statements for executive pay, board composition, and shareholder proposals:

```python
proxy = Company("AAPL").get_filings(form="DEF 14A")[0].obj()
proxy.peo_name                # CEO name
proxy.peo_total_comp          # CEO total compensation
proxy.executive_compensation  # Multi-year compensation DataFrame
```

[:material-notebook: Executive Compensation](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/executive-compensation-sec-python.ipynb){ .md-button }

### Business Development Companies

Analyze BDC portfolio investments and lending activity:

```python
bdc = Company("ARCC").get_filings(form="10-K")[0].obj()
```

[:material-notebook: N-PORT](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/mutual-fund-holdings-nport-python.ipynb){ .md-button }
&nbsp;
[:material-notebook: N-MFP](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/money-market-fund-nmfp-python.ipynb){ .md-button }
&nbsp;
[:material-notebook: BDC](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/bdc-business-development-company-python.ipynb){ .md-button }

---

## Current Filings

Monitor SEC filings as they're published. The SEC updates its filing index throughout the day, and edgartools gives you access to the latest submissions:

```python
from edgar import get_current_filings

filings = get_current_filings()               # Everything filed today
eightks = filings.filter(form="8-K")          # Just current events
tenks = filings.filter(form="10-K")           # Just annual reports
```

This is useful for building filing alert systems, monitoring specific companies for new submissions, or tracking daily filing activity across the market.

[:material-notebook: Open in Colab](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/sec-filings-today-python.ipynb){ .md-button }

---

## AI and MCP Integration

EdgarTools includes a built-in MCP (Model Context Protocol) server, enabling AI assistants like Claude to query SEC data directly through natural language:

```bash
# Run the MCP server
edgartools-mcp

# Or with uvx (no install needed)
uvx edgartools-mcp
```

Once connected, you can ask an AI assistant questions like "What was Apple's revenue last year?" or "Show me Elon Musk's recent stock sales" and it will use edgartools to fetch and analyze the data.

The MCP server exposes tools for company research, filing search, financial analysis, ownership tracking, and multi-company comparison — giving AI agents structured access to the full SEC EDGAR database.

This works with Claude Desktop, Claude Code, and any MCP-compatible AI client. See the [AI Integration Guide](ai-integration.md) for setup instructions.

---

## EdgarTools vs Alternatives

### EdgarTools vs sec-api.io

| Feature | EdgarTools | sec-api.io |
|---------|:---:|:---:|
| **Price** | Free | $49–$239/month |
| **API key required** | No | Yes |
| **Open source** | Yes (MIT) | No |
| **Lines of code for financials** | 3 | 15+ |
| **XBRL parsing** | Native Python objects | JSON |
| **Filing types with typed objects** | 17+ | Raw download |
| **Works offline (with cache)** | Yes | No |
| **AI/MCP integration** | Built-in | No |

### EdgarTools vs sec-edgar-downloader

`sec-edgar-downloader` downloads raw filing documents to disk. It's a downloader — you get HTML and XML files, then you're on your own for parsing. EdgarTools downloads *and* parses filings into structured Python objects with properties, methods, and DataFrames. If you need to analyze the data (not just store the files), edgartools does both.

### EdgarTools vs python-edgar

`python-edgar` provides basic access to the EDGAR full-text search and filing index. EdgarTools provides that plus XBRL parsing, typed data objects for 17+ filing types, financial statement extraction, rich terminal display, and Jupyter/Colab integration.

### When to Use What

- **Need structured financial analysis in Python?** Use EdgarTools — it's built for this.
- **Need a hosted API with real-time WebSocket streams?** sec-api.io offers infrastructure features a client library can't.
- **Just need to bulk download filing documents?** sec-edgar-downloader is a simple file downloader.
- **Need to work in a language other than Python?** sec-api.io offers REST endpoints for any language.

---

## Common Use Cases

### Financial Research and Modeling

Pull income statements, balance sheets, and cash flows across multiple years for any public company. Build financial models, calculate ratios, and compare companies — all without leaving Python.

```python
from edgar import Company

# Get multi-year financials for modeling
financials = Company("AMZN").get_financials()
income = financials.income_statement()
df = income.to_dataframe()  # Ready for pandas analysis
```

### NLP and Text Analysis

Extract clean text from filings for sentiment analysis, topic modeling, or training language models on financial documents:

```python
filing = Company("JPM").get_filings(form="10-K")[0]
text = filing.text()  # Clean text, no HTML
```

### Portfolio Monitoring

Track what institutional investors are buying and selling each quarter, monitor insider transactions for signal detection, and watch for material events through 8-K filings.

### Academic Research

EdgarTools is used in academic settings for corporate governance studies, market efficiency research, and large-scale financial data analysis. The structured data objects and DataFrame outputs integrate directly into scientific Python workflows (pandas, numpy, scikit-learn).

### Building RAG Systems

The `text()` and `markdown()` methods produce clean document representations suitable for chunking and embedding in retrieval-augmented generation (RAG) pipelines. Combined with the MCP server, edgartools can serve as a live data source for AI-powered financial research assistants and chatbots.

---

## Resources

### Documentation

- [Quick Start](quickstart.md) — Your first analysis in 5 minutes
- [Financial Data Guide](guides/financial-data.md) — Income statements, balance sheets, cash flow
- [Filing Types](data-objects.md) — All 17+ supported filing types
- [XBRL Deep Dive](xbrl/index.md) — Advanced structured financial data
- [API Reference](api/company.md) — Complete class documentation

### Interactive Notebooks

54 Colab-ready notebooks covering every feature — browse the full collection on the [Notebooks](notebooks.md) page.

### Community

- [GitHub](https://github.com/dgunning/edgartools) — Source code, issues, and discussions
- [PyPI](https://pypi.org/project/edgartools/) — Package releases
- [ReadTheDocs](https://edgartools.readthedocs.io/) — Full documentation

---

*EdgarTools is free and open source (MIT license). No API key, no subscription, no limits. Just `pip install edgartools` and start analyzing SEC data. Built and maintained by the open source community.*
