# EdgarTools MCP Quickstart Guide

This guide helps you get started with EdgarTools MCP server in under 5 minutes.

## Installation

```bash
# Install EdgarTools with AI features
pip install edgartools[ai]
```

## Starting the Server

EdgarTools provides two ways to start the MCP server:

### Option 1: Python Module (Recommended)
```bash
python -m edgar.ai
```

### Option 2: Console Script
```bash
edgartools-mcp
```

Both methods work identically and will start the MCP server listening on stdin/stdout.

## Client Configuration

### Claude Desktop

**Configuration File Location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

**Configuration:**
```json
{
  "mcpServers": {
    "edgartools": {
      "command": "python",
      "args": ["-m", "edgar.ai"]
    }
  }
}
```

**After configuring:**
1. Restart Claude Desktop
2. Look for the hammer icon (🔨) indicating MCP tools are available
3. Try asking: "Get information about Apple Inc"

### Cline (VS Code Extension)

**Configuration File:** `.vscode/cline_mcp_settings.json` in your project

```json
{
  "mcpServers": {
    "edgartools": {
      "command": "python",
      "args": ["-m", "edgar.ai"]
    }
  }
}
```

### Continue.dev

**Configuration File:** `~/.continue/config.json`

```json
{
  "mcpServers": {
    "edgartools": {
      "command": "python",
      "args": ["-m", "edgar.ai"]
    }
  }
}
```

## Available Tools

Once connected, AI agents have access to:

### 1. edgar_get_company
Get comprehensive company information from SEC filings.

**Example prompts:**
- "Get information about Tesla"
- "Show me Apple's company details with financials"
- "Tell me about Microsoft using ticker MSFT"

**Parameters:**
- `identifier` (required): Company ticker, CIK, or name
- `include_financials` (optional): Include latest financial statements

### 2. edgar_current_filings
Get the most recent SEC filings across all companies.

**Example prompts:**
- "Show me the latest SEC filings"
- "What are the most recent 10-K filings?"
- "Get current 8-K filings"

**Parameters:**
- `limit` (optional): Number of filings to return (default: 20)
- `form_type` (optional): Filter by form type (e.g., "10-K", "10-Q", "8-K")

## Environment Variables

Set your SEC identity (recommended):

```bash
# Add to your ~/.bashrc or ~/.zshrc
export EDGAR_IDENTITY="Your Name your.email@company.com"
```

Without this, EdgarTools uses a default identity. The SEC requires proper identification for API requests.

## Troubleshooting

### Server won't start

**Issue:** `ModuleNotFoundError: No module named 'mcp'`

**Solution:** Install AI dependencies
```bash
pip install edgartools[ai]
```

### Client can't find server

**Issue:** Claude Desktop shows connection error

**Solution:** Verify the command works from terminal first
```bash
python -m edgar.ai
# Should show: Starting EdgarTools MCP Server v...
# Press Ctrl+C to stop
```

### Wrong Python version

**Issue:** Server starts but tools don't work

**Solution:** MCP requires Python 3.10+. Check your version:
```bash
python --version
```

If using Python 3.9 or earlier, upgrade Python:
```bash
# macOS with Homebrew
brew install python@3.11

# Update your config to use the specific version
{
  "mcpServers": {
    "edgartools": {
      "command": "/opt/homebrew/bin/python3.11",
      "args": ["-m", "edgar.ai"]
    }
  }
}
```

## Verification

Test that everything is working:

1. **Start the server manually:**
   ```bash
   python -m edgar.ai
   ```
   You should see: `Starting EdgarTools MCP Server v4.18.0`

2. **Test in your MCP client:**
   Ask: "Get information about Apple Inc including financials"

3. **Check server logs:**
   The server logs to stderr. Check your MCP client's developer console for any errors.

## Next Steps

- Read the [full MCP documentation](./edgartools-mcp-ai-support.md) for advanced features
- See [AI package structure](./ai-mcp-package-structure-plan.md) for architecture details
- Explore example notebooks showing MCP workflows

## Support

- **Issues:** https://github.com/dgunning/edgartools/issues
- **Discussions:** https://github.com/dgunning/edgartools/discussions
- **Documentation:** https://dgunning.github.io/edgartools/
