# SEC EDGAR MCP for Private Credit

A fork of [EdgarTools](https://github.com/dgunning/edgartools), focused on private credit research through the **Model Context Protocol (MCP)**. It gives AI assistants access to borrower loan evidence, supporting disclosures and filed agreements from SEC EDGAR, alongside the broader company and financial data capabilities of the original library.

The private credit additions expose richer BDC loan evidence, selection of specific reporting periods, continuation through long results and access to exact documents and exhibits. Two prompt templates guide assistants through the research workflows below.

## Private credit use cases

### 1. Investigate borrower deterioration

**Is repayment becoming less likely?**

Business development companies (BDCs) disclose investments in private businesses, providing a public window into some private loans. Retrieve a named borrower's holdings from selected annual or quarterly filings, including available principal, cost, fair value, interest terms and payment-in-kind (PIK) interest. PIK is interest added to debt rather than paid in cash.

Investigate non-accrual evidence, where a lender has stopped recognizing interest income because collection is uncertain, and read the supporting footnotes and narrative. Retrieve another period when needed so the analyst or assistant can compare the evidence.

**Supporting tools:** `edgar_fund` actions `bdc_search`, `bdc_portfolio` and `bdc_nonaccrual`; `edgar_notes` and `edgar_read` for supporting disclosures; `edgar_search` and `edgar_company` for filing discovery.

### 2. Investigate lender protections

**What protects us if repayment fails?**

Locate filed credit agreements, guarantees and amendments. Search for provisions addressing collateral, repayment priority, releases and enforcement, then read the surrounding passages, definitions and exceptions.

Each document remains tied to its filing and source URL. References to earlier filings can be pursued when discoverable. Confirm which borrower, lender and obligation each agreement covers: a BDC's own borrowing agreement may concern different debt from a loan to its portfolio company.

**Supporting tools:** `edgar_document` actions `list`, `search` and `read`; `edgar_text_search` for discovery across filings; `edgar_filing` for filing context and document identity.

## What else the MCP provides

The server exposes **14 callable tools** for SEC research:

| Capability | Tools | Information available |
|---|---|---|
| Company and filing discovery | `edgar_company`, `edgar_search`, `edgar_screen` | Company profiles, filing history and filters such as industry or exchange |
| Financial analysis | `edgar_trends`, `edgar_compare` | Financial time series, growth rates and company comparisons |
| Filing content | `edgar_filing`, `edgar_read`, `edgar_notes` | Filing context, report sections, financial notes and disclosure tables |
| Text and exhibits | `edgar_text_search`, `edgar_document` | SEC full-text search and specific filing attachments |
| Ownership and governance | `edgar_ownership`, `edgar_proxy` | Insider transactions, institutional portfolios, executive compensation and governance |
| Funds and recent filings | `edgar_fund`, `edgar_monitor` | Fund, ETF, BDC and money market data; the latest SEC filings feed |

These tools build on EdgarTools' Python APIs for financial statements, XBRL data and filings such as 10-K, 10-Q, 8-K, Form 4, 13F and DEF 14A. The Python library remains available for programmatic use.

## Get started

Use Python 3.10 or later. Install **this fork** to receive its private credit additions:

```bash
git clone https://github.com/bryan-xiao97/edgartools-PC.git
cd edgartools-PC
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[ai]"
```

The SEC requires an identifying name and email for requests. Set your identity and check the server configuration:

```bash
export EDGAR_IDENTITY="Your Name your.email@example.com"
python -m edgar.ai --test
```

For Claude Desktop on macOS, add this entry under `mcpServers` in `~/Library/Application Support/Claude/claude_desktop_config.json`. Preserve any other server entries and replace the Python path with the absolute path to your checkout's virtual environment:

```json
{
  "mcpServers": {
    "sec-edgar-mcp": {
      "command": "/absolute/path/edgartools-PC/.venv/bin/python",
      "args": ["-m", "edgar.ai"],
      "env": {
        "EDGAR_IDENTITY": "Your Name your.email@example.com"
      }
    }
  }
}
```

Restart Claude Desktop after changing the configuration. Other MCP clients can launch the same command with the same environment variable. See the [MCP setup guide](edgar/ai/mcp/docs/MCP_QUICKSTART.md) for more detail.

## Start a research workflow

The server also exposes **9 prompt templates**. A template gives the assistant a research workflow; the assistant then calls the tools to retrieve evidence. Select a template in your client's MCP prompt menu or ask the assistant to use the tools directly.

| Private credit template | Required inputs | Optional inputs |
|---|---|---|
| `borrower_credit_review` | `borrower`, `bdc` | `period`, `comparison_period` as reporting period ends in YYYY-MM-DD format |
| `lender_protection_review` | `borrower` | `filing_or_url` (SEC accession number or document URL), `focus` |

Example requests:

> Investigate Ivy Hill's loan holdings reported by Ares Capital (ARCC) for the quarter ended June 30, 2026. Retrieve valuations, payment terms, non-accrual evidence and supporting disclosures. Cite the selected filing and explain any evidence gaps.

> Find filed agreements covering [borrower]'s financing. Identify collateral, guarantees and repayment priority, read the relevant provisions in context and explain which documents remain missing.

The other templates cover company due diligence, earnings analysis, industry research, insider activity, fund analysis, filing comparison and activist tracking. Template definitions are in [prompts.py](edgar/ai/mcp/tools/prompts.py).

## Evidence and coverage

Public SEC disclosures provide a partial view of private credit. A reported holding represents one lender's position, and agreements or amendments may be unavailable. Long extracted results can be paged; unreadable documents and extraction limitations remain visible.

Keep reported zero values distinct from missing disclosures or failed extraction. Absence from an extracted non-accrual list does not establish that a loan is performing, and PIK interest alone does not establish distress. Analysts and assistants interpret the retrieved evidence; the MCP does not assign credit ratings, determine legal enforceability or estimate recoveries.

## Upstream project

This repository builds on the original [EdgarTools](https://github.com/dgunning/edgartools) project by Dwight Gunning and its contributors. See the [upstream documentation](https://edgartools.readthedocs.io/) for the general Python library. Fork-specific MCP setup and workflows are described in the [local MCP guide](edgar/ai/mcp/docs/MCP_QUICKSTART.md).
