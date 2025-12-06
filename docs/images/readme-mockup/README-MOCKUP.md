<p align="center">
<a href="https://github.com/dgunning/edgartools">
    <img src="../edgartools-logo.png" alt="EdgarTools Python SEC EDGAR library logo" height="80">
</a>
</p>

<h3 align="center">The AI-Native SEC Filing Analysis Platform</h3>

<p align="center">
  <a href="https://pypi.org/project/edgartools"><img src="https://img.shields.io/pypi/v/edgartools.svg" alt="PyPI - Version"></a>
  <a href="https://github.com/dgunning/edgartools/actions"><img src="https://img.shields.io/github/actions/workflow/status/dgunning/edgartools/python-hatch-workflow.yml" alt="GitHub Workflow Status"></a>
  <a href="https://www.codefactor.io/repository/github/dgunning/edgartools"><img src="https://www.codefactor.io/repository/github/dgunning/edgartools/badge" alt="CodeFactor"></a>
  <a href="https://github.com/dgunning/edgartools/blob/main/LICENSE"><img src="https://img.shields.io/github/license/dgunning/edgartools" alt="GitHub"></a>
  <a href="https://pypi.org/project/edgartools"><img src="https://img.shields.io/pypi/dm/edgartools" alt="PyPI - Downloads"></a>
</p>

<div align="center">
  <img src="badge-ai-native.svg" alt="AI-Native" />
  <img src="badge-mcp-ready.svg" alt="MCP Ready" />
  <img src="badge-10x-faster.svg" alt="10x Faster" />
  <img src="badge-zero-cost.svg" alt="Zero Cost" />
</div>

<p align="center">
  <b>Transform SEC filing analysis from hours of wrangling to minutes of insight. The world's most powerful open-source SEC data library combines intuitive APIs, standardized financial data, and native AI agent support.</b>
</p>

<br />

<div align="center">
  <img src="divider-hexagons.svg" width="80%" alt="divider" />
</div>

<br />

## Why EdgarTools?

<table>
  <tr>
    <td align="center" width="33%">
      <img src="icon-speed.svg" width="80" alt="Speed" /><br />
      <h3>Lightning Fast</h3>
      <p>Get 5 years of financials in 2-3 seconds vs 30-60 seconds with alternatives. Built for analysts who process hundreds of filings.</p>
    </td>
    <td align="center" width="33%">
      <img src="icon-ai.svg" width="80" alt="AI Integration" /><br />
      <h3>AI-Native</h3>
      <p>Production MCP server for Claude Desktop, Cline, and Continue.dev. Token-optimized outputs for LLM consumption.</p>
    </td>
    <td align="center" width="33%">
      <img src="icon-quality.svg" width="80" alt="Data Quality" /><br />
      <h3>Data Quality</h3>
      <p>Automatic standardization across companies. Tesla's "AutomotiveRevenue" → "Revenue". Clean, analysis-ready DataFrames.</p>
    </td>
  </tr>
</table>

<br />

<div align="center">
  <img src="divider-hexagons.svg" width="80%" alt="divider" />
</div>

<br />

<div align="center">
  <img src="section-quick-start.svg" alt="Quick Start" />
</div>

<br />

### Installation

```bash
# Full installation with AI/MCP support
pip install "edgartools[ai]"

# Basic installation
pip install edgartools
```

### Your First Analysis (3 lines)

```python
from edgar import Company

apple = Company("AAPL")
financials = apple.get_financials().get_revenue()
```

### AI Agent Integration

```bash
# Start MCP server for Claude Desktop
python -m edgar.ai
```

Configure in Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "edgartools": {
      "command": "python3",
      "args": ["-m", "edgar.ai"],
      "env": {
        "EDGAR_IDENTITY": "Your Name your.email@example.com"
      }
    }
  }
}
```

Now Claude can analyze any SEC filing, compare financials, or screen stocks using natural language.

<br />

<div align="center">
  <img src="divider-hexagons.svg" width="80%" alt="divider" />
</div>

<br />

## EdgarTools vs Alternatives

| Feature | EdgarTools | sec-api | OpenEDGAR | Official SEC APIs |
|---------|------------|---------|-----------|-------------------|
| **Cost** | Free | $50-500/month | Free | Free |
| **XBRL Standardization** | ✅ Automatic | ❌ Raw only | ❌ Raw only | ❌ Raw only |
| **AI/MCP Integration** | ✅ Production ready | ❌ No | ❌ No | ❌ No |
| **Insider Trading (Forms 3,4,5)** | ✅ Structured objects | ⚠️ Raw XML | ❌ No | ⚠️ Raw XML |
| **13F Fund Holdings** | ✅ Full analysis | ⚠️ Basic | ❌ No | ⚠️ Basic |
| **Performance** | 2-3 seconds | 30-60 seconds | 5-10 minutes | 10-30 seconds |
| **Setup Complexity** | `pip install` | API key required | Django setup | No setup |

<details>
<summary><b>View Performance Benchmarks</b></summary>

<br />

| Operation | EdgarTools | Alternatives | Speedup |
|-----------|------------|--------------|---------|
| Get 5 years of financials | 2-3 seconds | 30-60 seconds | **15-20x faster** |
| Parse 100 10-K filings | 2-5 minutes | 30-60 minutes | **10-15x faster** |
| Extract all insider trades | 10-15 seconds | 5-10 minutes | **30x faster** |
| Query XBRL facts | Instant (cached) | 5-15 seconds | **Instant** |

</details>

<br />

<div align="center">
  <img src="divider-hexagons.svg" width="80%" alt="divider" />
</div>

<br />

## Complete Feature Set

**Filing Types Supported**
- Annual Reports (10-K, 20-F, 40-F)
- Quarterly Reports (10-Q)
- Current Reports (8-K, 6-K)
- Insider Transactions (Forms 3, 4, 5)
- Fund Holdings (13F-HR)
- Proxy Statements (DEF 14A)
- Registration Statements (S-1, S-3, S-4, S-8)
- 30+ other form types

**Data Extraction**
- Financial statements (Balance Sheet, Income, Cash Flow)
- Standardized metrics API (`get_revenue()`, `get_net_income()`, etc.)
- XBRL facts with dimensional breakdowns
- Clean text extraction from HTML
- Section-level access (Risk Factors, MD&A, etc.)

**Developer Experience**
- Type hints and IntelliSense support
- Rich display in Jupyter notebooks
- Automatic pandas DataFrame conversion
- Comprehensive error handling
- Smart caching and rate limiting

**AI/MCP Capabilities**
- `edgar_company_research` - Comprehensive company intelligence
- `edgar_analyze_financials` - Multi-period financial analysis
- Token-optimized for LLM consumption
- Compatible with Claude Desktop, Cline, Continue.dev

<br />

<div align="center">
  <img src="divider-hexagons.svg" width="80%" alt="divider" />
</div>

<br />

## Real-World Impact

> **Financial Analysis Firm**: "EdgarTools reduced our data preparation time from 6 hours to 15 minutes. We can now analyze 500+ companies in the time it used to take for 10." — 95% time savings

> **Academic Research**: "For our corporate governance study of 3,000 companies over 10 years, EdgarTools made the impossible possible. The standardized data quality is exceptional."

> **Investment Fund**: "We track insider trading across our entire portfolio in real-time. EdgarTools' Form 4 parsing is the most accurate we've found."

<br />

<div align="center">
  <img src="divider-hexagons.svg" width="80%" alt="divider" />
</div>

<br />

## Documentation & Community

**Documentation**
- [Quick Start Guide](https://edgartools.readthedocs.io/en/latest/quick-guide/) - Get started in 5 minutes
- [User Examples](https://edgartools.readthedocs.io/en/latest/examples/) - Real-world use cases
- [Full API Documentation](https://edgartools.readthedocs.io/) - Complete reference
- [MCP Quickstart](https://github.com/dgunning/edgartools/blob/main/edgar/ai/docs/MCP_QUICKSTART.md) - AI agent setup

**Community**
- [GitHub Discussions](https://github.com/dgunning/edgartools/discussions) - Ask questions, share insights
- [GitHub Issues](https://github.com/dgunning/edgartools/issues) - Bug reports and feature requests
- [EdgarTools Blog](https://www.edgartools.io) - Tutorials and updates

<br />

<div align="center">
  <img src="divider-hexagons.svg" width="80%" alt="divider" />
</div>

<br />

## Contributing

We welcome contributions from the community! Ways to help:

- **Code**: Fix bugs, add features, improve documentation
- **Examples**: Share interesting use cases and analyses
- **Feedback**: Report issues or suggest improvements
- **Spread the Word**: Star the repo, share with colleagues

See our [Contributing Guide](CONTRIBUTING.md) for details.

<br />

<div align="center">
  <img src="divider-hexagons.svg" width="80%" alt="divider" />
</div>

<br />

## Support EdgarTools

If you find EdgarTools valuable, please consider supporting its development:

<div align="center">
<a href="https://www.buymeacoffee.com/edgartools" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;width: 144px !important;" >
</a>
</div>

<br />

Your support helps maintain and improve EdgarTools for the entire community!

<br />

<div align="center">
  <img src="divider-hexagons.svg" width="80%" alt="divider" />
</div>

<br />

## License

EdgarTools is distributed under the [MIT License](LICENSE).

<br />

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=dgunning/edgartools&type=Timeline)](https://star-history.com/#dgunning/edgartools&Timeline)

</div>
