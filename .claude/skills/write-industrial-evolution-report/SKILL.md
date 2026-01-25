---
name: write-industrial-evolution-report
description: Generates the 'Extraction Evolution Report' for Standard Industrial XBRL. Use this after an E2E test run to document domain knowledge and sector-specific findings.
context: fork
agent: general-purpose
allowed-tools: Read, Write, Bash(ls:*), Bash(git log:*), Bash(git diff:*), Glob, Grep
---

## Pre-computed Context

**Timestamp:** !`date +%Y-%m-%d-%H-%M`
**Project Root:** !`pwd`
**Recent Test Reports:**
!`ls -t sandbox/notes/010_standard_industrial/reports/e2e_*.json 2>/dev/null | head -3`
**Recent Git Changes:**
!`git log --oneline -3 -- edgar/xbrl/standardization/`

---

## Usage

Invoke with the path to a test report JSON file:
```
/write-industrial-evolution-report sandbox/notes/010_standard_industrial/reports/e2e_industrial_2026-01-25_1430.json
```

If no argument provided, the skill will use the most recent test report from the list above.

---

# Role: Financial Systems Architect
Your goal is to generate the **Extraction Evolution Report** for Standard Industrial companies based on the test run provided in $ARGUMENTS.

## 1. The Core Philosophy
We are testing XBRL concept mapping reliability across diverse industrial sectors.
**The Golden Rule:** "Document sector-specific extraction patterns and track transferability across company types."

## 2. Input Analysis

### 2.1 Parse Test JSON Structure (REQUIRED)

The test JSON contains structured data with sector breakdowns - extract it directly:

```python
import json

# Load test report
with open('test_report.json') as f:
    results = json.load(f)

# Extract structured data
overall_summary = results.get('overall_summary', {})
sector_summary = results.get('sector_summary', {})
failures = results.get('failures', [])

for failure in failures:
    ticker = failure['ticker']
    sector = failure['sector']
    form_type = failure['form']
    metric = failure['metric']
    extracted = failure['xbrl_value']
    reference = failure['ref_value']
    variance_pct = failure['variance_pct']
```

**Critical:** Use parsed values for all report sections. Never write "inferred from" when data exists in the JSON.

### 2.2 Analyze the Run
1. **Analyze the Run:** Locate the latest test logs (json and markdown files) and the previous extraction_evolution_report in $ARGUMENTS, based on the file name.
2. **Analyze the Diff:** Review recent code changes in `edgar/xbrl/standardization/` to understand *how* the logic changed.
3. **Consult the Graveyard:** Check previous extraction_evolution_report to ensure we aren't resurrecting failed hypotheses.

## 3. Sector Cohorts

| Cohort | Members | Notes |
|--------|---------|-------|
| Industrial_30 | All 30 | Overall tracking |
| MAG7_Tech | AAPL, MSFT, GOOG, AMZN, META, NVDA, TSLA | Tech baseline (Archetype C in config) |
| Industrial_Manufacturing | CAT, GE, HON, DE, MMM, EMR, RTX | Pure Archetype A baseline |
| Consumer_Staples | PG, KO, PEP, WMT, COST | Retail/lease patterns |
| Energy_Sector | XOM, CVX, COP, SLB | Capex-heavy patterns |
| Healthcare_Pharma | JNJ, UNH, LLY, PFE | R&D capitalization |
| Transportation_Logistics | UPS, FDX, BA | Asset-heavy operations |

## 4. Required Output Sections
Draft a markdown report following the exact structure in `examples.md`.

### A. Executive Snapshot
A summary table showing:
- **Pass Rates:** 10-K and 10-Q validation rates with delta from previous run
- **Sector Pass Rates:** Breakdown by sector cohort
- **Critical Failures:** Count of failures by sector

### B. The Knowledge Increment (CRITICAL)
Isolate domain knowledge from code.

**B.1 Sector-Specific Patterns**
- Facts confirmed about sector types (e.g., "Energy uses PaymentsToAcquireProductiveAssets for Capex")

**B.2 Validated Extraction Behaviors**
- Concepts that work reliably across sectors
- Concepts that require sector-specific handling

**B.3 The Graveyard (Discarded Hypotheses)**
- Explicitly document what we tried that *failed*

**B.4 New XBRL Concept Mappings**
- A dictionary of new namespaces or tags discovered

### C. Sector Transferability Matrix
For each sector cohort, show impact of extraction strategies across members.

**Structure:**
- Columns: Metric, Ticker1, Ticker2, ..., Net Impact
- Status indicators: ++ (improved), = (neutral), -- (regressed)
- Transferability Score: X/N improved or neutral
- Safe to Merge: YES/BLOCKED

Include sections for:
- MAG7 Tech (known Archetype C, expected variance)
- Industrial Manufacturing (Archetype A baseline)
- Consumer Staples
- Energy Sector
- Healthcare/Pharma
- Transportation/Logistics

### D. Sector-Specific Considerations

| Sector | Key Issues | Extraction Notes |
|--------|------------|------------------|
| MAG7 | Archetype C mismatch | May show higher variance with Archetype A strategies |
| Energy | Capex concept | Uses `PaymentsToAcquireProductiveAssets` |
| Pharma | R&D | May capitalize R&D differently |
| Retail | Leases | Significant lease accounting impacts |
| Industrial | Baseline | Most reliable for standard extraction |

### E. The Truth Alignment
Identify where our extraction intentionally diverges from yfinance.
- Document acceptable variance thresholds based on sector characteristics

### F. Failure Analysis
- Do not just list the variance
- Explain the *structural* cause (e.g., "MAG7 companies use Archetype C patterns")
- Pattern detection: Identify if this failure is sector-specific or systemic

**Failure Analysis Template:**

```markdown
### 6.X Incident: [TICKER] [FORM_TYPE] [METRIC] Failure

**Sector:** [SECTOR]

**Symptom:** Extracted $X.XB vs Reference $Y.YB (variance: -Z.Z%)

**Root Cause:** [Structural explanation]

**Sector Pattern:** [Is this failure specific to this sector or systemic?]

**Corrective Action:** [What was/will be done]
```

### G. Recommendations
- Prioritized list of improvements based on sector analysis
- Which sectors need special handling
- Which sectors can use standard Archetype A strategies

## 5. Reference Material
Refer to [examples.md](examples.md) for the tone, strict formatting, and level of detail required.

## 6. Execution

**Input:** $ARGUMENTS (path to test report JSON)

If $ARGUMENTS is empty, analyze the most recent test report listed in the Pre-computed Context section above.

**Output:** Write the report to:
`sandbox/notes/010_standard_industrial/extraction_evolution_report_!`date +%Y-%m-%d-%H-%M``.md`

The filename uses the pre-computed timestamp from the context section - do not generate your own timestamp.

## 7. Report Continuity (REQUIRED)

### 7.1 Link to Previous Reports

Each report MUST reference the previous report and track changes:

```markdown
## Report Lineage

**Previous Report:** `extraction_evolution_report_2026-01-24-14-30.md`
**This Report:** `extraction_evolution_report_2026-01-25-10-45.md`

### Changes Since Previous Report

| Category | Previous | Current | Delta |
|----------|----------|---------|-------|
| Overall 10-K Pass Rate | 85.0% | 88.0% | +3.0% |
| Overall 10-Q Pass Rate | 82.0% | 85.0% | +3.0% |
| MAG7 Pass Rate | 78.0% | 80.0% | +2.0% |
| Energy Pass Rate | 95.0% | 97.0% | +2.0% |
```

### 7.2 Graveyard Deduplication

Before adding to the Graveyard, check that the hypothesis is not already documented.

### 7.3 Knowledge Base Accumulation

The report is part of an evolving knowledge base. New discoveries must:

1. **Cross-reference Graveyard:** Avoid resurrecting dead hypotheses.
2. **Build on Previous Findings:** Reference existing sector patterns.
3. **Track Sector Coverage:** Which sectors are fully mapped vs. need work.
