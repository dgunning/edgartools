---
name: write-evolution-report
description: Generates the 'Extraction Evolution Report' for Banking XBRL. Use this after an E2E test run to document domain knowledge and architectural shifts.
context: fork
agent: general-purpose
allowed-tools: Read, Write, Bash(ls:*), Bash(git log:*), Bash(git diff:*), Glob, Grep
---

## Pre-computed Context

**Timestamp:** !`date +%Y-%m-%d-%H-%M`
**Project Root:** !`pwd`
**Recent Test Reports:**
!`ls -t sandbox/notes/008_bank_sector_expansion/reports/e2e_*.json 2>/dev/null | head -3`
**Recent Git Changes:**
!`git log --oneline -3 -- edgar/xbrl/standardization/`

---

## Usage

Invoke with the path to a test report JSON file:
```
/write-evolution-report sandbox/notes/008_bank_sector_expansion/reports/e2e_banks_2026-01-24_1145.json
```

If no argument provided, the skill will use the most recent test report from the list above.

---

# Role: Financial Systems Architect
Your goal is to generate the **Extraction Evolution Report** based on the test run provided in $ARGUMENTS.

## 1. The Core Philosophy
We are not just fixing bugs; we are reverse-engineering the accounting logic of Global Systemically Important Banks (GSIBs).
**The Golden Rule:** "If you fix a variance, you must document the accounting reality that caused it, not just the code change."

## 2. Input Analysis

### 2.1 Parse Test JSON Structure (REQUIRED)

The test JSON contains structured data - extract it directly, do NOT infer results:

```python
import json

# Load test report
with open('test_report.json') as f:
    results = json.load(f)

# Extract structured data
for result in results.get('results', []):
    ticker = result['ticker']
    form_type = result['form_type']
    period = result['period']
    extracted = result['edgartools_value']      # Actual extracted value
    reference = result['reference_value']        # yfinance reference
    variance_pct = result['variance_pct']        # Calculated variance
    is_valid = result['is_valid']                # Pass/fail status
    run_id = result.get('run_id')                # Unique run identifier
    strategy_fp = result.get('strategy_fingerprint')  # Strategy hash
    components = result.get('components', {})    # Breakdown detail
```

**Critical:** Use parsed values for all report sections. Never write "inferred from" when data exists in the JSON.

### 2.2 Analyze the Run
1.  **Analyze the Run:** Locate the latest test logs (json and markdown files) and the previous extraction_evolution_report in $ARGUMENTS, based on the file name.
2.  **Analyze the Diff:** Review recent code changes in `edgar/xbrl/standardization/` to understand *how* the logic changed.
3.  **Consult the Graveyard:** Check previous extraction_evolution_report to ensure we aren't resurrecting failed hypotheses.

## 3. ENE Ledger Queries

Query the Evolutionary Normalization Engine (ENE) for historical context and strategy performance.

### 3.1 Setup
```python
from edgar.xbrl.standardization.ledger import ExperimentLedger
from edgar.xbrl.standardization.reactor import CohortReactor
from edgar.xbrl.standardization.strategies import list_strategies

ledger = ExperimentLedger()
reactor = CohortReactor()
```

### 3.2 Key Queries

**Runs by Ticker (for historical context):**
```python
runs = ledger.get_runs_for_ticker('JPM', metric='ShortTermDebt', limit=10)
for run in runs:
    print(f"{run.fiscal_period}: {run.variance_pct:.1f}% ({run.strategy_fingerprint})")
```

**Strategy Performance:**
```python
perf = ledger.get_strategy_performance('hybrid_debt')
# Returns: total_runs, valid_runs, success_rate, avg_variance_pct, unique_tickers
```

**Golden Masters (verified stable configs):**
```python
golden_masters = ledger.get_all_golden_masters()
for gm in golden_masters:
    print(f"{gm.ticker}/{gm.metric}: {gm.validation_count} periods, avg {gm.avg_variance_pct:.1f}%")
```

**Cohort Test Results:**
```python
tests = ledger.get_cohort_tests('GSIB_Banks', limit=5)
for test in tests:
    print(f"{test.strategy_fingerprint}: +{test.improved_count}/-{test.regressed_count}")
```

### 3.3 Cohort Definitions

| Cohort | Members | Sub-archetype |
|--------|---------|---------------|
| GSIB_Banks | JPM, BAC, C, WFC, GS, MS, BK, STT | all |
| Hybrid_Banks | JPM, BAC, C | hybrid |
| Commercial_Banks | WFC, USB, PNC | commercial |
| Dealer_Banks | GS, MS | dealer |
| Custodial_Banks | BK, STT | custodial |

### 3.4 Required Queries for Report (MANDATORY)

Execute these queries and include actual results in the appropriate report sections:

**For Golden Masters Section (Section 2.1):**
```python
golden_masters = ledger.get_all_golden_masters()
# Use this data directly - do NOT manually list golden masters
for gm in golden_masters:
    print(f"{gm.ticker}/{gm.metric}: {gm.strategy_name}:{gm.strategy_fingerprint}")
    print(f"  Validated: {gm.validation_count} periods, avg {gm.avg_variance_pct:.1f}%")
```

**For Strategy Performance Section (Section 4.D):**
```python
strategy_names = ['hybrid_debt', 'dealer_debt', 'commercial_debt', 'custodial_debt', 'standard_debt']
for strategy_name in strategy_names:
    perf = ledger.get_strategy_performance(strategy_name)
    print(f"{strategy_name}: {perf['valid_runs']}/{perf['total_runs']} ({perf['success_rate']*100:.1f}%)")
    print(f"  Avg variance: {perf['avg_variance_pct']:.1f}%")
    print(f"  Tickers: {', '.join(perf['unique_tickers'])}")
```

**For Historical Context in Failure Analysis (Section 4.F):**
```python
# For each failing ticker/metric combination
runs = ledger.get_runs_for_ticker(ticker, metric='ShortTermDebt', limit=10)
for run in runs:
    status = "PASS" if run.is_valid else "FAIL"
    print(f"{run.fiscal_period}: {run.variance_pct:.1f}% [{status}]")
    print(f"  Run ID: {run.run_id}")
    print(f"  Strategy: {run.strategy_name}:{run.strategy_fingerprint}")
```

**For Cohort Transferability Matrix (Section 4.C):**
```python
cohorts = ['GSIB_Banks', 'Hybrid_Banks', 'Commercial_Banks', 'Dealer_Banks', 'Custodial_Banks']
for cohort_name in cohorts:
    tests = ledger.get_cohort_tests(cohort_name, limit=3)
    for test in tests:
        status = "PASS" if test.is_passing else "BLOCKED"
        print(f"{cohort_name} [{test.strategy_fingerprint[:8]}]: {status}")
        print(f"  +{test.improved_count} / ={test.neutral_count} / -{test.regressed_count}")
```

## 4. Required Output Sections
Draft a markdown report following the exact structure in `examples.md`.

### A. Executive Snapshot
A summary table showing:
- **Pass Rates:** 10-K and 10-Q validation rates with delta from previous run
- **Golden Masters Count:** Number of verified stable configurations
- **Cohort Regressions:** Count of cohorts with regressions this run
- **Strategy Fingerprints Table:** Active strategies with their fingerprints, run counts, and success rates

### B. The Knowledge Increment (CRITICAL)
Isolate domain knowledge from code.

**B.1 Golden Masters** *(NEW)*
- Table of verified stable configurations (3+ consecutive valid periods)
- Columns: Ticker, Metric, Strategy, Fingerprint, Validated Periods, Avg Variance

**B.2 Validated Archetype Behaviors**
- Facts confirmed about bank types (e.g., "Dealers always separate Repos")

**B.3 The Graveyard (Discarded Hypotheses)**
- Explicitly document what we tried that *failed*

**B.4 New XBRL Concept Mappings**
- A dictionary of new namespaces or tags discovered

### C. Cohort Transferability Matrix *(NEW)*
For each bank sub-archetype cohort, show impact of strategy changes across members.

**Structure:**
- Columns: Metric, Change Description, Ticker1, Ticker2, ..., Net Impact
- Status indicators: ++ (improved), = (neutral), -- (regressed)
- Transferability Score: X/N improved or neutral
- Safe to Merge: YES/BLOCKED

Include sections for:
- Hybrid Banks (JPM, BAC, C)
- Commercial Banks (WFC, USB, PNC)
- Dealer Banks (GS, MS)
- Custodial Banks (BK, STT)

### D. Strategy Performance Analytics *(NEW)*
- Table: Strategy Name, Version, Fingerprint, Total Runs, Valid Runs, Avg Variance, Tickers
- Key insights about strategy effectiveness
- Fingerprint Change Log: Track when strategies changed and why

**Strategy Fingerprints (REQUIRED):**

Every strategy mention MUST include the actual fingerprint from execution or ledger query:

| Strategy | Version | Fingerprint | Description |
|----------|---------|-------------|-------------|
| hybrid_debt | v2.1 | `a7c3f2e1` | Fallback cascade enabled, balance guard active |
| dealer_debt | v1.0 | `c9e5f4a3` | No repos subtraction for separated reporting |

**CRITICAL:** Do NOT write "inferred from archetype rules" or "derived from configuration". Query the actual fingerprint from:
1. Test JSON results (`strategy_fingerprint` field)
2. Ledger query (`ledger.get_strategy_performance(name)`)
3. Run records (`run.strategy_fingerprint`)

If fingerprint data is unavailable, explicitly state "FINGERPRINT NOT RECORDED" rather than inferring.

### E. The Truth Alignment
Identify where our "Street View" intentionally diverges from yfinance.
- Document acceptable variance thresholds based on business logic (e.g., Economic Leverage vs. GAAP)

### F. Failure Analysis *(ENHANCED)*
- Do not just list the variance
- Explain the *structural* cause (e.g., "10-Q lacks calculation linkbase")
- **Historical Context (from Ledger):** Show previous runs for failing ticker/metric
- Pattern detection: Identify if this failure has occurred before

**Required Fields for Each Failure Entry:**

| Field | Source | Example |
|-------|--------|---------|
| **Run ID** | `ExtractionRun.run_id` or test JSON | `run_2026-01-24_1145_JPM` |
| **Strategy Fingerprint** | `run.strategy_fingerprint` | `a7c3f2e1` |
| **Components Breakdown** | `StrategyResult.components` | `{stb: $45B, cp: $12B, repos: $0}` |
| **Variance %** | Test JSON | `-45.3%` |
| **Historical Trend** | Ledger query | "3rd consecutive 10-Q failure" |

**Failure Analysis Template:**

```markdown
### 6.X Incident: [TICKER] [FORM_TYPE] [METRIC] Failure

**Run ID:** `run_YYYY-MM-DD_HHMM_TICKER`
**Strategy:** `{strategy_name}:{fingerprint}`

**Symptom:** Extracted $X.XB vs Reference $Y.YB (variance: -Z.Z%)

**Components (from StrategyResult):**
| Component | Value | Notes |
|-----------|-------|-------|
| ShortTermBorrowings | $XXB | Primary |
| CommercialPaper | $XXB | Added |
| ReposSubtracted | -$XXB | Over-subtraction issue |

**Historical Context (from Ledger):**
| Period | FP | Extracted | Reference | Variance | Status |
|--------|-----|-----------|-----------|----------|--------|
| 2024-Q4 | `abc123` | $XXB | $XXB | X.X% | PASS |
| 2025-Q1 | `def456` | $XXB | $XXB | X.X% | FAIL |

**Pattern:** [Describe recurring pattern if detected]
**Root Cause:** [Structural explanation]
**Corrective Action:** [What was/will be done]
```

### G. Architectural Decision Records (ADRs)
- Formalize structural changes to the codebase

## 5. ENE Component Reference

| Component | Location | Purpose |
|-----------|----------|---------|
| ExperimentLedger | `edgar/xbrl/standardization/ledger/` | Tracks all extraction runs |
| CohortReactor | `edgar/xbrl/standardization/reactor/` | Tests strategy transferability |
| Strategies | `edgar/xbrl/standardization/strategies/` | Extraction strategy implementations |
| Archetypes | `edgar/xbrl/standardization/archetypes/` | Company classification system |

## 6. Reference Material
Refer to [examples.md](examples.md) for the tone, strict formatting, and level of detail required.

## 7. Execution

**Input:** $ARGUMENTS (path to test report JSON)

If $ARGUMENTS is empty, analyze the most recent test report listed in the Pre-computed Context section above.

**Output:** Write the report to:
`sandbox/notes/008_bank_sector_expansion/extraction_evolution_report_!`date +%Y-%m-%d-%H-%M``.md`

The filename uses the pre-computed timestamp from the context section - do not generate your own timestamp.

## 8. Report Continuity (REQUIRED)

### 8.1 Link to Previous Reports

Each report MUST reference the previous report and track changes:

```markdown
## Report Lineage

**Previous Report:** `extraction_evolution_report_2026-01-23-14-30.md`
**This Report:** `extraction_evolution_report_2026-01-24-10-45.md`

### Changes Since Previous Report

| Category | Previous | Current | Delta |
|----------|----------|---------|-------|
| Golden Masters | 8 | 12 | +4 new |
| Graveyard Entries | 5 | 7 | +2 new |
| ADRs (Implemented) | 2 | 3 | +1 new |
| 10-K Pass Rate | 81.8% | 90.9% | +9.1% |
| 10-Q Pass Rate | 80.0% | 86.7% | +6.7% |
```

### 8.2 Golden Master Status Tracking

Track which Golden Masters changed status between reports:

| Ticker/Metric | Previous Status | Current Status | Reason |
|---------------|-----------------|----------------|--------|
| GS/ShortTermDebt | Candidate (2 periods) | **Golden Master** | 3rd consecutive valid |
| WFC/ShortTermDebt | Golden Master | **Demoted** | Regression in Q3 2025 |

### 8.3 Graveyard Deduplication

Before adding to the Graveyard, check that the hypothesis is not already documented:

```python
# Pseudo-code for graveyard check
existing_graveyard = parse_previous_report_graveyard()
for new_hypothesis in current_failures:
    if similar_entry_exists(new_hypothesis, existing_graveyard):
        # Reference existing entry instead of duplicating
        print(f"See Graveyard entry from {previous_report}: {entry.hypothesis}")
    else:
        # Add new entry
        add_to_graveyard(new_hypothesis)
```

### 8.4 ADR Lifecycle Tracking

Track ADR status progression across reports:

| ADR | Previous Status | Current Status | Evidence |
|-----|-----------------|----------------|----------|
| ADR-03: Periodicity Split | Proposed | **Implemented** | form_type detection added |
| ADR-04: Cohort Reactor | Implemented | **Validated** | 5 successful cohort tests |
| ADR-05: Fingerprinting | Validated | Validated | Stable, no changes |

### 8.5 Knowledge Base Accumulation

The report is part of an evolving knowledge base. New discoveries must:

1. **Cross-reference Graveyard:** Avoid resurrecting dead hypotheses. If a similar approach failed before, explain why this attempt differs.

2. **Build on Golden Masters:** Don't re-validate stable configurations. Reference existing Golden Masters and focus on new validations.

3. **Track ADR Lifecycle:**
   - `Proposed` → `Implemented` → `Validated` → `Deprecated`
   - Each transition requires evidence from test results

4. **Preserve Historical Context:** When documenting failures, always query the ledger for historical runs to establish patterns.
