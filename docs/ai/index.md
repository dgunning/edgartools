# AI Integration

EdgarTools gives AI agents direct access to every SEC filing, financial statement, and company disclosure. No API key, no paywall, no setup beyond a few lines of config.

## See It in Action

Once connected, you just talk to Claude. No special syntax. No tool names to memorize.

---

**"What is Apple's CEO compensation?"**

Claude returns structured data from Apple's latest proxy statement -- in 0.3 seconds:

```json
{
  "company": "Apple Inc.",
  "form": "DEF 14A",
  "ceo": {"name": "Mr. Cook", "total_comp": 74294811, "actually_paid": 108423733},
  "pay_vs_performance": {"company_tsr": 233.88, "peer_tsr": 279.51, "net_income": 112010000000}
}
```

---

**"Compare Apple, Microsoft, and Google on revenue and margins"**

Claude pulls XBRL financials for all three and computes margins side-by-side:

```json
{
  "companies": [
    {"name": "Apple Inc.",      "revenue": 416161000000, "net_margin": "26.9%", "gross_margin": "46.9%"},
    {"name": "MICROSOFT CORP",  "revenue": 375000000000, "net_margin": "27.2%", "gross_margin": "69.9%"},
    {"name": "Alphabet Inc.",   "revenue": 405640000000, "net_margin": "27.8%", "gross_margin": "58.3%"}
  ]
}
```

---

**"Show me what 8-Ks were filed in the last hour"**

Claude queries the SEC's live filing feed -- these are filings from *today*:

```json
{
  "filings": [
    {"form": "8-K", "filed": "2026-03-26", "company": "Haymaker Acquisition Corp. 4"},
    {"form": "8-K", "filed": "2026-03-26", "company": "GUOCHUN INTERNATIONAL INC."},
    {"form": "8-K", "filed": "2026-03-26", "company": "Quoin Pharmaceuticals, Ltd."}
  ]
}
```

---

**"What does Apple's debt note say?"**

Claude drills into the notes behind the balance sheet -- which line items the note explains, structured tables, and the narrative:

```json
{
  "notes": [{
    "number": 9,
    "title": "Debt",
    "expands": ["Commercial paper", "Term debt"],
    "expands_statements": ["BalanceSheet", "CashFlowStatement"],
    "context": "The Company issues unsecured short-term promissory notes pursuant to a commercial paper program..."
  }]
}
```

## Two Ways to Use AI with EdgarTools

| I want to... | Use | Setup time |
|--------------|-----|------------|
| **Ask Claude questions** about companies, filings, and financials | [MCP Server](mcp-setup.md) | 2 minutes |
| **Have Claude write EdgarTools code** using best practices | [Skills](skills.md) | 1 minute |
| **Both** | Install both -- they complement each other | 3 minutes |

### MCP Server

The [Model Context Protocol](https://modelcontextprotocol.io/) server gives Claude (and any MCP-compatible client) 13 tools for SEC data -- organized around what you actually want to do, not how APIs are structured. No code required.

- **Discover**: Find companies, screen by industry, monitor live filings
- **Examine**: Parse any filing into structured data, extract specific sections, drill into notes
- **Analyze**: Financial trends, peer comparisons, insider transactions, fund portfolios

[Set up the MCP Server →](mcp-setup.md){ .md-button } [Browse all 13 tools →](mcp-tools.md){ .md-button }

### Skills

Skills are structured documentation packages that teach Claude how to write better EdgarTools code. They guide Claude to use the right APIs, avoid common mistakes, and follow best practices.

Without skills, Claude might write verbose code using low-level APIs:

```python
# Without skills -- verbose, fragile
facts = company.get_facts()
income = facts.income_statement(periods=1, annual=True)
if income is not None and not income.empty:
    if 'Revenue' in income.columns:
        revenue = income['Revenue'].iloc[0]
```

With skills, Claude writes idiomatic code:

```python
# With skills -- clean, correct
financials = company.get_financials()
revenue = financials.get_revenue()
```

[Install Skills →](skills.md){ .md-button }

## What Makes This Different

**Free.** SEC EDGAR is a public resource. EdgarTools is MIT-licensed open source. No intermediary extracting rent.

**No API key.** No signup form. No OAuth flow. Set your `EDGAR_IDENTITY` and go.

**Live data.** The live filing monitor gives you what's being filed *right now*. Most services give you yesterday's data.

**Structured, not raw.** When Claude parses a 10-K, it gets a typed object with extracted financials, notes, and sections -- not raw HTML.

**Intent-based tools.** "Tell me about Apple" is one tool call, not five.

## Built-in AI Features

These work without the `[ai]` extra -- they're part of the core library.

### .docs Property

Every major EdgarTools object has a `.docs` property with searchable API documentation:

```python
from edgar import Company

company = Company("AAPL")
company.docs                       # Full API reference
company.docs.search("financials")  # Search for specific topics
```

Available on: `Company`, `Filing`, `Filings`, `XBRL`, `Statement`

### to_context()

`to_context()` produces token-efficient structured text for LLM context windows. All financial objects support it, with a `detail` parameter that controls verbosity.

```python
from edgar import Company

company = Company("MSFT")
financials = company.get_financials()

# Control token budget
financials.income_statement().to_context('minimal')    # ~100 tokens: entity + period + line item count
financials.income_statement().to_context('standard')   # ~300 tokens (default): adds key line items
financials.income_statement().to_context('full')       # ~500+ tokens: all rows
```

The same pattern works for notes:

```python
tenk = company.get_filings(form="10-K").latest().obj()
notes = tenk.notes

notes.to_context('minimal')                          # note titles only
notes.to_context('standard')                        # + tables + narrative excerpt
notes['Debt'].to_context('full')                    # everything for one note
```

**Objects with `to_context()`:**

| Object | `detail` levels | Notes |
|--------|----------------|-------|
| `Statement` | minimal / standard / full | Key line items at standard+ |
| `Note` | minimal / standard / full | Tables + narrative + policies |
| `Notes` | minimal / standard / full | `focus=` param filters to relevant notes |
| `RenderedStatement` | minimal / standard / full | Same as Statement |
| `FilingViewer` | standard / full | SEC viewer navigation context |
| `NonAccrualResult` | minimal / standard / full | BDC non-accrual analysis context |

### to_markdown()

`to_markdown()` renders financial data as GitHub-Flavored Markdown. Use it when you want formatted output for RAG retrieval, document stores, or direct inclusion in LLM prompts.

```python
from edgar import Company

company = Company("JPM")
financials = company.get_financials()

# Full income statement as markdown -- company header + GFM table
md = financials.income_statement().to_markdown()

# Minimal: table only, no company header (good for chunking)
md = financials.income_statement().to_markdown(detail='minimal')

# Full: adds source attribution footer
md = financials.income_statement().to_markdown(detail='full')
```

The `optimize_for_llm=True` default removes abstract header rows that have no values, keeping tables compact. Set `optimize_for_llm=False` to preserve the full hierarchy.

**For notes**, `to_markdown()` renders tables and prose together:

```python
tenk = company.get_filings(form="10-K").latest().obj()

# All notes as one markdown document
md = tenk.notes.to_markdown()

# Focus on specific topics (searches note titles)
md = tenk.notes.to_markdown(focus='Debt')
md = tenk.notes.to_markdown(focus=['Debt', 'Revenue'])

# One note
md = tenk.notes['Income Taxes'].to_markdown(detail='full')
```

**Individual line items** include a note reference when available:

```python
stmt = financials.balance_sheet()
goodwill = stmt['Goodwill']
print(goodwill.to_markdown())
# **Goodwill**: 67,886 (2024-09-28), 65,413 (2023-09-30)
#
# > Related: Note 7 — Goodwill and Intangible Assets
```

**Objects with `to_markdown()`:**

| Object | `detail` levels | Key options |
|--------|----------------|-------------|
| `Statement` | minimal / standard / full | `optimize_for_llm=True` |
| `RenderedStatement` | minimal / standard / full | `optimize_for_llm=True` |
| `Note` | minimal / standard / full | `optimize_for_llm=True` |
| `Notes` | minimal / standard / full | `focus=` to filter notes |
| `StatementLineItem` | n/a | `include_note=True` |

### Choosing Between to_context() and to_markdown()

Use `to_context()` when you want **navigation context** -- the LLM needs to understand what's available and where values come from. It uses a compact key-value format and includes discovery hints like "AVAILABLE ACTIONS".

Use `to_markdown()` when you want **content** -- the actual numbers and text in a format suitable for display, storage, or retrieval. It produces standard GFM tables that most LLMs render correctly.

For RAG pipelines:

- Chunk and embed `to_markdown()` output to represent financial statement content
- Use `to_context()` for the system prompt when you want the LLM to understand document structure before receiving retrieved chunks
- `Notes.to_markdown(focus='Debt')` is effective for retrieval because it co-locates related tables and narrative

### compare_context()

`FilingViewer.compare_context()` generates an LLM-ready prompt comparing the SEC's own viewer rendering against your XBRL parser output. This is useful for validating that parsed statements match the authoritative SEC display.

```python
from edgar import Company

filing = Company("GS").get_filings(form="10-K").latest()
viewer = filing.viewer()
xbrl = filing.xbrl()

# Get a comparison prompt for the balance sheet
prompt = viewer.compare_context(xbrl, statement='balance_sheet')

# Pass to an LLM for validation
# The prompt includes both renderings side by side with instructions
# to flag any discrepancies in values, labels, or ordering
print(prompt[:500])
```

Available statements: `'balance_sheet'`, `'income_statement'`, `'cashflow_statement'`, `'comprehensive_income'`.

The SEC viewer is treated as the authoritative source. The prompt instructs the LLM to flag anything in the XBRL output that differs.
