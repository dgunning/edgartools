# EdgarTools Notebooks

Interactive Jupyter notebooks for working with SEC EDGAR filings in Python -- free, no API key required.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/dgunning/edgartools/blob/main/notebooks/01_getting_started.ipynb)

## How to Use

1. Click any "Open in Colab" badge to run instantly in your browser
2. Or install locally: `pip install edgartools`
3. Open any notebook in Jupyter Lab, VS Code, or Google Colab

## Notebooks

### Getting Started
- **01_getting_started.ipynb** - Get started with SEC filings in Python
- **Beginners-Guide.ipynb** - Complete introduction to EdgarTools
- **Beginners-filings-attachments.ipynb** - Working with filing attachments
- **Ticker-Search-with-edgartools.ipynb** - Search SEC filings by ticker symbol
- **02_troubleshooting_ssl.ipynb** - Troubleshooting SSL connection issues

### Filings
- **sec-filings-today-python.ipynb** - Get today's SEC filings with Python
- **download-10k-annual-report-python.ipynb** - Download and parse 10-K annual reports
- **Paging-Through-Filings.ipynb** - Browse and navigate SEC filing collections
- **Filtering-by-industry.ipynb** - Filter SEC filings by industry/SIC code
- **Extract-Earnings-Releases.ipynb** - Extract 8-K earnings releases with Python

### Financial Statements (XBRL)
- **extract-revenue-earnings-python.ipynb** - Extract revenue and earnings from SEC filings
- **compare-company-financials-python.ipynb** - Compare company financials with Python
- **Viewing-Financial-Statements.ipynb** - Extract financial statements from SEC filings
- **Reading-Data-From-XBRL.ipynb** - Parse XBRL financial data from SEC EDGAR
- **XBRL2-Cashflow-Statements.ipynb** - Analyze cash flow statements
- **XBRL2-StandardizedStatements.ipynb** - Standardized financial statements
- **XBRL2-FactQueries.ipynb** - Query XBRL facts with the enhanced API
- **XBRL2-PeriodViews.ipynb** - Multi-period financial statement views
- **XBRL2-QuarterlyStatements.ipynb** - Quarterly financial statement analysis
- **XBRL2-StitchingStatements.ipynb** - Stitch statements across multiple filings
- **XBRL2-CustomTags.ipynb** - Handle custom company XBRL tags
- **XBRL2-NonFinancialStatements.ipynb** - Non-financial disclosures and segments
- **XBRL2-Instance-Only-XBRL.ipynb** - Parse instance-only XBRL documents
- **XBRLConcepts.ipynb** - Explore XBRL taxonomy concepts

### Institutional Holdings
- **13f-institutional-holdings-python.ipynb** - Analyze 13F institutional holdings with Python

### Investment Funds
- **Fund-Filings.ipynb** - Overview of fund filing types
- **Fund-Derivatives.ipynb** - Analyze fund derivative holdings

### Insider Trading
- **insider-trading-sec-form4-python.ipynb** - Track insider trading from SEC Form 4 with Python
- **Initial-Insider-Transactions.ipynb** - Deep analysis of initial insider ownership (Form 3)

## Running on Google Colab

Click the "Open in Colab" badge at the top of any notebook, or:
1. Go to https://colab.research.google.com/
2. File > Open notebook > GitHub tab
3. Enter `dgunning/edgartools` and select a notebook

## Resources

- [EdgarTools Documentation](https://edgartools.readthedocs.io/)
- [GitHub Repository](https://github.com/dgunning/edgartools)
- [PyPI Package](https://pypi.org/project/edgartools/)
