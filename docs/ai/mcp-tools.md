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

??? example "Example response"

    ```json
    {
      "company": "NVIDIA CORP",
      "profile": {
        "tickers": ["NVDA"],
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

??? example "Example response"

    ```json
    {
      "filings": [
        {"accession_number": "0001104659-26-034967", "form": "8-K", "filed": "2026-03-26", "company": "Haymaker Acquisition Corp. 4"},
        {"accession_number": "0001765048-26-000002", "form": "8-K", "filed": "2026-03-26", "company": "GUOCHUN INTERNATIONAL INC."},
        {"accession_number": "0001104659-26-034951", "form": "8-K", "filed": "2026-03-26", "company": "Quoin Pharmaceuticals, Ltd."}
      ],
      "count": 3,
      "form_filter": "8-K"
    }
    ```

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

??? example "Example response"

    ```json
    {
      "accession_number": "0000320193-25-000079",
      "form": "10-K",
      "company": "Apple Inc.",
      "filed": "2025-10-31",
      "data_object_type": "TenK",
      "context": "Revenue: $416.2B | Net Income: $112.0B | Total Assets: $359.2B\n\nSECTIONS: Item 1, Item 1A, Item 1B, Item 1C, Item 2, Item 3, ..."
    }
    ```

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
| `accession_number` | Filing accession number. Takes precedence over `period`. |
| `identifier` | Company ticker/CIK (alternative -- selects the latest ORIGINAL filing; amendments (`/A`) are only reachable by `accession_number`) |
| `form` | Form type. Required whenever `identifier` is given. |
| `period` | Reporting period (`YYYY-MM-DD`) that must exactly match the chosen filing's `period_of_report`. Requires `identifier` and `form`. |
| `sections` | Sections to extract. Use `summary` for metadata, `all` for everything. With a `cursor`, must be exactly the one section being continued. |
| `cursor` | Continuation cursor from a previous response's `section_pages.<section>.next_cursor`, to fetch the next page of that one section. |

**Try asking Claude:**

- "Show me the risk factors from Apple's latest 10-K"
- "Get the MD&A section from Tesla's most recent annual report"
- "Read the CEO compensation from Microsoft's proxy statement"
- "Read ARCC's MD&A for the quarter ended 2026-06-30" -- `identifier="ARCC", form="10-Q", period="2026-06-30", sections=["mda"]`

Each requested section is capped at one page of text; a truncated section's `section_pages.<section>` block carries a `next_cursor` -- pass it back as `cursor` with `sections` set to that SAME single section name to read the rest.

### edgar_notes

Drill into the notes and disclosures behind financial statement numbers. Use this when you need to explain *why* a number is what it is -- debt terms, revenue recognition policies, lease schedules, contingencies.

| Parameter | Description |
|-----------|-------------|
| `identifier` | Ticker, CIK, or name. Optional when `accession_number` is given. |
| `topic` | Note topic: `debt`, `revenue`, `leases`, `contingencies`, etc. Omit for table of contents. |
| `form` | Filing form type (default: `10-K`). Use `10-Q` for quarterly notes. |
| `detail` | `minimal` (titles only), `standard` (context + tables), or `full` (includes DataFrame data) |
| `accession_number` | Exact accession number pinning a specific filing. Takes precedence over `period`. |
| `period` | Reporting period (`YYYY-MM-DD`) that must exactly match the chosen filing's `period_of_report`. |
| `cursor` | Continuation cursor from a previous response's table/context `next_cursor`. Must be passed together with the SAME `topic` (and, for a note's context, the same `detail`) the original call used, or it is rejected as `CURSOR_MISMATCH`. |
| `limit` | Max table rows per page (default 20, max 50). |

**Try asking Claude:**

- "What does Apple's debt note say?"
- "Show me Tesla's revenue recognition policy"
- "What does ARCC's debt note say for the quarter ended 2026-06-30?" -- `topic="debt", identifier="ARCC", form="10-Q", period="2026-06-30"`

??? example "Example response"

    ```json
    {
      "company": "Apple Inc. [AAPL]",
      "total_notes": 16,
      "topic": "debt",
      "notes": [{
        "number": 9,
        "title": "Debt",
        "expands": ["Commercial paper", "Term debt"],
        "expands_statements": ["BalanceSheet", "CashFlowStatement"],
        "tables": [{"title": "Debt (Tables)"}],
        "context": "NOTE 9: Debt\n\nCommercial Paper\n\nThe Company issues unsecured short-term promissory notes..."
      }]
    }
    ```

A matched note's table rows and narrative `context` text are each capped per page; when more remains, that block carries a `next_cursor` to continue reading that one table or context.

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

??? example "Example response"

    ```json
    {
      "company": "MICROSOFT CORP",
      "period_type": "annual",
      "trends": {
        "revenue": {
          "values": [
            {"value": 375000000000, "period": "2025"},
            {"value": 245122000000, "period": "2024"},
            {"value": 211915000000, "period": "2023"}
          ],
          "growth_rates": [
            {"period": "2025", "growth": "53.0%"},
            {"period": "2024", "growth": "15.7%"}
          ],
          "cagr": "33.0%"
        }
      }
    }
    ```

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

??? example "Example response"

    ```json
    {
      "companies": [
        {"identifier": "AAPL", "name": "Apple Inc.", "metrics": {"revenue": 416161000000, "net_margin": "26.9%", "gross_margin": "46.9%"}},
        {"identifier": "MSFT", "name": "MICROSOFT CORP", "metrics": {"revenue": 375000000000, "net_margin": "27.2%", "gross_margin": "69.9%"}},
        {"identifier": "GOOGL", "name": "Alphabet Inc.", "metrics": {"revenue": 405640000000, "net_margin": "27.8%", "gross_margin": "58.3%"}}
      ]
    }
    ```

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

Mutual funds, ETFs, BDCs, and money market funds -- lookup, search, portfolio holdings, yields, and (for BDCs) filing-scoped Schedule of Investments and non-accrual evidence.

| Parameter | Description |
|-----------|-------------|
| `action` | `lookup`, `search`, `portfolio`, `money_market`, `bdc_search`, `bdc_portfolio`, or `bdc_nonaccrual` (required) |
| `identifier` | Fund ticker, series ID, or CIK. BDC actions only: optional when `accession_number` is given. |
| `query` | Search text for fund or BDC name |
| `limit` | Max results per page (default 20, max 50) |
| `accession_number` | BDC actions only. Exact SEC accession number pinning a specific filing. Takes precedence over `period`. |
| `form` | BDC actions only. `10-K` (default) or `10-Q`. |
| `period` | BDC actions only. Reporting period (`YYYY-MM-DD`) that must exactly match the chosen filing's `period_of_report`. |
| `borrower` | BDC actions only. Case-insensitive substring filter on the portfolio company/borrower name (or raw investment identifier). |
| `cursor` | Continuation cursor from a previous `bdc_portfolio`/`bdc_nonaccrual` response's `page.next_cursor`, to fetch the next page. |
| `include_untyped` | BDC actions only. Include investments with an unrecognized classification (default false). |

**Try asking Claude:**

- "Look up the Vanguard 500 Index Fund"
- "Show me SPY's portfolio holdings"
- "What money market funds does Fidelity offer?"
- "Show me ARCC's loan portfolio for the quarter ended 2026-06-30"
- "Which of ARCC's investments are on non-accrual?"

#### Credit evidence (BDC loans)

`bdc_portfolio` and `bdc_nonaccrual` return evidence from exactly ONE chosen filing's Schedule of Investments. Pick the filing with `accession_number`, or `identifier` + `form` + `period`; with neither `accession_number` nor `period`, the latest original (non-amendment) filing of `form` is used.

```
# Latest 10-K, all extracted holdings
action="bdc_portfolio", identifier="ARCC"

# A specific quarter
action="bdc_portfolio", identifier="ARCC", form="10-Q", period="2026-06-30"

# A specific filing, no identifier needed
action="bdc_portfolio", accession_number="0001628280-26-050307"

# Filter to one borrower
action="bdc_portfolio", identifier="ARCC", borrower="Ivy Hill"

# Next page (limit clamps to 50 rows/page)
action="bdc_portfolio", identifier="ARCC", cursor="<page.next_cursor from the previous call>"

# Non-accrual evidence for the same filing
action="bdc_nonaccrual", identifier="ARCC", form="10-Q", period="2026-06-30"
```

`bdc_portfolio` response blocks:

- `source` -- provenance: `cik`, `entity`, `form`, `accession_number`, `period_of_report`, `filed`, `url`, `is_amendment`, `selected_by` (`"accession"`, `"period"`, or `"latest"`)
- `page` -- `offset`, `returned`, `total_matching`, `total_extracted`, `remaining`, `next_cursor`
- `extraction` -- `method`, `field_coverage` (fraction of holdings with each field populated), `rate_convention: "decimal_fraction"`, and the extraction's own stated `limitation`
- `filtered_totals` -- present only when `borrower` is given: `count`/`fair_value`/`cost` for the matching subset, kept separate from the filing-wide `total_investments`/`total_fair_value`/`total_cost`

`bdc_nonaccrual` additionally returns `evidence_level` (`"investment"` when individual non-accrual investments were resolved, `"aggregate"` when only a portfolio-level rate/value was disclosed, or `"none"`), `warnings`, and `interpretation_limits` -- read `interpretation_limits` before treating the result as a default list: non-accrual is an accounting status (interest income no longer recognized), not a legal default determination, and absence from the list does not establish that a loan is performing.

Measured 2026-09-28: ARCC's 10-Q for the quarter ended 2026-06-30 (accession `0001628280-26-050307`) has 1,481 extracted holdings, all reachable page by page via `cursor`, and 32 investments identified as non-accrual from its footnote disclosure.

Comparing periods (e.g. did non-accrual grow quarter over quarter) is the caller's job -- call `bdc_portfolio`/`bdc_nonaccrual` once per period and diff the results yourself.

#### BDC and filing-selection error codes

| Code | Meaning |
|------|---------|
| `PERIOD_NOT_FOUND` | No original filing of the requested `form` matches `period` exactly. `suggestions` lists available periods, most recent first. |
| `SELECTION_MISMATCH` | `accession_number` was given together with an `identifier` whose CIK differs from the accession's filer. |
| `FILING_NOT_FOUND` | No filing could be resolved for the given selector. |
| `COMPANY_NOT_FOUND` | `identifier` did not resolve to a company or BDC. |
| `AMBIGUOUS_BDC` | `identifier` (a name) matched more than one BDC; `suggestions` lists the candidates by name/ticker/CIK. |
| `NOT_A_BDC` | The resolved company/CIK is not a Business Development Company. |
| `NO_XBRL` | The chosen filing has no XBRL data at all. |
| `INVALID_ARGUMENTS` | A required parameter is missing, e.g. neither `identifier` nor `accession_number`. |
| `CURSOR_MISMATCH` | The cursor's tool/accession/document/query don't match the current call. |
| `CURSOR_STALE` | The cursor is well-formed but the underlying result changed since it was issued. |
| `INVALID_CURSOR` | The cursor could not be decoded, or exceeds the 2,048-character cap. |

The filing-selection codes (`PERIOD_NOT_FOUND`, `SELECTION_MISMATCH`, `FILING_NOT_FOUND`, `COMPANY_NOT_FOUND`) and the cursor codes (`CURSOR_MISMATCH`, `CURSOR_STALE`, `INVALID_CURSOR`) apply identically to `edgar_notes` and `edgar_read`.

### edgar_proxy

Executive compensation and pay-vs-performance from DEF 14A proxy statements.

| Parameter | Description |
|-----------|-------------|
| `identifier` | Ticker, CIK, or name (required) |
| `filing_index` | Which proxy filing, 0=latest (default: 0) |

**Try asking Claude:**

- "What is Apple's CEO compensation?"
- "Show me Microsoft's pay vs performance data"

??? example "Example response"

    ```json
    {
      "company": "Apple Inc.",
      "form": "DEF 14A",
      "filing_date": "2026-01-08",
      "ceo": {"name": "Mr. Cook", "total_comp": 74294811, "actually_paid": 108423733},
      "neo_average": {"total_comp": 23812358, "actually_paid": 34125743},
      "pay_vs_performance": {"company_tsr": 233.88, "peer_tsr": 279.51, "net_income": 112010000000},
      "performance_measures": ["Net Sales", "Operating Income", "Relative TSR"]
    }
    ```

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

**Credit evidence (BDC loans):**
`edgar_fund` (`bdc_search`) → `edgar_search`/`edgar_company` (list 10-K/10-Q filings with periods) → `edgar_fund` (`bdc_portfolio`, with `period` + `borrower`) → `edgar_fund` (`bdc_nonaccrual`) → `edgar_notes`/`edgar_read` (same `period`, for narrative context). Continue any of these with the `cursor` from a `next_cursor` field; comparing periods is the caller's job.

For pre-built multi-step analysis workflows, see [Workflows](mcp-workflows.md).
