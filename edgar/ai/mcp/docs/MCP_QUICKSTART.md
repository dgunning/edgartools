# EdgarTools MCP Quickstart Guide

This guide helps you get started with EdgarTools MCP server in under 5 minutes.

## Installation

```bash
# Install EdgarTools with AI features
pip install "edgartools[ai]"
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

Once connected, AI agents have access to five intent-based tools:

#### 1. edgar_company
Get company profile, financials, recent filings, and ownership in one call.

**Example prompts:**
- "Show me Apple's profile and latest financials"
- "Get Microsoft's recent filings and ownership data"

**Parameters:**
- `identifier` (required): Company ticker, CIK, or name
- `include`: Sections to return: `profile`, `financials`, `filings`, `ownership`
- `periods` (default: 4): Number of financial periods
- `annual` (default: true): Annual vs quarterly data

#### 2. edgar_search
Search for companies or filings.

**Example prompts:**
- "Search for semiconductor companies"
- "Find Apple's 10-K filings"
- "Search for recent 8-K filings"

**Parameters:**
- `query` (required): Search keywords
- `search_type`: `companies`, `filings`, or `all`
- `identifier`: Limit to a specific company
- `form`: Filter by form type (e.g., "10-K", "8-K")
- `limit` (default: 10): Max results

#### 3. edgar_filing
Read filing content or specific sections.

**Example prompts:**
- "Show me the risk factors from Apple's latest 10-K"
- "Get the MD&A section from Tesla's most recent annual report"

**Parameters:**
- `accession_number`: SEC accession number
- OR `identifier` + `form`: Company + form type
- `sections`: `summary`, `business`, `risk_factors`, `mda`, `financials`, or `all`

#### 4. edgar_compare
Compare companies side-by-side or analyze an industry.

**Example prompts:**
- "Compare Apple, Microsoft, and Google on revenue and net income"
- "How do the top semiconductor companies compare?"

**Parameters:**
- `identifiers`: List of tickers/CIKs to compare
- OR `industry`: Industry name
- `metrics`: Metrics to compare (e.g., `revenue`, `net_income`)
- `periods` (default: 4): Number of periods

#### 5. edgar_ownership
Insider transactions, institutional holders, or fund portfolios.

**Example prompts:**
- "Show me recent insider transactions at Apple"
- "Who are Tesla's largest institutional holders?"
- "What stocks does Berkshire Hathaway hold?"

**Parameters:**
- `identifier` (required): Company ticker, CIK, or fund CIK
- `analysis_type`: `insiders`, `institutions`, or `fund_portfolio`
- `days` (default: 90): Lookback for insider trades
- `limit` (default: 20): Max results

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
pip install "edgartools[ai]"
# or with pip3
pip3 install "edgartools[ai]"
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
