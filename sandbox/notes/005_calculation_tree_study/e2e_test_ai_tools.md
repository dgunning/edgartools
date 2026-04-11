# E2E Test: Concept Mapping Workflow with AI Agent Tools

## Purpose

This test validates the concept mapping workflow and AI agent tools by running a complete end-to-end mapping for MAG7 companies. It tests:

1. **Static workflow** (orchestrator) handles majority of cases
2. **Validation feedback loop** identifies INVALID mappings
3. **AI agent tools** can resolve gaps when invoked

---

## Task for Claude Code Agent

You are testing the concept mapping workflow. Execute the following steps:

### Step 1: Run the Orchestrator

```python
from edgar import set_identity
from edgar.xbrl.standardization.orchestrator import Orchestrator

set_identity("Dev Gunning developer-gunning@gmail.com")

orchestrator = Orchestrator()
results = orchestrator.map_companies(
    tickers=['AAPL', 'GOOG', 'AMZN'],  # Subset for speed
    use_ai=False,  # Skip Layer 2 AI to test tools separately
    validate=True   # Enable validation feedback loop
)
```

**Expected:** Some metrics will have `validation_status="invalid"` or be unmapped.

---

### Step 2: Identify Gaps and Invalid Mappings

```python
# Find all gaps and invalid mappings
issues = {}
for ticker, metrics in results.items():
    for metric, result in metrics.items():
        if not result.is_mapped:
            issues.setdefault(ticker, []).append(f"UNMAPPED: {metric}")
        elif result.validation_status == "invalid":
            issues.setdefault(ticker, []).append(f"INVALID: {metric}")

print("Issues found:")
for ticker, problems in issues.items():
    print(f"\n{ticker}:")
    for p in problems:
        print(f"  - {p}")
```

---

### Step 3: Use AI Tools to Resolve ONE Issue

Pick one issue and use the tools to resolve it:

```python
from edgar.xbrl.standardization.tools import (
    discover_concepts,
    check_fallback_quality,
    verify_mapping
)
from edgar import Company

# Example: Resolve IntangibleAssets for AMZN
ticker = "AMZN"
metric = "IntangibleAssets"

# Step 3a: Discover candidate concepts
company = Company(ticker)
filing = list(company.get_filings(form='10-K'))[0]
xbrl = filing.xbrl()
facts = company.get_facts().to_dataframe()

candidates = discover_concepts(metric, xbrl, facts)
print(f"Top 3 candidates for {metric}:")
for c in candidates[:3]:
    print(f"  {c.concept} (confidence: {c.confidence:.2f})")

# Step 3b: Check fallback quality of best candidate
best = candidates[0]
quality = check_fallback_quality(metric, best.concept)
print(f"\nQuality check: is_valid={quality.is_valid}")
if quality.issues:
    print(f"Issues: {quality.issues}")

# Step 3c: Verify the mapping value
if quality.is_valid:
    verification = verify_mapping(metric, best.concept, xbrl, ticker)
    print(f"\nVerification: {verification.status}")
    if verification.xbrl_value and verification.reference_value:
        print(f"XBRL: {verification.xbrl_value/1e9:.2f}B")
        print(f"Reference: {verification.reference_value/1e9:.2f}B")
```

---

### Step 4: Use learn_mappings for Cross-Company Patterns

```python
from edgar.xbrl.standardization.tools import learn_mappings

# Discover patterns for a metric across companies
result = learn_mappings("IntangibleAssets", ["AAPL", "GOOG", "AMZN", "MSFT"])

print(f"\n{result.summary}")
print(f"\nNew concept variants to add: {result.new_concept_variants}")
```

---

### Step 5: Run Full Resolution Workflow with Coverage Comparison

Use the `resolve_gaps` tool to resolve ALL gaps and compare coverage:

```python
from edgar.xbrl.standardization.tools.resolve_gaps import (
    resolve_all_gaps,
    calculate_coverage,
    generate_report,
    update_config,
    learn_patterns
)

# Calculate BEFORE coverage
before = calculate_coverage(results)
print(f"BEFORE: {before}")

# Resolve all gaps
resolutions, updated_results = resolve_all_gaps(results)

# Calculate AFTER coverage
after = calculate_coverage(updated_results)
print(f"AFTER: {after}")

# Learn patterns from failures
patterns = learn_patterns(resolutions)

# Update config with new concepts
config_changes = update_config(resolutions)

# Generate comprehensive report
report = generate_report(before, after, resolutions, patterns, config_changes)
print(report)
```

**Expected Output:**
```
COVERAGE COMPARISON
  Before: 85.7% (84/98 metrics mapped)
  After:  97.9% (96/98 metrics mapped)
  Improvement: +12.2% (+12 metrics)
```

---

### Quick Version: One-Line Resolution

For convenience, use the `resolve()` function:

```python
from edgar.xbrl.standardization.tools.resolve_gaps import resolve

# Run full workflow with report
report = resolve()  # Uses MAG7 by default

# Or specify tickers:
report = resolve(['AAPL', 'GOOG', 'AMZN'])

# Access results
print(f"Before: {report.before}")
print(f"After: {report.after}")
print(f"Resolved: {sum(1 for r in report.resolutions if r.resolved)}")
print(f"Config changes: {report.config_changes}")
```

---

## Success Criteria

| Test | Pass Condition |
|------|----------------|
| Orchestrator runs | Completes without errors |
| Validation feedback | At least some `validation_status` set to "valid" or "invalid" |
| discover_concepts | Returns at least 1 candidate |
| check_fallback_quality | Correctly rejects parent concepts |
| verify_mapping | Returns variance percentage |
| learn_mappings | Finds at least 1 new variant |
| **resolve_all_gaps** | Resolves at least 1 gap |
| **Coverage improvement** | After coverage > Before coverage |
| **Config auto-update** | At least 1 new concept added to metrics.yaml |

---

## Files Involved

- Orchestrator: `edgar/xbrl/standardization/orchestrator.py`
- Models: `edgar/xbrl/standardization/models.py`
- Validator: `edgar/xbrl/standardization/reference_validator.py`
- Tools: `edgar/xbrl/standardization/tools/`
- **Gap Resolver**: `edgar/xbrl/standardization/tools/resolve_gaps.py`
- **Agent**: `.claude/agents/concept-mapping-resolver.md`
- **Command**: `.claude/commands/resolve-gaps.md`
