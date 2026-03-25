# XBRL Standardization

Maps company-specific XBRL concepts to standardized metrics, enabling cross-company financial comparisons. Uses a multi-layer architecture (Tree Parser → Facts Search → AI Semantic) with validation against yfinance reference data.

## Directory Structure

```
standardization/
├── config/                     Tier 1 configuration (YAML)
│   ├── metrics.yaml            Metric definitions, known_concepts, tree_hints
│   ├── companies.yaml          Company-specific overrides, exclusions, divergences
│   ├── industry_metrics.yaml   Industry-specific concept mappings
│   ├── yf_snapshots/           Cached yfinance reference data
│   └── onboarding_reports/     Per-company onboarding results
├── layers/                     Multi-layer mapping engine
│   ├── tree_parser.py          Layer 1: Static calculation tree parsing
│   ├── facts_search.py         Layer 2: Static facts database search
│   └── ai_semantic.py          Layer 3: Dynamic AI semantic mapping
├── ledger/
│   └── schema.py               SQLite experiment ledger (extraction runs, golden masters, auto-eval)
├── tools/                      Reusable tools for agents and automation
│   ├── auto_eval.py            CQS computation, gap analysis, cohort definitions
│   ├── auto_eval_loop.py       Experiment loop, TeamSession, propose_and_evaluate_loop
│   ├── auto_eval_checkpoint.py Checkpoint I/O and team dashboard
│   ├── auto_eval_dashboard.py  Morning review terminal dashboard (EF/SA scores)
│   ├── auto_solver.py          Subset-sum search for yfinance composite formulas
│   ├── discover_concepts.py    Search calc trees + facts for concept candidates
│   ├── verify_mapping.py       Value comparison against yfinance
│   ├── learn_mappings.py       Cross-company pattern discovery
│   ├── onboard_company.py      Automated single/batch company onboarding
│   ├── refresh_yf_snapshots.py Refresh yfinance reference snapshots
│   ├── bulk_preload.py         Pre-download SEC filings for offline operation
│   ├── pipeline_orchestrator.py State machine for batch expansion
│   └── ...
├── orchestrator.py             Main multi-layer orchestrator
├── reference_validator.py      Validation against yfinance snapshots
├── models.py                   MappingResult, MappingSource, ConfidenceLevel
└── config_loader.py            YAML config loading
```

## Autonomous System Documentation

For architecture, current state, CQS formula, decision gates, file map, and agent guide, see:
- **[docs/autonomous-system/architecture.md](../../../docs/autonomous-system/architecture.md)** — How it works now
- **[docs/autonomous-system/roadmap.md](../../../docs/autonomous-system/roadmap.md)** — History, progress, and active milestones

Use `/update-autonomous-docs` after implementing changes to keep those docs current.
