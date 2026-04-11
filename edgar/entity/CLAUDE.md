# Entity Package

Core domain model for SEC filers (companies, funds, insiders). Provides a unified interface for accessing entity data, filings, and financial facts.

## Architecture

```
SecFiler (Abstract Base)
├── Entity (Concrete implementation)
├── Company (Entity subclass with additional features)
└── Fund (Separate in edgar.funds but integrated here)
```

## Core Components

| File | Purpose | Size |
|------|---------|------|
| `core.py` | Base classes: `SecFiler`, `Entity`, `Company` | |
| `entity_facts.py` | Company facts API integration | 63KB — read in chunks |
| `filings.py` | Entity-specific filing operations | |
| `statement.py` | Financial statement construction | |
| `statement_builder.py` | Advanced statement building logic | |
| `search.py` | Company search functionality | |

## Key Patterns

**Entity resolution**: `Company("AAPL")` resolves ticker → CIK via `edgar/reference/` data. Also accepts CIK directly.

**Facts access**: Two paths to financial data:
```python
# Path 1: via Company facts API (aggregated across filings)
company = Company("AAPL")
facts = company.get_facts()
income = facts.get_income_statement()

# Path 2: via individual filing XBRL (single filing, full detail)
filing = company.get_filings(form="10-K").latest()
xbrl = filing.xbrl()
```

**Statement building**: `statement_builder.py` uses `data/learned_mappings.json` for concept mappings and `data/virtual_trees.json` for statement structure.

## Gotchas

- **Period mismatch (Issue #408)**: SEC Facts API includes both annual and quarterly facts marked as `fiscal_period="FY"`. Duration-based filtering (>300 days = annual) is the fix. Applied in `entity_facts.py`.
- **NoCompanyFactsFound**: Investment companies and foreign filers may not have facts. Check entity type first.
- **Duplicate facts**: Facts API returns multiple versions — prefer non-amended, most recent fiscal period.
- **Cache location**: Facts cached in `~/.edgar/company_facts/`. Clear with `rm -rf ~/.edgar/company_facts/` if stale.
- **Large facts objects**: Can exceed 100MB for some companies. Use selective field access.
- **Concept variations**: Companies use non-standard taxonomies. Fix by updating `data/learned_mappings.json`.

## Integration Points

- **→ XBRL package**: `filing.xbrl()` hands off to `edgar.xbrl` for single-filing processing
- **→ Financials module**: `company.get_financials()` wraps entity facts into structured statements
- **→ Reference data**: `edgar/reference/` provides ticker/CIK lookups and form definitions

## When Making Changes

1. Test with diverse companies: AAPL (large cap), TSLA (complex), DNA (recent IPO)
2. Check facts alignment against SEC website
3. Update `data/learned_mappings.json` if adding new concept support
4. Run: `pytest tests/test_entity*.py -xvs`
