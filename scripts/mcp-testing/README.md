# EdgarTools MCP Testing Scripts

Helper scripts for testing the EdgarTools MCP server before release.

## Quick Start

Test the MCP server in 3 steps:

```bash
cd scripts/mcp-testing

# 1. Build and install in test environment
./install-local-mcp.sh

# 2. Configure Claude Desktop
./configure-claude-mcp.sh

# 3. Watch logs while testing
./watch-mcp-logs.sh
```

## Scripts

### 1. install-local-mcp.sh

Builds EdgarTools from source and installs it in a test virtual environment.

**Usage:**
```bash
./install-local-mcp.sh [venv_path]
```

**What it does:**
- Builds wheel distribution with `hatch build`
- Creates fresh virtual environment (default: `/tmp/edgartools-mcp-test`)
- Installs package with `[ai]` extras
- Runs verification test (`python -m edgar.ai --test`)
- Shows Python path for Claude Desktop config

**Example:**
```bash
# Use default location
./install-local-mcp.sh

# Use custom location
./install-local-mcp.sh ~/mcp-test-env
```

### 2. configure-claude-mcp.sh

Updates Claude Desktop configuration to use your test environment.

**Usage:**
```bash
./configure-claude-mcp.sh [python_path] [identity]
```

**What it does:**
- Backs up existing Claude Desktop config
- Updates config with test Python path
- Sets EDGAR_IDENTITY environment variable
- Verifies server can start
- Shows next steps

**Example:**
```bash
# Use defaults (prompts for identity)
./configure-claude-mcp.sh

# Specify everything
./configure-claude-mcp.sh /tmp/edgartools-mcp-test/bin/python "John Doe john@example.com"
```

### 3. watch-mcp-logs.sh

Monitors Claude Desktop MCP logs in real-time with color-coded output.

**Usage:**
```bash
./watch-mcp-logs.sh [options]
```

**Options:**
- `--clear` - Clear logs before watching
- `--errors` - Show only errors and warnings
- `--both` - Show both main and server logs
- `--help` - Show help message

**What it does:**
- Tails MCP log files
- Color-codes output (errors=red, warnings=yellow, info=blue)
- Shows real-time updates
- Press Ctrl+C to stop

**Examples:**
```bash
# Watch server log (default)
./watch-mcp-logs.sh

# Clear logs first, then watch
./watch-mcp-logs.sh --clear

# Show only errors
./watch-mcp-logs.sh --errors

# Watch both logs
./watch-mcp-logs.sh --both
```

### 4. test-mcp-tools.sh

Runs smoke tests to verify the MCP server is working correctly.

**Usage:**
```bash
./test-mcp-tools.sh [python_path]
```

**What it does:**
- Tests server configuration (`--test` flag)
- Verifies module imports
- Tests tool handlers
- Validates core EdgarTools functionality
- Tests workflow tools (company_research)
- Shows suggested test prompts

**Example:**
```bash
# Use default Python path
./test-mcp-tools.sh

# Use custom Python path
./test-mcp-tools.sh ~/mcp-test-env/bin/python
```

### 5. cleanup-mcp-test.sh

Removes test artifacts and optionally restores previous configuration.

**Usage:**
```bash
./cleanup-mcp-test.sh [options]
```

**Options:**
- `--all` - Remove everything (venv, logs, config)
- `--venv` - Remove only virtual environment
- `--logs` - Clear only MCP logs
- `--config` - Restore previous Claude config
- `--keep-config` - Keep current config (default)

**What it does:**
- Removes test virtual environment
- Clears MCP logs
- Optionally restores backed-up Claude config
- Shows current state after cleanup

**Examples:**
```bash
# Remove everything
./cleanup-mcp-test.sh --all

# Remove only venv
./cleanup-mcp-test.sh --venv

# Clear logs and restore config
./cleanup-mcp-test.sh --logs --config
```

## Testing Workflow

### Initial Setup

1. **Build and install:**
   ```bash
   ./install-local-mcp.sh
   ```

2. **Configure Claude Desktop:**
   ```bash
   ./configure-claude-mcp.sh
   ```

3. **Restart Claude Desktop**

### Testing Iteration

When you make changes to the code:

1. **Reinstall:**
   ```bash
   ./install-local-mcp.sh
   ```

2. **Restart Claude Desktop**

3. **Watch logs:**
   ```bash
   ./watch-mcp-logs.sh --clear
   ```

4. **Test in Claude Desktop:**
   - "Research Tesla with financials"
   - "Analyze Apple's income statement for 4 years"
   - "Show me the latest 10-K filings"

### Cleanup After Testing

```bash
# Keep config, remove venv only
./cleanup-mcp-test.sh --venv

# Full cleanup
./cleanup-mcp-test.sh --all
```

## Test Checklist

Use this checklist to verify all functionality:

### Installation Tests
- [ ] Fresh install completes without errors
- [ ] `python -m edgar.ai --test` passes all checks
- [ ] Package includes all dependencies

### Configuration Tests
- [ ] Claude Desktop config updates successfully
- [ ] Config backup created
- [ ] Python path is correct
- [ ] EDGAR_IDENTITY is set

### Functional Tests
- [ ] Server starts in Claude Desktop
- [ ] MCP indicator (🔨) appears
- [ ] All 4 tools visible in tool list

### Workflow Tool Tests

**edgar_company_research:**
- [ ] Minimal detail level works
- [ ] Standard detail level works
- [ ] Detailed level works
- [ ] Financials appear when requested
- [ ] Error handling works (invalid ticker)

**edgar_analyze_financials:**
- [ ] Single statement works (income only)
- [ ] Multiple statements work
- [ ] Annual periods work
- [ ] Quarterly periods work
- [ ] Error handling works

**Legacy Tools:**
- [ ] edgar_get_company works
- [ ] edgar_current_filings works

### Log Tests
- [ ] Server logs to stderr properly
- [ ] Errors are clear and actionable
- [ ] No unexpected warnings

## Troubleshooting

### "spawn python ENOENT" error

Check that your Python path is correct:

```bash
# Verify Python exists
/tmp/edgartools-mcp-test/bin/python --version

# Reconfigure if needed
./configure-claude-mcp.sh
```

### Module import errors

Reinstall with AI extras:

```bash
./cleanup-mcp-test.sh --venv
./install-local-mcp.sh
```

### Server won't start

Check the logs:

```bash
./watch-mcp-logs.sh
```

Then restart Claude Desktop and watch for errors.

### Test script fails

Run the test script to see specific failures:

```bash
./test-mcp-tools.sh
```

## Advanced Usage

### Testing with Multiple Environments

You can maintain multiple test environments:

```bash
# Development environment
./install-local-mcp.sh ~/mcp-dev

# Staging environment
./install-local-mcp.sh ~/mcp-staging

# Switch between them
./configure-claude-mcp.sh ~/mcp-dev/bin/python
# or
./configure-claude-mcp.sh ~/mcp-staging/bin/python
```

### Continuous Log Monitoring

Keep logs visible during testing:

```bash
# Terminal 1: Watch logs
./watch-mcp-logs.sh --clear

# Terminal 2: Run tests or use Claude Desktop
```

### Automated Testing

Create a test script that runs all checks:

```bash
#!/bin/bash
./install-local-mcp.sh && \
./test-mcp-tools.sh && \
./configure-claude-mcp.sh && \
echo "Ready to test in Claude Desktop"
```

## macOS Specific Notes

- Python is typically `python3` on macOS (Homebrew installs)
- Claude Desktop config location: `~/Library/Application Support/Claude/`
- Logs location: `~/Library/Logs/Claude/`

## Support

If you encounter issues:

1. Check the logs with `./watch-mcp-logs.sh`
2. Run verification: `./test-mcp-tools.sh`
3. See main docs: `../../edgar/ai/docs/MCP_QUICKSTART.md`
4. File an issue: https://github.com/dgunning/edgartools/issues
