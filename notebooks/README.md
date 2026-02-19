# EdgarTools Notebooks

Interactive Jupyter notebooks for working with SEC EDGAR filings in Python — free, no API key required.

Run any notebook instantly in your browser with Google Colab — no local setup needed.

---

## Start Here: Learning Path

**New to EdgarTools?** Follow this path in order:

| Step | Notebook | What You'll Learn |
|------|----------|-------------------|
| 1 | [First Steps](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/00_first_steps.ipynb) | Company lookup → financials → export to CSV (15 min) |
| 2 | [Getting Started](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/01_getting_started.ipynb) | Filing history, date filtering, company data |
| 3 | [Financial Statements](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/financial-statements-sec-python.ipynb) | Income statement, balance sheet, cash flow |
| 4 | [Search Filings](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/search-sec-filings-python.ipynb) | Find exactly the filings you need |
| 5+ | **Pick a topic below** | Based on your goals |

---

## Quick Setup

Every notebook starts with the same two lines:

```python
!pip install edgartools

from edgar import set_identity
set_identity("Your Name your@email.com")  # Required by SEC
```

---

## Difficulty Levels

| Icon | Level | Who It's For |
|------|-------|--------------|
| 🟢 | Beginner | Anyone — no Python experience needed |
| 🟡 | Intermediate | Comfortable with Python basics (`for` loops, variables, lists) |
| 🔴 | Advanced | Experienced Python users comfortable with pandas and financial data |

---

## Notebooks by Topic

### Getting Started 🟢

| Notebook | What You'll Learn |
|----------|-------------------|
| [First Steps](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/00_first_steps.ipynb) | Company lookup, get revenue, browse filings, export to CSV |
| [Getting Started](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/01_getting_started.ipynb) | Companies, filings, date filtering |
| [Troubleshooting SSL](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/02_troubleshooting_ssl.ipynb) | Fix SSL/certificate errors on corporate networks |
| [Beginner's Guide](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/Beginners-Guide.ipynb) | Complete introduction to EdgarTools |

---

### Financial Statements 🟡

| Notebook | What You'll Learn |
|----------|-------------------|
| [Financial Statements](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/financial-statements-sec-python.ipynb) | Income statement, balance sheet, cash flow from 10-K |
| [Viewing Financial Statements](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/Viewing-Financial-Statements.ipynb) | Deep dive into `get_financials()` |
| [Extract Revenue & Earnings](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/extract-revenue-earnings-python.ipynb) | Pull specific metrics (revenue, EPS, margins) |
| [Compare Company Financials](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/compare-company-financials-python.ipynb) | Side-by-side multi-company analysis |
| [Statements to DataFrame](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/financial-statements-to-dataframe.ipynb) | Export to pandas, CSV, or Excel |
| [10-Q Quarterly Earnings](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/10q-quarterly-earnings-python.ipynb) | Quarterly (10-Q) financial reports |

---

### Company Research 🟡

| Notebook | What You'll Learn |
|----------|-------------------|
| [SEC EDGAR API Overview](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/sec-edgar-api-python.ipynb) | Comprehensive library overview |
| [Company Data](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/sec-company-data-python.ipynb) | Company metadata, CIK lookup, filing history |
| [Ticker Search](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/Ticker-Search-with-edgartools.ipynb) | Find companies by ticker, name, or keyword |
| [Industry & SIC Codes](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/sec-industry-sic-code-python.ipynb) | Filter companies by SIC industry code |
| [Filter by Industry](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/Filtering-by-industry.ipynb) | Screen companies by industry and exchange |

---

### Working with Filings 🟡

| Notebook | What You'll Learn |
|----------|-------------------|
| [Search & Filter Filings](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/search-sec-filings-python.ipynb) | Find filings by form type, date, company |
| [Today's Filings](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/sec-filings-today-python.ipynb) | Monitor what was filed today |
| [Analyze 10-K Reports](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/analyze-10k-annual-report-python.ipynb) | Business description, risk factors, MD&A |
| [Download 10-K Reports](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/download-10k-annual-report-python.ipynb) | Download and parse 10-K documents |
| [10-K Business Description](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/10k-business-description-python.ipynb) | Extract business overview text from 10-Ks |
| [8-K Earnings Releases](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/8k-earnings-release-python.ipynb) | Current event (8-K) reports |
| [Extract Earnings Releases](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/Extract-Earnings-Releases.ipynb) | Parse press releases and tables from 8-Ks |
| [Filing Exhibits](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/sec-filing-exhibits-python.ipynb) | Access filing attachments and exhibits |
| [Filing Text & NLP](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/sec-filing-text-nlp-python.ipynb) | Extract text for NLP and sentiment analysis |
| [Filing Attachments](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/Beginners-filings-attachments.ipynb) | Work with filing attachments (beginner) |
| [Paging Through Filings](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/Paging-Through-Filings.ipynb) | Navigate large filing collections |
| [Bulk Download](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/download-sec-filings-bulk-python.ipynb) | Download many filings at once |
| [Monitor Filings](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/monitor-sec-filings-python.ipynb) | Watch for new filings from specific companies |
| [SEC Comment Letters](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/sec-comment-letters-python.ipynb) | SEC review letters and company responses |

---

### Insider Trading & Ownership 🟡

| Notebook | What You'll Learn |
|----------|-------------------|
| [Insider Trading (Form 4)](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/insider-trading-sec-form4-python.ipynb) | Track insider buys, sells, and option exercises |
| [Initial Insider Transactions](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/Initial-Insider-Transactions.ipynb) | Initial ownership reports (Form 3) |
| [13F Institutional Holdings](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/13f-institutional-holdings-python.ipynb) | Analyze hedge fund portfolios |
| [Beneficial Ownership](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/beneficial-ownership-sec-python.ipynb) | Schedule 13D/G activist positions |
| [Executive Compensation](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/executive-compensation-sec-python.ipynb) | CEO and executive pay from proxy statements |
| [Proxy Statements (DEF 14A)](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/proxy-statement-def14a-python.ipynb) | Board members, votes, shareholder proposals |

---

### Investment Funds 🟡

| Notebook | What You'll Learn |
|----------|-------------------|
| [ETF & Fund Holdings](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/etf-fund-holdings-python.ipynb) | ETF portfolio holdings |
| [Mutual Fund Holdings (N-PORT)](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/mutual-fund-holdings-nport-python.ipynb) | Mutual fund portfolios from N-PORT filings |
| [Money Market Funds (N-MFP)](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/money-market-fund-nmfp-python.ipynb) | Money market fund data |
| [Fund Census (N-CEN)](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/fund-census-ncen-python.ipynb) | Fund registration and census data |
| [BDCs](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/bdc-business-development-company-python.ipynb) | Business Development Companies |
| [Fund Filings](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/Fund-Filings.ipynb) | Overview of all fund filing types |
| [Fund Derivatives](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/Fund-Derivatives.ipynb) | Derivatives in fund portfolios |

---

### XBRL & Raw Data 🔴 Advanced

For developers who need direct access to XBRL facts and concepts.

> **Tip:** Most users should start with `get_financials()` (🟡 notebooks above). These notebooks are for advanced use cases where you need raw fact-level access.

| Notebook | What You'll Learn |
|----------|-------------------|
| [XBRL Financial Data](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/xbrl-financial-data-python.ipynb) | Low-level XBRL data access |
| [Reading Data from XBRL](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/Reading-Data-From-XBRL.ipynb) | Read raw facts from XBRL instance documents |
| [XBRL Concepts](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/XBRLConcepts.ipynb) | Understand XBRL taxonomy concepts |
| [Standardized Statements](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/XBRL2-StandardizedStatements.ipynb) | Cross-company standardized financials |
| [Quarterly XBRL Statements](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/XBRL2-QuarterlyStatements.ipynb) | Quarterly statements via XBRL |
| [Stitching Statements](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/XBRL2-StitchingStatements.ipynb) | Combine multiple filings for time-series analysis |
| [XBRL Fact Queries](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/XBRL2-FactQueries.ipynb) | Query individual XBRL facts with filters |
| [Period Views](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/XBRL2-PeriodViews.ipynb) | Control which time periods are shown |
| [Cash Flow Statements](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/XBRL2-Cashflow-Statements.ipynb) | Cash flow extraction and analysis |
| [Custom XBRL Tags](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/XBRL2-CustomTags.ipynb) | Handle company-specific XBRL tags |
| [Non-Financial Statements](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/XBRL2-NonFinancialStatements.ipynb) | Non-financial XBRL disclosures and segments |
| [Instance-Only XBRL](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/XBRL2-Instance-Only-XBRL.ipynb) | Parse instance-only XBRL documents |

---

## Running on Google Colab

Click any link in the tables above, or:
1. Go to [colab.research.google.com](https://colab.research.google.com/)
2. **File → Open notebook → GitHub tab**
3. Enter `dgunning/edgartools` and select a notebook

## Running Locally

```bash
pip install edgartools
jupyter lab notebooks/00_first_steps.ipynb
```

---

## More Resources

- [Documentation](https://edgartools.readthedocs.io)
- [Quick Start Guide](https://edgartools.readthedocs.io/en/latest/quickstart/)
- [Common Pitfalls](https://edgartools.readthedocs.io/en/latest/common-pitfalls/)
- [GitHub](https://github.com/dgunning/edgartools)
- [PyPI](https://pypi.org/project/edgartools/)
