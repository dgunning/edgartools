---
title: "Give Claude a Bloomberg Terminal: The EdgarTools MCP Server"
description: "EdgarTools now ships an MCP server that gives Claude and other AI agents direct access to every SEC filing, financial statement, and company disclosure — no API key, no paywall, no setup beyond two lines of config."
keywords: ["edgartools", "mcp server", "claude desktop", "sec edgar", "python", "sec filings", "model context protocol", "ai agent", "financial data", "xbrl", "sec edgar api", "claude mcp", "sec filing analysis", "insider trading", "institutional ownership", "edgar python", "mcp tools"]
tags: ["mcp", "ai", "sec-edgar", "release"]
slug: edgartools-mcp-server
date: 2026-03-25
---

# Give Claude a Bloomberg Terminal: The EdgarTools MCP Server

*13 tools. Zero API keys. Every SEC filing ever made.*

---

Here's something I've noticed over the past year: people don't want a Python library for SEC filings. They want *answers* about SEC filings. "What did Tesla's insiders do last quarter?" "How does Nvidia's revenue growth compare to AMD?" "What was just filed with the SEC in the last hour?"

The Python library gets you there. But increasingly, the person asking the question isn't writing Python — they're talking to Claude.

So we built an MCP server.

## What MCP Is (and Why You Should Care)

The [Model Context Protocol](https://modelcontextprotocol.io/) is an open standard from Anthropic that lets AI agents call external tools. Think of it as USB-C for AI: a single plug that connects Claude to any data source — databases, APIs, file systems, or in our case, every filing in the SEC's EDGAR database.

Before MCP, getting Claude to analyze SEC filings meant copying and pasting text into the chat window. With MCP, Claude can *query the SEC directly*. It can pull filings, parse XBRL, compare companies, and monitor live filing activity — all without you lifting a finger.

## 13 Tools, Organized by What You Actually Want to Do

Most API wrappers expose endpoints. We designed tools around **intent**. You don't call `get_filing_by_accession_number` and then `parse_xbrl_instance` — you ask a question and the right tool handles the plumbing.

### Discover

| Tool | What it does |
|------|-------------|
| **edgar_company** | Start here. One call gets you profile, financials, filings, and ownership for any company. |
| **edgar_search** | Find companies by name or list filings by form type. |
| **edgar_screen** | Filter companies by industry, exchange, or state — using local data, zero API calls. |
| **edgar_text_search** | Full-text search across filing content via SEC EFTS. |
| **edgar_monitor** | See what was filed with the SEC *in the last hour*. |

### Examine

| Tool | What it does |
|------|-------------|
| **edgar_filing** | Parse any filing by URL or accession number into a structured object — 10-K, Form 4, 13F, proxy statement. |
| **edgar_read** | Extract specific sections: risk factors, MD&A, business description, financial statements. |
| **edgar_notes** | Drill into notes and disclosures — the detail behind financial statement numbers. |

### Analyze

| Tool | What it does |
|------|-------------|
| **edgar_trends** | Revenue, income, EPS time series with YoY and QoQ growth rates. XBRL-sourced. |
| **edgar_compare** | Side-by-side company comparison with automatic peer selection. |
| **edgar_ownership** | Insider transactions (Form 4) and institutional portfolios (13F). |
| **edgar_fund** | Mutual funds, ETFs, BDCs, money market funds — holdings, yields, performance. |
| **edgar_proxy** | Executive compensation and pay-vs-performance from DEF 14A proxy statements. |

The one that surprises people most is `edgar_monitor`. No other financial data MCP server offers a live filings feed. Claude can watch what's being filed *right now* and flag anything interesting — a new 8-K from a company you follow, a Form 4 insider purchase, a 13F portfolio disclosure.

## Setup: Two Minutes, No API Key

Every SEC filing is public data. EDGAR is a free, open API maintained by the US government. You don't need a Bloomberg terminal, a FactSet subscription, or an API key. You need two lines of JSON.

### Claude Desktop

Open Settings → Developer → Edit Config:

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

That's it. Restart Claude Desktop. You now have full SEC EDGAR access.

The `EDGAR_IDENTITY` is a [SEC requirement](https://www.sec.gov/os/webmaster-faq#developers) — they ask that automated tools identify themselves with a name and email. No registration, no approval process. Just tell them who you are.

### Claude Code

```bash
claude mcp add edgartools -- uvx --from "edgartools[ai]" edgartools-mcp
```

### Verify It Works

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

## What This Looks Like in Practice

Once the server is running, you just talk to Claude. No special syntax. No tool names to memorize.

**"What did Nvidia file this quarter?"**

Claude calls `edgar_company` with `identifier=NVDA` and `include=filings`, returning the latest 10-Q, 8-Ks, proxy statements, and insider transactions — all structured, not raw HTML.

**"Compare Microsoft and Google's revenue growth over the last 5 years"**

Claude calls `edgar_trends` for both companies, pulls XBRL-sourced revenue data, computes year-over-year growth rates, and presents a side-by-side table. No scraping. No manual data entry.

**"Has any insider at CrowdStrike sold shares in the last 30 days?"**

Claude calls `edgar_ownership` with `analysis_type="insiders"` and `identifier="CRWD"`, returning Form 4 transactions — who sold, how many shares, at what price, and whether it was a planned 10b5-1 trade or a discretionary sale.

**"Show me what 8-Ks were filed in the last hour"**

Claude calls `edgar_monitor` and filters for form 8-K. You get real-time awareness of material events — earnings releases, leadership changes, acquisitions — as they hit the SEC's servers.

**"Read the risk factors from Tesla's latest 10-K"**

Claude calls `edgar_filing` to find the latest 10-K, then `edgar_read` to extract Item 1A — Risk Factors. You get structured text, not a 200-page PDF.

## Pre-Built Workflows

For common research patterns, the server ships with **7 multi-step prompts** that chain tools together:

| Prompt | What it does |
|--------|-------------|
| **due_diligence** | Full company analysis — profile, financials, risks, insider activity |
| **earnings_analysis** | Earnings deep dive — latest 8-K, trends, peer comparison |
| **industry_overview** | Sector survey — screen companies, compare top players, identify trends |
| **insider_monitor** | Track insider buying and selling patterns |
| **fund_analysis** | Mutual fund or ETF deep dive — holdings, performance, fund family |
| **filing_comparison** | Compare filings across time or across companies |
| **activist_tracking** | Monitor SC 13D/G activist investor positions |

These are templates, not black boxes. Claude follows them step by step, and you can interrupt, redirect, or drill deeper at any point.

## What Makes This Different

There are other financial data MCP servers. Here's why this one is worth your attention:

**Free.** Not freemium, not "free tier with limits." Free. SEC EDGAR is a public resource funded by filing fees that public companies already pay. EdgarTools is MIT-licensed open source. The data flows from the SEC to your Claude session with no intermediary extracting rent.

**No API key.** No signup form. No OAuth flow. No usage dashboard. Set your `EDGAR_IDENTITY` and go.

**Live data.** `edgar_monitor` gives you a live feed of what's being filed right now. Most financial data services give you data from yesterday. The SEC publishes filings within minutes of receipt.

**Structured, not raw.** When Claude parses a 10-K through EdgarTools, it gets a typed `TenK` object with extracted financials, notes, and sections — not raw HTML that it has to interpret on the fly. Same for Form 4 insider transactions, 13F institutional holdings, DEF 14A proxy statements, and 30+ other form types.

**Intent-based design.** Tools match how analysts think, not how APIs are structured. "Tell me about Apple" is one tool call, not five.

**Intelligent errors.** If you ask for a company that doesn't exist, the server doesn't return a 404. It returns a structured error with suggestions: "Did you mean AAPL? Try edgar_search to find the right name."

## Deployment Options

The server runs anywhere Python runs:

| Method | Command | Best for |
|--------|---------|----------|
| **uvx** | `uvx --from "edgartools[ai]" edgartools-mcp` | Individual use, no install needed |
| **pip** | `pip install "edgartools[ai]"` then `edgartools-mcp` | Permanent install |
| **Docker** | `docker run -i hackerdogs/edgartools-mcp` | Team servers, CI/CD |
| **HTTP** | `edgartools-mcp --transport streamable-http --port 8000` | Remote / multi-user |

The server is stateless — no database, no session storage, no persistent data. Every request goes directly to the SEC. You can run it behind a load balancer, scale it horizontally, or tear it down and restart it with zero consequences.

## The Bigger Picture

EdgarTools started as a Python library. Then it became the most popular way to access SEC data in Python — [2.3 million downloads](https://pypi.org/project/edgartools/) and counting. The MCP server is the next step: making that same data accessible to AI agents that are increasingly doing the analytical work that used to require a human with a Bloomberg terminal.

The SEC files 500,000+ submissions a year. Every 10-K, every 8-K, every Form 4, every 13F — all of it is public data that tells you what's happening inside American companies. The hard part was never access. It was parsing, structuring, and making sense of it. That's what EdgarTools does, and now Claude can do it too.

```bash
# Start here
uvx --from "edgartools[ai]" edgartools-mcp --test
```

---

*[EdgarTools](https://github.com/dgunning/edgartools) is open source under the MIT license. The MCP server is registered in the [official MCP registry](https://github.com/modelcontextprotocol/servers). Contributions, bug reports, and [GitHub stars](https://github.com/dgunning/edgartools/stargazers) are always welcome.*
