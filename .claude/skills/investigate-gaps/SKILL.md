---
name: investigate-gaps
description: Investigate unresolved gaps from cohort report, auto-apply confident fixes, escalate ambiguous cases (outer loop).
---

# /investigate-gaps — Outer Loop

Investigate unresolved gaps, apply confident fixes automatically, escalate the rest.

## Usage

```
/investigate-gaps cohort-2026-04-05-retail-batch-1
/investigate-gaps path/to/cohort-report.md
```

## What it does

1. **PARSE** — Read cohort report from `/expand-cohort` output
2. **PRIORITIZE** — Group gaps by (metric, industry), rank by total CQS impact
3. **INVESTIGATE** — Per gap group: discover concepts, verify mappings, classify root cause
4. **SCORE** — Confidence scorer gates auto-apply: concept_absent >= 0.85, sign_error >= 0.95, wrong_concept >= 0.90
5. **APPLY** — Auto-apply confident fixes via `config_applier`; revert on regression
6. **DETECT** — Flag patterns: same fix applied to 3+ companies in same industry
7. **ESCALATE** — Generate escalation report for ambiguous gaps

## Entry Point

```python
from edgar.xbrl.standardization.tools.investigate_gaps import run_investigation

escalation_path = run_investigation(
    cohort_report_path=Path("cohort-reports/cohort-2026-04-05-retail-batch-1.md"),
)
```

## Output

Escalation report at `escalation-reports/escalation-{cohort-name}.md` with:
- Auto-fixes applied (with confidence scores)
- Escalated gaps (with evidence and recommendations)
- Detected patterns for global promotion

## Safety Rules

- Never propose a concept without verifying it exists in the company's XBRL
- Revert any fix that causes CQS regression
- Escalate after 3 failed resolution attempts
- `reference_mismatch` and `reference_disputed` ALWAYS escalate — never auto-apply
