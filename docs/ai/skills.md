# Skills

Skills are structured documentation packages that teach Claude how to write better EdgarTools code. They guide Claude to use the right APIs, avoid common mistakes, and follow best practices.

## What Do Skills Do?

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

Skills cover patterns, sharp edges (common mistakes), and API routing decisions across six domains.

## Installing Skills

**For Claude Code** (auto-discovered):

```python
from edgar.ai import install_skill
install_skill()  # Installs to ~/.claude/skills/edgartools/
```

**For Claude Desktop** (upload as project knowledge):

```python
from edgar.ai import package_skill
package_skill()  # Creates edgartools.zip
```

Upload the ZIP to a Claude Desktop Project.

## Skill Domains

| Domain | What It Covers |
|--------|---------------|
| **core** | Company lookup, filing search, API routing, quick reference |
| **financials** | Financial statements, metrics, multi-company comparison |
| **holdings** | 13F filings, institutional portfolios |
| **ownership** | Insider transactions (Form 4), ownership summaries |
| **reports** | 10-K, 10-Q, 8-K document sections |
| **xbrl** | XBRL fact extraction, statement rendering |

## Skills vs MCP Server

| I want to... | Use |
|-------------|-----|
| Ask Claude questions about companies and filings | [MCP Server](mcp-setup.md) |
| Have Claude write EdgarTools code for me | Skills |
| Both | Install both -- they complement each other |

Skills improve code generation. The MCP Server provides data access. They solve different problems and work well together.
