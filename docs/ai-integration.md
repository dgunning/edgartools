# AI Integration

EdgarTools provides two AI integration features:

1. **MCP Server** -- Gives any MCP-compatible AI client direct access to SEC filing data through five specialized tools
2. **Skills** -- Teaches Claude how to write better EdgarTools code by providing structured patterns and best practices

Both are optional. Install with:

```bash
pip install "edgartools[ai]"
```

## MCP Server

The [Model Context Protocol](https://modelcontextprotocol.io/) server gives any MCP-compatible AI client access to SEC filing data -- whether that's a developer's Claude Desktop, a team's shared server, or a containerized deployment. No code required.

### Setup

Choose the deployment method that fits your use case:

#### uvx (recommended -- zero install)

Ideal for individual use or scripted deployment. Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

```json
{
  "mcpServers": {
    "edgartools": {
      "command": "uvx",
      "args": ["--from", "edgartools[ai]", "edgartools-mcp"],
      "env": {
        "EDGAR_IDENTITY": "Your Name your.email@example.com"
      }
    }
  }
}
```

If you get a "spawn uvx ENOENT" error on macOS, use the full path to uvx (find it with `which uvx`).

#### Python

When edgartools is already installed in your environment:

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

On Windows, use `python` instead of `python3`.

#### Docker

For server or production deployments where you want isolation and reproducibility:

```dockerfile
FROM python:3.12-slim
RUN pip install "edgartools[ai]"
ENV EDGAR_IDENTITY="Your Name your.email@example.com"
ENTRYPOINT ["python", "-m", "edgar.ai"]
```

Build and run:

```bash
docker build -t edgartools-mcp .
docker run -i edgartools-mcp
```

The community also maintains Docker images -- see [hackerdogs/edgartools-mcp](https://hub.docker.com/r/hackerdogs/edgartools-mcp) on Docker Hub for a ready-to-use container with config templates for multiple MCP clients.

Replace `Your Name your.email@example.com` with your actual name and email. The SEC requires this to identify API users.

**Verify**

```bash
python -m edgar.ai --test
```

**For Claude Desktop**, add the config above to your config file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows) and restart. You should see the MCP tools icon in the chat input.

> **[edgar.tools also runs a hosted MCP server with AI-enriched data — no local setup needed →](https://app.edgar.tools/docs/mcp/setup?utm_source=edgartools-docs&utm_medium=see-live&utm_content=ai-integration)**

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

### Any MCP Client

The server works with any MCP-compatible client -- Claude Desktop, Cline, Continue.dev, or your own tooling. The configuration is the same `mcpServers` block regardless of client:

```json
{
  "mcpServers": {
    "edgartools": {
      "command": "uvx",
      "args": ["--from", "edgartools[ai]", "edgartools-mcp"],
      "env": {
        "EDGAR_IDENTITY": "Your Name your.email@example.com"
      }
    }
  }
}
```

Where it goes depends on the client: Claude Desktop config file, Cline MCP settings, `~/.continue/config.json`, etc.

!!! info "edgar.tools also runs a hosted MCP server"
    The local edgartools MCP server queries EDGAR directly through Python. The **[edgar.tools hosted MCP server](https://app.edgar.tools/docs/mcp/setup?utm_source=edgartools-docs&utm_medium=see-live&utm_content=ai-integration)** adds AI-enriched data processed server-side:

    | Capability | Local (edgartools) | Hosted (edgar.tools) |
    |---|---|---|
    | Material events | Basic 8-K parsing | LLM-classified event types |
    | Disclosure search | — | 12 XBRL topic clusters, all years |
    | Insider data | Individual Form 4s | 802K+ transactions with sentiment |
    | Filing sections | Raw text | AI summaries and key takeaways |

    Free tier: truncated MCP responses. Professional ($24.99/mo): full results.

    **[Set up the hosted MCP server →](https://app.edgar.tools/docs/mcp/setup?utm_source=edgartools-docs&utm_medium=see-live&utm_content=ai-integration)**

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
