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
| `tier_c_judge.py` | Tier C LLM-judge: prompt builder + verdict parser + evidence gatherer |
| `test_tier_c_judge.py` | Fast unit tests for the Tier C pure functions |

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
- **Tier C: LLM-judge semantic audit** (`tier_c_judge.py`). For facets where a
  value can be clean and internally consistent yet still semantically wrong (is
  this *the lead* agent? is this *the* registered amount?). Mirrors
  `edgar/ai/evaluation/judge.py`: the module only builds prompts and parses
  verdicts; a Claude Code subagent does the judging (no API key, no per-run cost,
  nothing non-deterministic in the gate). It is an **audit, not a gate** — a
  confirmed disagreement becomes a new Tier B oracle or a hand-verified
  `corpus.json` anchor, which is what guards CI.
  - Run it: `get_judge_tasks(corpus, facet=...)` builds `{prompt, ...}` per
    covered value; spawn one subagent per `task["prompt"]`; feed each reply to
    `parse_offering_judge_verdict(...)`; `summarize_verdicts(...)` prints the
    disagreement catalog.
  - Best for the **semantic** facets (`lead_bookrunner`, `fee_capacity`). A live
    run confirmed both (Laidlaw placement agent; Vincerx $100M recovered from the
    amendment's parent registration) and, when fed thin evidence, produced a
    *false* disagreement on a BofA structured note — fixed by surfacing the
    labeled `Selling Agent:` field and the `("BofAS")` abbreviation definition in
    the evidence.
  - **Not** for `shelf_status`: the same run showed the judge botching the
    three-year date arithmetic (blessed a wrong status with high confidence). Date
    consistency belongs to the deterministic Tier B lifecycle oracle, not an LLM.

## Baseline (2026-06-20, post fu3x/2w5y/2h4c/zxnj + cover-agent + fee-source fallback)

| facet | coverage | bad_rate | verified | remaining triage target |
|-------|----------|----------|----------|-------------------------|
| fee_capacity | 78% | 0% | 9/9 | null: pre-2022 inline "Calculation of Registration Fee" tables (needs corpus anchors) |
| lead_bookrunner | 93% | 0% | — | one prose-only structured note (not worth a fragile pattern) |
| shelf_status | 100% | 0% | 2/2 | — |

Both coverage attacks that lifted these numbers were measured here: the 424B2
cover-agent extraction (lead_bookrunner 21%→93%) and the amendment fee-source
fallback (fee_capacity 67%→78%). The lifecycle Tier B oracle now verifies
shelf_status date/takedown consistency.
