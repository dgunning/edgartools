<p align="center">
<a href="https://github.com/dgunning/edgartools">
    <img src="docs/images/edgartools-logo.png" alt="EdgarTools Python SEC EDGAR library logo" height="80">
</a>
</p>

<h3 align="center">The AI-Native Python Library for SEC EDGAR Data</h3>

<p align="center">
  <a href="https://pypi.org/project/edgartools"><img src="https://img.shields.io/pypi/v/edgartools.svg" alt="PyPI - Version"></a>
  <a href="https://github.com/dgunning/edgartools/actions"><img src="https://img.shields.io/github/actions/workflow/status/dgunning/edgartools/python-hatch-workflow.yml" alt="GitHub Workflow Status"></a>
  <a href="https://www.codefactor.io/repository/github/dgunning/edgartools"><img src="https://www.codefactor.io/repository/github/dgunning/edgartools/badge" alt="CodeFactor"></a>
  <a href="https://github.com/pypa/hatch"><img src="https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg" alt="Hatch project"></a>
  <a href="https://github.com/dgunning/edgartools/blob/main/LICENSE"><img src="https://img.shields.io/github/license/dgunning/edgartools" alt="GitHub"></a>
  <a href="https://pypi.org/project/edgartools"><img src="https://img.shields.io/pypi/dm/edgartools" alt="PyPI - Downloads"></a>
</p>

<p align="center">
  <img src="docs/images/badges/badge-ai-native.svg" alt="AI Native">
  <img src="docs/images/badges/badge-mcp-ready.svg" alt="MCP Ready">
  <img src="docs/images/badges/badge-10x-faster.svg" alt="10x Faster">
  <img src="docs/images/badges/badge-zero-cost.svg" alt="Zero Cost">
  <img src="docs/images/badges/badge-open-source.svg" alt="Open Source">
  <img src="docs/images/badges/badge-type-safe.svg" alt="Type Safe">
</p>

<p align="center">
  <b>The only SEC EDGAR library built from the ground up for AI agents and LLMs. Extract financial data in 3 lines of code instead of 100+. Production-ready MCP server included.</b>
</p>

![EdgarTools SEC filing data extraction demo](docs/images/edgartools-demo.gif)

<p align="center">
  <img src="docs/images/dividers/divider-hexagons.svg" alt="">
</p>

## Why EdgarTools?

EdgarTools is the **fastest, most powerful open-source library** for SEC EDGAR data extraction. Built for financial analysts, data scientists, and AI developers who need reliable, production-ready access to SEC filings.

<table align="center">
<tr>
  <td align="center" width="33%">
    <img src="docs/images/icons/icon-speed.svg" width="80" alt="Lightning Fast"><br>
    <b>Lightning Fast</b><br>
    10-30x faster than alternatives<br>
    Optimized with lxml & PyArrow
  </td>
  <td align="center" width="33%">
    <img src="docs/images/icons/icon-ai.svg" width="80" alt="AI Native"><br>
    <b>AI Native</b><br>
    Built-in MCP server for Claude<br>
    LLM-optimized text extraction
  </td>
  <td align="center" width="33%">
    <img src="docs/images/icons/icon-quality.svg" width="80" alt="Data Quality"><br>
    <b>Production Quality</b><br>
    1000+ tests, type hints<br>
    Battle-tested by analysts
  </td>
</tr>
<tr>
  <td align="center" width="33%">
    <img src="docs/images/icons/icon-xbrl.svg" width="80" alt="XBRL Support"><br>
    <b>XBRL Native</b><br>
    Full XBRL standardization<br>
    Cross-company comparisons
  </td>
  <td align="center" width="33%">
    <img src="docs/images/icons/icon-data.svg" width="80" alt="Rich Data"><br>
    <b>Rich Data Objects</b><br>
    Smart parsing for every form<br>
    Pandas-ready DataFrames
  </td>
  <td align="center" width="33%">
    <img src="docs/images/icons/icon-community.svg" width="80" alt="Open Source"><br>
    <b>Open Source</b><br>
    MIT license, community-driven<br>
    Transparent & auditable
  </td>
</tr>
</table>

<p align="center">
  <img src="docs/images/dividers/divider-hexagons.svg" alt="">
</p>

<p align="center">
  <img src="docs/images/sections/section-ai-integration.svg" alt="AI Integration">
</p>

### Built for AI Agents & LLMs

EdgarTools ships with a **production-ready MCP (Model Context Protocol) server** that enables Claude and other AI assistants to analyze SEC filings directly. No API keys, no rate limits, no costs.

```python
# Start the MCP server for Claude
uv run mcp-server-edgar

# Or install globally
pip install edgartools
mcp-server-edgar
```

Once configured, Claude can:
- Research companies and extract financial metrics
- Analyze filings and answer complex questions
- Track insider transactions and fund holdings
- Compare companies across standardized XBRL data
- Generate reports with accurate SEC data

**AI-Optimized Features:**
- Clean text extraction optimized for LLM context windows
- Markdown conversion preserves document structure
- Section extraction (MD&A, Risk Factors, etc.)
- Chunking support for large documents
- Zero hallucination with direct SEC data access

<p align="center">
  <img src="docs/images/dividers/divider-hexagons.svg" alt="">
</p>

<p align="center">
  <img src="docs/images/sections/section-quick-start.svg" alt="Quick Start">
</p>

```python
# 1. Install
pip install edgartools

# 2. Set your identity (required by SEC regulations)
from edgar import *
set_identity("your.name@example.com")

# 3. Get company financials in 1 line
balance_sheet = Company("AAPL").get_financials().balance_sheet()

# 4. Or explore any filing
company = Company("MSFT")
filings = company.get_filings(form="10-K")
latest_10k = filings[0]

# 5. Extract clean text for analysis
text = latest_10k.markdown()  # LLM-ready format
```

![Apple SEC Form 4 insider transaction data extraction with Python](docs/images/aapl-insider.png)

<p align="center">
  <img src="docs/images/dividers/divider-hexagons.svg" alt="">
</p>

<p align="center">
  <img src="docs/images/sections/section-features.svg" alt="Key Features">
</p>

### Comprehensive SEC Data Access

<table>
<tr>
<td width="50%">

**Financial Statements**
- Balance Sheets, Income Statements, Cash Flows
- Individual line items via XBRL tags
- Multi-period comparisons
- Standardized cross-company data
- Automatic unit conversion

**Fund Holdings (13F)**
- Complete 13F filing history
- Portfolio composition analysis
- Position tracking over time
- Ownership percentages
- Value calculations

**Insider Transactions**
- Form 3, 4, 5 structured data
- Transaction history by insider
- Ownership changes
- Grant and exercise details
- Automatic parsing

</td>
<td width="50%">

**Filing Intelligence**
- Any form type (10-K, 10-Q, 8-K, S-1, etc.)
- Complete history since 1994
- Smart data objects for each form
- Automatic HTML to clean text
- Section extraction (Risk Factors, MD&A)

**Performance & Reliability**
- 10-30x faster than alternatives
- Automatic rate limiting
- Smart caching
- Robust error handling
- Type hints throughout

**Developer Experience**
- Intuitive, consistent API
- Pandas DataFrame integration
- Rich terminal output
- Comprehensive documentation
- 1000+ tests

</td>
</tr>
</table>

<p align="center">
  <img src="docs/images/dividers/divider-hexagons.svg" alt="">
</p>

<p align="center">
  <img src="docs/images/sections/section-performance.svg" alt="Performance">
</p>

### Performance That Matters

| Operation | EdgarTools | Alternative | Speedup |
|-----------|------------|-------------|---------|
| Download 10-K filing | 0.5s | 5-15s | <img src="docs/images/icons/compare-check.svg" width="20"> **10-30x** |
| Parse financial statements | 0.3s | 3-10s | <img src="docs/images/icons/compare-check.svg" width="20"> **10-30x** |
| Extract XBRL data | 1.2s | 15-45s | <img src="docs/images/icons/compare-check.svg" width="20"> **12-37x** |
| Text extraction & cleaning | 0.4s | 2-8s | <img src="docs/images/icons/compare-check.svg" width="20"> **5-20x** |

Benchmarks run on standard laptop. Alternative = typical web scraping implementation.

<details>
<summary><b>Why is EdgarTools so fast?</b></summary>

1. **Optimized parsing**: Uses `lxml` for HTML/XML parsing instead of BeautifulSoup
2. **Efficient data structures**: Leverages PyArrow for financial data when available
3. **Smart caching**: Avoids redundant downloads and parsing
4. **Minimal dependencies**: Lean dependency tree reduces overhead
5. **Purpose-built**: Designed specifically for SEC filings, not general web scraping

</details>

<p align="center">
  <img src="docs/images/dividers/divider-hexagons.svg" alt="">
</p>

## Comparison with Alternatives

| Feature | EdgarTools | sec-api (paid) | OpenEDGAR | Manual Scraping |
|---------|------------|----------------|-----------|-----------------|
| **AI/MCP Integration** | <img src="docs/images/icons/compare-check.svg" width="20"> | <img src="docs/images/icons/compare-cross.svg" width="20"> | <img src="docs/images/icons/compare-cross.svg" width="20"> | <img src="docs/images/icons/compare-cross.svg" width="20"> |
| **Cost** | Free | $150+/mo | Free | Free |
| **Speed** | 10-30x baseline | Fast (API) | Slow | Slow |
| **XBRL Support** | <img src="docs/images/icons/compare-check.svg" width="20"> Full | <img src="docs/images/icons/compare-partial.svg" width="20"> Partial | <img src="docs/images/icons/compare-cross.svg" width="20"> | <img src="docs/images/icons/compare-cross.svg" width="20"> |
| **Financial Statements** | <img src="docs/images/icons/compare-check.svg" width="20"> Parsed | <img src="docs/images/icons/compare-check.svg" width="20"> Parsed | <img src="docs/images/icons/compare-partial.svg" width="20"> Basic | <img src="docs/images/icons/compare-cross.svg" width="20"> DIY |
| **LLM-Ready Output** | <img src="docs/images/icons/compare-check.svg" width="20"> | <img src="docs/images/icons/compare-cross.svg" width="20"> | <img src="docs/images/icons/compare-cross.svg" width="20"> | <img src="docs/images/icons/compare-cross.svg" width="20"> |
| **Type Hints** | <img src="docs/images/icons/compare-check.svg" width="20"> | <img src="docs/images/icons/compare-cross.svg" width="20"> | <img src="docs/images/icons/compare-partial.svg" width="20"> | <img src="docs/images/icons/compare-cross.svg" width="20"> |
| **Rate Limiting** | <img src="docs/images/icons/compare-check.svg" width="20"> Auto | N/A (API) | <img src="docs/images/icons/compare-cross.svg" width="20"> Manual | <img src="docs/images/icons/compare-cross.svg" width="20"> Manual |
| **Open Source** | <img src="docs/images/icons/compare-check.svg" width="20"> MIT | <img src="docs/images/icons/compare-cross.svg" width="20"> Proprietary | <img src="docs/images/icons/compare-check.svg" width="20"> Apache | N/A |

<p align="center">
  <img src="docs/images/dividers/divider-hexagons.svg" alt="">
</p>

## Real-World Use Cases

### Company Financial Analysis

**Problem:** Need to analyze a company's financial health across multiple periods.

![Microsoft SEC 10-K financial data analysis with EdgarTools](docs/images/MSFT_financial_complex.png)

[See full code](docs/examples.md#company_financial_analysis)

<p align="center">
  <img src="docs/images/dividers/divider-hexagons.svg" alt="">
</p>

<p align="center">
  <img src="docs/images/sections/section-community.svg" alt="Community & Support">
</p>

### Documentation & Resources

- [User Journeys / Examples](https://edgartools.readthedocs.io/en/latest/examples/)
- [Quick Guide](https://edgartools.readthedocs.io/en/latest/quick-guide/)
- [Full API Documentation](https://edgartools.readthedocs.io/)
- [EdgarTools Blog](https://www.edgartools.io)

### Get Help & Connect

- [GitHub Issues](https://github.com/dgunning/edgartools/issues) - Bug reports and feature requests
- [Discussions](https://github.com/dgunning/edgartools/discussions) - Questions and community discussions

### Contributing

We welcome contributions from the community! Here's how you can help:

- **Code**: Fix bugs, add features, improve documentation
- **Examples**: Share interesting use cases and examples
- **Feedback**: Report issues or suggest improvements
- **Spread the Word**: Star the repo, share with colleagues

See our [Contributing Guide](CONTRIBUTING.md) for details.

<p align="center">
  <img src="docs/images/dividers/divider-hexagons.svg" alt="">
</p>

## Support the Project

If you find EdgarTools valuable, please consider supporting its development:

<a href="https://www.buymeacoffee.com/edgartools" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;width: 144px !important;" >
</a>

Your support helps maintain and improve EdgarTools for the entire community!

---

<p align="center">
EdgarTools is distributed under the <a href="LICENSE">MIT License</a>
</p>

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=dgunning/edgartools&type=Timeline)](https://star-history.com/#dgunning/edgartools&Timeline)
