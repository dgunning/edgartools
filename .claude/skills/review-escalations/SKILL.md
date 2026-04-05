---
name: review-escalations
description: Interactive human+agent review of escalated gaps. Captures patterns into global config.
---

# /review-escalations — Interactive Review

Review escalated gaps from `/investigate-gaps` with human decision-making.

## Usage

```
/review-escalations cohort-2026-04-05-retail-batch-1
/review-escalations path/to/escalation-report.md
```

## What it does

1. **LOAD** — Read escalation report
2. **PRESENT** — Show one gap at a time with full evidence
3. **DECIDE** — Wait for human decision:
   - `apply` — Apply the recommended fix
   - `exclude` — Exclude the metric for this company
   - `divergence` — Document as known divergence
   - `skip` — Leave for later
   - `pattern` — "This applies to all {industry}" → update industry_metrics.yaml
4. **RECORD** — Mark each gap as reviewed in the escalation report
5. **PROMOTE** — If `pattern` chosen, add to industry_metrics.yaml forbidden_metrics

## Interaction Pattern

For each escalated gap, present:

```
Gap 3/12: D:OperatingIncome (unmapped, confidence: 0.65)

Evidence:
- Calc tree has OperatingExpenses but no OperatingIncome node
- Peer utilities also lack this concept

Recommendation: DOCUMENT_DIVERGENCE
Why escalated: Ambiguous — could be reference_mismatch or needs_composite

Decision? [apply/exclude/divergence/skip/pattern]:
```

## Pattern Capture

When the human says "pattern" or "applies to all utilities":
1. Add metric to the industry's `forbidden_metrics` in `industry_metrics.yaml`
2. Apply the fix to all companies in that industry in the current cohort
3. Log the pattern promotion for audit trail
