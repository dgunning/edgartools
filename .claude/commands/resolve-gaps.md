---
description: "Resolve XBRL concept mapping gaps after running the orchestrator. Uses AI tools to discover, validate, and verify new concepts, then auto-updates metrics.yaml."
allowed_tools: [Read, Write, Edit, Glob, Grep, Bash, Task]
model: "sonnet"
---

# Resolve Concept Mapping Gaps

You are running the concept mapping gap resolution workflow. This workflow:
1. Analyzes orchestrator results to find unmapped/invalid mappings
2. Uses AI tools to discover and verify candidate concepts
3. Updates metrics.yaml with newly discovered concepts
4. Generates a coverage comparison report

## Workflow

### Step 1: Run Orchestrator (if not already done)

```python
from edgar import set_identity
from edgar.xbrl.standardization.orchestrator import Orchestrator

set_identity("Dev Gunning developer-gunning@gmail.com")

orchestrator = Orchestrator()
results = orchestrator.map_companies(
    tickers=['AAPL', 'GOOG', 'AMZN', 'MSFT', 'META', 'NVDA', 'TSLA'],
    use_ai=False,  # Test static layers only
    validate=True   # Enable validation feedback
)
```

### Step 2: Calculate Before Coverage

```python
from edgar.xbrl.standardization.tools.resolve_gaps import calculate_coverage

before = calculate_coverage(results)
print(f"BEFORE: {before}")
```

### Step 3: Resolve All Gaps

```python
from edgar.xbrl.standardization.tools.resolve_gaps import resolve_all_gaps

resolutions, updated_results = resolve_all_gaps(results)
```

### Step 4: Calculate After Coverage

```python
after = calculate_coverage(updated_results)
print(f"AFTER: {after}")
```

### Step 5: Learn Patterns from Failures

```python
from edgar.xbrl.standardization.tools.resolve_gaps import learn_patterns

patterns = learn_patterns(resolutions)
if patterns:
    print(f"Patterns discovered: {patterns}")
```

### Step 6: Update Config

```python
from edgar.xbrl.standardization.tools.resolve_gaps import update_config

changes = update_config(resolutions)
if changes:
    print(f"Config updated with {len(changes)} new concepts")
```

### Step 7: Generate Report

```python
from edgar.xbrl.standardization.tools.resolve_gaps import generate_report

report = generate_report(before, after, resolutions, patterns, changes)
print(report)
```

## Quick Version

For a quick run with all steps combined:

```python
from edgar.xbrl.standardization.tools.resolve_gaps import resolve

report = resolve()  # Uses MAG7 by default
# Or specify tickers:
report = resolve(['AAPL', 'GOOG', 'AMZN'])
```

## Expected Output

```
============================================================
CONCEPT MAPPING RESOLUTION REPORT
============================================================

COVERAGE COMPARISON
  Before: 85.7% (84/98 mapped)
  After:  97.9% (96/98 mapped)
  Improvement: +12.2% (+12 metrics)

RESOLUTION DETAILS

AAPL:
  [OK] IntangibleAssets: Resolved -> us-gaap:IntangibleAssetsNetExcludingGoodwill
      Source: facts, Confidence: 0.95
      Verification: XBRL=4.2B, Ref=4.2B, Variance=0.1%

  [--] Capex: Unable to resolve
      Reason: All 5 candidates failed verification
      Candidates tried: 5

...

CONFIG CHANGES
  Updated: edgar/xbrl/standardization/config/metrics.yaml
    - IntangibleAssets: +IntangibleAssetsNetExcludingGoodwill
    - ShortTermDebt: +ShortTermBorrowings

============================================================
```

## Arguments

If the user provides arguments (e.g., `/resolve-gaps AAPL GOOG`), use those as the ticker list:

```python
tickers = $ARGS.split() if $ARGS else None
report = resolve(tickers)
```
