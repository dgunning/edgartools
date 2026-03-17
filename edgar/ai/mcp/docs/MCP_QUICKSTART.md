# EdgarTools MCP Quickstart Guide

This guide helps you get the EdgarTools MCP server running in under 5 minutes -- whether you're setting up Claude Desktop on your laptop, deploying a shared server for your team, or running a containerized instance in production.

## Installation

```bash
# Install EdgarTools with AI features
pip install "edgartools[ai]"
```

## Starting the Server

EdgarTools provides several ways to start the MCP server:

### Option 1: uvx (No installation required)
```bash
uvx --from "edgartools[ai]" edgartools-mcp
```
This runs the server in an isolated environment without needing to install edgartools globally. Requires [uv](https://docs.astral.sh/uv/getting-started/installation/). Ideal for individual use or scripted deployment.

### Option 2: Python Module
```bash
python -m edgar.ai
```

### Option 3: Console Script
```bash
edgartools-mcp
```

### Option 4: Docker
```bash
docker run -i hackerdogs/edgartools-mcp
```

Or build your own:

```dockerfile
FROM python:3.12-slim
RUN pip install "edgartools[ai]"
ENV EDGAR_IDENTITY="Your Name your.email@example.com"
ENTRYPOINT ["python", "-m", "edgar.ai"]
```

Docker is ideal for server deployments, CI/CD pipelines, and teams that want a consistent, isolated runtime.

All methods start the MCP server using stdio transport by default. The server is stateless -- it makes SEC API calls on demand and holds no persistent data, which makes it straightforward to run centrally for a team.

### Option 5: HTTP Transport (Remote / Team Deployment)
```bash
edgartools-mcp --transport streamable-http --port 8000
```

This starts the server on `http://0.0.0.0:8000/mcp` using the MCP Streamable HTTP transport. Use this for remote deployments, team servers, or registry-listed instances.

**CLI flags:**
- `--transport stdio` (default) or `--transport streamable-http`
- `--host 0.0.0.0` (default) — bind address
- `--port 8000` (default) — listen port

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

**Configuration with uvx (Recommended — no Python setup needed):**
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

> **Note:** On macOS, Claude Desktop may not find `uvx` in your PATH. If you get a "spawn uvx ENOENT" error, use the full path (find it with `which uvx`):
> ```json
> "command": "/Users/yourname/.local/bin/uvx"
> ```

**Configuration with Python (macOS):**
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

**Configuration with Python (Windows):**
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

**Configuration for Remote HTTP Server:**

If the server is running with `--transport streamable-http`:
```json
{
  "mcpServers": {
    "edgartools": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Replace `localhost:8000` with your server's host and port for remote deployments.

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

### Deploying for a Team

The EdgarTools MCP server is stateless -- it queries the SEC API on each request and holds no session data. This makes it straightforward to deploy centrally:

- **Docker**: Run the container on a shared server and point team members' MCP clients to it
- **Multiple instances**: Safe to run multiple instances behind a load balancer since there's no shared state
- **Configuration templates**: Create per-client config files with the appropriate `EDGAR_IDENTITY` for your organization

See [hackerdogs/edgartools-mcp](https://hub.docker.com/r/hackerdogs/edgartools-mcp) on Docker Hub for a community-maintained container with config templates for multiple clients.

## Available Tools

Once connected, AI agents have access to these tools:

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
Examine any SEC filing by accession number or URL.

**Example prompts:**
- "Tell me about filing 0000320193-23-000077"
- "What's in this SEC filing?" (paste URL)

**Parameters:**
- `input` (required): Accession number or SEC URL
- `detail`: `minimal`, `standard` (default), or `full`

#### 4. edgar_read
Read specific sections from a filing.

**Example prompts:**
- "Show me the risk factors from Apple's latest 10-K"
- "Get the MD&A section from Tesla's most recent annual report"

**Parameters:**
- `accession_number`: SEC accession number
- OR `identifier` + `form`: Company + form type
- `sections`: `summary`, `business`, `risk_factors`, `mda`, `financials`, or `all`

#### 5. edgar_compare
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
Insider transactions or fund portfolios.

**Example prompts:**
- "Show me recent insider transactions at Apple"
- "What stocks does Berkshire Hathaway hold?"

**Parameters:**
- `identifier` (required): Company ticker, CIK, or fund CIK
- `analysis_type`: `insiders`, `fund_portfolio`, or `portfolio_diff`
- `limit` (default: 20): Max results

#### 6. edgar_monitor
Get the latest SEC filings in real-time.

**Example prompts:**
- "What SEC filings were just submitted?"
- "Show me recent 8-K filings"

**Parameters:**
- `form`: Filter by form type (e.g., `8-K`, `4`)
- `limit` (default: 20): Max results

#### 7. edgar_trends
Get financial time series with growth rates.

**Example prompts:**
- "Show me Apple's revenue trend over 5 years"
- "What is Microsoft's EPS growth trajectory?"

**Parameters:**
- `identifier` (required): Company ticker, CIK, or name
- `concepts`: Metrics to track (e.g., `revenue`, `net_income`, `eps`)
- `periods` (default: 5): Number of periods

#### 8. edgar_screen
Discover companies by industry, exchange, or state.

**Example prompts:**
- "Find pharmaceutical companies on NYSE"
- "What software companies are incorporated in Delaware?"

**Parameters:**
- `industry`: Industry keyword
- `exchange`: Exchange name (e.g., `NYSE`, `Nasdaq`)
- `state`: State of incorporation (2-letter code)
- `limit` (default: 20): Max results

#### 9. edgar_text_search
Full-text search across SEC filing content.

**Example prompts:**
- "Search for filings mentioning artificial intelligence"
- "Find 8-K filings about cybersecurity incidents"

**Parameters:**
- `query` (required): Search text
- `identifier`: Limit to a specific company
- `forms`: Filter by form types (e.g., `["8-K", "10-K"]`)
- `start_date`: Start date filter

#### 10. edgar_fund
Get fund, ETF, BDC, and money market fund data.

**Example prompts:**
- "Look up the Vanguard 500 Index Fund"
- "Show me SPY's portfolio holdings"
- "What money market funds does Vanguard offer?"

**Parameters:**
- `action` (required): `lookup`, `search`, `portfolio`, `money_market`, `bdc_search`, or `bdc_portfolio`
- `identifier`: Fund ticker, series ID, or CIK
- `query`: Search text for fund or BDC name
- `limit` (default: 20): Max results

#### 11. edgar_proxy
Get executive compensation and governance data from DEF 14A proxy statements.

**Example prompts:**
- "What is Apple's CEO compensation?"
- "Show me Microsoft's pay vs performance data"

**Parameters:**
- `identifier` (required): Company ticker, CIK, or name
- `filing_index` (default: 0): Which proxy filing (0=latest)

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
