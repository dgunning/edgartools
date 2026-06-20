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
| `corpus.json` | Frozen, stratified list of real filings (anchors + frontier + live breadth) |
| `build_corpus.py` | Rebuild/refresh the corpus (`--no-live` for anchors only) |
| `run_eval.py` | Tier A runner: bucket each facet, print dashboard + failure catalog |
| `thresholds.json` | Locked coverage floors / bad_rate ceilings (the ratchet) |
| `test_eval_ratchet.py` | Network-marked guardrail asserting thresholds hold |
| `test_frontier.py` | Fast unit tests pinning the frontier/ratchet partition |
| `tier_c_judge.py` | Tier C LLM-judge: prompt builder + verdict parser + evidence gatherer |
| `test_tier_c_judge.py` | Fast unit tests for the Tier C pure functions |

## Corpus strata

- **anchors** — hand-verified known-good (and known-deferred) values; regression
  guards. An `expected` mismatch is forced to `bad`.
- **frontier** — documented coverage gaps with hand-verified ground truth, carried
  with `"frontier": true`. They are run and reported but **excluded from the
  ratcheted denominator** (`summarize` skips them by default), so adding a gap case
  never lowers a floor. A frontier entry that is `null` today is the *gap*; once an
  extractor reaches it, its `expected` value (or `deferred`) starts being checked
  and a wrong value turns `bad`. Watch the gap close in the dashboard's
  "Frontier (known gaps — NOT ratcheted)" section.
- **live** — breadth-only sample (no expectations), surfaces unknown failure modes.

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
| fee_capacity | 78% | 0% | 9/9 | frontier: pre-2022 inline "Calculation of Registration Fee" tables |
| lead_bookrunner | 93% | 0% | — | one prose-only structured note (not worth a fragile pattern) |
| shelf_status | 100% | 0% | 2/2 | — |

Coverage/bad_rate are over the *ratcheted* scope only (frontier excluded). Both
attacks that lifted these numbers were measured here: the 424B2 cover-agent
extraction (lead_bookrunner 21%→93%) and the amendment fee-source fallback
(fee_capacity 67%→78%). The lifecycle Tier B oracle now verifies shelf_status
date/takedown consistency.

## Frontier: pre-2022 inline fee tables (the next lever)

Before the EX-FILING FEES (Exhibit 107) regime, the registration-fee table lived
inline in the S-3/S-1 body, with no exhibit to parse. `extract_registration_fee_table`
only reads the EX-107 attachment, so **every pre-2022 filing returns `None`** — a
hard wall the frozen 2025 corpus could not see. The corpus now carries 8
hand-verified pre-2022 entries spanning consumer, medical-device, biotech, energy,
clean-energy, financial, tech, and REIT issuers (5 concrete fixed-dollar shelves +
3 indeterminate 457(r) WKSI shelves). Current frontier state: **0/8 reachable**.

`_find_fee_table` already *locates* the inline body table on all of them; the gap
is parsing the older cover-table layout (totals like `Total $30,000,000`). Closing
it is the next bead: extend `_parse_fee_table_html` (or add an inline path) to read
the pre-checkbox table, then the 5 concrete entries return `expected` and the 3
WKSI shelves return `deferred`, and the frontier section walks toward 8/8.
