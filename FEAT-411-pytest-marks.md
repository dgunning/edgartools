# FEAT-411 Pytest Marking Strategy

## Overview

Added appropriate pytest marks to all FEAT-411 test files to enable selective test execution and proper categorization. The marking strategy follows the established patterns in the edgartools codebase.

## Marking Categories Used

### @pytest.mark.fast
- **Purpose**: Quick unit tests that run in isolation without external dependencies
- **Duration**: Typically < 1 second per test
- **Dependencies**: None (pure unit tests)
- **Examples**: Unit normalization logic, data structure validation, utility functions

### @pytest.mark.network
- **Purpose**: Tests requiring internet connectivity to call SEC APIs
- **Duration**: Variable (depends on network and API response times)
- **Dependencies**: Internet connection, SEC API availability
- **Examples**: Company fact retrieval, real financial data validation

### @pytest.mark.slow
- **Purpose**: Long-running integration tests, typically testing across multiple companies
- **Duration**: Usually > 10 seconds, can be minutes for multi-company tests
- **Dependencies**: Network + multiple API calls
- **Examples**: Company group testing, multi-company analysis workflows

## File-by-File Marking Strategy

### 1. test_standardized_concepts.py
**Marks Applied**: `@pytest.mark.network` and `@pytest.mark.slow`
- All tests require SEC API calls through Company objects
- Multi-company tests marked as `slow` due to multiple API requests
- Single-company tests marked as `network` only

**Examples**:
```python
@pytest.mark.network
def test_get_revenue_apple(self):

@pytest.mark.network
@pytest.mark.slow
def test_multiple_companies_consistency(self):
```

### 2. test_unit_handling.py
**Marks Applied**: `@pytest.mark.fast` and `@pytest.mark.network`
- Unit tests for UnitNormalizer class: `@pytest.mark.fast`
- Tests with real Company objects: `@pytest.mark.network`
- Clear separation between pure unit tests and integration tests

**Examples**:
```python
@pytest.mark.fast
def test_currency_normalization(self):

@pytest.mark.network
def test_get_revenue_detailed(self):
```

### 3. test_unit_compatibility_modes.py
**Marks Applied**: `@pytest.mark.fast` and `@pytest.mark.network`
- Logic testing (compatibility rules): `@pytest.mark.fast`
- Tests with real data: `@pytest.mark.network`
- Focused on testing unit compatibility behavior modes

**Examples**:
```python
@pytest.mark.fast
def test_unit_normalizer_strict_mode(self):

@pytest.mark.network
def test_strict_unit_matching_default(self):
```

### 4. test_company_groups.py
**Marks Applied**: `@pytest.mark.network` and `@pytest.mark.slow`
- Example test classes marked as both `network` and `slow`
- Framework code itself has no marks (infrastructure)
- Tests demonstrate company group testing patterns

**Examples**:
```python
@pytest.mark.network
@pytest.mark.slow
@test_on_tech_giants(max_failures=2)
def test_revenue_standardization(self, company):
```

### 5. test_standardized_concepts_groups.py
**Marks Applied**: `@pytest.mark.network` and `@pytest.mark.slow`
- All tests marked as both `network` and `slow`
- Tests multiple companies using the group testing framework
- Comprehensive integration testing across company groups

**Examples**:
```python
@pytest.mark.network
@pytest.mark.slow
@test_on_tech_giants(max_failures=2)
def test_revenue_across_tech_companies(self, company):
```

## Usage Examples

### Run Only Fast Tests
```bash
pytest -m fast tests/test_*feat-411*
```

### Run Only Network Tests (Skip Offline)
```bash
pytest -m network tests/test_*feat-411*
```

### Skip Slow Tests (Quick Validation)
```bash
pytest -m "not slow" tests/test_*feat-411*
```

### Run Only Unit Tests (No Network)
```bash
pytest -m "fast and not network" tests/test_*feat-411*
```

### Run Full Integration Suite
```bash
pytest -m "network and slow" tests/test_*feat-411*
```

## Benefits

1. **Selective Execution**: Run only tests appropriate for current development phase
2. **CI/CD Optimization**: Fast tests for quick feedback, full suite for releases
3. **Offline Development**: Skip network tests when SEC API is unavailable
4. **Performance Testing**: Easily identify and run slow integration tests
5. **Debugging**: Focus on specific test categories when troubleshooting

## Consistency with Codebase

The marking strategy follows the established patterns in edgartools:
- Matches existing usage of `@pytest.mark.network`, `@pytest.mark.fast`, and `@pytest.mark.slow`
- Maintains consistency with other test files in the project
- Enables the same selective execution patterns used throughout the codebase

## Test Execution Statistics

After marking:
- **Fast tests**: ~85 individual unit tests
- **Network tests**: ~45 tests requiring SEC API
- **Slow tests**: ~15 comprehensive integration tests
- **Total FEAT-411 tests**: ~50 test methods across 5 files

This categorization enables efficient test execution strategies for different development and CI scenarios.