# EdgarTools Notebooks

Interactive Jupyter notebooks demonstrating EdgarTools functionality.

## How to Use

1. Install EdgarTools: `pip install edgartools`
2. Open any notebook in Jupyter Lab, VS Code, or Google Colab
3. Run cells to see examples in action

## Notebook Categories

### 📚 Beginner (`beginner/`)
Start here if you're new to EdgarTools or SEC filings:
- **Beginners-Guide.ipynb** - Complete introduction to EdgarTools
- **Beginners-filings-attachments.ipynb** - Working with filing attachments
- **Ticker-Search-with-edgartools.ipynb** - Finding companies by ticker

### 📁 Filings (`filings/`)
Working with SEC filings and filtering:
- **Paging-Through-Filings.ipynb** - Navigating large filing collections
- **Filtering-by-industry.ipynb** - Filter companies by industry/SIC code
- **Extract-Earnings-Releases.ipynb** - Extract earnings releases from 8-Ks

### 📊 XBRL Financial Data (`xbrl/`)
Comprehensive XBRL parsing and financial statement analysis:
- **Reading-Data-From-XBRL.ipynb** - Introduction to XBRL data extraction
- **Viewing-Financial-Statements.ipynb** - Display financial statements
- **XBRL2-** series - Deep dives into XBRL features (13 notebooks)
  - Cashflow, Income, Balance Sheet statements
  - Fact queries and custom tags
  - Financial ratios and fraud analysis
  - Period views and quarterly statements
  - Statement stitching across filings

### 💼 Investment Funds (`funds/`)
Working with fund filings (N-CSR, NPORT, etc.):
- **Fund-Filings.ipynb** - Overview of fund filing types
- **Fund-Derivatives.ipynb** - Analyzing fund derivative holdings
- **Funds.ipynb** - Fund company data access

### 👥 Insider Trading (`insiders/`)
Tracking insider transactions (Form 3, 4, 5):
- **Initial-Insider-Transactions.ipynb** - Parse and analyze insider trades

### 🔍 Other (`other/`)
Additional features and utilities:
- **ConceptSearch.ipynb** - Search for XBRL concepts

## Running on Google Colab

Click the "Open in Colab" badge (if present) or:
1. Go to https://colab.research.google.com/
2. File → Upload notebook
3. Select any `.ipynb` file from this directory

## Contributing

Found an issue or have an improvement? Open an issue or PR at:
https://github.com/dgunning/edgartools

## See Also

- **[../scripts/](../scripts/)** - Python scripts for quick reference
- **[../../docs/](../../docs/)** - Full documentation
- [EdgarTools Documentation](https://edgartools.readthedocs.io/)
