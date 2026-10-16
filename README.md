<a href="https://github.com/dgunning/edgartools">
  <img src="https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/edgartools-mark.svg" alt="EdgarTools logo" align="left" height="80" hspace="20">
</a>

# EdgarTools — Python Library for SEC EDGAR Filings

<br clear="left">

<p>
  <a href="https://pypi.org/project/edgartools"><img src="https://img.shields.io/pypi/v/edgartools.svg" alt="PyPI - Version"></a>
  <a href="https://github.com/dgunning/edgartools/actions"><img src="https://img.shields.io/github/actions/workflow/status/dgunning/edgartools/python-hatch-workflow.yml" alt="GitHub Workflow Status"></a>
  <a href="https://github.com/dgunning/edgartools/actions/workflows/regression-tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/dgunning/edgartools/regression-tests.yml?branch=main&label=regression" alt="Regression Tests"></a>
  <a href="https://www.codefactor.io/repository/github/dgunning/edgartools"><img src="https://www.codefactor.io/repository/github/dgunning/edgartools/badge" alt="CodeFactor"></a>
  <a href="https://github.com/dgunning/edgartools/blob/main/LICENSE.txt"><img src="https://img.shields.io/github/license/dgunning/edgartools" alt="GitHub"></a>
  <a href="https://edgartools.readthedocs.io/"><img alt="Documentation" src="https://img.shields.io/badge/docs-edgartools-blue"></a>
  <img alt="Pepy Total Downloads" src="https://img.shields.io/pepy/dt/edgartools">
  <a href="https://pepy.tech/project/edgartools"><img alt="Pepy Monthly Downloads" src="https://static.pepy.tech/badge/edgartools/month"></a>
  <a href="https://github.com/dgunning/edgartools/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/dgunning/edgartools?style=social"></a>

</p>

**EdgarTools** is a Python library for accessing SEC EDGAR filings as structured data. Parse financial statements, insider trades, fund holdings, proxy statements, and dozens of other filing types with a consistent Python API — in a few lines of code. Free and open source.

![EdgarTools SEC filing data extraction demo](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/edgartools-demo.gif)

## Why EdgarTools?

SEC EDGAR has every filing since 1994, free — and almost none of it is ready to use. EdgarTools turns any filing into a typed Python object, so a 10-K's revenue is one line instead of an afternoon of XBRL parsing.

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
    Typed objects + pandas DataFrames for 90 form types
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

**1. Install.** The package is `edgartools`; the module you import is `edgar`. Python 3.11+.

```bash
uv add edgartools        # or: pip install edgartools
```

**2. Identify yourself to the SEC.** EDGAR requires a contact email on every request. There is no key, signup or rate-limit tier.

```python
from edgar import Company, set_identity

set_identity("your.name@example.com")
```

**3. Get data.**

```python
# Five fiscal years of standardized income statement, from XBRL
Company("NVDA").income_statement(periods=5)
#> Total Revenue $215.9B $130.5B $60.9B
```

## Why not just call SEC's APIs?

`data.sec.gov` gives you JSON facts and filing indexes. Everything past that is your code. EdgarTools does that part:

- **Section text and markdown.** Item 1A, Item 7 or any Item of a 10-K or 10-Q as text, and whole filings as markdown for RAG. Raw HTML is where hand-rolled parsers break.
- **Parsed forms, not XML.** 13F holdings, Form 4 transactions, N-PORT portfolios and 8-K items as typed objects and DataFrames.
- **Statements that line up.** Rows standardized across filers, so "Total Revenue" means the same thing for a bank and a chipmaker, plus discrete quarters (Q4 derived from the 10-K) and trailing twelve months.
- **Search and plumbing.** Full-text search over filing content, the live filing feed, rate limiting, caching and offline storage.

It runs in your own process, MIT-licensed, with no API key and no vendor quota; SEC's fair-access limit of 10 requests a second still applies, and EdgarTools keeps to it.

## What you can do

### Full-text search across SEC filings

Search the text of every filing since 2001, not just form types and dates.

```python
from edgar import search_filings

# Every 10-K filed since 2025 that mentions tariffs
results = search_filings("tariff", forms="10-K", start_date="2025-01-01")
results[0].get_filing()  # the Filing behind a hit, ready for .obj() or .markdown()

# Structured: 8-Ks that reported a cybersecurity incident (Item 1.05) in 2025
search_filings(forms="8-K", items="1.05", start_date="2025-01-01", end_date="2025-12-31")
#> 19 total
```
[Full-text search guide →](https://edgartools.readthedocs.io/en/latest/guides/full-text-search/)

### Financial statements over several years

```python
Company("MSFT").income_statement(periods=10)  # also .balance_sheet() and .cash_flow_statement()
```
[Financial Statements guide →](https://edgartools.readthedocs.io/en/latest/guides/financial-data/)

### One metric across companies

Pick rows by their standardized label, never by position: the first row of an income statement is not always total revenue.

```python
import pandas as pd

revenue = {
    ticker: Company(ticker).income_statement(periods=3, as_dataframe=True)
            .set_index("label").filter(like="FY").loc["Total Revenue"] / 1e9
    for ticker in ["JPM", "PFE", "XOM"]
}
pd.DataFrame(revenue).round(1)  # $ billions
#> FY 2025 182.4 62.6 332.2
```

### Quarterly figures and trailing twelve months

```python
nvda = Company("NVDA")
nvda.get_ttm_revenue()                                 # the last four quarters, summed
nvda.income_statement(period="quarterly", periods=8)   # discrete quarters; Q4 is derived from the 10-K
```

### Sections and markdown for RAG

```python
filing = Company("NVDA").latest("10-K")
filing.markdown()          # the whole filing as markdown

tenk = filing.obj()
tenk.risk_factors          # Item 1A as text
tenk["Item 1C"]            # any Item by number
```
[Sections guide →](https://edgartools.readthedocs.io/en/latest/concepts/data-objects/)

### Find filings, by anything

```python
from edgar import find, get_current_filings, get_filings

get_filings(2025, 4, form="10-K")   # every 10-K filed in Q4 2025
get_current_filings()               # the live feed, as SEC posts it
find("0000320193-25-000079")        # an accession number, CIK or ticker
```
[Finding filings guide →](https://edgartools.readthedocs.io/en/latest/guides/searching-filings/)

![find() resolving a ticker, a CIK and an accession number](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/universal-find.gif)

![get_current_filings() showing the live SEC filing feed](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/live-filings.gif)

### 13F institutional holdings

```python
thirteenf = Company("BRK.A").get_filings(form="13F-HR").latest().obj()
thirteenf.holdings  # every position, one row per security
```
[Institutional Holdings guide →](https://edgartools.readthedocs.io/en/latest/guides/thirteenf-data-object-guide/)

![Berkshire Hathaway's latest 13F holdings](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/thirteenf-holdings.gif)

### Insider trades from Form 4

```python
form4 = Company("TSLA").get_filings(form="4").latest().obj()
form4.to_dataframe()  # buys, sells, grants and exercises
```
[Insider Trades guide →](https://edgartools.readthedocs.io/en/latest/insider-filings/)

![Tesla's latest Form 4 parsed into a structured object](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/insider-form4.gif)

### Fund holdings from N-PORT

```python
from edgar import Fund

Fund("VOO").get_portfolio()  # the latest N-PORT holdings as a DataFrame
```
[Fund Portfolios guide →](https://edgartools.readthedocs.io/en/latest/guides/nport-data-object-guide/)

### 8-K events and earnings releases

```python
eightk = find("0001045810-26-000073").obj()  # NVIDIA, 2026-08-26
eightk.items      # ['Item 2.02', 'Item 9.01']
eightk.earnings   # the EX-99.1 press release tables, parsed
```
[Current Events guide →](https://edgartools.readthedocs.io/en/latest/eightk-filings/)

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

</td>
<td width="50%" valign="top">

**Filings & text**
- 36 typed data objects covering 90 form types; filings since 1994
- Section extraction (Risk Factors, MD&A): 91.5% of 10-K Item boundaries exact on a held-out set
- EX-21 subsidiaries, auditor info
- HTML → clean text + markdown for RAG; EDGAR full-text search
- Ticker/CIK lookup, industry & exchange filtering

**Built for production**
- Configurable rate limiting + enterprise/academic mirrors
- Smart caching, type hints throughout, 45,000+ tests
- [Enterprise configuration →](https://edgartools.readthedocs.io/en/latest/configuration/#enterprise-configuration)

</td>
</tr>
</table>

EdgarTools has typed objects for 90 SEC form types, including **10-K annual reports**, **10-Q quarterly filings**, **8-K current reports**, **13F institutional holdings**, **Form 4 insider transactions**, **proxy statements (DEF 14A)**, **S-1 registration statements**, **N-CSR fund reports**, **N-MFP money market data**, **N-PORT fund portfolios**, **Schedule 13D/G ownership**, **Form D offerings**, **Form C crowdfunding**, and **Form 144 restricted stock**. Parse XBRL financial data, extract text sections, and convert filings to pandas DataFrames. Every other filing is still reachable as a `Filing`, with its documents, text and attachments.

## Library or hosted?

**EdgarTools** is this library: free, MIT-licensed, running in your own Python process. **[edgar.tools](https://www.edgar.tools)** is the hosted platform built on it: the same parsing, kept running and current, with every answer cited to its filing. You are not paying for the parsing; you are paying for it to be run and answerable. No feature is ever removed from the library to sell the platform.

| If you want to… | Use |
|---|---|
| Build something that runs: pipelines, backfills, backtests, model corpora, notebooks, custom joins, anything repeated across hundreds of names or run inside your own network | **The library** |
| Ask, not build: what the companies you cover filed and what changed since last time, who sold, who holds it, one person across every company they touch, screens across a universe, alerts, cited answers to forward or share with a team. From a browser, a phone, Excel, Claude or ChatGPT, or an agent that cannot run Python | **[edgar.tools](https://app.edgar.tools)**. Free account to start |
| Own a maintained dataset (insider trades, 13F, BDC portfolios, material events), every row traceable to its filing, without running the pipeline | **[edgar.tools data licensing](https://www.edgar.tools/data)** |
| Fetch one known filing or one JSON document, once, from a script | **Neither**: call EDGAR directly |

Both have an MCP server: the library's runs locally (see AI Integration below), and edgar.tools' is hosted at [app.edgar.tools/mcp](https://app.edgar.tools/mcp). Attach one per client, not both: they overlap and split your assistant's routing.

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

This adds SEC analysis capabilities to Claude, including API documentation, code examples, and a form type reference.

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

See [AI Integration Guide](https://github.com/dgunning/edgartools/blob/main/docs/ai-integration.md) for complete documentation.

</details>

## Support the project

The SEC changes filing formats and ships a new XBRL taxonomy every year. Sponsorship is what keeps the parsers current and pays for new ones as new disclosures appear.

- **[GitHub Sponsors](https://github.com/sponsors/dgunning)**: monthly tiers for individuals, and for teams running EdgarTools in production, tiers with a first-response time on the issues you open and your logo in this README.
- **[Buy Me a Coffee](https://www.buymeacoffee.com/edgartools)**: a one-time thank-you.
- **[Consulting](https://www.edgar.tools/consulting)**: help from the library's author with SEC data pipelines and financial AI built on it.

<p align="center">
  <a href="https://github.com/sponsors/dgunning" target="_blank">
    <img src="https://img.shields.io/badge/Sponsor-30363D?style=for-the-badge&logo=GitHub-Sponsors&logoColor=EA4AAA" alt="Sponsor on GitHub" height="44">
  </a>
  &nbsp;&nbsp;
  <a href="https://www.buymeacoffee.com/edgartools" target="_blank">
    <img src="https://img.shields.io/badge/Buy_me_a_coffee-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=black" alt="Buy Me A Coffee" height="44">
  </a>
</p>

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

See our [Contributing Guide](https://github.com/dgunning/edgartools/blob/main/CONTRIBUTING.md) for details.

---

<p align="center">
EdgarTools is distributed under the <a href="https://github.com/dgunning/edgartools/blob/main/LICENSE.txt">MIT License</a>
</p>

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=dgunning/edgartools&type=Timeline)](https://star-history.com/#dgunning/edgartools&Timeline)

<!-- mcp-name: io.github.dgunning/edgartools -->
