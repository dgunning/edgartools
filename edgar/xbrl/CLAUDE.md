# XBRL Package

Handles XBRL parsing, processing, and rendering from SEC filings. Converts raw XBRL XML into structured financial statements and queryable facts.

## Architecture

```
XBRL (Core parser & data container)
├── FactsView (Query interface for facts)
├── FactQuery (Fluent query builder)
├── Statement (Single financial statement)
└── RenderedStatement (Rich-formatted output)
```

## Core Components

| File | Purpose | Size |
|------|---------|------|
| `xbrl.py` | Main XBRL parser and data container | 66KB — read in chunks |
| `facts.py` | Query interface and fact processing | 55KB — read in chunks |
| `statements.py` | Financial statement abstraction | 46KB — read in chunks |
| `rendering.py` | Rich table formatting and display | 72KB — read in chunks |
| `periods.py` | Period selection and fiscal logic | |
| `models.py` | Data models for XBRL structures | |
| `stitching.py` | Multi-filing fact stitching (XBRLS) | |

## Standardization Subsystem

The `standardization/` subdirectory contains the autonomous extraction quality system — mapping company-specific XBRL concepts to standardized metrics across 100+ companies.

See `docs/autonomous-system/architecture.md` for full documentation.

Key files:
- `standardization/orchestrator.py` — Multi-layer mapping engine
- `standardization/reference_validator.py` — Validation against yfinance + SEC API
- `standardization/tools/auto_eval.py` — CQS computation and gap analysis
- `standardization/tools/auto_eval_loop.py` — Overnight experiment loop
- `standardization/config/metrics.yaml` — Metric definitions (Tier 1 config)

## Key Patterns

**Period selection** (`periods.py`): Annual reports filter by duration > 300 days. Quarterly uses year-over-year comparison. Key function: `determine_periods_to_display()`.

**Fact querying**: Use `FactQuery` fluent builder:
```python
xbrl.facts.query().by_concept("Revenue").by_fiscal_year(2024).to_dataframe()
```

**Statement access**:
```python
xbrl.statements.income_statement()   # Returns Statement or raises StatementNotFound
xbrl.statements.balance_sheet()
xbrl.statements.cash_flow_statement()
```

## Gotchas

- `StatementNotFound` is raised, not `None` returned — always handle it
- Facts are cached after first `get_facts()` call; DataFrames cached after first conversion
- Facts can be large (500+ MB for complex filings) — use `.limit()` in queries
- Companies use non-standard presentation roles — check `statement_resolver.py` for patterns
- Both annual and quarterly facts can be marked as `fiscal_period="FY"` — duration is the reliable indicator (annual: 363-365 days, quarterly: ~90 days)
