# EdgarTools API Analysis

## Overview

EdgarTools is a Python library designed to facilitate interactions with the SEC EDGAR database. It provides a comprehensive API for retrieving, filtering, and analyzing SEC filings and related data. This document examines the API design, identifies inconsistencies, and offers recommendations for improvement.

## Core API Structure

The API is organized around several key concepts:

1. **Filings & Filing** - Collections of SEC filings and individual filing objects
2. **Entity & Company** - Representations of entities that file with the SEC
3. **XBRL** - Tools for working with structured financial data
4. **Attachments** - Handling of documents attached to filings

## Key Entry Points

### Main Entry Points

```python
# Get filings for a specific year/quarter/date range
filings = get_filings(year=2023, quarter=1)

# Search for a company by name or ticker
company = find_company("Apple")

# Get a specific filing by accession number
filing = get_by_accession_number("0000320193-23-000077")

# Get the latest filings
latest = get_current_filings()

# All-purpose search function
result = find("AAPL")  # Can take accession number, CIK, ticker, etc.
```

## Strengths

1. **Comprehensive coverage** - Supports a wide range of SEC filing types and queries
2. **PyArrow integration** - Efficient data handling using PyArrow tables
3. **Rich display capabilities** - Well-designed terminal visualization
4. **Flexible filtering** - Multiple ways to filter and navigate filings
5. **Caching mechanisms** - Appropriate use of caching for performance

## Consistency Issues

### 1. Method Naming Inconsistencies

| Area | Inconsistency |
|------|--------------|
| Navigation | Both `prev()` and `previous()` exist as methods |
| Data access | Mix of property access and method calls (e.g., `filing.html()` vs `filing.document`) |
| Object retrieval | Inconsistent between `get(index_or_accession_number)` and bracket access `[index]` |

### 2. Parameter Naming Inconsistencies

| Area | Inconsistency |
|------|--------------|
| Filings retrieval | `filing_date` and `date` are equivalent aliases |
| Accession numbers | Both `accession_no` and `accession_number` used in different contexts |
| CIK parameters | Inconsistent handling of CIK as string vs integer across APIs |

### 3. Return Type Inconsistencies

| Method | Inconsistency |
|--------|--------------|
| `filings.latest(n)` | Returns a Filing if n=1, Filings otherwise |
| `filings.filter()` | Returns None on invalid date instead of empty Filings |
| `find()` | Returns different types (Filing, Entity, CompanySearchResults) |

### 4. Object Relationship Confusion

The relationship between these classes is not always clear:
- `Filing` vs `CompanyFiling`
- `Company` vs `Entity` vs `CompanyData`
- `CurrentFilings` vs regular `Filings`

## Redundant Parts

1. **Multiple download methods**:
   - `download_edgar_data()`
   - `download_filings()`
   - `download_facts()`
   - `download_submissions()`
   - `Filings.download()`
   
2. **Multiple filing search methods**:
   - `get_filings()`
   - `get_current_filings()`
   - `get_latest_filings()`
   - `latest_filings()`
   - `current_filings()`

3. **Cache usage is inconsistent**:
   - Some methods use `@lru_cache` while others use `@cached_property`
   - Cached and non-cached versions of functions exist

4. **Paging APIs**:
   - `Filings` has paging methods that are reimplemented in `CurrentFilings`

## Confusing Parts

1. **Type hinting issues**:
   - Inconsistent use of TypeVar and Generics
   - Mixed use of Union type vs Optional where appropriate
   - `IntString` used in some places, explicit `Union[str, int]` in others

2. **Aliases without clear purpose**:
   - `filing.homepage` and `filing.home` do the same thing
   - `filing.accession_number` and `filing.accession_no`

3. **Error handling**:
   - Some functions return None on error, others raise exceptions
   - Unclear when a method will log a warning vs. raising an exception

4. **Method overloading**:
   - The `get()` method behaves differently based on parameter type
   - The `filter()` method has many optional parameters with complex interactions

5. **Inheritance with behavior changes**:
   - `CurrentFilings` inherits from `Filings` but overrides key methods with different behavior

## Recommendations

1. **Standardize method naming conventions**:
   - Choose either `prev()` or `previous()`, not both
   - Be consistent with property vs. method access patterns

2. **Harmonize parameter names**:
   - Use consistent parameter names across similar functions
   - Standardize on either `accession_number` or `accession_no`

3. **Consistent return types**:
   - Methods like `filter()` should return empty results, not None
   - Clearly document when methods return different types

4. **Simplify the class hierarchy**:
   - Clarify relationships between similar classes
   - Consider using composition over inheritance for specialized behavior

5. **Consolidate redundant functionality**:
   - Merge similar download methods with appropriate parameters
   - Use aliasing for backward compatibility but consolidate core implementations

6. **Improve API documentation**:
   - Add clear type hints to all public methods
   - Document expected return types and error handling behavior
   - Clarify the purpose and relationships between similar classes

7. **Standardize error handling**:
   - Define a clear strategy for when to return None vs. raise exceptions
   - Use custom exceptions that provide helpful error messages

8. **Add fluent API patterns**:
   - Methods like `filter()` should return self to allow chaining
   - Standardize method chaining patterns across the API

## Specific Simplification Opportunities

1. Consolidate the download methods into a single, flexible function
2. Standardize on either `accession_number` or `accession_no` across all classes
3. Refactor `CurrentFilings` to use composition instead of inheritance
4. Create clearer distinctions between `Company`, `Entity`, and related classes
5. Standardize navigation patterns between `Filings` objects
6. Simplify the configuration of local vs. remote data storage

By addressing these issues, the EdgarTools API could become more intuitive, consistent, and easier to use for both new and experienced users.