<a href="https://github.com/dgunning/edgartools">
  <img src="https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/edgartools-mark.svg" alt="EdgarTools logo" align="left" height="80" hspace="20">
</a>

# EdgarTools — Python Library for SEC EDGAR Filings

<br clear="left">

<p>
  <a href="https://pypi.org/project/edgartools"><img src="https://img.shields.io/pypi/v/edgartools.svg" alt="PyPI - Version"></a>
  <a href="https://github.com/dgunning/edgartools/actions"><img src="https://img.shields.io/github/actions/workflow/status/dgunning/edgartools/python-hatch-workflow.yml" alt="GitHub Workflow Status"></a>
  <a href="https://www.codefactor.io/repository/github/dgunning/edgartools"><img src="https://www.codefactor.io/repository/github/dgunning/edgartools/badge" alt="CodeFactor"></a>
  <a href="https://github.com/dgunning/edgartools/blob/main/LICENSE"><img src="https://img.shields.io/github/license/dgunning/edgartools" alt="GitHub"></a>
  <a href="https://edgartools.readthedocs.io/"><img alt="Documentation" src="https://img.shields.io/badge/docs-edgartools-blue"></a>
  <img alt="Pepy Total Downloads" src="https://img.shields.io/pepy/dt/edgartools">
  <a href="https://pepy.tech/project/edgartools"><img alt="Pepy Monthly Downloads" src="https://static.pepy.tech/badge/edgartools/month"></a>
  <a href="https://github.com/dgunning/edgartools/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/dgunning/edgartools?style=social"></a>

</p>

**EdgarTools** is a Python library for accessing SEC EDGAR filings as structured data. Parse financial statements, insider trades, fund holdings, proxy statements, and 20+ other filing types with a consistent Python API — in a few lines of code. Free and open source.

![EdgarTools SEC filing data extraction demo](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/edgartools-demo.gif)

## Why EdgarTools?

SEC EDGAR has every filing back to 1994, free — and almost none of it is ready to use. EdgarTools turns any filing into a typed Python object, so a 10-K's revenue is one line instead of an afternoon of XBRL parsing.

```python
# Apple's latest income statement — rendered, standardized, done
from edgar import Company
Company("AAPL").get_financials().income_statement()
```

<table align="center">
<tr>
  <td align="center" width="33%">
    <img src="https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/icons/icon-data.svg" width="96" alt="Financial Statements"><br>
    <b>Financial Statements</b><br>
    Income, balance sheet, cash flow in one call<br>
    XBRL-standardized for cross-company comparison
  </td>
  <td align="center" width="33%">
    <img src="https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/icons/icon-filings.svg" width="96" alt="Every Filing Type"><br>
    <b>Every Filing Type</b><br>
    13F holdings, Form 4 insiders, 8-K events, funds, proxies<br>
    Typed objects + pandas DataFrames for 20+ forms
  </td>
  <td align="center" width="33%">
    <img src="https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/icons/icon-ai.svg" width="96" alt="Built for Pipelines & AI"><br>
    <b>Built for Pipelines &amp; AI</b><br>
    Rate-limit aware, smart caching, enterprise mirrors<br>
    Built-in MCP server + LLM-ready text for RAG
  </td>
</tr>
</table>

## How It Works

Everything starts with a **`Company`** or a **`Filing`**. Call **`.obj()`** and you get a typed object built for that form — its data ready as pandas DataFrames and clean text.

<p align="center">
  <img src="https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/how-it-works.svg" alt="How EdgarTools turns any SEC filing into a typed Python object">
</p>

The same typed output that reads cleanly in a notebook drops straight into a pipeline: DataFrames for your warehouse, LLM-ready text and an MCP server for your AI stack, rate-limit and enterprise-mirror aware for scale.

## Quick Start

**1. Install**

```bash
pip install edgartools
```

**2. Identify yourself to the SEC** — EDGAR requires an email with every request. No key, no signup, no rate-limit tier; set it once:

```python
from edgar import *
set_identity("your.name@example.com")
```

**3. Get data** — every filing is now a few lines away:

```python
# Standardized financial statements, straight from XBRL
Company("AAPL").get_financials().income_statement()

# The latest insider Form 4 as a structured object
Company("AAPL").get_filings(form="4").latest().obj()
```

![Apple SEC Form 4 insider transactions parsed into a structured Python object](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/quickstart-form4.gif)

**Next:** explore the [Use Cases](#use-cases) below, or dive into the [documentation](https://edgartools.readthedocs.io/) and [Quick Guide](https://edgartools.readthedocs.io/en/latest/quick-guide/).

## Use Cases

### Financial statements from 10-K and 10-Q filings

```python
financials = Company("MSFT").get_financials()
financials.balance_sheet()     # all line items
financials.income_statement()  # revenue, net income, EPS
```
[Financial Statements guide →](https://edgartools.readthedocs.io/en/latest/guides/financial-data/)

### Insider trading from SEC Form 4

```python
form4 = Company("TSLA").get_filings(form="4").latest().obj()
form4.to_dataframe()  # insider buy/sell transactions
```
[Insider Trades guide →](https://edgartools.readthedocs.io/en/latest/insider-filings/)

### 13F institutional holdings & hedge fund portfolios

```python
thirteenf = get_filings(form="13F-HR").latest().obj()
thirteenf.holdings  # every portfolio position as a DataFrame
```
[Institutional Holdings guide →](https://edgartools.readthedocs.io/en/latest/guides/thirteenf-data-object-guide/)

### 8-K current reports & corporate events

```python
eightk = get_filings(form="8-K").latest().obj()
eightk.items  # reported event items
```
[Current Events guide →](https://edgartools.readthedocs.io/en/latest/guides/eightk-data-object-guide/)

### XBRL financial data across companies

```python
facts = Company("AAPL").get_facts()
facts.query().by_concept("Revenue").to_dataframe()  # revenue history as a DataFrame
```
[XBRL Deep Dive →](https://edgartools.readthedocs.io/en/latest/xbrl/)

## Key Features

<table>
<tr>
<td width="50%" valign="top">

**Financial data**
- Income, balance sheet, cash flow — XBRL-standardized for cross-company comparison
- Individual line items, dimensional data, multi-period comparatives
- Company Facts API: time-series for any concept across years

**Funds & ownership**
- 13F holdings, N-PORT, N-MFP, N-CSR/N-CEN fund reports
- Form 3/4/5 insider transactions; Schedule 13D/G ownership
- Position tracking over time

</td>
<td width="50%" valign="top">

**Filings & text**
- Typed objects for 20+ forms; complete history since 1994
- Section extraction (Risk Factors, MD&A), EX-21 subsidiaries, auditor info
- HTML → clean text + markdown for RAG; full-text search
- Ticker/CIK lookup, industry & exchange filtering

**Built for production**
- Configurable rate limiting + enterprise/academic mirrors
- Smart caching, type hints throughout, 1000+ tests
- [Enterprise configuration →](docs/configuration.md#enterprise-configuration)

</td>
</tr>
</table>

EdgarTools supports all SEC form types including **10-K annual reports**, **10-Q quarterly filings**, **8-K current reports**, **13F institutional holdings**, **Form 4 insider transactions**, **proxy statements (DEF 14A)**, **S-1 registration statements**, **N-CSR fund reports**, **N-MFP money market data**, **N-PORT fund portfolios**, **Schedule 13D/G ownership**, **Form D offerings**, **Form C crowdfunding**, and **Form 144 restricted stock**. Parse XBRL financial data, extract text sections, and convert filings to pandas DataFrames.

## Comparison with Alternatives

EdgarTools is a **Python library** that talks directly to SEC EDGAR. [sec-api](https://sec-api.io) is the best-known **hosted API** that returns JSON. Both parse filings — the difference is how you work with the data, and what it costs you.

| | EdgarTools | sec-api |
|---|------------|---------|
| **Cost** | Free, MIT | $49+/mo |
| **Data format** | Typed Python objects → DataFrames | JSON you parse yourself |
| **Where it runs** | In your process — no key, no quotas, no vendor lock-in | Hosted API — key + rate tiers |
| **Filing coverage** | 20+ typed forms (10-K, 8-K, 13F, N-PORT, proxy…) | 15+ structured endpoints |
| **AI / MCP** | <img src="https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/icons/compare-check.svg" width="20"> Built in | <img src="https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/icons/compare-cross.svg" width="20"> |
| **Open source** | <img src="https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/icons/compare-check.svg" width="20"> Inspect, fork, self-host | <img src="https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/icons/compare-cross.svg" width="20"> Proprietary |

**Bottom line:** in Python, EdgarTools gives you typed objects, AI-native output, and the full SEC corpus — free, open, and inspectable, with no keys or bills. `pip install edgartools` and you're querying filings in two lines.

## Library or hosted?

**EdgarTools** is the open-source library — SEC-filing primitives you compose in your own code, free and self-run.

[**edgar.tools**](https://edgar.tools) is the hosted platform built on that same open engine: the full SEC corpus as a managed service, so your team gets the data without running the pipeline — and without the black box of a closed API.

Reach for the library when you want control in your own stack; reach for **edgar.tools** when you'd rather not operate it yourself.

## AI Integration

### Use EdgarTools with Claude Code & Claude Desktop

EdgarTools includes an MCP server and AI skills for Claude Desktop and Claude Code. Ask questions in natural language and get answers backed by real SEC data.

- *"Compare Apple and Microsoft's revenue growth rates over the past 3 years"*
- *"Which Tesla executives sold more than $1 million in stock in the past 6 months?"*

<details>
<summary><b>Setup Instructions</b></summary>

### Option 1: AI Skills (Recommended)

Install the EdgarTools skill for Claude Code or Claude Desktop:

```bash
pip install "edgartools[ai]"
python -c "from edgar.ai import install_skill; install_skill()"
```

This adds SEC analysis capabilities to Claude, including 3,450+ lines of API documentation, code examples, and form type reference.

### Option 2: MCP Server

Run EdgarTools as an MCP server for any AI client -- Claude Desktop, Cline, or your own containerized deployment.

Add to Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "edgartools": {
      "command": "uvx",
      "args": ["--from", "edgartools[ai]", "edgartools-mcp"],
      "env": {
        "EDGAR_IDENTITY": "Your Name your.email@example.com"
      }
    }
  }
}
```

Requires [uv](https://docs.astral.sh/uv/). Alternatively, `pip install "edgartools[ai]"` and use `python -m edgar.ai`.

See [AI Integration Guide](docs/ai-integration.md) for complete documentation.

</details>

## ❤️ Support This Project

EdgarTools runs in production at hedge funds, fintechs, and research desks — MIT-licensed, no keys, no subscriptions, and maintained by one person.

The SEC amends filing formats every quarter and ships a new XBRL taxonomy every year. Sponsorship is what keeps 20+ parsers current and funds new extractors as fresh disclosure types appear.

<p align="center">
  <a href="https://github.com/sponsors/dgunning" target="_blank">
    <img src="https://img.shields.io/badge/Sponsor-30363D?style=for-the-badge&logo=GitHub-Sponsors&logoColor=EA4AAA" alt="Sponsor on GitHub" height="44">
  </a>
  &nbsp;&nbsp;
  <a href="https://www.buymeacoffee.com/edgartools" target="_blank">
    <img src="https://img.shields.io/badge/Buy_me_a_coffee-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=black" alt="Buy Me A Coffee" height="44">
  </a>
</p>

<p align="center">
  <sub>Recurring sponsorship + corporate tiers via GitHub · One-time thanks via Buy Me a Coffee</sub>
</p>

---

### For teams running EdgarTools in production

If EdgarTools is in your data pipeline, [GitHub Sponsors](https://github.com/sponsors/dgunning) offers corporate tiers from **$250 to $1,500/mo** with:

- Response SLAs (24h–48h first response on critical issues)
- Quarterly strategy calls and roadmap input
- Logo placement in this README
- 7-day early access for internal regression testing
- Annual invoicing through GitHub — procurement-friendly

→ **[See sponsor tiers](https://github.com/sponsors/dgunning)**

## Community & Support

### Documentation & Resources

- [Documentation](https://edgartools.readthedocs.io/)
- [Notebooks / Examples](https://edgartools.readthedocs.io/en/latest/notebooks/)
- [Quick Guide](https://edgartools.readthedocs.io/en/latest/quick-guide/)
- [EdgarTools Blog](https://www.edgartools.io)

### Get Help & Connect

- [GitHub Issues](https://github.com/dgunning/edgartools/issues) - Bug reports and feature requests
- [Discussions](https://github.com/dgunning/edgartools/discussions) - Questions and community discussions

### Contributing

Contributions welcome:

- **Code**: Fix bugs, add features, improve documentation
- **Examples**: Share interesting use cases and examples
- **Feedback**: Report issues or suggest improvements
- **Spread the Word**: Star the repo, share with colleagues

See our [Contributing Guide](CONTRIBUTING.md) for details.

### Professional Services

Need help building production SEC data infrastructure? The creator of EdgarTools offers consulting for teams building financial AI products:

- **SEC Data Sprint** (1–3 days) — Working prototype on your data
- **Architecture Review** (1–2 weeks) — Pipeline audit with prioritized fixes
- **Pipeline Build** (2–4 weeks) — Production-ready code, tests, and handoff

[Learn more →](https://www.edgar.tools/consulting)

---

<p align="center">
EdgarTools is distributed under the <a href="LICENSE">MIT License</a>
</p>

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=dgunning/edgartools&type=Timeline)](https://star-history.com/#dgunning/edgartools&Timeline)

<!-- mcp-name: io.github.dgunning/edgartools -->
