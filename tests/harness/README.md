# Edgar Test Harness

A comprehensive, persistent test harness system for validating EdgarTools functionality across live SEC filings.

## Overview

The Edgar Test Harness provides a systematic way to test EdgarTools against real SEC filings with:

- **Persistent Storage**: SQLite database tracks sessions, runs, and results
- **Multiple Test Types**: Comparison, validation, performance, and regression testing
- **Flexible Filing Selection**: Date ranges, company lists, random sampling, and more
- **Rich Reporting**: Beautiful CLI output, CSV/JSON exports, markdown reports
- **Historical Analysis**: Trend tracking, regression detection, period comparisons

## Quick Start

### Installation

The test harness requires the optional `test-harness` dependency group:

```bash
pip install edgartools[test-harness]
```

This installs the `edgar-test` CLI command along with the required dependencies.

### Basic Usage

```bash
# Run validation tests on 10 random 10-K filings from 2024
edgar-test run --form 10-K --sample 10 --year 2024

# Show all test sessions
edgar-test show

# Show results from a specific run
edgar-test show --run 1

# Compare two test runs
edgar-test compare --run1 1 --run2 2

# Analyze trends for a test
edgar-test trends --test-name "10-K validation"
```

## CLI Commands

### `edgar-test run`

Run tests on selected SEC filings.

**Options:**
- `--form, -f`: Form type (required: 10-K, 8-K, 10-Q, etc.)
- `--sample, -n`: Number of filings to sample (default: 10)
- `--year, -y`: Year to sample from (default: current year)
- `--date-range`: Date range in YYYY-MM-DD:YYYY-MM-DD format
- `--companies`: Comma-separated list of tickers
- `--test-type, -t`: Type of test (comparison, validation, performance)
- `--session, -s`: Session name (creates new if doesn't exist)
- `--db-path`: Custom database path

**Examples:**

```bash
# Test 20 random 10-K filings from 2024
edgar-test run --form 10-K --sample 20 --year 2024

# Test specific companies
edgar-test run --form 10-Q --companies AAPL,MSFT,GOOGL

# Test filings in a date range
edgar-test run --form 8-K --date-range 2024-01-01:2024-03-31 --sample 50

# Run performance tests
edgar-test run --form 10-K --sample 10 --test-type performance
```

### `edgar-test show`

Display test results, runs, or sessions.

**Options:**
- `--session, -s`: Session ID to show runs for
- `--run, -r`: Run ID to show results for
- `--limit, -l`: Limit number of results (default: 20)
- `--db-path`: Custom database path

**Examples:**

```bash
# Show all sessions
edgar-test show

# Show runs in session 1
edgar-test show --session 1

# Show detailed results for run 5
edgar-test show --run 5 --limit 100
```

### `edgar-test compare`

Compare two test runs side-by-side.

**Options:**
- `--run1, -r1`: First run ID (required)
- `--run2, -r2`: Second run ID (required)
- `--db-path`: Custom database path

**Example:**

```bash
# Compare runs 5 and 6
edgar-test compare --run1 5 --run2 6
```

### `edgar-test trends`

Show historical trends for a specific test.

**Options:**
- `--test-name, -t`: Test name to analyze (required)
- `--limit, -l`: Number of runs to analyze (default: 20)
- `--db-path`: Custom database path

**Example:**

```bash
# Analyze trends for 10-K validation tests
edgar-test trends --test-name "10-K validation" --limit 30
```

## Programmatic Usage

### Basic Example

```python
from tests.harness import (
    HarnessStorage,
    FilingSelector,
    ValidationTestRunner
)

# Create storage
storage = HarnessStorage()

# Create session
session = storage.create_session("My Test Session")

# Create run
run = storage.create_run(
    session_id=session.id,
    name="10-K Validation",
    test_type="validation",
    config={'form': '10-K', 'sample': 10}
)

# Select filings
filings = FilingSelector.by_random_sample("10-K", 2024, 10)

# Define validators
validators = [
    lambda f: {'passed': f.form == '10-K', 'message': 'Form type check'},
    lambda f: {'passed': len(f.company) > 0, 'message': 'Company name check'}
]

# Run tests
runner = ValidationTestRunner(storage)
results = runner.run(run, filings, validators)

# Update run status
storage.update_run_status(run.id, 'completed')

# Get summary
from tests.harness import ResultReporter
reporter = ResultReporter(storage)
summary = reporter.generate_summary(run.id)
print(f"Success rate: {summary['success_rate']*100:.1f}%")
```

### Advanced Example: Comparison Testing

```python
from tests.harness import ComparisonTestRunner

# Define old and new implementations
def old_parser(filing):
    return filing.obj()  # Old implementation

def new_parser(filing):
    return filing.obj()  # New implementation

# Run comparison
runner = ComparisonTestRunner(storage)
results = runner.run(run, filings, old_parser, new_parser)

# Check for differences
differences = [r for r in results if r.status == 'fail']
print(f"Found {len(differences)} differences")
```

### Export Reports

```python
from tests.harness import ResultReporter
from pathlib import Path

reporter = ResultReporter(storage)

# Export to CSV
reporter.export_csv(run.id, Path("results.csv"))

# Export to JSON
reporter.export_json(run.id, Path("results.json"), include_details=True)

# Generate markdown report
reporter.generate_markdown_report(run.id, Path("report.md"))
```

### Trend Analysis

```python
from tests.harness import TrendAnalyzer

analyzer = TrendAnalyzer(storage)

# Detect regressions
regressions = analyzer.detect_regressions("10-K validation", threshold=0.05)
for regression in regressions:
    print(f"Regression detected in run {regression['run_id']}: "
          f"{regression['drop']*100:.1f}% drop (severity: {regression['severity']})")

# Analyze stability
stability = analyzer.analyze_stability("10-K validation", limit=20)
print(f"Test is {'stable' if stability['stable'] else 'unstable'}")
print(f"Trend: {stability['trend']}")

# Compare periods
comparison = analyzer.compare_periods("10-K validation", period1_runs=10, period2_runs=10)
print(f"Recent avg: {comparison['period1_avg']*100:.1f}%")
print(f"Older avg: {comparison['period2_avg']*100:.1f}%")
print(f"Change: {comparison['change_percent']:.1f}%")
```

## Test Types

### Comparison Tests

Compare output between two implementations to validate refactoring or upgrades.

```python
runner = ComparisonTestRunner(storage)
results = runner.run(
    run,
    filings,
    old_func=lambda f: old_implementation(f),
    new_func=lambda f: new_implementation(f),
    comparator=lambda a, b: a == b  # Optional custom comparator
)
```

### Validation Tests

Run multiple validation checks on each filing.

```python
validators = [
    lambda f: {'passed': f.form in ['10-K', '10-Q'], 'message': 'Valid form'},
    lambda f: {'passed': len(f.company) > 0, 'message': 'Has company name'},
    lambda f: {'passed': f.filing_date is not None, 'message': 'Has filing date'}
]

runner = ValidationTestRunner(storage)
results = runner.run(run, filings, validators)
```

### Performance Tests

Benchmark operations against performance thresholds.

```python
runner = PerformanceTestRunner(storage)
results = runner.run(
    run,
    filings,
    test_func=lambda f: f.xbrl(),  # Function to benchmark
    thresholds={'max_duration_ms': 5000}  # 5 second max
)
```

### Regression Tests

Compare current output against known baseline results.

```python
baseline_results = {
    '0001234567-24-000001': expected_output_1,
    '0001234567-24-000002': expected_output_2,
}

runner = RegressionTestRunner(storage)
results = runner.run(run, filings, test_func, baseline_results)
```

## Filing Selection Methods

### Date Range

```python
filings = FilingSelector.by_date_range(
    form="10-K",
    start_date="2024-01-01",
    end_date="2024-03-31",
    sample=50
)
```

### Company List

```python
filings = FilingSelector.by_company_list(
    companies=["AAPL", "MSFT", "GOOGL"],
    form="10-K",
    latest_n=2  # Last 2 10-Ks from each
)
```

### Random Sample

```python
filings = FilingSelector.by_random_sample(
    form="8-K",
    year=2024,
    sample=100,
    seed=42  # For reproducibility
)
```

### Company Subset

```python
filings = FilingSelector.by_company_subset(
    form="10-Q",
    subset_name="MEGA_CAP",
    sample=10,
    latest_n=1
)
```

### Recent Filings

```python
filings = FilingSelector.by_recent(
    form="8-K",
    days=7,
    sample=20
)
```

### Config-Based

```python
config = {
    'method': 'date_range',
    'params': {
        'form': '10-K',
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'sample': 100
    }
}

filings = FilingSelector.from_config(config)
```

## Database

The test harness uses SQLite for persistent storage with the following schema:

- **sessions**: Logical groupings of test runs
- **test_runs**: Individual test executions
- **test_results**: Results for each tested filing
- **filing_metadata**: Cached filing metadata

Default database location: `~/.edgar_test/harness.db`

Custom database:
```bash
edgar-test run --form 10-K --sample 10 --db-path /path/to/custom.db
```

## Architecture

```
tests/harness/
├── __init__.py         # Package exports
├── models.py           # Data models (Session, TestRun, TestResult)
├── storage.py          # SQLite operations
├── selectors.py        # Filing selection strategies
├── runner.py           # Test execution framework
├── reporters.py        # Reporting and analytics
└── cli.py              # Command-line interface
```

## Contributing

When adding new test types or selection methods:

1. Add the implementation to the appropriate module
2. Update `__init__.py` exports
3. Add comprehensive tests
4. Update this README with examples

## License

MIT License - See LICENSE file for details
