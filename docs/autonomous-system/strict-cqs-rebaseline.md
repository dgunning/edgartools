# Strict EF-CQS Rebaseline (Sub-project A)

*Internal operator doc — not customer-facing.*
*Audience: anyone reading the autonomous-system dashboard or roadmap during the
parallel observation window. Once the gate flips, this doc becomes historical.*

---

## What changed

A new field `ef_cqs_strict` is computed alongside the existing lenient `ef_cqs`
on every `compute_cqs()` call. The lenient field remains the decision gate
during a parallel observation window of at least four cohort runs. The strict
field is observed-only.

Both fields are surfaced in the dashboard (`print_cqs_report`) and on every
`CompanyCQS` / `CQSResult` object. Nothing else changed — no decision logic
moved.

The first parallel measurement (Run 025, all 123 onboarded companies, 2026-04-06):

```
EF-CQS (lenient, current gate): 0.8537  [BELOW TARGET — gate unchanged]
EF-CQS (strict, observed):      0.8151  [parallel — Δ=+0.0386 from explained_variance laundering]
```

## Why we added it

The lenient `ef_cqs` field had a quiet laundering loophole in
`_compute_company_cqs`. When a metric was listed in `known_divergences` (a
documented expectation that the company's XBRL report won't match the yfinance
reference), the company-level loop did three things:

1. Counted it toward `explained_variance_count`.
2. Skipped it via `continue` so it never incremented the `ef_pass_count` numerator.
3. Subtracted `explained_variance_count` from `effective_total` —
   so it was also removed from the denominator.

The combined effect: a documented divergence was treated as "not part of the
score at all" — a free pass laundered into the denominator.

Pre-measurement estimate (Sub-project A spec): 78 entries across 54 of 84
companies (64%) with a predicted strict rebaseline of 0.87 – 0.89.

**Measured (Run 025, all 123 companies, 2026-04-06):** 200 explained-variance
entries across 84 of 123 companies (68%). Strict EF-CQS = 0.8151, lenient EF-CQS
= 0.8537, delta = +0.0386. The laundering loophole is **larger** than the
pre-measurement estimate (3.86 pp vs ~5 pp predicted relative to the 0.9302
100-co baseline; absolute strict number is lower than predicted because the
all-123 cohort includes more untuned outliers than the 100-co subset).

Top contributors (per-company delta = lenient - strict, from Run 025):

| Ticker | Delta | Lenient | Strict | EV count |
|---|---|---|---|---|
| DUK | +0.2400 | 0.8400 | 0.6000 | 10 |
| GE | +0.1911 | 0.7857 | 0.5946 | 9 |
| SO | +0.1905 | 0.8571 | 0.6667 | 8 |
| NEE | +0.1862 | 0.8148 | 0.6286 | 8 |
| BRK-B | +0.1754 | 0.8519 | 0.6765 | 7 |
| AMT | +0.1715 | 0.7931 | 0.6216 | 8 |
| CAT | +0.1308 | 0.8065 | 0.6757 | 6 |

Utilities (DUK, SO, NEE, AMT) and conglomerates (GE, BRK-B, CAT) dominate.
39 of 123 companies have zero laundered divergences.

## How to read the numbers

* **`ef_cqs` (lenient)** is unchanged from before this PR. Anything you compare
  against historical baselines (Run 020, 021, 022, etc.) still uses this field.
  This is the gate during the observation window.
* **`ef_cqs_strict`** is computed by adding `explained_variance_count` back to
  the denominator only. The numerator (`ef_pass_count`) is identical to lenient
  because the loop already excluded those metrics from `ef_pass_count` before
  the field existed. Formally:

      ef_cqs_strict = ef_pass_count / (total - disputed_count - unverified_count)
      ef_cqs        = ef_pass_count / (total - disputed_count - unverified_count - explained_variance_count)

  Hence `ef_cqs_strict ≤ ef_cqs` always, with equality iff
  `explained_variance_count == 0`.
* The dashboard prints the delta as `Δ = ef_cqs - ef_cqs_strict`. A positive
  delta is the size of the laundering loophole; "delta is decreasing" is a
  good signal during the observation window because it means we're either
  deleting questionable known_divergences or fixing the underlying mismatches.
* `disputed_count` (notes containing `reference suspect`) and `unverified_count`
  (no reference data of any kind) remain excluded from both denominators —
  these are genuinely-not-applicable, not laundering.

## The cut-over criterion

The gate flips from lenient to strict in a separate PR (likely bundled with
Sub-project B's chokepoint work). Two conditions must both hold before the
cut-over PR is opened:

1. **At least 5 cohort runs** producing parallel `(lenient, strict)` pairs at
   the all-onboarded scope (currently ~123 companies). One pair per run; small
   per-component CI runs do not count toward the 5.
2. **Zero determinism regressions** during the same window. The CI gate at
   `tests/xbrl/standardization/test_determinism.py` must remain green on every
   nightly run during the observation period.

The "4 weeks" framing in the original Sub-project A spec is the upper bound on
calendar time, not the criterion. If both conditions are met after 8 days and
3 cohort runs, we still wait for the 5th run before flipping. If both are met
after 5 weeks, the 4-week framing is informational and we proceed.

The cut-over PR is intentionally separate so it can carry its own consensus
pre-merge review and so the rollback diff (gate ↔ field swap) is minimal.

## How to read trends across the cut

Once the gate flips:

* The `ef_cqs` field will be removed from the headline display (still computed
  for backward compatibility, but the dashboard headline shows `ef_cqs_strict`
  with no lenient comparison).
* All historical runs in the roadmap Run Log keep their original numbers — do
  not retroactively rewrite them. The Run Log entry for the cut-over run will
  call out the field swap explicitly.
* When comparing post-cut numbers to pre-cut numbers, subtract the typical Δ
  (recorded for each parallel run during the observation window) from the
  pre-cut lenient number to get an apples-to-apples comparison. The roadmap
  table for the parallel-window runs records both fields side-by-side
  precisely so this subtraction is mechanical.

## What this is NOT

* It is **not** a fix for the laundering loophole — it is a measurement of
  the loophole's contribution. The loophole stays open during the observation
  window because flipping the gate without observing the actual delta first
  would conflate "we changed the formula" with "the pipeline got worse."
* It is **not** a decision tool for individual `known_divergences`. The
  per-company audit of which divergences are legitimate vs. which should be
  fixed is a separate workstream (escalation review, Sub-project B).
* It is **not** the chokepoint or the regression gate. Those live in
  Sub-project B and consume `get_decision_threshold()` (which is honored by
  the `EDGAR_DETERMINISM_DEGRADED=1` env var).

## Related code

| Item | Location |
|---|---|
| `ef_cqs_strict` field | `CompanyCQS` and `CQSResult` in `edgar/xbrl/standardization/tools/auto_eval.py` |
| Strict computation | `_compute_company_cqs` (`strict_total` branch) |
| Strict aggregation | `_aggregate_cqs` parallel mean |
| Dashboard parallel display | `print_cqs_report` headline + per-company breakdown |
| Determinism CI gate | `tests/xbrl/standardization/test_determinism.py` |
| Rebaseline measurement script | `scripts/run_025_rebaseline.py` |
