# ADR-001: Separate Standardization Package from Upstream EdgarTools

**Status:** Deferred (revisit after Phase B, ~weeks 2-3 of Consensus 019 roadmap)
**Date:** 2026-04-02
**Context:** Subscription-grade financial database project

## Problem

We forked `dgunning/edgartools` and built a 255K-line standardization layer on the `feature/ai-concept-mapping` branch. The upstream repo is now **713 commits ahead** of our divergence point, with active development in the same XBRL areas we depend on.

Current pain:
- Upstream bug fixes to stitching, dimensional data, statement resolution — we don't get them
- Upstream new features (IFRS mappings, ConceptGraph, FilingViewer) — inaccessible to us
- Cherry-picking is manual and conflict-prone due to deep divergence
- The gap grows daily; a full merge would touch 255K+ lines

## Options Considered

### Option 1: Cherry-pick individual upstream commits
- Surgical, works for isolated fixes
- Labor-intensive, requires constant monitoring
- Breaks when commits touch files we've modified

### Option 2: Periodic merge/rebase of upstream
- Gets everything at once
- Merge would be extremely painful given 255K insertions / 138K deletions divergence
- High risk of subtle breakage in standardization layer

### Option 3: Extract standardization into a separate package (recommended)
- Install upstream `edgartools` as a pip dependency
- Our standardization code lives in its own package, imports EdgarTools public API
- Upstream upgrades come via `pip install --upgrade edgartools`
- Zero merge conflicts — different codebases entirely

## Decision

**Option 3** — extract into a separate package. Deferred until after Phase B stabilizes the extraction layer logic (COGS, OperatingIncome, ShortTermDebt fixes).

## Coupling Analysis

### What we use from EdgarTools (public API only)

```python
from edgar import Company, set_identity, use_local_storage

company = Company(ticker)
filings = company.get_filings(form="10-K")
xbrl = filings.latest().xbrl()
# Then: xbrl.facts, calculation trees, contexts, labels
```

### Private API touches (2 total, both optional)

| Import | Used for | Required? |
|--------|----------|-----------|
| `edgar.storage._local.is_using_local_storage` | Performance optimization | No |
| `edgar.storage._local.local_filing_path` | Local file fallback | No |

### Upstream files we modified (6 total)

| File | Change | Extraction plan |
|------|--------|----------------|
| `edgar/__init__.py` | 2 new import lines | Remove — our package has its own entry point |
| `edgar/entity/core.py` | Added `get_standardized_financials()` | Remove — becomes `standardize(Company("AAPL"))` in our package |
| `edgar/paths.py` | Added `get_financial_db_path()` | Remove — use our own path management |
| `edgar/sgml/sgml_common.py` | Local storage optimization | Remove — offer as PR to upstream |
| `edgar/standardized_financials.py` | New file (579 lines) | Move into our package |
| `edgar/financial_database.py` | New file (303 lines) | Move into our package |

## Extraction Plan

### Target package structure

```
edgartools-standardization/
├── standardization/
│   ├── __init__.py
│   ├── edgar_adapter.py          # Single interface to EdgarTools
│   ├── core.py                   # StandardConcept enum
│   ├── orchestrator.py           # Multi-layer extraction engine
│   ├── models.py                 # Data classes
│   ├── config_loader.py          # YAML config
│   ├── layers/                   # tree_parser, facts_search, ai_semantic, dimensional
│   ├── strategies/               # Industry-specific logic
│   ├── config/                   # metrics.yaml, companies.yaml, industry_metrics.yaml
│   ├── tools/                    # auto_eval, onboarding, solver, etc.
│   ├── ledger/                   # SQLite experiment tracking
│   └── database/                 # Financial database schema
├── pyproject.toml                # edgartools>=5.25,<6.0 as dependency
└── tests/
```

### Steps

1. **Rewire imports** (~1 day) — internal imports use new package path, EdgarTools imports use public API only
2. **Create adapter layer** (~half day) — single `edgar_adapter.py` that wraps all EdgarTools calls; if upstream API changes, we fix one file
3. **Remove 6 upstream modifications** (~1 hour) — revert our fork to clean upstream state
4. **Pin and test** (ongoing) — CI runs against upstream releases to catch breaking changes

### Estimated effort: 2-3 days

## Benefits

| Before (fork) | After (separate package) |
|---------------|--------------------------|
| 713 commits behind, growing | `pip install --upgrade edgartools` |
| Manual cherry-pick for bug fixes | Automatic via dependency |
| Upstream IFRS mappings inaccessible | Available immediately |
| Merge conflicts on every sync | Zero conflicts |
| One monolithic repo | Clean separation of concerns |

## Risks

- Upstream makes breaking change to `Filing.xbrl()` API — mitigated by adapter layer and version pinning
- We lose ability to patch upstream internals — mitigated by offering fixes as upstream PRs
- 2-3 day investment during active development — mitigated by deferring to post-Phase B

## References

- Consensus 019: "Diagnose, Then Fix" roadmap (2026-04-02)
- Upstream repo: https://github.com/dgunning/edgartools
- Our fork: https://github.com/sangicook/edgartools
- Feature branch: `feature/ai-concept-mapping`
