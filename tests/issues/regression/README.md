# Regression Tests

This directory contains regression tests for specific GitHub issues to prevent regressions of fixed bugs.

## 🔄 Automatic Test Marking

**Important**: All tests in this directory are automatically marked with `@pytest.mark.regression` by the test system. You **do not need to manually add the marker**.

## 📁 File Naming Convention

Use this naming pattern for regression test files:
```
test_issue_<issue_number>_<short_description>.py
```

Examples:
- `test_issue_429_statement_period_regression.py`
- `test_issue_332_6k_financials_regression.py`

## 🚫 CI Exclusion

Regression tests are **automatically excluded** from the main CI pipeline for faster feedback:

- ✅ **Main CI**: Runs `fast`, `network`, `slow`, `core` test groups (excludes regression)
- 🔍 **Regression CI**: Runs weekly or on-demand for comprehensive regression testing

## ✏️ Writing Regression Tests

### 1. Create the Test File
```python
#!/usr/bin/env python3
"""
Regression test for GitHub issue #XXX: Brief description

This test ensures that [describe what should not regress].

GitHub Issue: https://github.com/dgunning/edgartools/issues/XXX
"""

import pytest
# No need to add @pytest.mark.regression - it's automatic!

class TestIssueXXXRegression:
    def test_specific_issue_scenario(self):
        # Test the specific scenario that was broken
        pass
        
    def test_edge_case_that_caused_issue(self):
        # Test edge cases related to the issue
        pass
```

### 2. Test Structure
- **Focus on the specific issue** that was fixed
- **Include edge cases** that might cause the issue to reoccur
- **Use descriptive test names** that explain what's being tested
- **Add comments explaining why the test exists**

### 3. Test Data
- Use **real-world examples** that triggered the original issue
- Include **company/filing references** from the issue report
- Consider **multiple scenarios** if the issue had various manifestations

## 🧪 Running Regression Tests

```bash
# Run only regression tests
hatch run test-regression

# Run all tests including regression
hatch run test-full

# Check what tests are marked as regression
hatch run pytest --collect-only -m regression
```

## 🤖 For AI Agents

When fixing GitHub issues:

1. **Create regression test** in this directory
2. **Use the naming convention** above
3. **Don't manually add** `@pytest.mark.regression` (it's automatic)
4. **Test the specific bug** that was reported
5. **Include the GitHub issue URL** in docstring

The test system will automatically:
- Mark your test as a regression test
- Exclude it from main CI for faster feedback
- Include it in comprehensive regression testing

## 📊 Current Regression Tests

<!-- Update this list when adding new regression tests -->
- `test_issue_332_regression.py` - 6-K Filings Financials Access
- `test_issue_403_standard_parameter_regression.py` - Standard Parameter Support
- `test_issue_416_segment_member_values.py` - Product/Service Values Display  
- `test_issue_420_multi_year_income_statements.py` - Multi-Year Statement Retrieval
- `test_issue_427_xbrl_data_cap.py` - XBRL Data Capping at 2018
- `test_issue_429_statement_period_regression.py` - Statement Period Selection

---
*This directory ensures that once we fix a bug, it stays fixed.*