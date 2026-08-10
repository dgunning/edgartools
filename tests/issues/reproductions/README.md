# EdgarTools Issue Reproduction Files

This directory contains reproduction scripts and tests for reported issues in EdgarTools. The files are organized by the type of data source they test.

## Directory Structure

### `/entity-facts/` - Facts API Issues
Files testing issues with the SEC Facts API data source (`edgar.entity` module).

**What goes here:**
- Issues with `Company.income_statement()`, `Company.balance_sheet()`, `Company.cash_flow()` methods
- Facts API data completeness or accuracy problems  
- Period selection issues in Facts API data
- Revenue classification and deduplication issues
- Historical data availability problems

(The #412 and #438 files that used to be listed here were resolved on
2026-08-10 — their coverage now lives in `tests/issues/regression/`.)

### `/xbrl-parsing/` - XBRL Document Issues  
Files testing issues with direct XBRL document parsing (`edgar.xbrl` module).

**What goes here:**
- Issues with `filing.xbrl()` and XBRL statement parsing
- XBRL presentation tree problems
- Dimensional data filtering issues
- XBRL concept mapping problems
- Statement classification issues in XBRL documents

**Examples:**
- Issue #427: XBRL data parsing inconsistencies
- Issue #429: Statement regression in XBRL parsing

### `/data-quality/` - Cross-API Data Quality
Files testing data quality, consistency, and accuracy across both APIs.

**What goes here:**
- Multi-year financial data consistency
- Cross-validation between XBRL and Facts APIs
- Financial metrics accuracy tests
- Data standardization issues

### `/performance/` - Performance Issues
Files testing performance bottlenecks and optimization.

### `/filing-access/` - Filing Access Issues  
Files testing filing retrieval, caching, and access problems.

## File Naming Conventions

**Every `.py` file here must be named `test_*.py`.** `conftest.py` enforces this
and fails collection on anything else.

The three conventions this section used to list — `438-nvda-revenue-missing.py`,
`438-concept-mapping-debug.py`, and so on — all named files pytest does not
collect. Following them produced 137 files that yielded 54 tests: 95 with no
test function at all, and 22 whose test functions never ran. One of those 22 had
recorded the Citigroup extraction bug as its expected result and went on saying
so after the bug was fixed. They were removed in one pass; see `conftest.py`
for the detail.

So there is one convention now:

- **Tests**: `test_issue_XXX_short_description.py`, containing assertions.
- **Everything else**: not in this directory. Exploratory scripts, debug
  dumps and investigation notebooks belong outside the repository — a
  file in a test tree that cannot fail reads as coverage and is not.

A reproduction worth keeping is a reproduction worth asserting. If it has a
hand-checked value from a real filing, promote it to
`tests/issues/regression/` where CI will actually run it.

## EdgarTools Data Sources

EdgarTools provides financial data from two distinct sources:

1. **Facts API** (`edgar.entity` module)
   - SEC's structured facts endpoint
   - Accessed via `Company.income_statement()`, `Company.balance_sheet()`, etc.
   - Pre-processed, standardized data
   - Better for multi-year analysis and comparisons

2. **XBRL API** (`edgar.xbrl` module)  
   - Direct XBRL document parsing
   - Accessed via `filing.xbrl()` and statement methods
   - Raw XBRL data with full dimensional information
   - Better for detailed analysis and custom processing

## Important Notes

- **No `@pytest.mark.regression` in this directory.** `conftest.py` fails
  collection on it. See "This is not the regression tree" below.
- **Temporary debug files** should be cleaned up after issue resolution
- **Issue numbers** should be included in file names for traceability
- **API source** should be clear from file location and content

## This is not the regression tree

This line used to read "**Regression tests** must use `@pytest.mark.regression`
decorator", and following it was the whole problem. `-m regression` selects on
the marker, not on the path, so a marked test here ran in the regression lane
while sitting outside every gate that applies to
`tests/issues/regression/`:

| gate | what it enforces |
|---|---|
| `scripts/check_regression_provenance.py` | the module docstring names the issue, PR or bead |
| `scripts/check_regression_skips.py` | no runtime `pytest.skip()` — a regression test runs or fails |
| `tests/conftest.py` | fast/network classification, so the offline half gates pull requests |

32 tests across 6 files were in that state on 2026-08-10 (bead
`edgartools-07lk.24`, Tier 2). Two of them carried exactly the defects those
gates exist to catch — a `pytest.skip()` on missing data, and assertions wrapped
in an `if` whose false branch was the bug being tested.

**Where a test belongs:** if it should keep running forever, it goes in
`tests/issues/regression/`, with a provenance line in its module docstring. If
it is a scratch record of a bug as reported, it stays here, unmarked, and
`-m reproduction` runs it.