# EdgarTools Warehouse Spec Modules

## Purpose

This directory decomposes `specification.md` (the normative master spec) into seven
implementation-focused modules plus one shared contracts file. The decomposition exists
so that multiple subagents can implement different pipeline stages in parallel without
reading the full 1800-line master spec. All normative rules remain in `specification.md`
-- if a module file and the master spec disagree, the master spec wins.

## The 8 Modules

| ID | File | Lines | Status | Depends On |
|----|------|-------|--------|------------|
| M0 | spec-contracts.md | 234 | Complete | None |
| M1 | spec-infrastructure.md | 273 | Complete (verify-only) | M0 |
| M2 | spec-silver-metadata.md | 300 | Complete (verify-only) | M0 |
| M3 | spec-daily-index.md | 241 | Partial (bronze done, silver wiring pending) | M0, M2 |
| M4 | spec-artifact-text-parser.md | 266 | Not started | M0, M2 |
| M5 | spec-form-parsers.md | 260 | Not started (blocked on M4) | M0, M4 |
| M6 | spec-gold-star-schema.md | 283 | In progress | M0, M2 |
| M7 | spec-sync-control.md | 247 | Not started | M0, M2 |

## Dependency Graph

```
M0: spec-contracts.md  (no deps -- read first for every task)
  |
  +-- M1: spec-infrastructure.md   (verify-only; platform wiring)
  |
  +-- M2: spec-silver-metadata.md  (verify-only; silver.py DDL and loaders)
        |
        +-- M3: spec-daily-index.md        (bronze + silver daily index pipeline)
        |
        +-- M4: spec-artifact-text-parser.md  (artifact fetch + text extraction)
        |         |
        |         +-- M5: spec-form-parsers.md  (10-K/10-Q/8-K structured parsing)
        |
        +-- M6: spec-gold-star-schema.md   (gold dimension and fact tables)
        |
        +-- M7: spec-sync-control.md       (reconcile.py, targeted-resync, full-reconcile)
```

## Parallel Execution Waves

```
Wave 0  (prerequisite -- must be read before all other work)
  M0: spec-contracts.md

Wave 1  (verify-only; both are already complete)
  M1: Infrastructure          M2: Silver Metadata

Wave 2  (max parallelism -- 4 independent tracks, all unblock after Wave 1)
  M3: Daily Index             M4: Artifact/Text Parser
  M6: Gold Star Schema        M7: Sync Control

Wave 3  (after M4 completes)
  M5: Form Parsers

Wave 4  (integration smoke test)
  End-to-end run through ingest -> silver -> gold
  Minimum required: M2 + M3 + M6 complete
```

## How To Use A Spec Module

For each implementation task the subagent reads exactly two spec files:

1. `spec-contracts.md` (~234 lines) -- shared types, storage paths, naming conventions
2. The target module spec (~240-300 lines) -- tables, functions, acceptance criteria

Then it reads only the source files named inside the module spec.

Total context load: ~475-535 lines of spec + target source files. This fits comfortably
within a single subagent context window and avoids loading the full master spec.

## Parallel Safety Rules

Each module owns a distinct set of database tables and source locations. Subagents
working in parallel must not touch each other's tables or files. The rules are:

1. **Table ownership**: Each module spec lists the exact table names it owns. No module
   writes to another module's tables.

2. **Function namespacing**: New functions added to `runtime.py` or `silver.py` must use
   the module's prefix (e.g. `daily_index_*`, `artifact_*`, `gold_*`, `sync_*`).

3. **No cross-module wiring during implementation**: Each module implements its own
   end-to-end slice. Integration calls between modules (e.g. M3 triggering M4) are added
   only after both modules are individually complete and verified.

4. **schema.sql is append-only during parallel work**: Each module appends its DDL block
   to `schema.sql` in a clearly marked section. No module edits another module's DDL.

5. **cli.py commands are additive**: Each module adds its own CLI sub-commands without
   modifying existing commands defined by other modules.

## Source of Truth

`specification.md` (project root `docs/specification.md`) is the single normative
source. These spec modules are implementation-focused extracts: they restate the relevant
sections in task-ready form, add acceptance criteria, and list exact file locations.
If any detail in a module file conflicts with `specification.md`, treat
`specification.md` as correct and flag the discrepancy.
