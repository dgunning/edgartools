# EdgarTools AI Integration Examples

This directory contains examples demonstrating EdgarTools' AI-native features.

## Prerequisites

Install EdgarTools with AI dependencies:

```bash
pip install edgartools[ai]
```

Set your SEC identity (required by SEC regulations):

```python
from edgar import set_identity
set_identity("Your Name your.email@example.com")
```

## Examples

### 1. basic_docs.py - Interactive Documentation

Learn how to use the `.docs` property for interactive API documentation.

**Features demonstrated:**
- Displaying rich documentation in your terminal
- Searching documentation with BM25 semantic search
- Accessing docs on different objects (Company, Filing, XBRL, Statement)
- Building a learning workflow

**Run it:**
```bash
python examples/ai/basic_docs.py
```

**Key concepts:**
```python
company = Company("AAPL")

# Display documentation
company.docs

# Search documentation
company.docs.search("get financials")
```

### 2. ai_context.py - AI-Optimized Text Output

Generate token-efficient context for Large Language Models.

**Features demonstrated:**
- Using `.text()` methods for AI-optimized output
- Progressive disclosure (minimal/standard/detailed)
- Token limiting for LLM context windows
- Building multi-part contexts
- Format comparison (markdown-kv vs TSV)
- Batch processing with token budgets

**Run it:**
```bash
python examples/ai/ai_context.py
```

**Key concepts:**
```python
# Generate AI-optimized text
text = company.text(detail='standard', max_tokens=500)

# Build LLM context
context = f"""
# Company Overview
{company.text(detail='minimal', max_tokens=200)}

# Latest Filing
{filing.text(detail='standard', max_tokens=300)}
"""
```

### 3. skills_usage.py - AI Skills System

Work with EdgarTools' Skills system for specialized analysis.

**Features demonstrated:**
- Listing and accessing available skills
- Using helper functions for common workflows
- Accessing skill documentation
- Exporting skills to Claude Desktop format
- Building complete analysis workflows

**Run it:**
```bash
python examples/ai/skills_usage.py
```

**Key concepts:**
```python
from edgar.ai import list_skills, get_skill
from edgar.ai.helpers import get_revenue_trend, compare_companies_revenue

# List skills
skills = list_skills()

# Get specific skill
skill = get_skill("SEC Filing Analysis")

# Use helper functions
income = get_revenue_trend("AAPL", periods=3)
comparison = compare_companies_revenue(["AAPL", "MSFT"], periods=3)
```

## Common Workflows

### For Interactive Learning

```python
from edgar import Company

company = Company("AAPL")

# Explore documentation
company.docs

# Search for specific features
company.docs.search("xbrl statements")
```

### For AI Applications

```python
from edgar import Company

company = Company("AAPL")

# Generate AI-friendly context
context = company.text(
    detail='standard',
    max_tokens=500,
    format='markdown-kv'
)

# Use in your LLM pipeline
# response = llm.generate(context + user_query)
```

### For Specialized Analysis

```python
from edgar.ai.helpers import (
    get_revenue_trend,
    compare_companies_revenue
)

# Quick revenue analysis
income = get_revenue_trend("AAPL", periods=3)

# Multi-company comparison
comparison = compare_companies_revenue(
    ["AAPL", "MSFT", "GOOGL"],
    periods=3
)
```

## Token Optimization Tips

1. **Choose appropriate detail level:**
   - `minimal`: ~100-200 tokens
   - `standard`: ~300-500 tokens
   - `detailed`: ~800-1200 tokens

2. **Use max_tokens parameter:**
   ```python
   text = company.text(max_tokens=500)
   ```

3. **Batch with token budgets:**
   ```python
   token_budget = 2000
   tokens_used = 0

   for ticker in tickers:
       remaining = token_budget - tokens_used
       text = Company(ticker).text(max_tokens=min(remaining, 300))
       tokens_used += estimate_tokens(text)
   ```

4. **Use Entity Facts API for multi-period data:**
   ```python
   # More efficient
   income = company.income_statement(periods=3)  # ~500 tokens

   # Less efficient
   # Multiple filing accesses: ~3,750 tokens
   ```

## Integration Examples

### LangChain

```python
from langchain.text_splitter import MarkdownTextSplitter
from edgar import Company

company = Company("AAPL")
text = company.text(detail='detailed')

splitter = MarkdownTextSplitter(chunk_size=1000)
chunks = splitter.split_text(text)
```

### LlamaIndex

```python
from llama_index import Document
from edgar import Company

company = Company("AAPL")
text = company.text(detail='standard')

doc = Document(text=text, metadata={
    'ticker': 'AAPL',
    'source': 'edgartools'
})
```

### Custom AI Pipeline

```python
from edgar import Company

def analyze_company(ticker: str, llm):
    company = Company(ticker)

    # Build context
    context = f"""
    {company.text(detail='standard', max_tokens=500)}

    Please analyze this company's financial health.
    """

    return llm.generate(context)
```

## MCP Server Setup

For Claude Desktop integration, see the [MCP Quickstart Guide](../../edgar/ai/mcp/docs/MCP_QUICKSTART.md).

Quick setup:

1. Configure in `~/Library/Application Support/Claude/claude_desktop_config.json`:
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

2. Restart Claude Desktop

3. Ask Claude:
   - *"Research Apple Inc with financials"*
   - *"Analyze Tesla's revenue trends"*

## Additional Resources

- [AI Integration Guide](../../docs/ai-integration.md) - Comprehensive guide
- [EdgarTools Documentation](https://edgartools.readthedocs.io/)
- [AI Skills README](../../edgar/ai/skills/sec_analysis/readme.md)
- [GitHub Discussions](https://github.com/dgunning/edgartools/discussions)

## Contributing

Have an interesting AI integration example? We'd love to see it!

- Open an issue with your example
- Submit a pull request
- Share in GitHub Discussions

## Support

- [GitHub Issues](https://github.com/dgunning/edgartools/issues)
- [Discussions](https://github.com/dgunning/edgartools/discussions)
