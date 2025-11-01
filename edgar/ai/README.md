# EdgarTools AI

AI and LLM integration for SEC financial data analysis.

## Installation

The AI features are optional. Install them with:

```bash
# Basic AI features
pip install edgartools[ai]

# For development (includes mocking and testing tools)
pip install -e ".[ai,ai-dev]"
```

## Features

### 1. LLM Context Generation

Enhanced context generation for financial facts and entities:

```python
from edgar import Company
from edgar.ai import enhance_financial_fact_llm_context

# Get company financials
company = Company("AAPL")
filing = company.latest("10-K")
xbrl = filing.xbrl()

# Get a financial fact
revenue_fact = xbrl.facts.get("Revenue")

# Generate LLM-optimized context
context = enhance_financial_fact_llm_context(
    revenue_fact,
    detail_level='detailed',  # minimal, standard, or detailed
    max_tokens=500           # Optional token limit
)
```

### 2. Model Context Protocol (MCP) Server

Run EdgarTools as an MCP server for AI agents:

```bash
# Using Python module (recommended)
python -m edgar.ai

# Using console script (after pip install)
edgartools-mcp
```

**Quick Setup:** See [MCP Quickstart Guide](mcp/docs/MCP_QUICKSTART.md) for complete setup instructions.

#### Client Configuration Examples

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "edgartools": {
      "command": "python",
      "args": ["-m", "edgar.ai"],
      "env": {
        "EDGAR_IDENTITY": "Your Name your.email@example.com"
      }
    }
  }
}
```

**Cline/Continue.dev**:
```json
{
  "mcpServers": {
    "edgartools": {
      "command": "python",
      "args": ["-m", "edgar.ai"],
      "env": {
        "EDGAR_IDENTITY": "Your Name your.email@example.com"
      }
    }
  }
}
```

**Note:** The `EDGAR_IDENTITY` environment variable is required by the SEC for API requests.

After configuration, restart your MCP client and try:
- *"Research Apple Inc with financials"*
- *"Analyze Tesla's financial performance over the last 4 quarters"*
- *"Get Microsoft's latest income statement trends"*

### 3. Semantic Enrichment

Add business context and interpretations to financial data:

```python
from edgar.ai import SemanticEnricher

# Get concept definition
definition = SemanticEnricher.get_concept_definition("Revenue")
# "Total income generated from normal business operations"

# Get related concepts
related = SemanticEnricher.get_related_concepts("Revenue")
# ["GrossProfit", "OperatingIncome", "NetIncome"]

# Interpret values
interpretation = SemanticEnricher.interpret_value(
    "Revenue", 125_000_000_000, "USD"
)
# "The company is a billion-dollar business based on revenue"
```

### 4. Token Optimization

Optimize content for LLM context windows:

```python
from edgar.ai import TokenOptimizer

# Estimate tokens
tokens = TokenOptimizer.estimate_tokens(content)

# Optimize for token limit
optimized = TokenOptimizer.optimize_for_tokens(
    content, 
    max_tokens=1000
)
```

## Available MCP Tools

When running as an MCP server, the following tools are available:

- **edgar_company_research**: Get comprehensive company intelligence including profile, financial trends, and recent filing activity. Returns overview with 3-year financial data and last 5 filings.
- **edgar_analyze_financials**: Detailed financial statement analysis across multiple periods. Supports income statement, balance sheet, and cash flow analysis with annual or quarterly periods.

For detailed tool documentation, see the [MCP Quickstart Guide](mcp/docs/MCP_QUICKSTART.md).

## Examples

See the `examples/` directory for complete examples:

- `basic_usage.py`: Demonstrates all AI features
- More examples coming soon...

## Architecture

The AI package is organized as follows:

```
edgar/ai/
├── __init__.py          # Package initialization and capability detection
├── __main__.py          # Entry point: python -m edgar.ai
├── core.py              # Core AI functionality (AIEnabled, TokenOptimizer, etc.)
├── formats.py           # Format utilities
├── helpers.py           # Helper functions for SEC analysis workflows
│
├── mcp/                 # Model Context Protocol implementation
│   ├── __init__.py      # MCP package exports (main, test_server)
│   ├── server.py        # MCP server (production)
│   ├── tools/           # Workflow-oriented tool handlers
│   │   ├── company_research.py     # Company intelligence tool
│   │   ├── financial_analysis.py   # Financial analysis tool
│   │   └── utils.py                # Tool utilities
│   └── docs/            # MCP documentation
│       └── MCP_QUICKSTART.md
│
├── skills/              # AI Skills infrastructure
│   ├── base.py          # BaseSkill abstract class
│   └── core/            # EdgarTools skill
│
├── exporters/           # Export capabilities
│   └── claude_desktop.py
│
└── examples/            # Usage examples
    └── basic_usage.py
```

## Development

To contribute to the AI features:

1. Install development dependencies:
   ```bash
   pip install -e ".[ai,ai-dev]"
   ```

2. Run tests:
   ```bash
   # Test MCP tools
   pytest tests/test_mcp_tools.py

   # Test AI features
   pytest tests/test_ai_features.py

   # Test AI skills
   pytest tests/test_ai_skill_export.py
   ```

3. Check AI capabilities:
   ```python
   from edgar.ai import check_ai_capabilities
   print(check_ai_capabilities())
   ```

## Future Enhancements

- Streaming support for real-time updates
- Multi-agent collaboration
- Advanced prompt templates
- Vector embeddings for semantic search
- Fine-tuned models for SEC data

## Documentation

For more detailed documentation, see:
- [MCP Quickstart Guide](mcp/docs/MCP_QUICKSTART.md) - Get started in 5 minutes
- [MCP Implementation Review](MCP_IMPLEMENTATION_REVIEW.md) - Architecture analysis and migration details