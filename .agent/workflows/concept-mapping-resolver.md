---
description: Resolve XBRL concept mapping gaps for companies
---

# Concept Mapping Resolver Workflow

Use this workflow to systematically resolve XBRL concept mapping gaps for companies.

## Prerequisites

- edgartools package installed
- yfinance for validation
- Identity set: `set_identity('...')`

## Step 1: Run Initial Mapping

```bash
// turbo
python -c "
from edgar import set_identity, use_local_storage
from edgar.xbrl.standardization.orchestrator import Orchestrator
set_identity('...')
use_local_storage(True)

orchestrator = Orchestrator()
results = orchestrator.map_companies(tickers=['TICKER'], use_ai=False, validate=True)
"
```

## Step 2: Identify Gap Type

For each unresolved metric, classify:

| Gap Type | Cause | Solution |
|----------|-------|----------|
| **Industry Exclusion** | Metric N/A for industry (e.g., COGS for banks) | Add to `industry_exclusions` |
| **Concept Not Found** | Different XBRL concept name | Add fallback to `metrics.yaml` |
| **Composite Mismatch** | Sum of components differs from reference | Update extraction rules |
| **Validation Fail** | XBRL found but doesn't match yfinance | Multi-period validation |
| **Reference NaN** | yfinance returns NaN | Document in discrepancies |

## Step 3: Check Industry

```bash
// turbo
python -c "
from edgar import Company
from edgar.entity.mappings_loader import get_industry_for_sic
c = Company('TICKER')
print(f'SIC: {c.data.sic}, Industry: {get_industry_for_sic(c.data.sic)}')
"
```

## Step 4: Use Multi-Period Validation

```bash
// turbo
python -m edgar.xbrl.standardization.tools.validate_multi_period TICKER METRIC --years 3
```

## Step 5: Document Discrepancy (if applicable)

```bash
python -m edgar.xbrl.standardization.tools.discrepancy_manager add \
  TICKER METRIC --classification definition_mismatch --reason "..."
```

## Step 6: Log KPIs

```bash
// turbo
python -m edgar.xbrl.standardization.tools.kpi_tracker history
```

## Available Tools

| Tool | Purpose |
|------|---------|
| `orchestrator.py` | Run mapping for companies |
| `discrepancy_manager.py` | Add/search discrepancies |
| `kpi_tracker.py` | Track run statistics |
| `validate_multi_period.py` | 3-year validation |
| `auto_discovery.py` | Record new mappings |

## Config Files

| File | Location | Purpose |
|------|----------|---------|
| `metrics.yaml` | config/ | Known concepts, fallbacks |
| `companies.yaml` | config/ | Industry exclusions |
| `_defaults.json` | company_mappings/ | Universal extraction rules |
| `discrepancies.json` | company_mappings/ | Documented mismatches |
| `validation_history.json` | company_mappings/ | Multi-period trust |
