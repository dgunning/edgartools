# MCP Server Setup

Get the EdgarTools MCP server running in under 2 minutes. Once connected, Claude can query any SEC filing, extract financial data, and analyze companies directly.

## Quick Setup

### Claude Desktop

Add to your config file and restart Claude Desktop:

#### uvx (recommended -- zero install)

No Python installation needed. Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

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

If you get a "spawn uvx ENOENT" error on macOS, use the full path (find it with `which uvx`).

#### Python

Requires `pip install "edgartools[ai]"` first.

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

**Config file location:**

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Or: Claude Desktop → Settings → Developer → Edit Config.

### Claude Code

```bash
claude mcp add edgartools -- uvx --from "edgartools[ai]" edgartools-mcp
```

Set your SEC identity:
```bash
export EDGAR_IDENTITY="Your Name your.email@example.com"
```

### Verify

Before configuring any client, confirm the server works:

```bash
uvx --from "edgartools[ai]" edgartools-mcp --test
```

```
✓ EdgarTools v5.26.0 imports successfully
✓ MCP framework available
✓ 13 tools registered
✓ EDGAR_IDENTITY configured
✓ All checks passed — MCP server is ready to run
```

After configuring Claude Desktop, look for the MCP tools icon in the bottom-right of the chat input. Try asking: *"What did Apple file with the SEC this quarter?"*

## EDGAR_IDENTITY

The SEC [requires](https://www.sec.gov/os/webmaster-faq#developers) that automated tools identify themselves. Set `EDGAR_IDENTITY` to your name and email:

```
EDGAR_IDENTITY="Jane Smith jane.smith@example.com"
```

No registration. No approval process. No API key. Just tell them who you are. If not set, the server starts with a warning and SEC API requests may be rate-limited.

## Other MCP Clients

The server works with any MCP-compatible client. The `mcpServers` config block is the same -- only the config file location changes:

| Client | Config location |
|--------|----------------|
| **Claude Desktop** | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) |
| **Cline** | `.vscode/cline_mcp_settings.json` in your project |
| **Continue.dev** | `~/.continue/config.json` |

## Advanced Deployment

### Docker

For server deployments, CI/CD pipelines, or teams that want isolated runtime:

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

See [hackerdogs/edgartools-mcp](https://hub.docker.com/r/hackerdogs/edgartools-mcp) on Docker Hub for a community-maintained container.

### HTTP Transport (Team / Remote)

For shared servers or multi-user deployments, use Streamable HTTP transport:

```bash
edgartools-mcp --transport streamable-http --port 8000
```

Clients connect with a URL instead of launching a subprocess:

```json
{
  "mcpServers": {
    "edgartools": {
      "url": "http://your-server:8000/mcp"
    }
  }
}
```

| Flag | Default | Description |
|------|---------|-------------|
| `--transport` | `stdio` | `stdio` or `streamable-http` |
| `--host` | `0.0.0.0` | Bind address |
| `--port` | `8000` | Listen port |

The server is stateless -- no database, no session storage. Safe to run multiple instances behind a load balancer.

Docker with HTTP transport:

```dockerfile
FROM python:3.12-slim
RUN pip install "edgartools[ai]"
ENV EDGAR_IDENTITY="Your Name your.email@example.com"
ENTRYPOINT ["edgartools-mcp", "--transport", "streamable-http"]
EXPOSE 8000
```

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

## Troubleshooting

**"EDGAR_IDENTITY environment variable is required"**

Add your name and email to the `env` section of your MCP config.

**"Module edgar.ai not found"**

Install with AI extras: `pip install "edgartools[ai]"`

**"spawn python ENOENT" (macOS)**

Use `python3` instead of `python`, or specify the full path (find it with `which python3`).

**MCP server not appearing in Claude Desktop**

1. Verify JSON syntax in your config file
2. Restart Claude Desktop completely (quit and relaunch)
3. Run `edgartools-mcp --test` to verify server health

**Claude answers questions without calling any tools**

Claude may use its training data instead of querying EDGAR. Be specific: *"Using your SEC tools, show me Apple's latest 10-K financials"* or *"Check EDGAR for Tesla's recent insider transactions."*

## Migration from Legacy Setup

If you're using the old `run_mcp_server.py` entry point:

```json
// Old (deprecated)
{ "command": "python", "args": ["/path/to/edgartools/edgar/ai/run_mcp_server.py"] }

// New
{ "command": "uvx", "args": ["--from", "edgartools[ai]", "edgartools-mcp"] }
```

The old entry point still works but shows a deprecation warning.
