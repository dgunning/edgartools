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

**Step 1: Install Claude Desktop**
- Download from https://claude.ai/download (macOS or Windows)

**Step 2: Configure the Server**

You can configure EdgarTools MCP in two ways:

**Option A: Using Claude Desktop Settings (Easier)**
1. Open Claude Desktop
2. Go to Settings (macOS: `Cmd+,` / Windows: `Ctrl+,`)
3. Navigate to **Developer** tab
4. Click **Edit Config** button
5. This will open `claude_desktop_config.json` in your default editor

**Option B: Edit Configuration File Directly**

Configuration file location:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

**Configuration (macOS):**
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

**Configuration (Windows):**
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

**Important:** On macOS, use `python3` (not `python`) as the command. On Windows, use `python`.

**Important Notes:**
- Replace `"Your Name your.email@example.com"` with your actual name and email
- The `EDGAR_IDENTITY` is required by the SEC for API requests
- Use forward slashes in paths, even on Windows

**Step 3: Restart and Verify**
1. Save the configuration file
2. Restart Claude Desktop
3. Look for the MCP server indicator (🔨) in the bottom-right corner of the chat input
4. Try asking: "Research Apple Inc with financials"

### Cline (VS Code Extension)

**Configuration File:** `.vscode/cline_mcp_settings.json` in your project

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

**Note:** Use `python3` on macOS/Linux, or `python` on Windows.

### Continue.dev

**Configuration File:** `~/.continue/config.json`

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

**Note:** Use `python3` on macOS/Linux, or `python` on Windows.

## Available Tools

Once connected, AI agents have access to workflow-oriented tools designed for real-world research tasks:

### Workflow Tools (Recommended)

#### 1. edgar_company_research
Comprehensive company intelligence combining profile, financials, recent activity, and ownership in a single workflow.

**Example prompts:**
- "Research Tesla including financials and recent filings"
- "Give me a detailed analysis of Apple Inc"
- "Show me Microsoft's company profile with ownership data"

**Parameters:**
- `identifier` (required): Company ticker, CIK, or name
- `include_financials` (default: true): Include latest financial statements
- `include_filings` (default: true): Include recent filing activity summary
- `include_ownership` (default: false): Include insider/institutional ownership highlights
- `detail_level` (default: "standard"): Response detail - "minimal", "standard", or "detailed"

**What it provides:**
- Company profile (name, CIK, ticker, industry)
- Latest financial metrics and statements
- Recent filing activity summary
- Ownership highlights (when requested)

#### 2. edgar_analyze_financials
Multi-period financial statement analysis for trend analysis and comparisons.

**Example prompts:**
- "Analyze Apple's income statement for the last 4 years"
- "Show me Tesla's quarterly cash flow for the last 8 quarters"
- "Compare Microsoft's income, balance sheet, and cash flow statements"

**Parameters:**
- `company` (required): Company ticker, CIK, or name
- `periods` (default: 4): Number of periods to analyze
- `annual` (default: true): Annual (true) or quarterly (false) periods
- `statement_types` (default: ["income"]): Statements to include - "income", "balance", "cash_flow"

**What it provides:**
- Multi-period income statements
- Multi-period balance sheets
- Multi-period cash flow statements
- Formatted for AI analysis and comparison

### Basic Tools (Backward Compatibility)

#### 3. edgar_get_company
Get basic company information from SEC filings.

**Example prompts:**
- "Get information about Tesla"
- "Show me Apple's company details"

**Parameters:**
- `identifier` (required): Company ticker, CIK, or name
- `include_financials` (optional): Include latest financial statements

#### 4. edgar_current_filings
Get the most recent SEC filings across all companies.

**Example prompts:**
- "Show me the latest SEC filings"
- "What are the most recent 10-K filings?"
- "Get current 8-K filings"

**Parameters:**
- `limit` (optional): Number of filings to return (default: 20)
- `form_type` (optional): Filter by form type (e.g., "10-K", "10-Q", "8-K")

## Environment Variables

### EDGAR_IDENTITY (Recommended)

The SEC requires proper identification for all API requests. You can configure this in two ways:

**Option 1: In MCP Client Configuration (Recommended)**

Set it in your MCP client config as shown in the examples above:
```json
"env": {
  "EDGAR_IDENTITY": "Your Name your.email@example.com"
}
```

**Option 2: Shell Environment Variable**

Add to your `~/.bashrc` or `~/.zshrc`:
```bash
export EDGAR_IDENTITY="Your Name your.email@example.com"
```

**What happens if not set:**
- Server starts with a warning message
- SEC API may rate-limit or return errors
- The server will log helpful instructions for configuring it

**SEC Requirements:**
- Format: "Full Name email@domain.com"
- Must be a valid email you monitor
- Used by SEC to contact you if issues arise with your API usage

## Troubleshooting

### Finding Logs

Claude Desktop logs MCP server activity to help diagnose issues:

**Log Locations:**
- **macOS**: `~/Library/Logs/Claude/`
  - Main log: `mcp.log`
  - Server-specific: `mcp-server-edgartools.log`
- **Windows**: `%APPDATA%\Claude\logs\`

**Viewing logs:**
```bash
# macOS - watch logs in real-time
tail -f ~/Library/Logs/Claude/mcp-server-edgartools.log

# macOS - view recent errors
tail -50 ~/Library/Logs/Claude/mcp-server-edgartools.log | grep error
```

### "spawn python ENOENT" Error

**Issue:** Claude Desktop logs show `spawn python ENOENT` error

**Where to check:** View logs at `~/Library/Logs/Claude/mcp-server-edgartools.log`

**Cause:** The `python` command is not found in your system PATH. This is the most common issue on macOS.

**Solution:**

1. **Use `python3` instead of `python` (macOS/Linux):**
   ```json
   {
     "mcpServers": {
       "edgartools": {
         "command": "python3",
         "args": ["-m", "edgar.ai"]
       }
     }
   }
   ```

2. **Or specify the full Python path:**

   Find your Python path:
   ```bash
   which python3
   ```

   Then use the full path in your configuration:
   ```json
   {
     "mcpServers": {
       "edgartools": {
         "command": "/opt/homebrew/bin/python3",
         "args": ["-m", "edgar.ai"]
       }
     }
   }
   ```

3. **Verify Python is accessible:**
   ```bash
   python3 --version
   # Should show: Python 3.11.x or higher
   ```

### Server won't start

**Issue:** `ModuleNotFoundError: No module named 'mcp'`

**Solution:** Install AI dependencies
```bash
pip install edgartools[ai]
# or with pip3
pip3 install edgartools[ai]
```

### Client can't find server

**Issue:** Claude Desktop shows connection error

**Solution:** Verify the command works from terminal first
```bash
python3 -m edgar.ai
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

### Quick Test

Before configuring your MCP client, verify the server is working:

```bash
python -m edgar.ai --test
```

**Expected output:**
```
Testing EdgarTools MCP Server Configuration...

✓ EdgarTools v4.18.0 imports successfully
✓ MCP framework available
✓ EDGAR_IDENTITY configured: Your Name your@email.com
✓ Core EdgarTools functionality available

✓ All checks passed - MCP server is ready to run
```

If any checks fail, the test will show specific error messages and installation instructions.

### Full Integration Test

1. **Start the server manually:**
   ```bash
   python -m edgar.ai
   ```
   You should see: `Starting EdgarTools MCP Server v4.18.0`

2. **Configure your MCP client** (see configurations above)

3. **Test in your MCP client:**

   Try these example prompts:
   - "Research Apple Inc with financials and recent filings"
   - "Analyze Tesla's quarterly income statement for the last 4 quarters"
   - "Get the latest 10-K filings"

4. **Check server logs:**
   The server logs to stderr. Check your MCP client's developer console for any errors.

5. **Verify tool availability:**
   In Claude Desktop, look for the MCP indicator (🔨) in the bottom-right corner of the chat input. Clicking it should show available EdgarTools tools.

## Migration from Legacy Setup

If you're currently using the old `run_mcp_server.py` entry point, here's how to migrate:

### Old Configuration (Deprecated):
```json
{
  "mcpServers": {
    "edgartools": {
      "command": "python",
      "args": ["/absolute/path/to/edgartools/edgar/ai/run_mcp_server.py"]
    }
  }
}
```

### New Configuration (macOS):
```json
{
  "mcpServers": {
    "edgartools": {
      "command": "python3",
      "args": ["-m", "edgar.ai"],
      "env": {
        "EDGAR_IDENTITY": "Your Name your@email.com"
      }
    }
  }
}
```

### New Configuration (Windows):
```json
{
  "mcpServers": {
    "edgartools": {
      "command": "python",
      "args": ["-m", "edgar.ai"],
      "env": {
        "EDGAR_IDENTITY": "Your Name your@email.com"
      }
    }
  }
}
```

### Benefits of Migrating:
- ✅ No absolute file paths required
- ✅ Works from any directory
- ✅ Proper SEC identity configuration
- ✅ Simpler configuration
- ✅ Better error messages
- ✅ Verification tool support (`--test` flag)

**Note:** The old entry point still works but shows a deprecation warning. It will be removed in a future version.

## Next Steps

- Read the [full MCP documentation](../../../docs-internal/features/edgartools-mcp-ai-support.md) for advanced features
- See [AI package structure](../../../docs-internal/features/ai-mcp-package-structure-plan.md) for architecture details
- Explore example notebooks showing MCP workflows

## Support

- **Issues:** https://github.com/dgunning/edgartools/issues
- **Discussions:** https://github.com/dgunning/edgartools/discussions
- **Documentation:** https://dgunning.github.io/edgartools/
