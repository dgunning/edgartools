# Subscription-Grade Financial Database: Multi-Model Consensus

*Consensus Report -- March 21, 2026*
*Continuation ID: `db9007c4-dab5-4929-88da-7f0a2ad2bfd8`*

---

## Date & Participants

| Role | Model | Stance |
|------|-------|--------|
| Optimistic advocate | OpenAI GPT-5.4 | For: argue what's achievable, propose concrete improvements |
| Skeptical challenger | Google Gemini 3.1 Pro | Against: challenge assumptions, identify fundamental gaps |
| Moderator & verifier | Claude Opus 4.6 | Neutral: verify claims against code, synthesize actionable roadmap |

## System State at Time of Discussion

| Metric | Value |
|--------|-------|
| CQS (Composite Quality Score) | 0.9734 |
| Companies evaluated | 100 (EXPANSION_COHORT_100) |
| Metrics extracted | 19 standardized financial line items |
| Pass rate | 96.0% |
| Mean variance | 0.9% |
| Coverage rate | 99.3% |
| Golden master rate | 96.7% |
| Active regressions | 9 |
| Reference source | yfinance (single source) |
| Validation mode | Latest filing only (single-period) |

### Recent Fixes Just Validated (Fixes 1-6)

- **Fix 1**: Auto-create missing YAML paths for company overrides
- **Fix 2**: Sign inversion detection and handling
- **Fix 3**: Regression tracking (enumerate regressed metrics by ticker)
- **Fix 4**: Multi-period solver ranking (stability > variance)
- **Fix 5**: Store actual XBRL concepts in golden masters (was storing strategy names like "tree")
- **Fix 6**: Guard against strategy-name golden concepts, route to solver with golden value

### Latest Run Results (100-company validation of Fixes 5+6)

- CQS: 0.9729 -> 0.9734 (+0.0005)
- Regressions: 10 -> 9
- 1/1 experiments kept (CME:IntangibleAssets -- solver found 3-component formula, 3/3 periods, 0.0% variance)
- 78 gaps exhausted -- most blocked by `reference_value=None` (yfinance gaps)
- Circuit breaker triggered after 10 consecutive failures

---

## GPT-5.4 Analysis (Optimistic Stance)

**Verdict:** Technically feasible to reach strong paid-data quality for a constrained universe, but the current bottleneck is no longer auto-eval throughput -- it is evaluation truth, ontology breadth, and governance. Subscription-grade quality will require a validator/reference architecture redesign plus targeted human review on tail cases.

### 1. Technical Feasibility

The extractor is promising: layered fallback, industry logic, composites, and provenance capture are the right primitives. But CQS 0.9734 is overstating readiness because the measurement loop is anchored to weak ground truth. The system conflates "no external reference" with "not worth solving" -- acceptable for bootstrapping, not for subscription-grade.

### 2. Embedded Assumptions That Will Fight You

- **20% tolerance** (`schema.py:113`): The pass/fail model is too coarse. Need metric-class tolerances, period-aware checks, and absolute+relative thresholds.
- **Permissive golden promotion** (`auto_eval.py:549`): `promote_golden_masters(min_periods=1)` contradicts the stated "3+ periods" requirement. Will contaminate goldens and mask regressions.
- **Strategy-label grouping** (`schema.py:823-826`): Golden master promotion groups by `ticker, metric, strategy_name`, not concept/fingerprint params -- risks promoting unstable semantics under a stable strategy label.
- **Reference exclusion** (`auto_eval_loop.py:1442-1452`): `reference_value=None` triggers `ADD_EXCLUSION`, institutionalizing reference incompleteness into product behavior.

### 3. User Value Assessment

For users, breadth and consistency matter more than squeezing CQS from 0.9734 to 0.9760 on 19 metrics. Highest-value improvements: better reference truth, historical consistency, more metrics with explicit applicability rules, faster filing freshness. A 19-metric system is useful but not Bloomberg-adjacent.

### 4. Where Effort Should Go

Do **not** spend the next cycle optimizing hybrid/team eval. Near diminishing returns on search mechanics. +0.0005 gain is signal. Priority order:

1. **Replace single-source validation** with a reference arbitration layer: SEC raw facts + company-reported 10-K values + commercial feed
2. **Move to longitudinal validation**: trailing 12 quarters + 5 annual periods
3. **Build a canonical fact store**: every extracted datum carries concept, dimensions, unit, scale, period type, restatement lineage, filing accession, amendment status
4. **Expand metric ontology** from 19 to ~50 before 500 companies. Do not scale universe first if ontology is shallow
5. **Applicability engine**: universal/non-universal flags in `metrics.yaml` are too weak. Model required/optional/forbidden by industry + filer profile

### 5. Autonomy Limits

Mostly autonomous for the head, not fully autonomous for the tail. Realistic target:
- **90-95% of volume** handled autonomously
- **High-risk residuals** routed to human review or delayed publish

Subscription-grade does not mean zero humans; it means users almost never see bad data. Full no-human for 500 companies/50 metrics is plausible only if you accept "very good mid-market quality," not Bloomberg/FactSet parity.

### 6. Concrete Architecture for 500+ Companies / 50+ Metrics

- **Ingestion layer**: SEC filing watcher, accession-based event stream, amendment/restatement detection, SLA queues
- **Canonical XBRL fact store**: normalized facts table keyed by issuer/accession/concept/context/unit/dimensions; preserve presentation/calculation/linkbase edges
- **Metric resolver layer**: deterministic resolver graph per metric (direct concept, dimensional rollup, composite formula, industry resolver, learned override)
- **Validation layer** with 3 scores: extraction fidelity vs SEC/XBRL semantics, standardization alignment vs internal canonical definition, external agreement vs references
- **Reference arbitration service**: multiple sources with confidence weighting and conflict states
- **Golden-master successor**: "verified resolver profiles" requiring multi-period stability, no amendment conflicts, and cross-source agreement
- **Risk engine**: publish/hold/escalate based on novelty score, variance, metric criticality, issuer archetype, amendment status
- **Ops surface**: exception queue, diff review, backfill/recompute, audit trail

### 7. Industry Perspective

Top vendors do not trust one source, do not rely on latest period only, and do not equate line-item name matching with semantic equivalence. They use canonical data models, issuer-specific templates, amendment handling, and exception workflows. The solver and autonomous proposal engine are differentiators, but they must sit behind stricter governance.

**Confidence: 9/10**

---

## Gemini 3.1 Analysis (Skeptical Stance)

**Verdict:** While the deterministic and AI-escalation engineering in the current pipeline is exceptional, you are hitting an "overfitting wall" at CQS 0.9734. Achieving subscription-grade quality autonomously is fundamentally unrealistic without an explicit human-in-the-loop (HITL) exception layer and a robust, institutional-grade reference dataset.

### 1. Diminishing Returns on Auto-Eval

The system is severely overfitting. CQS 0.9734 on just 19 metrics for 100 companies indicates the solver algorithms are optimizing for the quirks of a tiny statistical sample. Complex architectural shifts like Mode 3 (Runner/Evaluator parallel) will yield negligible real-world improvements until significantly more variance (500+ companies, 50+ metrics) is injected. Stop optimizing loop concurrency and start broadening the validation cohort.

### 2. Highest-Leverage Improvements

Dependency on yfinance as a source of truth is the single biggest bottleneck. Cannot build a Bloomberg-grade product using retail-grade, scraped reference data. The solver cannot discover formulas if `reference_value` is `None` or structurally incorrect. The absolute highest leverage improvement is swapping the validation baseline to a verifiable, multi-period institutional data source (like Compustat or Calcbench) and validating backward across 5-10 historical periods.

### 3. The Myth of Autonomous Institutional Quality

Financial reporting contains irreducible subjectivity -- non-GAAP reconciliations, one-time charges, and unique sector-specific accounting treatments require CPA-level interpretation. The AI can successfully navigate 90-95% of the structural XBRL taxonomy tree and act as an incredible triage engine, but the final 5-10% of mapping configurations require human sign-off. Institutional clients will not pay Bloomberg prices for data governed solely by an LLM guessing at edge conditions.

### 4. Target Architecture for Scale

To handle 500+ companies and 50+ metrics, the system needs fundamental architectural overhauls:

- **Decouple from YAML**: At scale, maintaining thousands of `company_overrides` and `standardization` blocks in YAML will become unreadable and unmergable. Migrate to a relational database (PostgreSQL) or GraphDB.
- **Continuous Event-Driven Updates**: Subscription services don't run in `run_overnight()` batches. Evolve to event-driven model leveraging EDGAR RSS feeds, triggering single-company extraction within seconds of filing.
- **Explicit HITL Dashboard**: Route `high_variance` and `unmapped` gaps to an internal tooling dashboard where financial analysts can securely inject ground-truth standardization formulas.

**Confidence: 9/10**

---

## Claude Verification of Claims

Both models made specific claims about the codebase. I verified each against the actual code:

### Claim 1: `promote_golden_masters(min_periods=1)` is too permissive

**VERIFIED.** At `auto_eval.py:549`:
```python
promoted = ledger.promote_golden_masters(min_periods=1)
```
The function signature defaults to `min_periods=3` (at `schema.py:778`), but the call site overrides it to 1. This means single-period extractions get promoted to golden masters, directly contradicting the stated "3+ period" requirement. This contaminates the golden master pool and masks regressions.

### Claim 2: 20% validity tolerance is too coarse

**VERIFIED.** At `schema.py:113`:
```python
# Valid if within 20% tolerance
```
And at `schema.py:791`:
```python
max_variance: Maximum average variance allowed for promotion (default 20%).
```
A single binary pass/fail at 20% is too coarse for subscription-grade. Revenue off by 19% passes; Revenue off by 21% fails. Meanwhile, `metrics.yaml` already defines per-metric tolerances (Capex: 40%, DepreciationAmortization: 30%) but `ExtractionRun.__post_init__` uses the hardcoded 20%.

### Claim 3: `reference_value=None` triggers metric exclusion

**VERIFIED.** At `auto_eval_loop.py:1442-1452`:
```python
# If reference value is None, this is likely a structural gap -> add exclusion
if gap.reference_value is None:
    return ConfigChange(
        file="companies.yaml",
        change_type=ChangeType.ADD_EXCLUSION,
        yaml_path=f"companies.{gap.ticker}.exclude_metrics",
        new_value=gap.metric,
        ...
    )
```
When yfinance returns None, the system proposes *excluding the metric for that company*. This institutionalizes reference gaps as product behavior. The correct response is "unverified" or "unknown", not "excluded".

---

## Points of Agreement (All Three)

| # | Point | GPT-5.4 | Gemini 3.1 | Claude |
|---|-------|---------|------------|--------|
| 1 | **Stop optimizing eval loop mechanics.** +0.0005 CQS per run = diminishing returns. Parallelism helps speed, not quality. | Yes | Yes | Yes |
| 2 | **yfinance is the existential bottleneck.** 78/79 gaps were `reference_value=None`. Solver is blind without a target. | Yes | Yes | Yes |
| 3 | **Need longitudinal/multi-period validation**, not just latest filing. | Yes | Yes | Yes |
| 4 | **90-95% autonomous is the realistic ceiling.** The tail needs human review or hold/escalate mechanism. | Yes | Yes | Yes |
| 5 | **Expand metrics (19->50) BEFORE scaling companies (100->500).** Shallow ontology + wide coverage = bad product. | Yes | Yes | Yes |

## Points of Disagreement + Resolution

### 1. YAML vs PostgreSQL for Config Storage

- **Gemini**: "Banish YAML, migrate to PostgreSQL/GraphDB for overrides"
- **GPT-5.4**: Incremental evolution, keep YAML + ledger as control plane
- **Claude resolution**: **Keep YAML.** YAML is version-controlled, git-diffable, and agent-friendly (agents can read/write it without DB credentials). At 500 companies the overrides section gets large, but that's manageable with better YAML organization (per-company files, per-industry files) rather than a storage layer swap. A hybrid approach (DB for runtime serving, YAML for version-controlled defaults) may be optimal later.

### 2. "Ditch yfinance immediately"

- **Both models**: Replace yfinance with Compustat, Calcbench, or institutional-grade data
- **Claude resolution**: **Impractical for an open-source project.** Licensed data costs $10K+/year. The pragmatic intermediate step is **SEC-native self-validation**: XBRL calculation linkbases already contain arithmetic relationships (Assets = Liabilities + Equity). We can validate internally against the company's own reported math -- free and authoritative. Add SEC EDGAR XBRL fact API as second free reference. Consider commercial data only if the project supports it.

### 3. "CQS is overfitting"

- **Gemini**: "Severely overfitting to a 100-company cohort"
- **GPT-5.4**: CQS overstates readiness due to weak ground truth
- **Claude resolution**: **Partially valid.** CQS measures real extraction accuracy against real filings -- it's not overfit in the ML sense (we're not training on test data). But the 100-company sample IS narrow, and expanding to 500 companies will absolutely expose new structural gaps (new industries, unusual accounting, extension taxonomies). The score will drop before it rises. The bigger issue is that CQS doesn't penalize what we DON'T extract (missing metrics, missing companies).

---

## Synthesized Roadmap

See **[Subscription-Grade Roadmap](subscription-grade-roadmap.md)** for the full actionable plan.

Summary of phases:

| Phase | Focus | Key Deliverable |
|-------|-------|-----------------|
| 1 | Fix governance bugs | Correct golden promotion, tolerances, exclusion logic |
| 2 | SEC-native self-validation | XBRL calc linkbase checks, cross-statement reconciliation |
| 3 | Metric expansion (19->50) + historical | Debt breakdown, per-share, 3 annual + 4 quarterly validation |
| 4 | Company scaling (100->500) + references | S&P 500, SEC XBRL API, event-driven processing |

---

## How to Reuse This Document

### Re-consulting the models

The consensus tool continuation ID `db9007c4-dab5-4929-88da-7f0a2ad2bfd8` preserves file context (not conversation transcript). To continue the discussion:

```
Use the consensus tool with continuation_id: db9007c4-dab5-4929-88da-7f0a2ad2bfd8
```

Note: The models will re-analyze the files but won't have the prior conversation. Share this document as context in the prompt.

### After each phase

Update the [Roadmap](subscription-grade-roadmap.md) tracking table with:
- Date completed
- CQS before/after
- Key findings
- Whether the consensus predictions held

### Related Documents

- [Auto-Eval Strategy](auto-eval-strategy.md) -- Technical architecture of the CQS loop
- [Verification Roadmap](verification-roadmap.md) -- Parallel track for test/verification quality
- [Auto-Eval Results](auto-eval-results.md) -- Historical CQS measurements
