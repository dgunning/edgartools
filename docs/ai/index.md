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

### .to_context() Method

Token-efficient output optimized for LLM context windows:

```python
company = Company("AAPL")

# Control detail level
company.to_context(detail='minimal')    # ~100 tokens
company.to_context(detail='standard')   # ~300 tokens (default)
company.to_context(detail='full')       # ~500 tokens

# Hard token limit
company.to_context(max_tokens=200)
```

Available on: `Company`, `Filing`, `Filings`, `XBRL`, `Statement`, and most data objects.
