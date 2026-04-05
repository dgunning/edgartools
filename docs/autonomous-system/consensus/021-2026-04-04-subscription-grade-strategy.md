# Consensus 021: Path to Subscription-Grade Financial Database

**Date**: 2026-04-04
**Models**: Claude Opus 4.6 (Advocate 7.5/10, Critic 7/10, Deepthinker synthesis)
**PAL Thread**: 35936e1f-50c4-4ebf-ba53-5fc84162b6c1

## Problem

EF-CQS at 0.8740 with 72 remaining gaps. Need strategy for subscription-grade quality (0.95+) and scaling from 50 to 500+ companies.

## Key Finding

**"Pure extraction fidelity" is already ~0.93+.** EF-CQS 0.87 conflates extraction errors with reference-standard disagreements (PPE+leases, D&A scope, ShortTermDebt aggregation). Only ~11 of 72 gaps are true extraction bugs. The extraction engine is near done. The bottleneck has shifted to product (provenance, documentation) and architecture (config scalability).

## Agreements

1. Fix 11 true extraction bugs first (Track 0) — highest ROI
2. AI layer should be deprioritized (0/18 kept proposals)
3. Industry-rule collapsing is the right config architecture (221 exclusions → ~15 rules)
4. Reference standard documentation should be static markdown, not runtime engine
5. Provenance metadata is the real product differentiator
6. No more `_apply_phaseN_overrides()` functions

## Execution Order

| Step | What | Time |
|------|------|------|
| Track 0 | Fix 11 real bugs, compute "pure EF" | 1-2 days |
| Track 1a | Collapse industry exclusions into industry_metrics.yaml | 1 week |
| Track 2 | Metric definition docs (static markdown) | 2-3 days |
| Provenance | Add xbrl_concept, filing_accession, period to StandardizedMetric | 1 week |
| Track 1b | Diagnose WSL YAML, migrate company overrides | 1 week |
| Track 3 | TotalLiabilities composite with NCI scope check | 1-2 weeks |
| Expansion | Redefine gate as pattern-coverage, expand 100→500 | After above |

## What NOT To Do

- No more AI overnight loops until config architecture is fixed
- No runtime yfinance reconciliation engine
- No more `_apply_phaseN_overrides()` functions
- Don't gate expansion on EF-CQS 0.95 if pure EF is already 0.93+

## Critical Risks

1. WSL YAML persistence — diagnose before Track 1b; SQLite is fallback
2. NCI scope consistency in TotalLiabilities composite — mandatory pre-check
3. Temptation to add Phase 12 Python overrides — route through industry rules instead

## Adjudicated Disagreements

| Issue | Resolution |
|-------|------------|
| Track 1 difficulty | Collapse in Python first, then migrate format |
| Track 3 safety | Build with mandatory NCI scope-consistency check |
| Strategic framing | Ship after Track 0; Tracks 1-3 are quality-of-life, not blockers |
