# XBRL2 Test Plan

## Overview

This document outlines the test strategy for the XBRL2 implementation in edgartools 4.0. It focuses on:

1. Creating a robust set of test fixtures using real EDGAR data
2. Ensuring comprehensive testing across a diverse set of companies
3. Testing across different time periods and statement types
4. Optimizing test performance through efficient fixture design

## Test Data Strategy

### Company Selection Criteria

Select companies from `edgar/reference/data/popular_us_stocks.csv` with the following characteristics:

1. **Industry Diversity**:
   - Technology (AAPL, MSFT, NVDA)
   - Financial Services (JPM, GS, V)
   - Healthcare (JNJ, PFE, UNH)
   - Consumer Products (PG, KO, WMT)
   - Industrial (BA, GD)
   - Energy (XOM, CVX)

2. **Size Diversity**:
   - Large cap (AAPL, MSFT, JPM)
   - Mid cap (NOW, HUBS, AYX)
   - Small cap (NEWR, SMAR)

3. **Statement Complexity**:
   - Companies with complex segment reporting (MSFT, AMZN)
   - Companies with extensive international operations (AAPL, KO)
   - Companies with frequent acquisitions (MSFT, CRM)

4. **Reporting Format Diversity**:
   - Companies using different XBRL tagging approaches
   - Companies with custom taxonomy extensions
   - Companies with dimensional reporting

### Time Period Coverage

For each selected company, include filings from multiple time periods:

1. **Recent Data** (2023-2025):
   - Latest 10-K and 10-Q filings to test with current XBRL taxonomy

2. **Historical Data** (2010-2015):
   - Older filings to test backward compatibility
   - At least one filing from 2010-2012 era (early XBRL adoption)
   - At least one filing from 2013-2015 era (mid XBRL evolution)

3. **Quarterly Variation**:
   - Include Q1, Q2, Q3 and Q4 reports to test quarterly variations

## Fixture Design

### 1. Core Test Fixtures

Create dedicated fixtures in `tests/xbrl2_fixtures.py` organized by:

```python
# Company-specific fixtures
@pytest.fixture(scope="session")
def aapl_10k_2023():
    """Latest annual report for Apple"""
    return XBRL.parse_directory(Path("tests/fixtures/xbrl2/aapl/2023"))

@pytest.fixture(scope="session")
def msft_10q_2024():
    """Latest quarterly report for Microsoft"""
    return XBRL.parse_directory(Path("tests/fixtures/xbrl2/msft/10q_2024"))

@pytest.fixture(scope="session")
def nflx_10k_2010():
    """Historical Netflix filing from 2010"""
    return XBRL.parse_directory(Path("tests/fixtures/xbrl2/nflx/2010"))

# Statement-specific fixtures
@pytest.fixture(scope="session")
def complex_segment_statement():
    """Company with complex segment reporting"""
    return XBRL.parse_directory(Path("tests/fixtures/xbrl2/amzn/segments"))

@pytest.fixture(scope="session")
def dimensional_statement():
    """Company with dimensional reporting"""
    return XBRL.parse_directory(Path("tests/fixtures/xbrl2/ko/dimensional"))

# Special case fixtures
@pytest.fixture(scope="session")
def custom_taxonomy_example():
    """Company using extensive custom taxonomy"""
    return XBRL.parse_directory(Path("tests/fixtures/xbrl2/custom_taxonomy"))
```

### 2. Fixture File Organization

Store all test fixtures in a dedicated directory structure:

```
/tests/fixtures/xbrl2/
├── aapl/
│   ├── 10k_2023/
│   │   ├── aapl-20230930.xsd
│   │   ├── aapl-20230930_cal.xml
│   │   ├── aapl-20230930_def.xml
│   │   ├── aapl-20230930_htm.xml
│   │   ├── aapl-20230930_lab.xml
│   │   └── aapl-20230930_pre.xml
│   └── 10q_2024/
│       └── ...
├── msft/
│   ├── 10k_2024/
│   └── 10q_2024/
├── nflx/
│   ├── 2010/
│   └── 2024/
├── special_cases/
│   ├── custom_taxonomy/
│   ├── dimensional/
│   └── segments/
└── ... (other companies)
```

### 3. Fixture Creation Script

Create a script to automate fixture download and preparation:

```python
# tests/fixtures/generate_xbrl2_fixtures.py
"""
Script to download and prepare XBRL2 test fixtures.
Run this script to update or regenerate the test fixtures.
"""

import os
from pathlib import Path
from edgar import Company, Filing, XBRL

FIXTURE_DIR = Path("tests/fixtures/xbrl2")

# Companies to include
COMPANIES = [
    # (Ticker, CIK, Form types, Years)
    ("AAPL", "320193", ["10-K", "10-Q"], [2023, 2015, 2010]),
    ("MSFT", "789019", ["10-K", "10-Q"], [2024, 2015]),
    ("JPM", "19617", ["10-K"], [2024, 2013]),
    # ... additional companies
]

def download_filing_xbrl(ticker, cik, form, year):
    """Download a specific filing's XBRL data."""
    company = Company(ticker, cik)
    filings = company.get_filings(form_type=form, year=year)
    if not filings:
        print(f"No {form} filings found for {ticker} in {year}")
        return None
    
    filing = filings[0]  # Get the most recent filing for that year
    xbrl = XBRL.from_filing(filing)
    
    # Create target directory
    target_dir = FIXTURE_DIR / ticker.lower() / f"{form.lower()}_{year}"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Save XBRL files to the target directory
    # (Implementation details for saving XBRL files)
    
    return target_dir

def main():
    """Download all test fixtures."""
    for ticker, cik, forms, years in COMPANIES:
        for form in forms:
            for year in years:
                print(f"Downloading {ticker} {form} {year}...")
                download_filing_xbrl(ticker, cik, form, year)

if __name__ == "__main__":
    main()
```

## Specific Test Areas

### 1. Basic Statement Testing

Test the core financial statements for all companies:

- Balance Sheet
- Income Statement
- Cash Flow Statement
- Statement of Stockholders' Equity

Test both standard and parenthetical versions where available.

### 2. Non-Financial XBRL Testing

Test non-financial XBRL data including:

- Segment reporting
- Geographic data
- Revenue breakdowns
- Property and equipment details
- Risk factors
- Management discussion

### 3. Period Handling

Test different period scenarios:

- Annual periods (full year)
- Quarterly periods
- Year-to-date periods
- Comparative periods

### 4. Calculation Testing

Test calculation relationships:

- Verify totals match the sum of components
- Test calculation accuracy for key financial ratios
- Test handling of calculation inconsistencies

### 5. Dimensional Data

Test handling of dimensional data:

- Tables with multiple dimensions
- Member-axis combinations
- Default member handling
- Domain aggregations

### 6. Historical Taxonomy Support

Test with historical taxonomies:

- US GAAP taxonomies from 2010-present
- Test backward compatibility with older filing formats

## Performance Optimization

### 1. Test Fixture Caching

Use session-scoped fixtures to maximize cache reuse:

```python
@pytest.fixture(scope="session")
def cached_companies():
    """Cache for all company fixtures to avoid reloading."""
    return {
        "aapl": XBRL.parse_directory(Path("tests/fixtures/xbrl2/aapl/10k_2023")),
        "msft": XBRL.parse_directory(Path("tests/fixtures/xbrl2/msft/10k_2024")),
        # ... additional companies
    }

@pytest.fixture
def aapl_xbrl(cached_companies):
    """Get the cached Apple XBRL instance."""
    return cached_companies["aapl"]
```

### 2. Targeted Testing Strategy

Divide tests into categories:

1. **Fast tests**: Use smaller fixtures, test specific functions
2. **Medium tests**: Test integration between components
3. **Slow tests**: Full end-to-end tests, comprehensive checks

Use pytest markers to organize tests:

```python
@pytest.mark.fast
def test_balance_sheet_layout(aapl_xbrl):
    """Test basic balance sheet structure."""
    # ...

@pytest.mark.slow
def test_comprehensive_statements(cached_companies):
    """Test all statements for all companies."""
    # ...
```

### 3. Parallel Testing

Configure pytest-xdist for parallel execution:

```
# Run tests in parallel
pytest -xvs tests/test_xbrl2*.py -n auto
```

Add support in conftest.py:

```python
def pytest_configure(config):
    """Configure pytest for parallel execution."""
    config.addinivalue_line("markers", "fast: mark a test as a fast test")
    config.addinivalue_line("markers", "slow: mark a test as a slow test")
```

## Specific Test Cases

### 1. Statement Resolution

```python
def test_statement_resolution():
    """Test that statements are correctly identified."""
    for company, xbrl_obj in cached_companies.items():
        # Verify balance sheet is found
        balance_sheet = xbrl_obj.statements.balance_sheet()
        assert balance_sheet, f"Balance sheet not found for {company}"
        
        # Verify income statement is found
        income_stmt = xbrl_obj.statements.income_statement()
        assert income_stmt, f"Income statement not found for {company}"
```

### 2. Data Accuracy

```python
def test_data_accuracy():
    """Test that parsed data matches expected values."""
    # Test specific known values from filings
    xbrl = cached_companies["aapl"]
    income_stmt = xbrl.statements.income_statement()
    df = income_stmt.to_dataframe()
    
    # Verify revenue values match expected amounts
    revenue_row = df[df["concept"] == "us-gaap_Revenues"]
    assert not revenue_row.empty, "Revenue concept not found"
    assert revenue_row["2023-09-30"].iloc[0] == 394328000000  # Expected value in USD
```

### 3. Fact Queries

```python
def test_fact_queries():
    """Test the fact query API."""
    xbrl = cached_companies["msft"]
    
    # Test querying by concept
    results = xbrl.query("Assets").period("2024-06-30").to_list()
    assert results, "No assets found"
    
    # Test more complex queries
    segment_results = xbrl.query("Revenues").dimension("Segment", "Cloud").to_list()
    assert segment_results, "No cloud segment revenues found"
```

## Implementation Plan

1. **Phase 1: Fixture Setup** (1-2 weeks)
   - Create fixture directory structure
   - Implement fixture download script
   - Setup initial test fixtures for 3-5 key companies

2. **Phase 2: Core Tests** (2-3 weeks)
   - Implement statement resolution tests
   - Implement data accuracy tests
   - Implement calculation verification tests

3. **Phase 3: Extended Tests** (2-3 weeks)
   - Implement dimensional data tests
   - Implement historical taxonomy tests
   - Implement edge case tests

4. **Phase 4: Performance Optimization** (1-2 weeks)
   - Implement caching strategies
   - Set up parallel testing
   - Optimize slow tests

## Conclusion

This test plan provides a comprehensive approach for validating the XBRL2 implementation in edgartools 4.0. By using real EDGAR data across diverse companies and time periods, we ensure that the XBRL2 module handles all scenarios correctly while maintaining optimal performance through efficient fixture design and test organization.