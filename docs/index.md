
# EdgarTools

**Powerful Python library for SEC data analysis and financial research**

EdgarTools makes it simple to access, analyze, and extract insights from SEC filings. Whether you're analyzing company financials, tracking insider trading, or researching investment funds, edgartools provides the tools you need.

---

## What You Can Do

**Analyze Company Financials**

Extract financial statements, calculate ratios, and track performance over time.

```python
company = Company("AAPL")
financials = company.get_financials()
income_statement = financials.income_statement()
```

**Track Insider Trading**

Monitor insider transactions from Forms 3, 4, and 5 with structured data objects.

```python
filings = company.get_filings(form="4").head(10)
transactions = pd.concat([f.obj()
                         .to_dataframe()
                         .fillna('')
                for f in filings])
```

**Research Investment Funds**

Analyze 13F holdings, track portfolio changes, and compare fund strategies.

```python
fund = Company("BRK-A")
holdings = fund.get_filings(form="13F-HR").latest().obj()
```

**Extract Filing Data**

Access any SEC filing since 1994 with clean, structured data extraction.

```python
filing = company.get_filings(form="10-K").latest()
text = filing.text()  # Clean, readable text
```

## Key Features

### 🚀 **Easy to Use**
- Simple, intuitive API designed for both beginners and experts
- Comprehensive documentation with real-world examples
- Smart defaults that handle edge cases automatically

### 📊 **Complete SEC Data Access**
- **All filing types**: 10-K, 10-Q, 8-K, 13F, Form 4, S-1, and more
- **Historical data**: Access filings back to 1994
- **Real-time data**: Get the latest filings as they're published

### 🔍 **Advanced XBRL Support**
- Extract structured financial data from XBRL filings
- Query individual financial line items with standardized concepts
- Handle complex financial statement hierarchies automatically

### ⚡ **Performance Optimized**
- Efficient data handling for large datasets
- Local caching to minimize API calls
- Batch processing capabilities for bulk analysis

### 🛠 **Developer Friendly**
- Type hints and comprehensive error handling
- Jupyter notebook integration with rich display
- Pandas DataFrames for seamless data analysis

## Installation

Install edgartools with pip:

```bash
pip install edgartools
```

Or use uv for faster installation:

```bash
uv pip install edgartools
```

## Get Started in 2 Minutes

1. **Install and set your identity** (required by SEC):
```python
from edgar import *
set_identity("your.name@email.com")
```

2. **Find a company and get their latest financial data**:

```python
company = Company("TSLA")
latest_10k = company.get_filings(form="10-K").latest()
financials = latest_10k.obj().financials()
```

## Popular Use Cases

### Financial Analysis
- Compare companies across industries
- Track financial performance over time
- Calculate and analyze financial ratios
- Build custom financial dashboards

### Investment Research
- Analyze fund holdings and strategy changes
- Track insider buying and selling activity
- Monitor material events through 8-K filings
- Research IPOs and new offerings

### Academic Research
- Large-scale financial data analysis
- Corporate governance studies
- Market efficiency research
- Regulatory compliance analysis

### AI/ML Applications
- Extract clean text for natural language processing
- Build predictive models with financial data
- Automate document analysis workflows
- Create training datasets for financial AI
- **Advanced ranking search** with BM25 and semantic structure awareness

## Why Choose EdgarTools?

| Feature | EdgarTools | Alternative Solutions |
|---------|------------|----------------------|
| **Ease of Use** | ✅ Simple, Pythonic API | ❌ Complex setup required |
| **Data Quality** | ✅ Clean, standardized data | ⚠️ Raw data needs processing |
| **Performance** | ✅ Optimized for large datasets | ❌ Slow for bulk operations |
| **Documentation** | ✅ Comprehensive with examples | ⚠️ Limited examples |
| **Active Development** | ✅ Regular updates and features | ❌ Infrequent updates |
| **Community** | ✅ Growing user base | ⚠️ Limited community |

## Community & Support

- **📖 Documentation**: Comprehensive guides and API reference
- **💬 GitHub Discussions**: Ask questions and share insights
- **🐛 Issue Tracker**: Report bugs and request features
- **📧 Email Support**: Direct support for enterprise users

### Support the Project

If you find EdgarTools useful, please consider supporting its development:

<a href="https://www.buymeacoffee.com/edgartools" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;width: 144px !important;" >
</a>

Your support helps maintain and improve EdgarTools for the entire community!

## What's Next?

**[Quick Start](quickstart.md)** - Your first analysis in 5 minutes

**[Financial Data](guides/financial-data.md)** - Get income statements, balance sheets, cash flow

**[Filing Types](data-objects.md)** - Work with 10-K, 8-K, 13F, and more

**[API Reference](api/company.md)** - Complete documentation

**[Examples](examples.md)** - Real-world code patterns

---

**Ready to start analyzing SEC data?** [Install EdgarTools](installation.md) and begin your first analysis today.