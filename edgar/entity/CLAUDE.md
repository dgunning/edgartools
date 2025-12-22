# Entity Package - AI Assistant Guide

## Package Overview
The `edgar.entity` package is the **core domain model** for SEC filers (companies, funds, insiders). It provides a unified interface for accessing entity data, filings, and financial facts.

## Critical Architecture Points

### Class Hierarchy
```
SecFiler (Abstract Base)
├── Entity (Concrete implementation)
├── Company (Entity subclass with additional features)
└── Fund (Separate in edgar.funds but integrated here)
```

### Core Components
1. **core.py** - Base classes (`SecFiler`, `Entity`, `Company`)
2. **entity_facts.py** - Company facts API integration (financial data)
3. **filings.py** - Entity-specific filing operations
4. **statement.py** - Financial statement construction
5. **statement_builder.py** - Advanced statement building logic
6. **search.py** - Company search functionality

## Common Maintenance Tasks

### 1. Facts API Issues
**Problem**: Company facts not loading or incorrect data
```python
# Check these areas:
# 1. entity_facts.py - get_company_facts() 
# 2. entity_facts.py - EntityFacts.__post_init__()
# 3. Check SEC API endpoint: https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
```

**Known Issues**:
- Facts API returns inconsistent units (shares vs thousands)
- Period alignment issues between facts and XBRL
- Missing data for newer companies

### 2. Statement Building Problems
**Problem**: Financial statements incomplete or misaligned
```python
# Key files to check:
# 1. statement_builder.py - build_statement()
# 2. data/learned_mappings.json - Concept mappings
# 3. data/virtual_trees.json - Statement structure

# Common fixes:
# - Update learned mappings for new concept variations
# - Check period selection logic in select_periods()
# - Verify calculation tree processing
```

### 3. Entity Resolution
**Problem**: Can't find company by ticker/CIK
```python
# Check:
# 1. tickers.py - get_cik_lookup_data()
# 2. Reference data freshness in edgar/reference/
# 3. Identity resolution in core.py - get_entity()
```

## Testing Patterns

### Unit Tests
```python
# Always test with real CIKs:
TEST_COMPANIES = {
    'AAPL': '0000320193',  # Large cap, consistent filer
    'TSLA': '0001318605',  # Complex financials
    'DNA': '0001850261',   # Recent IPO, limited history
}
```

### Integration Tests
```python
# Test full pipeline:
company = Company('AAPL')
facts = company.get_facts()
statement = facts.get_income_statement()
assert statement is not None
```

## Performance Considerations

### Caching Strategy
- EntityFacts are cached in `.edgar/company_facts/`
- Cache invalidation: 24 hours for facts
- Use `use_cache=False` for testing fresh data

### Memory Management
- Facts objects can be large (>100MB for some companies)
- Use selective field access: `facts.get_fact('Revenue')`
- Clear facts after use in batch operations

## Integration Points

### With XBRL Package
```python
# Entity provides filing access, XBRL processes it:
filing = company.get_filing('10-K')
xbrl = filing.xbrl()  # Hands off to edgar.xbrl
```

### With Financials Module
```python
# Statement objects wrap entity facts:
from edgar.financials import IncomeStatement
stmt = IncomeStatement(facts.get_income_statement())
```

## Common Bugs & Solutions

### Bug: "NoCompanyFactsFound"
**Cause**: Company may be investment company or foreign filer
**Solution**: Check entity type first:
```python
entity = get_entity(cik)
if isinstance(entity, Company):
    facts = entity.get_facts()
```

### Bug: Duplicate Facts in Statements
**Cause**: Facts API returns multiple versions
**Solution**: See `duplicate-fact-handling.md` in docs/
- Check filing dates
- Prefer non-amended values
- Use most recent fiscal period

### Bug: Statement Concepts Not Found
**Cause**: Company uses non-standard taxonomy
**Solution**: Update learned mappings:
```python
# 1. Run learning pipeline (see docs/LEARNING_PIPELINE_FINAL.md)
# 2. Update data/learned_mappings.json
# 3. Test with company's actual concepts
```

### Bug: Incorrect Period Values (Issue #408) - FIXED
**Issue**: Annual statements showing quarterly values ($64B instead of $274B)
**Root Cause**: SEC Facts API includes both annual (363 days) and quarterly (90 days) facts marked as `fiscal_period="FY"`
**Fix Applied**: Duration-based filtering in `enhanced_statement.py`:
```python
# The fix checks period duration to distinguish annual from quarterly
if fact.period_start and fact.period_end:
    duration = (fact.period_end - fact.period_start).days
    if duration > 300:  # This is truly annual
        # Include in annual periods
```
**Key Insights**:
- Both annual and quarterly facts can be marked as "FY"
- Duration is the reliable indicator (annual: 363-365 days, quarterly: ~90 days)
- Multiple versions exist from comparative filings
- Test with: `pytest tests/test_entity_facts_annual_periods.py`

## Code Style & Conventions

### Naming
- Use `entity` for generic SEC filers
- Use `company` for corporate entities only
- Use `facts` for financial data collections

### Error Handling
```python
# Always provide context in exceptions:
raise NoCompanyFactsFound(
    f"No company facts found for {self.cik} ({self.name})"
)
```

### Type Hints
```python
# Use specific types:
def get_entity(identifier: str | int) -> Entity | Company | Fund:
    ...
```

## Debugging Tips

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
# Check logs for API calls and cache hits
```

### Inspect Raw Facts
```python
# View raw JSON structure:
facts = company.get_facts()
print(facts.to_dict()['facts']['us-gaap'].keys())
```

### Test Statement Building
```python
# Use statement builder directly:
from edgar.entity.statement_builder import StatementBuilder
builder = StatementBuilder(facts)
stmt = builder.build_statement('income')
```

## Bug Reproduction Snippets

The `gists/bugs/` directory contains minimal reproducible examples of reported issues. Use these for:
1. **Understanding the issue** - Run the snippet to see the problem
2. **Testing fixes** - Verify your solution works
3. **Regression testing** - Ensure fix doesn't break later

### How to Use Bug Snippets

1. **Find relevant bug**:
```bash
# List all entity/facts related bugs
ls gists/bugs/*AAPL*.py gists/bugs/*Facts*.py
```

2. **Run the reproduction**:
```python
# Most bugs use this import pattern:
from gists.bugs.imports import *  # Sets up common imports

# Or run directly:
python gists/bugs/408-AppleCashFlow.py
```

3. **Debug systematically**:
```python
# Add debug output to understand the issue
import json
facts = aapl.facts
raw_data = facts.to_dict()

# Check specific periods
for fact in raw_data['facts']['us-gaap']['Revenue']['units']['USD']:
    if fact['fy'] == 2020:
        print(f"Period: {fact['period']}, Value: {fact['val']}, Frame: {fact.get('frame')}")
```

### Common Bug Patterns

**Pattern 1: Period Mismatch**
- Files: `408-AppleCashFlow.py`, `405-AAPLFacts.py`
- Issue: Annual values showing quarterly data
- Check: Period selection logic, frame matching

**Pattern 2: Missing Concepts**
- Files: `406-AAPLIncome.py`, `339-AMDIncome.py`
- Issue: Standard concepts not found
- Check: Learned mappings, taxonomy variations

**Pattern 3: Data Quality**
- Files: `309-MessyData.py`, `353-BlankMultistatements.py`
- Issue: Incomplete or malformed data
- Check: Data validation, error handling

### Creating New Bug Snippets

When you encounter a new bug, create a minimal reproduction:

```python
# gists/bugs/XXX-CompanyIssue.py
from gists.bugs.imports import *

"""
Issue #XXX: [Brief description]
User reports: [What user sees]
Expected: [What should happen]
Actual: [What actually happens]
"""

# Minimal code to reproduce
company = Company("TICKER")
# ... minimal steps to show bug ...

# Add assertion that should pass when fixed
# assert expected_value == actual_value
```

## Package Dependencies

**Internal**:
- `edgar.core` - Configuration, identity
- `edgar.reference` - Static data lookups
- `edgar.httpclient` - API communication
- `edgar.xbrl` - XBRL processing (optional)

**External**:
- `httpx` - HTTP client
- `pydantic` - Data validation
- `rich` - Terminal display
- `pandas` - Data manipulation

## Future Improvements (TODO)

1. **Async Facts Loading** - Parallel fetch for multiple companies
2. **Smart Concept Learning** - ML-based concept mapping
3. **Facts Validation** - Detect and fix data anomalies
4. **Statement Templates** - Industry-specific statements
5. **Real-time Updates** - WebSocket for live facts

## Quick Reference

### Get Company and Facts
```python
from edgar import Company
company = Company('AAPL')
facts = company.get_facts()
```

### Build Financial Statement
```python
income = facts.get_income_statement()
balance = facts.get_balance_sheet()
cash = facts.get_cash_flow_statement()
```

### Search for Companies
```python
from edgar.entity import find_company
results = find_company("Tesla")
company = results[0].as_entity()
```

### Handle Different Entity Types
```python
from edgar import get_entity
entity = get_entity('0000320193')  # Apple's CIK

if hasattr(entity, 'get_facts'):
    # It's a company with facts
    facts = entity.get_facts()
else:
    # It's a fund or other entity type
    filings = entity.get_filings()
```

## When Making Changes

1. **Run tests**: `pytest tests/test_entity*.py -xvs`
2. **Check facts alignment**: Compare with SEC website
3. **Update mappings**: If adding new concept support
4. **Document gotchas**: Add to this file
5. **Consider caching**: Facts are expensive to fetch

## Bug Fixing Workflow

When fixing entity/facts issues:

1. **Locate the bug snippet**:
```bash
# Find relevant reproduction
ls -la gists/bugs/ | grep -i "facts\|entity\|income\|balance"
```

2. **Run and understand**:
```python
# Run the bug reproduction
python gists/bugs/408-AppleCashFlow.py

# Add debug output to understand root cause
```

3. **Identify fix location**:
- Period issues → `entity_facts.py`: `_get_statement_data()`
- Concept mapping → `data/learned_mappings.json`
- Statement building → `statement_builder.py`: `build_statement()`

4. **Test fix with snippet**:
```python
# Apply fix and rerun
python gists/bugs/408-AppleCashFlow.py
# Should now show correct values
```

5. **Verify no regressions**:
```bash
# Run all related bug snippets
for file in gists/bugs/*AAPL*.py gists/bugs/*Facts*.py; do
    echo "Testing: $file"
    python "$file" || echo "FAILED: $file"
done
```

6. **Create test case**:
```python
# Add to tests/test_entity_facts.py
def test_annual_period_selection_issue_408():
    """Ensure annual periods return full year, not quarterly data"""
    aapl = Company("AAPL")
    facts = aapl.facts
    income = facts.income_statement(annual=True, periods=1)
    # Revenue should be ~$365B for 2021, not ~$95B (Q4)
    revenue_2021 = income.get_value("Revenue", period="2021")
    assert revenue_2021 > 300_000_000_000  # Should be annual total
```

## Emergency Fixes

### Clear Facts Cache
```bash
rm -rf ~/.edgar/company_facts/
```

### Force Refresh Reference Data
```python
from edgar.reference import update_all_reference_data
update_all_reference_data()
```

### Rebuild Statement Mappings
```python
# Run: python edgar/entity/data/process_mappings.py
```

---

*Remember: The entity package is central to EdgarTools. Changes here affect many downstream components. Always test thoroughly with diverse company types.*