# to_context() Design Guidelines

Standard for making EdgarTools data objects AI-native.

## Purpose

`to_context()` is how an edgartools object introduces itself to an LLM. It answers three questions:

1. **What am I?** — Type, identity, key metadata
2. **What do I contain?** — The most important data, token-efficiently
3. **What can you do with me?** — Available methods, properties, next steps

It is NOT a human display method (`__repr__`), a serialization format (`.to_dict()`), or a full data dump. It is a compact, opinionated summary designed to fit inside an LLM context window alongside other content.

## Signature

```python
def to_context(self, detail: str = 'standard') -> str:
```

Every data object uses this exact signature. No exceptions.

- Returns a plain string (not dict, not JSON)
- `detail` accepts `'minimal'`, `'standard'`, `'full'`
- Default is `'standard'`
- No `max_tokens` parameter — token budget is managed by detail level
- No extra parameters (no `filing_date`, etc.) — the object should contain everything it needs

### Why no `max_tokens`?

Token budgets are the caller's concern, not the object's. The three detail levels give callers enough control. If a caller needs truncation, they truncate the string. This keeps `to_context()` simple and predictable.

## Format: Markdown-KV

All output uses **Markdown Key-Value** format. Research shows this gives 60.7% LLM accuracy — better than JSON, YAML, XML, or plain text — at 25% fewer tokens than JSON.

### Rules

```
OBJECT_TYPE: identity line

Key: Value
Key: Value

SECTION HEADER:
  Key: Value
  Key: Value

AVAILABLE ACTIONS:
  .method()          Description
  .property          Description
```

1. **First line** is always `TYPE: identity` in ALL CAPS type label
2. **Blank line** separates logical sections
3. **Keys** are title-case, no bold markers, no colons in key names
4. **Section headers** are ALL CAPS followed by colon
5. **Values** are on the same line as keys (no multi-line values)
6. **Actions** use 2-space indent with `.method()` left-aligned at column 2
7. **No emojis, no `===` banners, no `**bold**` markers, no `#` headers**
8. **No trailing whitespace, no trailing newlines**

### Why plain keys, not `**bold**`?

The `**bold**` format from `formats.py` is for generic dict-to-text conversion. For `to_context()`, we control the format directly and plain `Key: Value` is more token-efficient and easier to parse. The research advantage of markdown-KV comes from the structured key-value layout, not the bold markers.

## Detail Levels

### `minimal` — ~100-150 tokens

Identity + the 2-3 most important facts. Used when this object is embedded inside a parent's context (e.g., a Filing's context might include its Company at minimal detail).

```
FORM 4: Insider Transaction

Issuer: Apple Inc. (AAPL)
Owner: Tim Cook (CEO)
Transaction: Sale of 100,000 shares at $185.50
Date: 2024-03-15
```

No actions, no sections, no breakdowns. Just enough to know what this is and what matters.

### `standard` — ~250-350 tokens

Everything in minimal + secondary metadata + available actions. This is what MCP tools and interactive AI sessions use by default.

```
FORM 4: Insider Transaction

Issuer: Apple Inc. (AAPL)
CIK: 0000320193
Owner: Tim Cook
Relationship: Officer (CEO)
Date: 2024-03-15

TRANSACTIONS:
  Sale: 100,000 shares at $185.50 ($18,550,000)

HOLDINGS AFTER:
  Direct: 3,280,557 shares

AVAILABLE ACTIONS:
  .transactions          Transaction details (DataFrame)
  .holdings              Post-transaction holdings
  .owner                 Owner information
  .issuer                Issuer company details
  .to_dataframe()        All data as DataFrame
```

### `full` — ~500-800 tokens

Everything in standard + detailed breakdowns, additional context, previews. Used when the user is focused on this specific object.

Adds things like: derivative transactions, footnotes, all holdings (not just summary), related filings. Never exceeds ~800 tokens — if the data is large, summarize and point to the method that returns the full data.

## Content Guidelines

### What to Include

| Priority | Include | Example |
|----------|---------|---------|
| 1 | Identity (type + who/what) | `TENK: Apple Inc. (AAPL) Annual Report` |
| 2 | Time (when) | `Period: 2024-01-01 to 2024-12-31` |
| 3 | Key metrics (the headline numbers) | `Revenue: $394.3B, Net Income: $97.0B` |
| 4 | Structure (what's inside) | `Sections: Business, Risk Factors, MD&A, Financials` |
| 5 | Available actions | `.financials`, `.business_description`, `.risk_factors` |

### What to Exclude

- Raw HTML, raw XML, raw XBRL
- Full document text (that's what `.text()` or section accessors are for)
- Internal implementation details (parser state, cache keys, attachment indices)
- Redundant data (don't repeat what the Filing already tells you)
- Speculative data (don't compute ratios or interpretations — just expose the facts)

### Skip-if-None Pattern

Never show "N/A" or "None" or "Not available". If a field is None/empty, omit the line entirely. This keeps output compact and avoids LLMs fixating on missing data.

```python
# Good
if self.ticker:
    lines.append(f"Ticker: {self.ticker}")

# Bad
lines.append(f"Ticker: {self.ticker or 'N/A'}")
```

### Number Formatting

- Currencies: `$394.3B`, `$18.5M`, `$42,500` (use abbreviations for billions/millions)
- Shares: `100,000 shares` (comma-separated, always say "shares")
- Percentages: `12.5%` (one decimal)
- Counts: `42 holdings`, `8 sections` (always include the unit)
- Dates: `2024-03-15` (ISO 8601, no time)

### Available Actions Section

This is the most important section for AI usability. It tells the LLM what to do next.

```
AVAILABLE ACTIONS:
  .method_name()       What it returns (one line)
  .property_name       What it contains (one line)
```

Rules:
- **Always include** in `standard` and `full` detail levels
- **Never include** in `minimal`
- List the **5-8 most useful** actions, not every method
- Put the **most commonly needed** action first
- Use `.method()` for methods, `.property` for properties (no parens)
- Description is a short phrase, not a sentence — no period at the end
- Align descriptions to a consistent column for readability

### Composition Pattern

When a parent object embeds child context, call the child's `to_context(detail='minimal')` and indent it, or extract just the key fields. Don't call `to_context(detail='standard')` on children — that creates bloated output.

```python
# Good: summarize child inline
if self.deal:
    lines.append(f"Offering: {self.deal.offering_type} - {self.deal.security_type}")

# Bad: embed full child context
lines.append(self.deal.to_context(detail='standard'))
```

## Implementation Template

```python
def to_context(self, detail: str = 'standard') -> str:
    """
    AI-optimized context string.

    Args:
        detail: 'minimal' (~100 tokens), 'standard' (~300 tokens), 'full' (~500+ tokens)
    """
    lines = []

    # === IDENTITY (always present) ===
    lines.append(f"TYPE_LABEL: {self.identity_string}")
    lines.append("")

    # === CORE METADATA (always present) ===
    lines.append(f"Key: {self.value}")
    if self.optional_field:
        lines.append(f"Optional: {self.optional_field}")

    if detail == 'minimal':
        return "\n".join(lines)

    # === STANDARD: secondary data + actions ===
    lines.append(f"Secondary: {self.secondary_data}")

    # Structured section
    if self.has_important_collection:
        lines.append("")
        lines.append("SECTION NAME:")
        for item in self.collection[:5]:
            lines.append(f"  {item.summary}")
        if len(self.collection) > 5:
            lines.append(f"  ... ({len(self.collection) - 5} more)")

    # Actions
    lines.append("")
    lines.append("AVAILABLE ACTIONS:")
    lines.append("  .most_used()         What it returns")
    lines.append("  .second_most_used    What it contains")
    lines.append("  .to_dataframe()      All data as DataFrame")

    if detail == 'standard':
        return "\n".join(lines)

    # === FULL: detailed breakdowns ===
    lines.append("")
    lines.append("DETAILED SECTION:")
    for item in self.detailed_collection:
        lines.append(f"  {item.full_summary}")

    return "\n".join(lines)
```

## How MCP Tools Use to_context()

MCP tool handlers call `to_context()` to build their responses:

```python
# In an MCP tool handler
company = Company(identifier)
filing = company.get_filings(form="10-K").latest()
report = filing.obj()

# The tool response is built from to_context() at various levels
response = f"{company.to_context(detail='minimal')}\n\n{report.to_context(detail='standard')}"
```

This is why consistency matters — MCP tools compose multiple objects into a single response, and the format must be uniform so LLMs can parse it reliably.

## Currency Formatting Helper

Use a shared helper for consistent number formatting across all implementations:

```python
def _format_currency(value: float) -> str:
    """Format currency value with appropriate scale abbreviation."""
    if value is None:
        return ""
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1_000_000_000:
        return f"{sign}${abs_val / 1_000_000_000:,.1f}B"
    elif abs_val >= 1_000_000:
        return f"{sign}${abs_val / 1_000_000:,.1f}M"
    elif abs_val >= 1_000:
        return f"{sign}${abs_val:,.0f}"
    else:
        return f"{sign}${abs_val:,.2f}"
```

This should live in a shared location (e.g., `edgar/core/formatting.py`) and be importable by all data objects.

## Existing Implementation Conformance

These existing `to_context()` implementations predate these guidelines. When touched for any reason, bring them into conformance. The table below documents specific divergences.

| Class | Divergence | Fix |
|-------|-----------|-----|
| `Company` | Has `max_tokens` param | Remove `max_tokens`, callers truncate externally |
| `Company` | Uses `- Use .method()` bullet style for actions | Switch to `.method()  Description` column style |
| `XBRL` | Signature is `(max_tokens: int = 2000)` | Change to `(detail: str = 'standard')` |
| `XBRL` | Uses `**bold:**` markers | Switch to plain `Key: Value` |
| `XBRL` | Has emoji in output (`💡`) | Remove emoji |
| `XBRL` | No detail levels | Add minimal/standard/full |
| `Financials` | No `detail` parameter | Add `detail: str = 'standard'` |
| `Financials` | No AVAILABLE ACTIONS (uses inline method listing) | Restructure with proper actions section |
| `Filing` | Uses `- Use .method()` bullet style | Switch to column style |
| `Filings` | Uses `- Use .method()` bullet style | Switch to column style |
| `FormC` | Extra `filing_date` parameter | Remove; use `self.filing_date` if available |
| `Offering` | Uses `===` banner separators | Remove banners |
| `Offering` | No AVAILABLE ACTIONS section | Add actions section |
| `EarningsRelease` | Uses `=== header ===` format | Switch to `TYPE: identity` format |
| `FinancialTable` | Uses `=== header ===` format | Switch to `TYPE: identity` format |
| `ShelfLifecycle` | Actions only in `full` mode | Move to `standard` |
| `Prospectus424B` | Actions only in `full` mode | Move to `standard` |

These are not urgent — fix them incrementally when working on each class.

## Reference Examples

Concrete examples for the most important data objects. Use these as the target output when implementing.

### TenK (10-K Annual Report)

**minimal:**
```
TENK: Apple Inc. (AAPL) Annual Report

Period: 2023-10-01 to 2024-09-28
Filed: 2024-11-01
Revenue: $391.0B
Net Income: $93.7B
```

**standard:**
```
TENK: Apple Inc. (AAPL) Annual Report

Period: 2023-10-01 to 2024-09-28
Filed: 2024-11-01
Fiscal Year: 2024
CIK: 0000320193

FINANCIALS:
  Revenue: $391.0B
  Net Income: $93.7B
  Total Assets: $364.9B

SECTIONS:
  Business, Risk Factors, Properties, Legal Proceedings,
  MD&A, Financials, Controls and Procedures

AVAILABLE ACTIONS:
  .financials              XBRL financial statements
  .income_statement        Income statement (shortcut)
  .balance_sheet           Balance sheet (shortcut)
  .business_description    Item 1 text
  .risk_factors            Item 1A text
  .mda                     Item 7 MD&A text
  .items                   All sections by item number
```

**full:** Adds auditor info, subsidiary count, section previews (first 100 chars each).

### EightK (8-K Current Report)

**minimal:**
```
EIGHTK: Apple Inc. (AAPL) Current Report

Filed: 2024-11-01
Items: 2.02 (Results of Operations), 9.01 (Financial Statements and Exhibits)
```

**standard:**
```
EIGHTK: Apple Inc. (AAPL) Current Report

Filed: 2024-11-01
CIK: 0000320193

ITEMS:
  2.02: Results of Operations and Financial Condition
  9.01: Financial Statements and Exhibits

Flags: has_press_release, has_financials

AVAILABLE ACTIONS:
  .items                   All reported items
  .press_release           Press release attachment
  .financial_exhibits      Financial exhibit attachments
  .item_text(number)       Full text for specific item
  .to_dataframe()          Item summary as DataFrame
```

### Form4 (Insider Transaction)

**minimal:**
```
FORM4: Insider Transaction

Issuer: Apple Inc. (AAPL)
Owner: Timothy D. Cook (CEO)
Transaction: Sale of 100,000 shares at $185.50
Date: 2024-03-15
```

**standard:**
```
FORM4: Insider Transaction

Issuer: Apple Inc. (AAPL)
CIK: 0000320193
Owner: Timothy D. Cook
Relationship: Officer (Chief Executive Officer)
Filed: 2024-03-17

NON-DERIVATIVE TRANSACTIONS:
  Sale: 100,000 shares of Common Stock at $185.50 ($18.6M total)

HOLDINGS AFTER:
  Direct: 3,280,557 shares
  Indirect: 0 shares

AVAILABLE ACTIONS:
  .non_derivative_transactions    Non-derivative transaction details
  .derivative_transactions        Derivative transaction details
  .holdings                       Post-transaction holdings
  .owner                          Owner information
  .issuer                         Issuer company details
  .to_dataframe()                 All transactions as DataFrame
```

### ThirteenF (13F-HR Institutional Holdings)

**minimal:**
```
THIRTEENF: Berkshire Hathaway Inc

Report Date: 2024-06-30
Holdings: 42
Total Value: $280.2B
```

**standard:**
```
THIRTEENF: Berkshire Hathaway Inc

Report Date: 2024-06-30
CIK: 0001067983
Filed: 2024-08-14
Amendment: Original

SUMMARY:
  Holdings: 42
  Total Value: $280.2B

TOP HOLDINGS:
  Apple Inc: $84.2B (30.1%)
  Bank of America: $41.1B (14.7%)
  American Express: $35.1B (12.5%)
  Coca-Cola: $25.5B (9.1%)
  Chevron: $18.6B (6.6%)

AVAILABLE ACTIONS:
  .holdings                All holdings as DataFrame
  .top_holdings(n)         Top N holdings by value
  .filing_manager          Filer information
  .report_date             Report period end date
  .total_value             Portfolio total market value
```

### ProxyStatement (DEF 14A)

**minimal:**
```
PROXY: Apple Inc. (AAPL)

Filed: 2024-01-10
Meeting Date: 2024-03-01
Proposals: 6
```

**standard:**
```
PROXY: Apple Inc. (AAPL)

Filed: 2024-01-10
CIK: 0000320193
Meeting Date: 2024-03-01
Meeting Type: Annual

PROPOSALS:
  6 proposals (4 management, 2 shareholder)

EXECUTIVE COMPENSATION:
  CEO Total: $63.2M
  Named Officers: 5

AVAILABLE ACTIONS:
  .executive_compensation  Compensation tables
  .proposals               All proxy proposals
  .directors               Board of directors
  .pay_vs_performance      Pay vs performance data
  .ownership_table         Beneficial ownership table
  .to_dataframe()          Compensation as DataFrame
```

## Checklist for New Implementations

- [ ] Signature is exactly `to_context(self, detail: str = 'standard') -> str`
- [ ] First line is `TYPE_LABEL: identity` in ALL CAPS type label
- [ ] All three detail levels implemented and tested
- [ ] `minimal` is under 150 tokens
- [ ] `standard` is 250-350 tokens
- [ ] `full` is under 800 tokens
- [ ] `AVAILABLE ACTIONS:` section present in standard and full
- [ ] Actions list the 5-8 most useful methods/properties
- [ ] None/empty fields are silently omitted (no "N/A")
- [ ] Numbers use abbreviated formatting ($394.3B, 100,000 shares)
- [ ] Dates are ISO 8601
- [ ] No emojis, bold markers, banners, or markdown headers
- [ ] Docstring includes token estimates per detail level
