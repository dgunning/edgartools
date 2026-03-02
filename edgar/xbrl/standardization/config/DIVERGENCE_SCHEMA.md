# Known Divergences Schema

## Purpose

This document defines the schema for documenting known divergences between XBRL extraction and yfinance reference data in `companies.yaml`. Proper documentation enables:

1. **Traceability** - Know when and why divergences were added
2. **Review cycles** - Periodically revisit to check if issues are resolved
3. **Remediation tracking** - Track progress toward fixing root causes

---

## Schema Definition

```yaml
known_divergences:
  MetricName:
    # Required fields
    form_types: ["10-K", "10-Q"]        # Which form types are affected
    skip_validation: true               # Whether to skip E2E validation
    reason: >                           # Explanation of the divergence
      Brief description of why this metric diverges.

    # Tracking fields (recommended)
    added_date: "2026-01-26"            # When this divergence was documented
    added_commit: "abc1234"             # Git commit that added this divergence

    # Scope fields (optional)
    fiscal_years: [2023, 2024]          # Specific fiscal years affected (if not all)
    variance_pct: 50.0                  # Expected variance percentage

    # Remediation fields (optional)
    remediation_status: "deferred"      # none | investigating | deferred | wont_fix | resolved
    remediation_notes: >                # Notes on potential fix path
      Description of what would be needed to fix this.
    review_date: "2026-06-01"           # When to revisit this divergence
    github_issue: "#123"                # Link to tracking issue if any
```

---

## Remediation Status Values

| Status | Meaning |
|--------|---------|
| `none` | No remediation attempted or planned |
| `investigating` | Actively investigating root cause |
| `deferred` | Known fix exists but deprioritized |
| `wont_fix` | Structural limitation, no fix planned |
| `resolved` | Issue fixed, divergence can be removed |

---

## Divergence Categories

### 1. Structural Mismatch (wont_fix)

Data is fundamentally different between sources due to methodology differences.

**Examples:**
- Stock splits (XBRL pre-split vs yfinance post-split adjusted)
- Corporate actions (spin-offs, restatements)
- Insurance premiums vs contract revenue

**Schema example:**
```yaml
WeightedAverageSharesDiluted:
  form_types: ["10-K", "10-Q"]
  skip_validation: true
  reason: "10-for-1 stock split. XBRL pre-split, yfinance post-split."
  added_date: "2026-01-26"
  remediation_status: "wont_fix"
  remediation_notes: "Would require split adjustment infrastructure in reference_validator"
```

### 2. Concept Selection Issue (investigating/deferred)

We're extracting the wrong XBRL concept.

**Examples:**
- M&A acquisitions instead of PP&E capex
- Commercial paper only instead of full short-term debt

**Schema example:**
```yaml
Capex:
  form_types: ["10-K"]
  skip_validation: true
  reason: "Extracting PaymentsToAcquireBusinesses instead of PaymentsToAcquirePropertyPlantAndEquipment"
  added_date: "2026-01-26"
  remediation_status: "investigating"
  remediation_notes: "Need to add exclude_patterns to Capex metric or improve tree_hints"
  review_date: "2026-02-01"
```

### 3. Subsidiary/Segment Structure (deferred)

Company has complex structure that complicates extraction.

**Examples:**
- Financial services subsidiaries (CAT Financial, John Deere Financial)
- Segment-level vs consolidated reporting

**Schema example:**
```yaml
ShortTermDebt:
  form_types: ["10-K", "10-Q"]
  skip_validation: true
  reason: "Financial services subsidiary debt not consolidated in standard XBRL concepts"
  added_date: "2026-01-26"
  variance_pct: 65.0
  remediation_status: "deferred"
  remediation_notes: "Would require custom composite extraction for this company"
```

### 4. Industry-Specific Reporting (wont_fix/deferred)

Industry uses non-standard concepts that require specialized extractors.

**Examples:**
- Insurance premiums (UNH)
- Energy sector operating income
- Bank interest income/expense

**Schema example:**
```yaml
Revenue:
  form_types: ["10-K", "10-Q"]
  skip_validation: true
  reason: "Insurance uses PremiumsEarnedNet not RevenueFromContractWithCustomer"
  added_date: "2026-01-26"
  remediation_status: "deferred"
  remediation_notes: "InsuranceExtractor needs extract_revenue method"
  github_issue: "#TBD"
```

---

## Review Process

### Quarterly Review

Every quarter, run the divergence review script:

```bash
python scripts/review_divergences.py
```

This script will:
1. List all divergences by remediation_status
2. Flag divergences past their review_date
3. Suggest removals for `resolved` status items
4. Generate a report for architect review

### After E2E Test Improvements

When significant extraction improvements are made:

1. Run full E2E test suite
2. Check if any skipped divergences now pass
3. Update remediation_status to `resolved` for fixed items
4. Remove divergences that have been resolved for 2+ test runs

---

## Adding New Divergences

When adding a new known_divergence:

1. **Document the root cause** - Don't just skip, understand why
2. **Set added_date** - Use current date
3. **Set remediation_status** - What's the path forward?
4. **Set review_date** - When should we revisit? (default: 3 months)
5. **Add to Evolution Report** - Document in the next test run's report

**Template:**
```yaml
MetricName:
  form_types: ["10-K"]
  skip_validation: true
  reason: >
    [One sentence explaining the divergence]
  added_date: "YYYY-MM-DD"
  variance_pct: XX.X
  remediation_status: "investigating"  # or deferred/wont_fix
  remediation_notes: >
    [What would be needed to fix this]
  review_date: "YYYY-MM-DD"  # 3 months from added_date
```

---

## Existing Divergences Inventory

See `companies.yaml` for the current list. Key divergences as of 2026-01-26:

| Company | Metric | Category | Status |
|---------|--------|----------|--------|
| NVDA | WeightedAverageSharesDiluted | Stock split | wont_fix |
| GE | Revenue, COGS | Spin-off | wont_fix |
| CAT | ShortTermDebt, LongTermDebt, AR | Subsidiary | deferred |
| UNH | Revenue | Industry | deferred |
| Energy sector | OperatingIncome | Industry | deferred |
| DE | OperatingIncome | Subsidiary | deferred |
| PFE | OperatingIncome | COVID charges | deferred |
