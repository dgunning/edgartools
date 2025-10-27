<p align="center">
<a href="https://github.com/dgunning/edgartools">
    <img src="docs/images/edgartools-logo.png" alt="EdgarTools Python SEC EDGAR library logo" height="80">
</a>
</p>

<h3 align="center">Python Library for SEC EDGAR Data Extraction and Analysis</h3>

<p align="center">
  <a href="https://pypi.org/project/edgartools"><img src="https://img.shields.io/pypi/v/edgartools.svg" alt="PyPI - Version"></a>
  <a href="https://github.com/dgunning/edgartools/actions"><img src="https://img.shields.io/github/actions/workflow/status/dgunning/edgartools/python-hatch-workflow.yml" alt="GitHub Workflow Status"></a>
  <a href="https://www.codefactor.io/repository/github/dgunning/edgartools"><img src="https://www.codefactor.io/repository/github/dgunning/edgartools/badge" alt="CodeFactor"></a>
  <a href="https://github.com/pypa/hatch"><img src="https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg" alt="Hatch project"></a>
  <a href="https://github.com/dgunning/edgartools/blob/main/LICENSE"><img src="https://img.shields.io/github/license/dgunning/edgartools" alt="GitHub"></a>
  <a href="https://pypi.org/project/edgartools"><img src="https://img.shields.io/pypi/dm/edgartools" alt="PyPI - Downloads"></a>
</p>

<p align="center">
  <b>Extract financial data from SEC EDGAR filings in 3 lines of Python code instead of 100+. Access company financials, insider trades, fund holdings, and XBRL data with an intuitive API designed for financial analysis.</b>
</p>

![EdgarTools SEC filing data extraction demo](docs/images/edgartools-demo.gif)

## SEC Filing Data Extraction with Python

| With EdgarTools                               | Without EdgarTools                          |
|-----------------------------------------------|---------------------------------------------|
| ✅ Instant access to any filing since 1994     | ❌ Hours spent navigating SEC.gov            |
| ✅ Clean Python API with intuitive methods     | ❌ Complex web scraping code                 |
| ✅ Automatic parsing into pandas DataFrames    | ❌ Manual extraction of financial data       |
| ✅ Specialized data objects for each form type | ❌ Custom code for each filing type          |
| ✅ One-line conversion to clean, readable text | ❌ Messy HTML parsing for text extraction    |
| ✅ LLM-ready text extraction for AI pipelines  | ❌ Extra processing for AI/LLM compatibility |
| ✅ Automatic throttling to avoid blocks        | ❌ Rate limiting headaches                   |

## Apple's income statement in 1 line of code

```python
balance_sheet = Company("AAPL").get_financials().balance_sheet()         
```

## 🚀 Quick Start (2-minute tutorial)

```python
# 1. Import the library
from edgar import *

# 2. Tell the SEC who you are (required by SEC regulations)
set_identity("your.name@example.com")  # Replace with your email

# 3. Find a company
company = Company("MSFT")  # Microsoft

# 4. Get company filings
filings = company.get_filings() 

# 5. Filter by form 
insider_filings = filings.filter(form="4")  # Insider transactions

# 6. Get the latest filing
insider_filing = insider_filings[0]

# 7. Convert to a data object
ownership = insider_filing.obj()
```

![Apple SEC Form 4 insider transaction data extraction with Python](docs/images/aapl-insider.png)


## SEC Filing Analysis: Real-World Solutions

### Company Financial Analysis

**Problem:** Need to analyze a company's financial health across multiple periods.

![Microsoft SEC 10-K financial data analysis with EdgarTools](docs/images/MSFT_financial_complex.png)

[See full code](docs/examples.md#company_financial_analysis)



## 📚 Documentation


- [User Journeys / Examples](https://edgartools.readthedocs.io/en/latest/examples/)
- [Quick Guide](https://edgartools.readthedocs.io/en/latest/quick-guide/)
- [Full API Documentation](https://edgartools.readthedocs.io/)
- [EdgarTools Blog](https://www.edgartools.io)

## 👥 Community & Support

- [GitHub Issues](https://github.com/dgunning/edgartools/issues) - Bug reports and feature requests
- [Discussions](https://github.com/dgunning/edgartools/discussions) - Questions and community discussions

## 🔮 Roadmap

- **Coming Soon**: Enhanced visualization tools for financial data
- **In Development**: Machine learning integrations for financial sentiment analysis
- **Planned**: Interactive dashboard for filing exploration

## 🤝 Contributing

We welcome contributions from the community! Here's how you can help:

- **Code**: Fix bugs, add features, improve documentation
- **Examples**: Share interesting use cases and examples
- **Feedback**: Report issues or suggest improvements
- **Spread the Word**: Star the repo, share with colleagues

See our [Contributing Guide](CONTRIBUTING.md) for details.

## ❤️ Sponsors & Support

If you find EdgarTools valuable, please consider supporting its development:

<a href="https://www.buymeacoffee.com/edgartools" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;width: 144px !important;" >
</a>

Your support helps maintain and improve EdgarTools for the entire community!

## Key Features for SEC Data Extraction and Analysis

- **Comprehensive Filing Access**: Retrieve **any** SEC filing (10-K, 10-Q, 8-K, 13F, S-1, Form 4, etc.) since 1994.
- **Financial Statement Extraction**: Easily access **Balance Sheets, Income Statements, Cash Flows**, and individual line items using XBRL tags or common names.
- **SEC EDGAR API**: Programmatic access to the complete SEC database.
- **Smart Data Objects**: Automatic parsing of filings into structured Python objects.
- **Fund Holdings Analysis**: Extract and analyze **13F holdings** data for investment managers.
- **Insider Transaction Monitoring**: Get structured data from **Form 3, 4, 5** filings.
- **Clean Text Extraction**: One-line conversion from filing HTML to clean, readable text suitable for NLP.
- **Targeted Section Extraction**: Pull specific sections like **Risk Factors (Item 1A)** or **MD&A (Item 7)**.
- **AI/LLM Ready**: Text formatting and chunking optimized for AI pipelines.
- **Performance Optimized**: Leverages libraries like `lxml` and potentially `PyArrow` for efficient data handling.
- **XBRL Support**: Extract and analyze XBRL-tagged data.
- **Intuitive API**: Simple, consistent interface for all data types.

## 🤖 AI-Native Integration

EdgarTools is designed from the ground up to work seamlessly with AI agents and LLM applications:

### Interactive Documentation

Every major object includes rich, searchable documentation accessible via the `.docs` property:

```python
from edgar import Company

company = Company("AAPL")

# Beautiful rich display with full API documentation
company.docs

# Search documentation with BM25 ranking
company.docs.search("get financials")

# AI-optimized text output for LLM context
context = company.text(detail='standard', max_tokens=500)
```

**3,450+ lines of API documentation** covering Company, Filing, XBRL, and Statement objects - always at your fingertips!

### AI Skills System

Extensible skill packages for specialized SEC analysis:

```python
from edgar.ai import list_skills, export_skill

# List available skills
skills = list_skills()

# Export to Claude Desktop format
export_skill("sec-analysis", format="claude-desktop")
```

Skills include:
- **Tutorial documentation** (skill.md, workflows.md, objects.md)
- **API reference** (complete method documentation)
- **Helper functions** (pre-built analysis workflows)

### Model Context Protocol (MCP) Server

Run EdgarTools as an MCP server for Claude Desktop and other MCP clients:

```bash
pip install edgartools[ai]
python -m edgar.ai
```

Configure in Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "edgartools": {
      "command": "python",
      "args": ["-m", "edgar.ai"],
      "env": {
        "EDGAR_IDENTITY": "Your Name your.email@example.com"
      }
    }
  }
}
```

Then ask Claude:
- *"Research Apple Inc with financials"*
- *"Analyze Tesla's revenue trends over the last 4 quarters"*
- *"Compare Microsoft and Google's cash positions"*

### Why AI-Native Matters

- **Zero Friction**: `.docs` property provides instant learning without leaving your REPL
- **Token Efficient**: `.text()` methods use research-backed markdown-kv format
- **Progressive Disclosure**: Three detail levels (minimal/standard/detailed) for different contexts
- **Searchable**: BM25 semantic search finds relevant information instantly
- **Extensible**: BaseSkill class enables third-party skill packages

See [AI Integration Guide](docs/ai-integration.md) for complete documentation *(coming soon)*.

---

EdgarTools is distributed under the [MIT License](LICENSE).

## 📊 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=dgunning/edgartools&type=Timeline)](https://star-history.com/#dgunning/edgartools&Timeline)