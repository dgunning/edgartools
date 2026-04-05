# Expansion Pipeline Design — Agent-Driven Company Coverage Expansion

*Date: 2026-04-05*
*Status: Design approved, pending implementation*

---

## Problem

We have 100 companies at EF-CQS 0.9302. Expanding to the S&P 500 (and beyond) requires:

1. **Mechanical onboarding** — running each new company through the extraction pipeline, applying known patterns, and measuring quality
2. **Hard gap investigation** — understanding why certain metrics fail for certain companies and deciding the correct resolution (exclusion, divergence, concept fix, formula, escalation)
3. **Knowledge capture** — ensuring that patterns discovered for one company benefit future companies

The autonomous loop (`auto_eval_loop.py`) was deprecated because config-only fixes hit a ceiling for improving *existing* companies. But for *new* companies, the same patterns that already work for the existing 100 resolve ~80-90% of metrics. The remaining ~10-20% require investigation — the same kind of work done manually in Phase 11.

## Solution

Three independent skills that a Claude Code agent invokes in sequence. State passes between phases via **markdown reports on disk** — durable, human-readable, and session-crash-safe.

```
/expand-cohort [tickers]          -> Inner loop: onboard + measure + apply patterns
/investigate-gaps [cohort-name]   -> Outer loop: investigate + fix + escalate
/review-escalations [cohort-name] -> Interactive: human + agent review unresolved gaps
```

## Architecture

### Nested Loop

```
+--------------- OUTER LOOP (per cohort) ----------------+
|                                                         |
|  /expand-cohort                                         |
|    ONBOARD -> MEASURE -> DIAGNOSE -> FIX -> VALIDATE    |
|    -> REPORT (cohort-report.md)                         |
|         |                                               |
|         v                                               |
|  /investigate-gaps                                      |
|    GATHER EVIDENCE -> CLASSIFY -> DECIDE -> VALIDATE    |
|    -> UPDATE cohort-report.md                           |
|    -> WRITE escalation-report.md                        |
|         |                                               |
|         v                                               |
|  /review-escalations                                    |
|    PRESENT gap -> HUMAN DECIDES -> APPLY -> NEXT        |
|    -> UPDATE escalation-report.md                       |
|    -> UPDATE global config (archetypes, known_concepts) |
|                                                         |
+---------------------------------------------------------+
```

### Worktree Parallelism

Multiple cohorts run in parallel via git worktrees. Each worktree handles a different set of tickers.

```
main branch
  |
  +-- worktree-A: /expand-cohort HD,LOW,MCD,YUM  -> /investigate-gaps
  |     changes: company_overrides/HD.json, LOW.json, MCD.json, YUM.json
  |
  +-- worktree-B: /expand-cohort D,NEE,SO,DUK    -> /investigate-gaps
  |     changes: company_overrides/D.json, NEE.json, SO.json, DUK.json
  |
  +-- worktree-C: /expand-cohort BK,STT,PNC,USB  -> /investigate-gaps
        changes: company_overrides/BK.json, STT.json, PNC.json, USB.json

After completion:
  merge worktree-A -> main (no conflicts — different files)
  merge worktree-B -> main
  merge worktree-C -> main

On main:
  /review-escalations for each cohort
  -> Global patterns (archetypes, known_concepts) applied here
```

**Conflict avoidance rule:** Worktree agents only modify per-company files (`company_overrides/*.json`, `companies.yaml` entries for their tickers). Global config changes (`metrics.yaml`, `industry_metrics.yaml`) happen on main during `/review-escalations`.

---

## Skill 1: `/expand-cohort` — Inner Loop

**Purpose:** Onboard new companies, apply known patterns, get them to 80%+ EF-CQS.

**Input:** Comma-separated tickers or a named batch (e.g., `SP500-batch-3`)

**Steps:**

| Step | What | Tool Used |
|------|------|-----------|
| ONBOARD | Resolve CIK, detect archetype, fetch yfinance snapshot, run orchestrator | `onboard_company()` |
| MEASURE | Compute EF-CQS for the cohort | `compute_cqs()` |
| DIAGNOSE | Identify gaps, classify by capability tier (C1/C2/C3) | `identify_gaps()` |
| FIX | Apply deterministic fixes: industry exclusions, known concept mappings, concept existence checks, composite formulas | `discover_concepts()`, `verify_mapping()`, `learn_mappings()`, `derivation_planner` |
| VALIDATE | Re-measure. Per-company gate: EF-CQS >= 0.80 | `compute_cqs()` |
| REPORT | Write cohort report markdown | New: report generator |

**Quality gate:** Companies with EF-CQS >= 0.80 are `graduated`. Below 0.80 are `needs_investigation`.

**Output:** `cohort-reports/cohort-YYYY-MM-DD-{name}.md`

### Cohort Report Format

```markdown
# Cohort Report: {name}
Generated: {timestamp}
Status: inner_loop_complete | investigation_complete | reviewed

## Summary
- Companies: N onboarded, M graduated, K need investigation
- EF-CQS: X.XX (cohort average)
- Fixes applied: N (breakdown by type)
- Gaps remaining: N (breakdown by gap_type)

## Company Results
| Ticker | EF-CQS | Status | Gaps | Notes |
|--------|--------|--------|------|-------|

## Fixes Applied
| # | Ticker | Metric | Action | Confidence | Detail |

## Unresolved Gaps
| # | Ticker | Metric | Gap Type | Variance | Root Cause | Graveyard |
```

---

## Skill 2: `/investigate-gaps` — Outer Loop

**Purpose:** Investigate unresolved gaps from the cohort report. Auto-apply confident fixes. Escalate ambiguous cases.

**Input:** Cohort report path or cohort name

**Per-gap investigation workflow:**

### Step 1: Gather Evidence

| Evidence | Tool | What it tells us |
|----------|------|-----------------|
| Available XBRL concepts | `discover_concepts()` | What concepts exist for this metric in this filing |
| Value match | `verify_mapping()` | Does the best candidate match the reference value |
| Peer company patterns | `learn_mappings()` | What do similar companies use for this metric |
| Concept existence | Element context index check | Is the concept actually in the filing's XBRL |
| Multi-period consistency | Multiple-period extraction | Is this variance consistent or a one-off |

### Step 2: Classify Root Cause

| Root Cause | Signal |
|------------|--------|
| `concept_absent` | Concept doesn't exist in filing's XBRL (calc tree + facts + element index all empty) |
| `reference_mismatch` | XBRL is correct, yfinance aggregates differently (e.g., PPE includes operating leases) |
| `wrong_concept` | Currently mapped to wrong concept, a better one exists with lower variance |
| `needs_composite` | Individual components exist, need formula to combine them |
| `sign_error` | Value is negated vs. reference |
| `genuinely_broken` | Extraction engine limitation, no config fix possible |

### Step 3: Decide Action (Confidence-Gated)

**Auto-apply (confidence >= 0.90):**

| Root Cause | Action | Confidence Basis |
|------------|--------|-----------------|
| `concept_absent` | `EXCLUDE_METRIC` (not_applicable) | Concept missing from calc tree + facts + element index |
| `reference_mismatch` | `DOCUMENT_DIVERGENCE` | Consistent across 2+ periods, peer pattern confirms |
| `wrong_concept` | `MAP_CONCEPT` | verify_mapping confirms < 5% variance |
| `needs_composite` | `ADD_FORMULA` | derivation_planner confirms all components exist |
| `sign_error` | `FIX_SIGN_CONVENTION` | Value is exact negative of reference |

**Escalate (confidence < 0.90):**
- Write to escalation report with all evidence gathered
- Include agent's best-guess recommendation

### Step 4: Validate (After Each Auto-Applied Fix)

- `compute_cqs()` on affected company
- If regression: revert fix, move gap to escalation
- If improved: keep fix, update cohort report

### Safety Rules

1. Never propose a concept without verifying it exists in the filing
2. Never apply a fix that causes a regression (measure before/after)
3. After 3 failed fix attempts on the same gap: auto-escalate
4. Cross-company patterns must have >= 2 peer confirmations before applying globally
5. Global config changes are deferred to `/review-escalations` on main

**Output:** Updated cohort report + `escalation-reports/escalation-YYYY-MM-DD-{name}.md`

### Escalation Report Format

```markdown
# Escalation Report: {name}
Generated: {timestamp}
Status: pending_review | reviewed

## Summary
- Gaps investigated: N
- Auto-resolved: M (breakdown by action type)
- Escalated: K
- EF-CQS improvement: X.XX -> Y.YY

## Auto-Applied Fixes
| # | Ticker | Metric | Action | Evidence Summary |

## Escalated Gaps

### Gap N: {Ticker} - {Metric} ({gap_type})
**Confidence:** X.XX
**Evidence:**
- {discovery results}
- {peer patterns}
- {multi-period data}
**Why escalated:** {explanation}
**Agent recommendation:** {best guess action + reasoning}
```

---

## Skill 3: `/review-escalations` — Interactive Review

**Purpose:** Human + agent review each escalated gap together. Decisions are recorded in the report. Patterns are captured in global config.

**Input:** Escalation report path or cohort name

**Interaction pattern:**

The agent presents one gap at a time with full evidence from the escalation report. The human decides:

| Human says | Agent does |
|------------|-----------|
| "divergence" / "document it" | Apply DOCUMENT_DIVERGENCE, mark reviewed |
| "exclude" / "not applicable" | Apply EXCLUDE_METRIC, mark reviewed |
| "try concept X" | Run verify_mapping, show result, apply if valid |
| "skip" / "defer" | Mark as deferred, move to next |
| "this applies to all {industry}" | Apply fix + update industry_metrics.yaml archetype |
| "escalate to engineering" | Mark as engineering_backlog |

**Key behaviors:**

1. **One gap at a time** — presents evidence, waits for decision
2. **Updates report after every decision** — safe to interrupt and resume
3. **Learns patterns** — "applies to all utilities" updates the archetype, not just the single company. Future `/expand-cohort` runs benefit automatically.
4. **Global config changes happen here** — new known_concepts in `metrics.yaml`, new archetype rules in `industry_metrics.yaml`. This is the only place global config is modified.

**Report update format:**

```markdown
### Gap N: {Ticker} - {Metric}
**Status:** reviewed
**Decision:** {action taken}
**Reviewer note:** "{human's reasoning}"
**Applied:** {timestamp}
**Pattern captured:** {if archetype updated, note here}
```

---

## What We Build vs. What Exists

| Component | Status | Work |
|-----------|--------|------|
| `onboard_company.py` | Exists | Minor adaptation for structured results |
| `compute_cqs()` | Exists | None |
| `identify_gaps()` | Exists | None |
| `discover_concepts()` | Exists | None |
| `verify_mapping()` | Exists | None |
| `learn_mappings()` | Exists | None |
| `derivation_planner.py` | Exists | None |
| Config applier (TypedAction -> JSON) | Exists in deprecated code | Extract + simplify from `auto_eval_loop.py` |
| **Gap investigator** | New | Investigation workflow using existing tools |
| **Confidence scorer** | New | Rules engine: evidence -> confidence score |
| **Cohort report generator** | New | Markdown writer from CQS + gap data |
| **Escalation report generator** | New | Markdown writer from investigation results |
| **`/expand-cohort` skill** | New | Skill file orchestrating inner loop |
| **`/investigate-gaps` skill** | New | Skill file orchestrating outer loop |
| **`/review-escalations` skill** | New | Skill file for interactive review |
| CLAUDE.md | Exists | Add 3-line mention of expansion skills |

## File Locations

```
edgar/xbrl/standardization/
  tools/
    expand_cohort.py          # Inner loop orchestration
    investigate_gaps.py       # Outer loop investigation logic
    config_applier.py         # TypedAction -> per-company JSON (extracted from deprecated code)
    confidence_scorer.py      # Evidence -> confidence rules engine
    report_generator.py       # Cohort + escalation report markdown writers
  cohort-reports/             # Cohort report markdown files
  escalation-reports/         # Escalation report markdown files

.claude/skills/
  expand-cohort/SKILL.md
  investigate-gaps/SKILL.md
  review-escalations/SKILL.md
```

## CLAUDE.md Update

Add to the "Autonomous System" section:

> **Expansion Pipeline:** Three skills for expanding company coverage:
> - `/expand-cohort [tickers]` — Onboard new companies, apply known patterns, measure quality (inner loop). Run in worktrees for parallel cohorts.
> - `/investigate-gaps [cohort]` — Investigate unresolved gaps, auto-apply confident fixes, escalate ambiguous cases (outer loop).
> - `/review-escalations [cohort]` — Interactive review of escalated gaps with human. Captures patterns into global config.

## Success Criteria

1. A new batch of 10-20 companies can be onboarded and reach >= 0.80 EF-CQS with a single `/expand-cohort` invocation
2. `/investigate-gaps` auto-resolves >= 70% of remaining gaps (matching Phase 11's manual resolution rate)
3. `/review-escalations` captures patterns that benefit subsequent batches (measurable: fewer gaps per batch over time)
4. Three parallel worktrees can run `/expand-cohort` + `/investigate-gaps` without merge conflicts
5. The complete pipeline (all 3 skills) can expand coverage by 50 companies per session
