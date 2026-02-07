# AI Integration

EdgarTools provides two AI integration features:

1. **MCP Server** -- Gives Claude Desktop (and other MCP clients) direct access to SEC filing data through five specialized tools
2. **Skills** -- Teaches Claude how to write better EdgarTools code by providing structured patterns and best practices

Both are optional. Install with:

```bash
pip install "edgartools[ai]"
```

## MCP Server

The [Model Context Protocol](https://modelcontextprotocol.io/) server allows Claude Desktop to query SEC filing data directly -- no code required.

### Setup

**1. Configure Claude Desktop**

Add to your Claude Desktop config file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "edgartools": {
      "command": "python3",
      "args": ["-m", "edgar.ai"],
      "env": {
        "EDGAR_IDENTITY": "Your Name your.email@example.com"
      }
    }
  }
}
```

Replace `Your Name your.email@example.com` with your actual name and email. The SEC requires this to identify API users.

On Windows, use `python` instead of `python3`.

**2. Verify**

```bash
python -m edgar.ai --test
```

**3. Restart Claude Desktop.** You should see the MCP tools icon in the chat input.

### Available Tools

#### edgar_company

Get company profile, financials, recent filings, and ownership in one call.

| Parameter | Description |
|-----------|-------------|
| `identifier` | Ticker, CIK, or company name (required) |
| `include` | Sections to return: `profile`, `financials`, `filings`, `ownership` |
| `periods` | Number of financial periods (default: 4) |
| `annual` | Annual vs quarterly data (default: true) |

**Try asking Claude:**

- "Show me Apple's profile and latest financials"
- "Get Microsoft's recent filings and ownership data"

#### edgar_search

Search for companies or filings.

| Parameter | Description |
|-----------|-------------|
| `query` | Search keywords (required) |
| `search_type` | `companies`, `filings`, or `all` |
| `identifier` | Limit to a specific company |
| `form` | Filter by form type (e.g., `10-K`, `8-K`) |
| `limit` | Max results (default: 10) |

**Try asking Claude:**

- "Search for semiconductor companies"
- "Find Apple's 10-K filings"

#### edgar_filing

Read filing content or specific sections.

| Parameter | Description |
|-----------|-------------|
| `accession_number` | SEC accession number |
| `identifier` + `form` | Alternative: company + form type |
| `sections` | `summary`, `business`, `risk_factors`, `mda`, `financials`, or `all` |

**Try asking Claude:**

- "Show me the risk factors from Apple's latest 10-K"
- "Get the MD&A section from Tesla's most recent annual report"

#### edgar_compare

Compare companies side-by-side or analyze an industry.

| Parameter | Description |
|-----------|-------------|
| `identifiers` | List of tickers/CIKs to compare |
| `industry` | Alternative: industry name |
| `metrics` | Metrics to compare (e.g., `revenue`, `net_income`) |
| `periods` | Number of periods (default: 4) |

**Try asking Claude:**

- "Compare Apple, Microsoft, and Google on revenue and net income"
- "How do the top semiconductor companies compare?"

#### edgar_ownership

Insider transactions, institutional holders, or fund portfolios.

| Parameter | Description |
|-----------|-------------|
| `identifier` | Ticker, CIK, or fund CIK (required) |
| `analysis_type` | `insiders`, `institutions`, or `fund_portfolio` |
| `days` | Lookback period for insider trades (default: 90) |
| `limit` | Max results (default: 20) |

**Try asking Claude:**

- "Show me recent insider transactions at Apple"
- "Who are Tesla's largest institutional holders?"
- "What stocks does Berkshire Hathaway hold?"

### Other MCP Clients

The server works with any MCP-compatible client. Use the same configuration format:

**Cline (VS Code)**: Add to your Cline MCP settings

**Continue.dev**: Add to `~/.continue/config.json`

```json
{
  "mcpServers": {
    "edgartools": {
      "command": "python3",
      "args": ["-m", "edgar.ai"],
      "env": {
        "EDGAR_IDENTITY": "Your Name your.email@example.com"
      }
    }
  }
}
```

## Skills

Skills are structured documentation packages that teach Claude how to write better EdgarTools code. They guide Claude to use the right APIs, avoid common mistakes, and follow best practices.

### What Do Skills Do?

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

### Installing Skills

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

### Skill Domains

| Domain | What It Covers |
|--------|---------------|
| **core** | Company lookup, filing search, API routing, quick reference |
| **financials** | Financial statements, metrics, multi-company comparison |
| **holdings** | 13F filings, institutional portfolios |
| **ownership** | Insider transactions (Form 4), ownership summaries |
| **reports** | 10-K, 10-Q, 8-K document sections |
| **xbrl** | XBRL fact extraction, statement rendering |

### When to Use Which

| I want to... | Use |
|-------------|-----|
| Ask Claude questions about companies/filings | MCP Server |
| Have Claude write EdgarTools code for me | Skills |
| Both | Install both -- they complement each other |

## Built-in AI Features

These work without the `[ai]` extra.

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

## Troubleshooting

**"EDGAR_IDENTITY environment variable is required"**

Add your name and email to the `env` section of your MCP config. The SEC requires identification for API access.

**"Module edgar.ai not found"**

Install with AI extras: `pip install "edgartools[ai]"`

**"python3: command not found" (Windows)**

Use `python` instead of `python3` in your MCP config.

**MCP server not appearing in Claude Desktop**

1. Check the config file location is correct for your OS
2. Validate JSON syntax
3. Restart Claude Desktop completely (quit and relaunch)
4. Run `python -m edgar.ai --test` to verify

**Skills not being picked up**

1. Verify installation: `ls ~/.claude/skills/edgartools/`
2. For Claude Desktop, upload as ZIP to a Project instead
3. Skills only affect code generation, not conversational responses
