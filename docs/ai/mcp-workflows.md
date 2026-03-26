# MCP Workflows

The EdgarTools MCP server ships with 7 pre-built analysis workflows that chain tools together into multi-step research patterns. These are MCP prompts -- templates that guide Claude through a complete analysis.

## Pre-Built Workflows

| Workflow | What it does | Key parameter |
|----------|-------------|---------------|
| **due_diligence** | Full company analysis -- profile, financials, risks, insider activity | `identifier` (ticker/CIK) |
| **earnings_analysis** | Earnings deep dive -- latest 8-K, trends, peer comparison | `identifier` |
| **industry_overview** | Sector survey -- screen companies, compare top players, identify trends | `industry` (keyword) |
| **insider_monitor** | Track insider buying and selling patterns | `identifier` |
| **fund_analysis** | Mutual fund or ETF deep dive -- holdings, performance, family | `identifier` (fund ticker/CIK) |
| **filing_comparison** | Compare filings across time or across companies | `identifier`, optional `form` (default: 10-K), optional `compare_to` |
| **activist_tracking** | Monitor SC 13D/G activist investor positions | `identifier` |

These are templates, not black boxes. Claude follows them step by step, and you can interrupt, redirect, or drill deeper at any point.

---

## Due Diligence

*"Run a due diligence analysis on NVDA"*

Claude walks through:

1. **Company profile** -- `edgar_company` with full financials and filings
2. **Financial trends** -- `edgar_trends` for revenue, net income, and EPS over 5 years
3. **Risk factors** -- `edgar_read` extracts Item 1A from the latest 10-K
4. **Recent events** -- `edgar_read` checks the latest 8-K for material events
5. **Insider activity** -- `edgar_ownership` reviews recent Form 4 transactions
6. **Synthesis** -- business overview, financial health, key risks, insider sentiment

## Earnings Analysis

*"Analyze Microsoft's recent earnings"*

Claude walks through:

1. **Latest earnings** -- `edgar_read` finds the most recent earnings 8-K
2. **Financial trends** -- `edgar_trends` for revenue, net income, EPS, and gross profit (annual and quarterly)
3. **Peer comparison** -- `edgar_compare` against 2-3 peer companies
4. **Management commentary** -- `edgar_read` extracts MD&A from the latest 10-K/10-Q
5. **Synthesis** -- growth trends, margin analysis, peer performance, management outlook

## Industry Overview

*"Give me an overview of the semiconductor industry"*

Claude walks through:

1. **Screen companies** -- `edgar_screen` discovers companies in the sector
2. **Top players** -- selects the 3-5 largest companies from results
3. **Comparative analysis** -- `edgar_compare` on revenue, net income, margins, and assets
4. **Growth trends** -- `edgar_trends` for the top 2-3 sector leaders
5. **Recent activity** -- `edgar_monitor` checks for recent filings from sector companies
6. **Synthesis** -- landscape, comparative performance, growth dynamics, recent events

## Insider Monitor

*"Track insider activity at Tesla"*

Claude walks through:

1. **Company context** -- `edgar_company` for company profile
2. **Insider transactions** -- `edgar_ownership` pulls recent Form 4 filings
3. **Financial context** -- `edgar_trends` for revenue, net income, and EPS
4. **Recent filings** -- `edgar_monitor` checks for very recent Form 4 filings
5. **Synthesis** -- who is buying/selling, patterns, alignment with financials, notable transactions

## Fund Analysis

*"Deep dive into SPY"*

Claude walks through:

1. **Fund lookup** -- `edgar_fund` gets fund hierarchy (company, series, share classes, tickers)
2. **Portfolio holdings** -- `edgar_fund` retrieves current holdings, top positions, sector concentration
3. **Money market check** -- if applicable, gets yield data, WAM/WAL, and share class details
4. **Top holdings analysis** -- `edgar_company` for the top 3-5 portfolio holdings
5. **Related funds** -- `edgar_fund` searches for other funds in the same family
6. **Synthesis** -- overview, composition, concentration, key metrics, related funds

## Filing Comparison

*"Compare Apple's 10-K filings year over year"*

Claude walks through:

1. **Company profile** -- `edgar_company` for context
2. **Latest filing** -- `edgar_read` extracts business, risk factors, and MD&A
3. **Previous filing** -- `edgar_search` finds the prior year's filing, `edgar_read` extracts same sections
4. **Financial trends** -- `edgar_trends` for revenue, net income, EPS, and assets
5. **Recent events** -- `edgar_read` checks for 8-Ks between the two filing periods
6. **Synthesis** -- business changes, new/removed risks, MD&A tone shifts, financial trajectory

For cross-company comparison, add a second company: *"Compare Apple's 10-K to Microsoft's 10-K"*

## Activist Tracking

*"Track activist investors at Disney"*

Claude walks through:

1. **Company profile** -- `edgar_company` for financial and governance context
2. **SC 13D filings** -- `edgar_read` finds activist ownership filings (>5% with intent to influence)
3. **SC 13G filings** -- `edgar_read` finds passive large holder filings
4. **Proxy context** -- `edgar_proxy` for executive compensation and governance data
5. **Full-text search** -- `edgar_text_search` for activist-related mentions
6. **Insider activity** -- `edgar_ownership` checks insider trading around activist events
7. **Synthesis** -- active 13D filers, passive holders, governance posture, timeline, outlook

---

## Your First 10 Minutes

After [setting up the MCP server](mcp-setup.md), try these three prompts to see the tools in action:

### 1. Company snapshot

> *"Tell me about Nvidia -- profile and recent financials"*

Claude calls `edgar_company` and returns:

```json
{
  "company": "NVIDIA CORP",
  "profile": {
    "industry": "Semiconductors & Related Devices",
    "exchanges": ["Nasdaq"],
    "shares_outstanding": 24300000000
  },
  "financials": {
    "periods": 4,
    "period_type": "annual",
    "income_statement": "FY 2026 | FY 2025 | FY 2024 | FY 2023 ..."
  }
}
```

**What to look for:** Revenue figures and filing dates. These are live from EDGAR, not Claude's training data. If you see current fiscal years, it's working.

### 2. Live filings

> *"What 8-K filings were submitted to the SEC in the last hour?"*

Claude calls `edgar_monitor` and returns:

```json
{
  "filings": [
    {"form": "8-K", "filed": "2026-03-26", "company": "Haymaker Acquisition Corp. 4"},
    {"form": "8-K", "filed": "2026-03-26", "company": "GUOCHUN INTERNATIONAL INC."},
    {"form": "8-K", "filed": "2026-03-26", "company": "Quoin Pharmaceuticals, Ltd."}
  ]
}
```

**What to look for:** Today's date in the `filed` field. These are filings that just hit the SEC's servers.

### 3. Executive compensation

> *"What is Apple's CEO compensation?"*

Claude calls `edgar_proxy` and returns:

```json
{
  "company": "Apple Inc.",
  "ceo": {"name": "Mr. Cook", "total_comp": 74294811, "actually_paid": 108423733},
  "pay_vs_performance": {"company_tsr": 233.88, "peer_tsr": 279.51},
  "performance_measures": ["Net Sales", "Operating Income", "Relative TSR"]
}
```

**What to look for:** Structured compensation data extracted from XBRL-tagged proxy statements -- not scraped text.

!!! tip "Be specific about using EDGAR"
    If Claude answers from its training data instead of calling tools, be explicit: *"Using your SEC tools, check EDGAR for..."*
