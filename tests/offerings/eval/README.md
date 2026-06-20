# Offerings Extraction Eval

A systematic evaluate-and-improve loop for the offerings extraction surface
(shelf lifecycle, underwriting, fee-table capacity). It generalizes the manual
"sample real filings → bucket the outputs → trace the biggest bucket to one root
cause → fix → re-measure" process that found edgartools-fu3x / 2w5y / 2h4c / zxnj.

## The loop

```
evaluate   run_eval.py over corpus.json  ->  dashboard + failure catalog
  triage   read the null clusters / failure catalog (ranked by count)
  improve  fix the highest-leverage cluster
re-measure rerun; coverage up, bad_rate stays 0, no anchor regresses
    lock   add a regression test + raise the floor in thresholds.json
```

## Files

| File | Role |
|------|------|
| `corpus.json` | Frozen, stratified list of real filings (anchors + live breadth) |
| `build_corpus.py` | Rebuild/refresh the corpus (`--no-live` for anchors only) |
| `run_eval.py` | Tier A runner: bucket each facet, print dashboard + failure catalog |
| `thresholds.json` | Locked coverage floors / bad_rate ceilings (the ratchet) |
| `test_eval_ratchet.py` | Network-marked guardrail asserting thresholds hold |

## Buckets

`ok` clean usable value · `suspect` a Tier B oracle judged it internally
inconsistent (likely wrong) · `null` no value (see cluster reason) · `deferred`
legitimately indeterminate (pay-as-you-go ASR capacity) · `bad` garbage or
out-of-range — **never ship** · `error` extractor raised.

`coverage = ok / applicable`  ·  `bad_rate = (bad + error + suspect) / applicable`
· `verified = oracle-passed / oracle-judged`

Anchor entries carry an `expected` value; a mismatch is forced to `bad`, so the
harness checks accuracy (not just coverage) on the hand-verified cases.

## Tiers

- **Tier A: coverage & validity.** No labels; runs on the whole corpus.
- **Tier B (started): self-check oracles.** No labels either — exploit the
  filing's internal redundancy. Implemented: `fee_capacity` cross-check —
  `Σ fee_amount / fee_rate` must reconcile with `total_offering_amount` (the
  offering cell validated via the independent fee÷rate path; carry-forward /
  offset filings are skipped). Next: `Σ per-security aggregate ≈ total`,
  `current_effective + 3y == shelf_expires`, every takedown ∈
  `[effective, expires]`. A covered value that fails its oracle is demoted to
  `suspect`, turning coverage into measured *accuracy*.
- **Tier C (later): LLM-judge** on a stratified sample via the existing
  `edgar/ai/evaluation` infra, for facets without a clean oracle.

## Baseline (2026-06-20, post fu3x/2w5y/2h4c/zxnj)

| facet | coverage | bad_rate | verified | top triage target |
|-------|----------|----------|----------|-------------------|
| fee_capacity | 67% | 0% | 9/9 | null: pre-2022 inline tables / no exhibit |
| lead_bookrunner | 21% | 0% | — | null: 424B2 structured-note cover agent not extracted |
| shelf_status | 100% | 0% | — | — |

The headline next target is **lead_bookrunner coverage** — the 2h4c guard removed
all garbage but the 424B2 structured-note covers return an honest `None`;
extracting the real agent ("BofA Securities, Inc.") is the deeper follow-up.
