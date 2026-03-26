# MCP Tools Reference

The EdgarTools MCP server provides 13 tools organized by intent -- what you actually want to do, not how APIs are structured.

| Tool | What it does |
|------|-------------|
| [edgar_company](#edgar_company) | Company profile, financials, filings, and ownership |
| [edgar_search](#edgar_search) | Find companies or filings by metadata |
| [edgar_screen](#edgar_screen) | Filter companies by industry, exchange, or state |
| [edgar_text_search](#edgar_text_search) | Full-text search across filing content |
| [edgar_monitor](#edgar_monitor) | Live SEC filing feed |
| [edgar_filing](#edgar_filing) | Parse any filing into structured data |
| [edgar_read](#edgar_read) | Extract specific sections from a filing |
| [edgar_notes](#edgar_notes) | Drill into notes and disclosures |
| [edgar_trends](#edgar_trends) | Financial time series with growth rates |
| [edgar_compare](#edgar_compare) | Side-by-side company comparison |
| [edgar_ownership](#edgar_ownership) | Insider transactions and institutional portfolios |
| [edgar_fund](#edgar_fund) | Mutual fund, ETF, BDC, and money market fund data |
| [edgar_proxy](#edgar_proxy) | Executive compensation and governance |

---

## Discover

### edgar_company

Start here for any company question. Returns profile, financials, recent filings, and ownership in one call.

| Parameter | Description |
|-----------|-------------|
| `identifier` | Ticker, CIK, or company name (required) |
| `include` | Sections to return: `profile`, `financials`, `filings`, `ownership` (default: profile, financials, filings) |
| `periods` | Number of financial periods (default: 4) |
| `period` | `annual` (default), `quarterly`, or `ttm` (trailing twelve months) |

**Try asking Claude:**

- "Show me Apple's profile and latest financials"
- "Get Microsoft's recent filings and ownership data"

### edgar_search

Search for companies or filings by metadata.

| Parameter | Description |
|-----------|-------------|
| `query` | Search keywords |
| `search_type` | `companies`, `filings`, or `all` (default: `all`) |
| `identifier` | Limit to a specific company |
| `form` | Filter by form type (e.g., `10-K`, `8-K`) |
| `limit` | Max results (default: 10) |

**Try asking Claude:**

- "Search for semiconductor companies"
- "Find Apple's 10-K filings"

### edgar_screen

Discover companies by industry, exchange, or state. Uses local reference data -- zero API calls.

| Parameter | Description |
|-----------|-------------|
| `industry` | Industry keyword |
| `sic` | Exact SIC code (integer) |
| `exchange` | Exchange name (e.g., `NYSE`, `Nasdaq`) |
| `state` | State of incorporation (2-letter code) |
| `limit` | Max results (default: 25) |

**Try asking Claude:**

- "Find pharmaceutical companies on NYSE"
- "What software companies are in Delaware?"

### edgar_text_search

Full-text search across SEC filing content via the SEC's EFTS (full-text search) system. Different from `edgar_search`, which searches metadata.

| Parameter | Description |
|-----------|-------------|
| `query` | Search text (required) |
| `identifier` | Limit to a specific company |
| `forms` | Filter by form types (e.g., `["8-K", "10-K"]`) |
| `start_date` | Start date filter |
| `end_date` | End date filter |

**Try asking Claude:**

- "Search for filings mentioning artificial intelligence"
- "Find 8-K filings about cybersecurity incidents"

### edgar_monitor

See what was filed with the SEC in the last few minutes. No other financial data MCP server offers this.

| Parameter | Description |
|-----------|-------------|
| `form` | Filter by form type (e.g., `8-K`, `4`) |
| `limit` | Max results (default: 20) |

**Try asking Claude:**

- "What SEC filings were just submitted?"
- "Show me recent 8-K filings"

---

## Examine

### edgar_filing

Parse any filing into a structured object. If the filing has a typed data object (10-K, 10-Q, 8-K, Form 4, 13F, DEF 14A, etc.), returns extracted financials, transactions, sections, or holdings.

Two ways to specify the filing:

1. **By company + form**: `identifier="AAPL"`, `form="10-K"` (gets the latest)
2. **By accession number or URL**: `input="0000320193-23-000077"`

| Parameter | Description |
|-----------|-------------|
| `identifier` | Ticker, CIK, or name (used with `form`) |
| `form` | Form type: `10-K`, `10-Q`, `8-K`, `DEF 14A`, `4`, `13F-HR`, etc. |
| `input` | Accession number or SEC URL (alternative to identifier + form) |
| `detail` | `minimal`, `standard` (default), or `full` |

**Try asking Claude:**

- "Show me Apple's latest 10-K"
- "What's in filing 0000320193-23-000077?"

### edgar_read

Extract specific sections from a filing. Use `edgar_filing` first to identify the filing, then `edgar_read` to get its content.

Available sections vary by form type:

| Form | Sections |
|------|----------|
| 10-K / 10-Q | `business`, `risk_factors`, `mda`, `financials`, `controls`, `legal` |
| 20-F | `business`, `risk_factors`, `mda`, `financials`, `directors`, `shareholders`, `controls` |
| 8-K | `items`, `press_release`, `earnings` |
| DEF 14A | `compensation`, `pay_performance`, `governance` |
| SC 13D / 13G | `ownership`, `purpose` |
| 13F-HR | `holdings`, `summary` |

| Parameter | Description |
|-----------|-------------|
| `accession_number` | Filing accession number |
| `identifier` | Company ticker/CIK (alternative -- gets most recent filing) |
| `form` | Form type (used with `identifier`) |
| `sections` | Sections to extract. Use `summary` for metadata, `all` for everything. |

**Try asking Claude:**

- "Show me the risk factors from Apple's latest 10-K"
- "Get the MD&A section from Tesla's most recent annual report"
- "Read the CEO compensation from Microsoft's proxy statement"

### edgar_notes

Drill into the notes and disclosures behind financial statement numbers. Use this when you need to explain *why* a number is what it is -- debt terms, revenue recognition policies, lease schedules, contingencies.

| Parameter | Description |
|-----------|-------------|
| `identifier` | Ticker, CIK, or name (required) |
| `topic` | Note topic: `debt`, `revenue`, `leases`, `contingencies`, etc. Omit for table of contents. |
| `form` | Filing form type (default: `10-K`). Use `10-Q` for quarterly notes. |
| `detail` | `minimal` (titles only), `standard` (context + tables), or `full` (includes DataFrame data) |

**Try asking Claude:**

- "What does Apple's debt note say?"
- "Show me Tesla's revenue recognition policy"

---

## Analyze

### edgar_trends

Financial time series with year-over-year and quarter-over-quarter growth rates. XBRL-sourced.

| Parameter | Description |
|-----------|-------------|
| `identifier` | Ticker, CIK, or name (required) |
| `concepts` | Metrics to track: `revenue`, `net_income`, `eps`, `gross_profit`, `assets`, etc. |
| `periods` | Number of periods (default: 8) |
| `period` | `annual` (default) or `quarterly` |
| `include_growth` | Include YoY/QoQ growth rates and CAGR (default: true) |

**Try asking Claude:**

- "Show me Apple's revenue trend over 8 years"
- "What is Microsoft's EPS growth trajectory?"

### edgar_compare

Compare companies side-by-side or analyze an industry.

| Parameter | Description |
|-----------|-------------|
| `identifiers` | List of tickers/CIKs to compare |
| `industry` | Alternative: industry name (auto-selects peers) |
| `metrics` | Metrics: `revenue`, `net_income`, `gross_profit`, `operating_income`, `assets`, `liabilities`, `equity`, `margins`, `growth` |
| `periods` | Number of periods (default: 3) |
| `annual` | Annual (default: true) or quarterly |
| `limit` | Max companies for industry comparison (default: 5) |

**Try asking Claude:**

- "Compare Apple, Microsoft, and Google on revenue and net income"
- "How do the top semiconductor companies compare?"

### edgar_ownership

Insider transactions (Form 4) or institutional portfolios (13F).

| Parameter | Description |
|-----------|-------------|
| `identifier` | Ticker, CIK, or fund CIK (required) |
| `analysis_type` | `insiders`, `fund_portfolio`, or `portfolio_diff` (required) |
| `limit` | Max results (default: 20) |

**Try asking Claude:**

- "Show me recent insider transactions at Apple"
- "What stocks does Berkshire Hathaway hold?"
- "How did Bridgewater's portfolio change last quarter?"

### edgar_fund

Mutual funds, ETFs, BDCs, and money market funds -- lookup, search, portfolio holdings, and yields.

| Parameter | Description |
|-----------|-------------|
| `action` | `lookup`, `search`, `portfolio`, `money_market`, `bdc_search`, or `bdc_portfolio` (required) |
| `identifier` | Fund ticker, series ID, or CIK |
| `query` | Search text for fund or BDC name |
| `limit` | Max results (default: 20) |

**Try asking Claude:**

- "Look up the Vanguard 500 Index Fund"
- "Show me SPY's portfolio holdings"
- "What money market funds does Fidelity offer?"

### edgar_proxy

Executive compensation and pay-vs-performance from DEF 14A proxy statements.

| Parameter | Description |
|-----------|-------------|
| `identifier` | Ticker, CIK, or name (required) |
| `filing_index` | Which proxy filing, 0=latest (default: 0) |

**Try asking Claude:**

- "What is Apple's CEO compensation?"
- "Show me Microsoft's pay vs performance data"

---

## Common Workflows

These patterns chain tools together for complete analyses:

**Company research:**
`edgar_company` → `edgar_read` (10-K sections) → `edgar_trends`

**Filing analysis:**
`edgar_filing` (by accession or URL) → `edgar_read` (extract sections)

**Event monitoring:**
`edgar_monitor` → `edgar_filing` (examine new filings)

**Peer comparison:**
`edgar_screen` (find peers) → `edgar_compare` (compare metrics)

For pre-built multi-step analysis workflows, see [Workflows](mcp-workflows.md).
