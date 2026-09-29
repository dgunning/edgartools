"""
BDC (Business Development Company) actions of the edgar_fund MCP tool.

`edgar_fund` (edgar/ai/mcp/tools/fund.py) registers the tool and dispatches
`bdc_search`, `bdc_portfolio` and `bdc_nonaccrual` here:

- `identity`: BDC identifier resolution, activity and filing selection.
- `paging`: cursor routing and page helpers shared by the actions.
- `portfolio`: `bdc_portfolio` and its Schedule of Investments text fallback.
- `nonaccrual`: `bdc_nonaccrual`.

Private to the MCP layer; no tool is registered from this package.
"""
