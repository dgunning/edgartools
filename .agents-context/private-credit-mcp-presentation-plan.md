# Private Credit Evidence Access: Presentation Plan

**Format:** 3 slides, approximately 4 minutes  
**Audience:** Private credit business and product stakeholders  
**Narrative:** The credit questions → the evidence interface → the foundation and development tools  
**Status:** EdgarTools and its MCP exist today. The private credit enhancements below are proposed in the agreed functional spec.

## Slide 1 — Better evidence for two critical lending questions

**Main message:** Help private credit firms investigate repayment concerns earlier and understand the protections behind their loans.

### On-slide content

| Will we get paid? | What protects us if we do not? |
|---|---|
| Warning signs are scattered across lenders’ filings and footnotes. | Collateral, guarantees and repayment priority are described in agreements and amendments. |
| Analysts need borrower-level loan values, payment terms and disclosed non-accrual evidence. | Analysts need the correct documents and relevant provisions in context. |
| **Value:** Focus attention sooner and preserve time to investigate or intervene. | **Value:** Make better-informed decisions about loan size, terms and potential losses. |

**Shared problem:** Too much manual work finding the right evidence and confirming its source.

**Footer:** Public SEC evidence complements the confidential information lenders already receive.

### Visual direction

Two equal columns, each led by its lending question. A single evidence-retrieval bar underneath connects both to the shared problem.

### Speaker notes

- A large credit loss can erase interest income from many successful loans. The value is better-supported decisions and less document research, not a promise to predict defaults.
- Business development companies (BDCs) disclose investments in private businesses, creating a public window into some private loans.
- Non-accrual means a lender has stopped recognizing interest income because collection is uncertain. PIK means interest is added to debt rather than paid in cash; it is not automatically a sign of distress.
- Public disclosures are incomplete: one lender’s position is not the borrower’s total debt.

## Slide 2 — MCP connects the analyst’s questions to SEC evidence

**Main message:** The MCP gives an AI assistant a consistent set of tools to find filings, retrieve data and read supporting disclosures.

### On-slide content

**MCP = Model Context Protocol:** the interface through which an AI assistant calls EdgarTools.

| Workflow | Existing tools to emphasize | Private credit relevance |
|---|---|---|
| **Find** | `edgar_search`, `edgar_text_search` | Locate reporting entities, filings and mentions of borrowers or credit topics. |
| **Inspect** | `edgar_fund`, `edgar_filing`, `edgar_notes`, `edgar_read` | Explore BDC holdings, financial disclosures and filing content. |
| **Add context** | `edgar_company`, `edgar_trends`, `edgar_compare`, `edgar_monitor` | Research reporting companies, peer financials and newly filed information. |

**Proposed private credit enhancements:**

- Retrieve named borrowers, available loan terms and non-accrual evidence from explicitly selected filings.
- Reach all extracted holdings and relevant readable content through filtering and continuation.
- Discover, search and read agreement exhibits with source citations and clear coverage limits.

**Boundary:** MCP retrieves evidence. The analyst or AI compares periods and interprets protections.

### Visual direction

A simple flow: **Analyst question → AI assistant + MCP tools → dated SEC evidence**. Use a distinct “Proposed” strip for enhancements so the audience does not mistake them for shipped capabilities.

### Speaker notes

- The current server registers 13 tools. Keep the slide focused on credit workflows; use this complete inventory as speaking support:

| Tool | Current purpose |
|---|---|
| `edgar_company` | Company profile, financials and filings |
| `edgar_search` | Company and filing discovery |
| `edgar_screen` | Filter companies by industry, exchange or state |
| `edgar_text_search` | Search filing text through SEC full-text search |
| `edgar_monitor` | Retrieve the latest filings feed; not borrower risk alerts |
| `edgar_filing` | Examine a filing’s structured context |
| `edgar_read` | Retrieve selected filing sections |
| `edgar_notes` | Explore financial notes and disclosure tables |
| `edgar_trends` | Financial time series and growth rates |
| `edgar_compare` | Compare reporting-company financial metrics |
| `edgar_ownership` | Insider transactions and institutional holdings |
| `edgar_fund` | Fund data, holdings and BDC portfolios |
| `edgar_proxy` | Executive compensation and governance |

- Several useful credit fields already exist in the Python library but are not surfaced by the BDC MCP action. Exhibit retrieval also needs a dedicated, usable MCP path.
- Historical loan comparisons and legal-term interpretation remain outside the agreed enhancement scope. Existing general financial comparison tools are a separate capability.

## Slide 3 — Build on EdgarTools, extend for private credit

**Main message:** Reuse an established SEC data foundation and focus development on making credit evidence accessible.

### On-slide content

| Foundation | Private credit enhancement | AI development assistants |
|---|---|---|
| **EdgarTools** | **Focused MCP extensions** | **Claude Code + Codex** |
| Python library for SEC filings, company financials, XBRL, reports, funds and documents. | Expose richer loan evidence, precise filing selection, complete retrieval and agreement access. | Assist developers with repository exploration, specifications, coding, review and verification. |
| Existing MCP makes these capabilities available to AI assistants. | Preserve sources, dates and meaningful explanations of missing data. | Support the engineering workflow; SEC filings remain the evidence source. |

**Footer:** Extend the evidence-access layer; credit judgment stays with the analyst or AI using it.

### Visual direction

Show **EdgarTools foundation → proposed private credit capabilities** as the main progression. Place **Claude Code + Codex** in a supporting band below, labelled “Development assistance,” rather than implying they are required runtime components.

### Speaker notes

- EdgarTools already supports broad company and filing research, with underlying BDC and document capabilities relevant to credit.
- The enhancement shifts attention toward a particular borrower, loan and source document, rather than requiring a new credit scoring platform.
- Describe Claude Code and Codex as development assistants. Do not imply that both produced specific changes or that implementation is complete.

## Grounding and presentation guardrails

- [Agreed functional spec](<specs/Private Credit Evidence Access - Functional Spec - 09.28.html>): business rationale, scope and desired outcomes.
- `edgar/ai/mcp/server.py:82–134`: registered tools and stated purposes.
- `edgar/ai/mcp/tools/fund.py:499–621`: current BDC response and limitations.
- `edgar/bdc/investments.py:1304–1321` and `edgar/bdc/nonaccrual.py:135–173,314–357`: existing credit evidence capabilities.
- `edgar/_filings.py:1597–1605,2181–2241`: underlying exhibit and document search access.
- Keep implementation status explicit. Avoid invented coverage, time-saving percentages or claims that the product estimates recoveries or prevents defaults.
