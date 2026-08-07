---
title: "Give Claude a Bloomberg Terminal: The EdgarTools MCP Server for SEC Filings"
description: "EdgarTools ships a free, open-source MCP server that connects Claude to SEC EDGAR — 13 tools for financial statements, insider trading, company filings, and live SEC data. No API key required. Python library with 2M+ downloads."
keywords: ["edgartools", "mcp server", "claude desktop", "sec edgar", "python", "sec filings", "model context protocol", "ai agent", "financial data", "xbrl", "sec edgar api", "claude mcp", "sec filing analysis", "insider trading", "institutional ownership", "edgar python", "mcp tools", "sec edgar python library", "xbrl parser python", "claude desktop mcp server", "financial data api free", "sec filings api", "10-K parser", "form 4 insider trading", "13F institutional holdings"]
tags: ["mcp", "ai", "sec-edgar", "python", "financial-data"]
slug: edgartools-mcp-server
date: 2026-03-25
---

# Give Claude a Bloomberg Terminal: The EdgarTools MCP Server

*13 tools. Zero API keys. Every SEC filing ever made.*

---

The question used to be "how do I pull data from SEC filings?" Now it's "why can't Claude do it for me?" Analysts, compliance teams, research desks — they've moved on. They're working inside AI tools, and they expect those tools to know what Apple reported last quarter. Instead they get hallucinated numbers, or a polite apology, or a suggestion to go check EDGAR themselves.

The answer is [MCP](https://modelcontextprotocol.io/) — Model Context Protocol. An AI model only knows what's in its context window. It can't reach out and pull a 10-K. MCP is the standard that lets the scaffolding around the model do that on its behalf — fetch real data from external sources and feed it back in. You're reading this because you're the developer, the quant, the data engineer who's going to wire that up. You're the person who connects the model to the data your team is already asking it about.

[EdgarTools](https://github.com/dgunning/edgartools) — the most popular Python library for SEC EDGAR data — now ships an MCP server that does exactly that. 13 tools that give any MCP-compatible AI assistant — Claude Desktop, Claude Code, or your own internal application — structured access to every SEC filing, financial statement, and company disclosure. No API key, no paywall. The model stops guessing and starts pulling real data.

![How the EdgarTools MCP server connects Claude to SEC EDGAR](images/mcp-architecture.webp)

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

![13 MCP tools organized by intent: Discover, Examine, Analyze](images/mcp-tool-organization.webp)

The one that surprises people most is `edgar_monitor`. No other financial data MCP server offers a live filings feed. Claude can watch what's being filed *right now* and flag anything interesting — a new 8-K from a company you follow, a Form 4 insider purchase, a 13F portfolio disclosure.

## Setup: Two Minutes, No API Key

Every SEC filing is public data. The SEC EDGAR API is free and maintained by the US government. You don't need a Bloomberg terminal, a FactSet subscription, or a financial data API key. You need two lines of JSON.

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
✓ EdgarTools v5.26.1 imports successfully
✓ MCP framework available
✓ 13 tools registered
✓ EDGAR_IDENTITY configured
✓ All checks passed — MCP server is ready to run
```

## What This Looks Like in Practice

Once the server is running, you just talk to Claude. No special syntax. No tool names to memorize. Here's what actually comes back — real data from real SEC filings.

![Claude Desktop showing Tim Cook's compensation data pulled from SEC EDGAR via EdgarTools](images/claude-desktop-tim-cook-compensation.webp)

**"What is Apple's CEO compensation?"**

Claude calls `edgar_proxy` and gets structured data from Apple's latest DEF 14A proxy statement — in under a second:

```json
{
  "company": "Apple Inc.",
  "form": "DEF 14A",
  "filing_date": "2026-01-08",
  "ceo": {
    "name": "Mr. Cook",
    "total_comp": 74294811,
    "actually_paid": 108423733
  },
  "pay_vs_performance": {
    "company_tsr": 233.88,
    "peer_tsr": 279.51,
    "net_income": 112010000000
  },
  "performance_measures": ["Net Sales", "Operating Income", "Relative TSR"]
}
```

CEO total compensation, actually-paid comp, total shareholder return vs peers, and the company's own performance measures — all extracted from XBRL-tagged proxy statement data. The kind of executive compensation analysis that used to require manually reading a 60-page DEF 14A.

---

**"Compare Apple, Microsoft, and Google on revenue and margins"**

Claude calls `edgar_compare` and pulls XBRL financials for all three companies:

```json
{
  "companies": [
    {"name": "Apple Inc.",      "revenue": 416161000000, "net_margin": "26.9%", "gross_margin": "46.9%"},
    {"name": "MICROSOFT CORP",  "revenue": 375000000000, "net_margin": "27.2%", "gross_margin": "69.9%"},
    {"name": "Alphabet Inc.",   "revenue": 405640000000, "net_margin": "27.8%", "gross_margin": "58.3%"}
  ]
}
```

Three companies, side-by-side, with computed margins. Each company also gets multi-period income statements for trend context. One tool call.

---

**"Show me Microsoft's revenue trend"**

Claude calls `edgar_trends` and returns multi-year time series with growth rates:

```json
{
  "company": "MICROSOFT CORP",
  "trends": {
    "revenue": {
      "values": [
        {"value": 375000000000, "period": "2025"},
        {"value": 245122000000, "period": "2024"},
        {"value": 211915000000, "period": "2023"}
      ],
      "growth_rates": [
        {"period": "2025", "growth": "53.0%"},
        {"period": "2024", "growth": "15.7%"}
      ],
      "cagr": "33.0%"
    }
  }
}
```

Year-over-year growth rates and CAGR computed automatically from XBRL financial data. No web scraping. No manual data entry. No CSV downloads.

---

**"Show me what 8-Ks were filed in the last hour"**

Claude calls `edgar_monitor` and returns what was *just filed today*:

```json
{
  "filings": [
    {"form": "8-K", "filed": "2026-03-26", "company": "Haymaker Acquisition Corp. 4"},
    {"form": "8-K", "filed": "2026-03-26", "company": "GUOCHUN INTERNATIONAL INC."},
    {"form": "8-K", "filed": "2026-03-26", "company": "Quoin Pharmaceuticals, Ltd."}
  ]
}
```

Real-time awareness of material events — earnings releases, leadership changes, acquisitions — as they hit the SEC's servers.

---

**"What does Apple's debt note say?"**

Claude calls `edgar_notes` and drills into the financial statement disclosures:

```json
{
  "company": "Apple Inc. [AAPL]",
  "total_notes": 16,
  "topic": "debt",
  "notes": [{
    "number": 9,
    "title": "Debt",
    "expands": ["Commercial paper", "Term debt"],
    "expands_statements": ["BalanceSheet", "CashFlowStatement"],
    "context": "The Company issues unsecured short-term promissory notes pursuant to a commercial paper program..."
  }]
}
```

Which statement line items the note explains, structured tables, and the narrative text. This is how Claude explains *why* a number is what it is — not just what the number is.

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

The EdgarTools MCP server is stateless — no database, no session storage, no persistent data. Every request goes directly to the SEC. You can run it behind a load balancer, scale it horizontally, or tear it down and restart it with zero consequences.

## The Bigger Picture

EdgarTools started as a Python library for parsing SEC filings. Then it became the most popular way to access SEC EDGAR data in Python — [2.3 million downloads](https://pypi.org/project/edgartools/) and counting, used by hedge funds, academic researchers, and fintech teams. The MCP server is the next step: making that same data accessible to AI agents that are increasingly doing the analytical work that used to require a human with a Bloomberg terminal.

The SEC processes 500,000+ submissions a year. Every 10-K annual report, every 8-K material event, every Form 4 insider trade, every 13F institutional holdings disclosure — all of it is public data that tells you what's happening inside American companies. The hard part was never access. It was parsing XBRL, structuring financial statements, and making sense of it all. That's what EdgarTools does, and now Claude can do it too.

```bash
# Start here
uvx --from "edgartools[ai]" edgartools-mcp --test
```

---

*[EdgarTools](https://github.com/dgunning/edgartools) is an open-source Python library for SEC EDGAR filings, available under the MIT license. Install with `pip install edgartools`. The MCP server is registered in the [official MCP registry](https://github.com/modelcontextprotocol/servers). Full [documentation](https://dgunning.github.io/edgartools/ai/), [PyPI package](https://pypi.org/project/edgartools/), and [source code](https://github.com/dgunning/edgartools) are available. Contributions, bug reports, and [GitHub stars](https://github.com/dgunning/edgartools/stargazers) are always welcome.*

---

**Want more from your MCP server?**

The local edgartools MCP server queries EDGAR directly through Python. The **[edgar.tools hosted MCP server](https://app.edgar.tools/docs/mcp/setup?utm_source=edgartools-blog&utm_medium=see-live&utm_content=mcp-server-post)** adds AI-enriched data processed server-side:

| Capability | Local (edgartools) | Hosted (edgar.tools) |
|---|---|---|
| Material events | Basic 8-K parsing | LLM-classified event types |
| Disclosure search | — | 12 XBRL topic clusters, all years |
| Insider data | Individual Form 4s | 802K+ transactions with sentiment |
| Filing sections | Raw text | AI summaries and key takeaways |

Free tier: truncated MCP responses. Professional ($24.99/mo): full results.

**[Set up the hosted MCP server →](https://app.edgar.tools/docs/mcp/setup?utm_source=edgartools-blog&utm_medium=see-live&utm_content=mcp-server-post)**