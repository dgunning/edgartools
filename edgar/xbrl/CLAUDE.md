# XBRL Package - AI Assistant Guide

## Package Overview
The `edgar.xbrl` package handles **XBRL (eXtensible Business Reporting Language)** parsing, processing, and rendering from SEC filings. This package is responsible for converting raw XBRL XML into structured financial statements and queryable facts.

## Critical Architecture Points

### Class Hierarchy
```
XBRL (Core parser & data container)
├── FactsView (Query interface for facts)
├── FactQuery (Fluent query builder)
├── Statement (Single financial statement)
└── RenderedStatement (Rich-formatted statement output)
```

### Core Components
1. **xbrl.py** - Main XBRL parser and data container
2. **facts.py** - Query interface and fact processing
3. **statements.py** - Financial statement abstraction
4. **rendering.py** - Rich table formatting and display
5. **periods.py** - Period selection and fiscal logic
6. **models.py** - Data models for XBRL structures

## Data Availability Checking Methods

### 1. **Direct Fact Counting**
```python
# Basic fact counting
xbrl = filing.xbrl()
total_facts = len(xbrl._facts)           # Raw facts count
total_contexts = len(xbrl.contexts)      # Context count
total_periods = len(xbrl.reporting_periods)  # Available periods
```

### 2. **FactsView Query Interface** (Primary Method)
```python
facts = xbrl.facts
# Query builder methods:
facts.query().by_concept("Revenue").by_period_key("duration_2024-01-01_2024-12-31").to_dataframe()
facts.query().by_statement_type("IncomeStatement").by_fiscal_year(2024).to_dataframe()
facts.query().by_label("Net Income", exact=True).limit(10).to_dataframe()
```

**Available Query Filters:**
- `by_concept(pattern, exact=False)` - Filter by XBRL concept name
- `by_label(pattern, exact=False)` - Filter by display label
- `by_period_key(period_key)` - Filter by specific period
- `by_period_type("instant"|"duration")` - Filter by period type
- `by_statement_type(statement)` - Filter by statement type
- `by_fiscal_year(year)` - Filter by fiscal year
- `by_fiscal_period("FY"|"Q1"|"Q2"|"Q3"|"Q4")` - Filter by fiscal period
- `by_dimension(dimension, value)` - Filter by dimensional data
- `by_value(filter_func)` - Filter by fact values
- `by_custom(filter_func)` - Custom filter functions

### 3. **Period-Specific Data Checking**
```python
# Check facts for specific periods
period_key = "duration_2024-01-01_2024-12-31"
period_facts = facts.query().by_period_key(period_key).to_dataframe()
fact_count = len(period_facts)

# Check essential concepts for a statement
income_facts = facts.query().by_statement_type("IncomeStatement").by_period_key(period_key).to_dataframe()
revenue_facts = facts.query().by_concept("Revenue").by_period_key(period_key).to_dataframe()
```

### 4. **Statement-Level Data Availability**
```python
# Check if statement has data
try:
    statement = xbrl.statements.income_statement()
    data_available = statement is not None
except StatementNotFound:
    data_available = False

# Get raw statement data for analysis
stmt_data = xbrl.get_statement("IncomeStatement")
line_items = len(stmt_data) if stmt_data else 0
```

### 5. **Stitching Query Interface** (Multi-filing)
```python
from edgar.xbrl.stitching import XBRLS
xbrls = XBRLS([xbrl1, xbrl2, xbrl3])
stitched_facts = xbrls.facts.query().by_concept("Revenue").to_dataframe()
```

## Period Selection Logic

### Current Implementation (`periods.py`)
The period selection uses sophisticated fiscal-aware logic:

**For Annual Reports (FY):**
- Filters periods by duration > 300 days (prevents quarterly data)
- Selects up to 3 fiscal years for trend analysis
- Respects fiscal year boundaries and dates

**For Quarterly Reports (Q1-Q4):**
- Attempts year-over-year quarterly comparison
- Includes YTD periods when available
- Uses intelligent duration-based classification

**Key Functions:**
- `determine_periods_to_display()` - Main period selection
- `get_period_views()` - Available period view options
- `filter_periods_by_type()` - Filter instant vs duration
- `sort_periods()` - Sort by date (newest first)

## Data Quality Assessment

### 1. **Fact Completeness**
```python
def check_essential_concepts(xbrl, statement_type, period_key):
    """Check if essential concepts are present for a period."""
    essential = {
        'IncomeStatement': ['Revenue', 'NetIncome', 'OperatingIncome'],
        'BalanceSheet': ['Assets', 'Liabilities', 'Equity'],
        'CashFlowStatement': ['OperatingCashFlow', 'InvestingCashFlow', 'FinancingCashFlow']
    }
    
    required = essential.get(statement_type, [])
    found = 0
    
    for concept in required:
        facts = xbrl.facts.query().by_concept(concept).by_period_key(period_key).to_dataframe()
        if len(facts) > 0:
            found += 1
    
    return found / len(required) if required else 0.0
```

### 2. **Period Data Density**
```python
def calculate_period_density(xbrl, period_key):
    """Calculate fact density for a specific period."""
    total_facts = len(xbrl.facts.query().by_period_key(period_key).to_dataframe())
    total_concepts = len(xbrl.facts.query().by_period_key(period_key).to_dataframe()['concept'].unique())
    
    return {
        'fact_count': total_facts,
        'concept_count': total_concepts,
        'density_score': total_facts / max(total_concepts, 1)
    }
```

## Common Maintenance Tasks

### 1. **Period Selection Issues**
**Problem**: Wrong periods selected for financial statements
```python
# Debug period selection
periods = xbrl.reporting_periods
for p in periods:
    print(f"Period: {p['label']}")
    if 'duration_' in p['key']:
        parts = p['key'].split('_')
        start, end = parts[1], parts[2]
        from datetime import datetime
        duration = (datetime.strptime(end, '%Y-%m-%d') - datetime.strptime(start, '%Y-%m-%d')).days
        print(f"  Duration: {duration} days")
    print(f"  Key: {p['key']}")
```

**Solution**: Check `periods.py` duration filtering logic and fiscal year end matching.

### 2. **Missing Statement Data**
**Problem**: Statement not found or empty
```python
# Debug statement availability
all_statements = xbrl.get_all_statements()
for stmt in all_statements:
    print(f"Statement: {stmt['type']} - Role: {stmt['role']}")
    
# Check concept coverage
income_data = xbrl.get_statement("IncomeStatement")
if income_data:
    concepts = [item['concept'] for item in income_data]
    print(f"Income statement concepts: {len(concepts)}")
```

**Solution**: Check `statement_resolver.py` patterns or add custom concept mappings.

### 3. **Query Performance Issues**
**Problem**: Slow fact queries
```python
# Use caching and efficient filters
facts = xbrl.facts  # Cached after first call
df = facts.query().by_statement_type("IncomeStatement").limit(100).to_dataframe()
```

**Solution**: Use specific filters early in the chain and limit results.

## Testing Patterns

### Unit Tests
```python
# Test with known filings
def test_apple_10k_periods():
    filing = Filing(company='Apple Inc.', cik=320193, form='10-K', ...)
    xbrl = filing.xbrl()
    
    # Check period selection
    periods = determine_periods_to_display(xbrl, 'IncomeStatement')
    assert len(periods) >= 2  # At least current + prior year
    
    # Check data availability
    for period_key, label in periods:
        facts = xbrl.facts.query().by_period_key(period_key).to_dataframe()
        assert len(facts) > 10  # Reasonable fact count
```

### Integration Tests
```python
# Test full statement rendering pipeline
def test_statement_rendering():
    xbrl = filing.xbrl()
    statement = xbrl.statements.income_statement()
    assert statement is not None
    
    # Check that rendering works
    rendered = statement.render()
    assert rendered is not None
    assert len(rendered.rows) > 5
```

## Performance Considerations

### Caching Strategy
- **Facts**: Cached in `FactsView` after first `get_facts()` call
- **DataFrames**: Cached in `_facts_df_cache` after first conversion
- **Statements**: Not cached - consider caching expensive operations

### Memory Management
- Facts can be large (500+ MB for complex filings)
- Use `.limit()` in queries for large datasets
- Clear caches in batch operations: `facts._facts_cache = None`

## Integration Points

### With Entity Package
```python
# XBRL provides raw data, Entity provides business logic
filing = company.get_filings(form="10-K").latest()
xbrl = filing.xbrl()  # Raw XBRL processing
facts = company.facts.income_statement()  # Business logic & presentation
```

### With Financials Module
```python
# XBRL statements can be wrapped by financials
from edgar.financials import IncomeStatement
xbrl_stmt = xbrl.statements.income_statement()
financial_stmt = IncomeStatement(xbrl_stmt)
```

## Common Bugs & Solutions

### Bug: "No Facts Found for Period"
**Cause**: Period key doesn't match available contexts
**Solution**: 
```python
# Debug context matching
available_contexts = list(xbrl.contexts.keys())
available_periods = [p['key'] for p in xbrl.reporting_periods]
print(f"Context count: {len(available_contexts)}")
print(f"Period count: {len(available_periods)}")
```

### Bug: "Incorrect Period Selected"
**Cause**: Duration filtering not working (quarterly shown as annual)
**Solution**: Check `periods.py` lines 486+ for duration > 300 check

### Bug: "Statement Not Found"
**Cause**: Company uses non-standard presentation roles
**Solution**: Check `statement_resolver.py` and add custom patterns

## Code Style & Conventions

### Naming
- Use `xbrl` for XBRL instances
- Use `facts` for FactsView instances
- Use `stmt` for Statement objects

### Error Handling
```python
# Always handle StatementNotFound
try:
    statement = xbrl.statements.balance_sheet()
except StatementNotFound:
    log.warning(f"Balance sheet not found in {xbrl.entity_name}")
    return None
```

### Type Hints
```python
from edgar.xbrl.xbrl import XBRL
from edgar.xbrl.facts import FactsView
from edgar.xbrl.statements import Statement

def process_xbrl(xbrl: XBRL) -> Optional[Statement]:
    ...
```

## Debugging Tips

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
# Check logs for period selection, statement matching, etc.
```

### Inspect Raw Data
```python
# View raw XBRL structure
print(f"Presentation trees: {list(xbrl.presentation_trees.keys())}")
print(f"Facts sample: {list(xbrl._facts.items())[:5]}")
print(f"Context sample: {list(xbrl.contexts.items())[0]}")
```

### Test Period Selection
```python
from edgar.xbrl.periods import determine_periods_to_display
periods = determine_periods_to_display(xbrl, 'IncomeStatement')
for period_key, label in periods:
    fact_count = len(xbrl.facts.query().by_period_key(period_key).to_dataframe())
    print(f"{label}: {fact_count} facts")
```

## Quick Reference

### Get Facts for Analysis
```python
xbrl = filing.xbrl()
facts = xbrl.facts

# All revenue facts
revenue_df = facts.query().by_concept("Revenue").to_dataframe()

# Facts for specific period
q2_facts = facts.query().by_period_key("duration_2024-04-01_2024-06-30").to_dataframe()

# Income statement facts only
income_df = facts.query().by_statement_type("IncomeStatement").to_dataframe()
```

### Check Data Availability
```python
# Period fact counts
for period in xbrl.reporting_periods:
    count = len(facts.query().by_period_key(period['key']).to_dataframe())
    print(f"{period['label']}: {count} facts")

# Essential concept coverage
essentials = ['Revenue', 'NetIncome', 'OperatingIncome']
for concept in essentials:
    count = len(facts.query().by_concept(concept).to_dataframe())
    print(f"{concept}: {count} facts across all periods")
```

### Render Statements
```python
# Default rendering (auto-selected periods)
income = xbrl.statements.income_statement()
print(income)  # Rich table output

# Custom period selection
income_custom = xbrl.render_statement("IncomeStatement", 
                                     period_view="Three Recent Periods")
```

## When Making Changes

1. **Test with diverse filings**: Different companies use different taxonomies
2. **Check period logic**: Ensure annual/quarterly logic is correct
3. **Verify fact queries**: Test query performance with large datasets
4. **Update documentation**: Complex XBRL logic needs clear documentation

## Data Availability Summary

**✅ What We Have:**
- Comprehensive fact query interface (`FactsView` + `FactQuery`)
- Period-aware filtering and selection
- Statement-level data checking
- Raw fact counting and enumeration

**⚠️ What We're Missing:**
- Automated data quality scoring
- Essential concept coverage checking
- Period data density analysis
- Smart fallback when periods lack data

**🔧 Recommended Improvements:**
1. Integrate data quality checking into period selection
2. Add fact density scoring for periods
3. Create essential concept coverage reports
4. Implement smart period fallbacks

The XBRL package provides solid foundations for data availability checking through the query interface, but could benefit from higher-level data quality assessment tools.