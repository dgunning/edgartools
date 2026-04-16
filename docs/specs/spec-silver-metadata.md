# Spec: Silver Metadata Pipeline (Module 2)

## Status

COMPLETE -- silver.py, loaders.py, runtime.py, cli.py all implemented.
Use this spec for verification only.

## References

- Read spec-contracts.md first (shared types and storage paths)
- Source: specification.md lines 418-735, 857-871, 1119-1136

## Tables Owned By This Module

| Table | Description |
|---|---|
| `sec_tracked_universe` | Canonical list of CIKs under active tracking |
| `sec_company` | Core company metadata from submissions JSON |
| `sec_company_address` | Business and mailing addresses per CIK |
| `sec_company_former_name` | Historical name changes with date and ordinal |
| `sec_company_ticker` | Exchange-listed ticker symbols per CIK |
| `sec_company_submission_file` | Pagination manifest files for full filing history |
| `sec_company_filing` | Full filing index (one row per accession) |
| `sec_current_filing_feed` | Latest-ingested daily feed snapshot |

Source: specification.md lines 857-871

## Load Interfaces

All 7 function signatures. Return types are dataclasses defined in runtime.py.

### `submissions_orchestrator`

```python
def submissions_orchestrator(
    cik: int,
    load_mode: str,
    recent_limit: int | None = None,
    force: bool = False,
) -> SubmissionsScopeResult:
    ...
```

- Inputs: one `CIK##########.json`, `load_mode` in {bootstrap_full, bootstrap_recent_10, daily_incremental, targeted_resync}
- Behavior: fetch raw submissions JSON, call all company-scope sub-loaders, merge to silver only after all stage steps succeed

### `bootstrap_full`

```python
def bootstrap_full(
    cik_list: list[int] | None = None,
    tracking_status_filter: str = "active",
    include_reference_refresh: bool = True,
    artifact_policy: str = "all_attachments",
    parser_policy: str = "configured_forms",
    force: bool = False,
) -> BootstrapResult:
    ...
```

- Inputs: tracked universe (optionally narrowed by cik_list), SEC reference files, all `CIK##########.json` and pagination files
- Outputs: full company metadata, full filing history, all artifacts, text and parser outputs

### `bootstrap_recent_10`

```python
def bootstrap_recent_10(
    cik_list: list[int] | None = None,
    tracking_status_filter: str = "active",
    include_reference_refresh: bool = True,
    recent_limit: int = 10,
    artifact_policy: str = "all_attachments",
    parser_policy: str = "configured_forms",
    force: bool = False,
) -> BootstrapResult:
    ...
```

- Same pipeline as bootstrap_full; only narrower filing selection (top `recent_limit` from `filings.recent`)
- Does not fetch pagination files

### `daily_incremental`

```python
def daily_incremental(
    start_date: date | None = None,
    end_date: date | None = None,
    include_reference_refresh: bool = False,
    tracking_status_filter: str = "active",
    force: bool = False,
) -> IncrementalResult:
    ...
```

- Inputs: `sec_tracked_universe`, `sec_daily_index_checkpoint`, SEC `form.YYYYMMDD.idx`
- If start_date omitted: start from next expected business day after last successful checkpoint
- If end_date omitted: use latest eligible finalized business date
- Calendar: Monday-Friday excluding US federal holidays; stop on first unresolved expected date

### `load_daily_form_index_for_date`

```python
def load_daily_form_index_for_date(
    target_date: date,
    force: bool = False,
) -> DailyIndexLoadResult:
    ...
```

- Inputs: one business date, SEC daily form-index file for that date
- Skips non-business dates; writes one checkpoint row; stages one `stg_daily_index_filing` dataset; derives impacted CIK and accession work sets

### `catch_up_daily_form_index`

```python
def catch_up_daily_form_index(
    end_date: date | None = None,
    force: bool = False,
) -> DailyIndexCatchupResult:
    ...
```

- Inputs: daily checkpoint state, expected business-day sequence up to end_date
- Loads dates ascending; does not skip gaps; stops on first unresolved expected date

### `targeted_resync`

```python
def targeted_resync(
    scope_type: str,
    scope_key: str,
    include_artifacts: bool = True,
    include_text: bool = True,
    include_parsers: bool = True,
    force: bool = True,
) -> ResyncResult:
    ...
```

- Valid scope_type values: `"reference"` (scope_key = reference file name), `"cik"` (scope_key = CIK integer string), `"accession"` (scope_key = accession number)
- Force-fetches from SEC, preserves bronze history, rebuilds only affected silver and gold scope

### `full_reconcile`

```python
def full_reconcile(
    cik_list: list[int] | None = None,
    sample_limit: int | None = None,
    include_reference_refresh: bool = True,
    auto_heal: bool = True,
) -> ReconcileResult:
    ...
```

- Inputs: tracked universe or explicit cik_list, live SEC reference and submissions sources, current silver state
- Detects drift, writes `sec_reconcile_finding`; if auto_heal=True launches targeted_resync for mismatches

Source: specification.md lines 418-624

---

## Company Submissions Loader Contract

### Sub-loaders (called by submissions_orchestrator)

```
stage_company_loader(payload, cik, sync_run_id, raw_object_id, load_mode)
stage_address_loader(payload, cik, sync_run_id, raw_object_id, load_mode)
stage_former_name_loader(payload, cik, sync_run_id, raw_object_id, load_mode)
stage_manifest_loader(payload, cik, sync_run_id, raw_object_id, load_mode)
stage_recent_filing_loader(payload, cik, sync_run_id, raw_object_id, load_mode, recent_limit=None)
```

### Common Stage Columns

`sync_run_id`, `raw_object_id`, `source_name`, `source_url`, `cik`, `load_mode`, `staged_at`, `record_hash`

### Idempotency Rules

- Stage ALL company-scope rowsets before any silver merge
- If any stage step fails, do not partially merge silver for that company scope
- All loaders must be idempotent (re-running produces same silver state)

### Silver Merge Order

1. `sec_company`
2. `sec_company_address`
3. `sec_company_former_name`
4. `sec_company_submission_file`
5. `sec_company_filing`

Source: specification.md lines 625-667

---

## Numbered Runbooks

### bootstrap_recent_10

1. Refresh SEC reference files if configured.
2. Resolve tracked-universe scope (optionally narrow by cik_list).
3. Fetch `CIK##########.json` for each target company.
4. Stage company, address, former-name, manifest, and recent-filing rows.
5. Select top 10 recent filings by `acceptanceDateTime desc, accession_number desc`.
6. Merge company-scope silver rows.
7. Fetch all attachments for selected filings.
8. Extract text.
9. Run parsers.
10. Build affected gold dimensions and facts.
11. Update checkpoints and sync state.

### bootstrap_full

1. Refresh SEC reference files if configured.
2. Resolve tracked-universe scope (optionally narrow by cik_list).
3. Fetch `CIK##########.json` for each target company.
4. Stage company, address, former-name, manifest, and recent-filing rows.
5. Merge company-scope silver rows.
6. Fetch and stage each listed pagination file.
7. Merge full filing history.
8. Fetch all attachments for included filings.
9. Extract text.
10. Run parsers.
11. Build affected gold dimensions and facts.
12. Update checkpoints and sync state.

### daily_incremental

1. Determine expected business-date range from checkpoint state.
2. Load missing or requested `form.YYYYMMDD.idx` files in ascending date order.
3. Stage `stg_daily_index_filing`.
4. Filter staged rows to tracked universe.
5. Derive impacted CIK and accession work sets.
6. Refresh submissions JSON for impacted CIKs.
7. Fetch artifacts for impacted accessions.
8. Extract text.
9. Run parsers.
10. Rebuild only affected gold rows.
11. Update date checkpoints and company sync state.

### targeted_resync

1. Resolve scope (reference / cik / accession).
2. Force fetch from SEC.
3. Rebuild affected stage rows.
4. Rebuild affected silver rows.
5. Refetch artifacts and rerun text and parsers if configured.
6. Rebuild affected gold rows.
7. Mark findings and checkpoints resolved only after success.

### full_reconcile

1. Refresh references if configured.
2. Snapshot tracked universe.
3. Fetch live submissions truth for target scope.
4. Build reconcile staging rowsets.
5. Compare live truth to silver state.
6. Write `sec_reconcile_finding`.
7. Group mismatches into resync scopes.
8. Launch targeted_resync if auto_heal=True.
9. Recompare healed scopes.
10. Persist reconciliation summary.

Source: specification.md lines 668-735

---

## Load Modes Summary

| Mode | Filing Scope | Discovery Source |
|---|---|---|
| `bootstrap_full` | All filings in history | CIK JSON + pagination files |
| `bootstrap_recent_10` | Latest 10 per company | CIK JSON `filings.recent` only |
| `daily_incremental` | New filings since last checkpoint | `form.YYYYMMDD.idx` |
| `targeted_resync` | One reference / CIK / accession | Force re-fetch from SEC |
| `full_reconcile` | Tracked universe or cik_list | Live SEC truth vs silver |

bootstrap_full and bootstrap_recent_10 share the same metadata, artifact, text, parser, silver, and gold pipelines -- filing scope is the only difference.

Source: specification.md lines 1119-1136

---

## Verification

### Files to Check

- `/edgar_warehouse/silver.py` -- DDL for all 8 owned tables (lines 19-200)
- `/edgar_warehouse/loaders.py` -- 5 sub-loader functions
- `/edgar_warehouse/runtime.py` -- BootstrapResult, IncrementalResult, ResyncResult, ReconcileResult, SubmissionsScopeResult
- `/edgar_warehouse/cli.py` -- CLI entry points for each load mode

### Key Assertions

- `sec_company` row count equals tracked universe size after bootstrap
- `sec_company_filing` row count per CIK matches `filings.recent` (recent_10) or full history (bootstrap_full)
- Re-running any loader on same input produces identical silver row hashes (idempotency)
- A failed sub-loader stage leaves silver rows for that CIK unchanged
- `sec_daily_index_checkpoint` has one row per business date; no gaps in completed range
- `targeted_resync(scope_type="cik", ...)` preserves bronze history and updates silver timestamp
