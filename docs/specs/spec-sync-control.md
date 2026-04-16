# Spec: Sync Control & Reconciliation (Module 7)

## Status

NOT STARTED. New file `edgar_warehouse/reconcile.py` must be created. Sync control table
DDL must be added to `edgar_warehouse/silver.py`. `targeted-resync` and `full-reconcile`
in `runtime.py` need real implementation replacing current stubs.

## References

- Read `docs/specs/spec-contracts.md` first
- Source: `specification.md` lines 551-599, 1137-1242, 1245-1354, 1423-1466

## Tables Owned By This Module

| Table | Purpose |
|---|---|
| `sec_sync_run` | One row per job run; tracks status, row counts, errors |
| `sec_source_checkpoint` | Latest successful checkpoint per source object or partition |
| `sec_company_sync_state` | Per-CIK lifecycle, freshness, and pagination completion state |
| `sec_reconcile_finding` | Persisted mismatch rows written during full reconciliation |

## sec_sync_run Schema

| Column | Type | Notes |
|---|---|---|
| `sync_run_id` | `TEXT` | Primary key |
| `sync_mode` | `TEXT` | `bootstrap`, `incremental`, `resync`, `reconcile` |
| `scope_type` | `TEXT` | `reference`, `submissions`, `pagination`, `current_feed`, `artifact_fetch`, `text`, `parser` |
| `scope_key` | `TEXT` | Nullable; e.g. `cik:320193`, `accession:0001140361-26-013192` |
| `started_at` | `TIMESTAMPTZ` | |
| `completed_at` | `TIMESTAMPTZ` | Nullable |
| `status` | `TEXT` | `queued`, `running`, `succeeded`, `failed`, `partial`, `skipped` |
| `rows_inserted` | `INTEGER` | Nullable |
| `rows_updated` | `INTEGER` | Nullable |
| `rows_deleted` | `INTEGER` | Nullable |
| `rows_skipped` | `INTEGER` | Nullable |
| `error_message` | `TEXT` | Nullable |

## sec_source_checkpoint Schema

Primary key: `(source_name, source_key)`

| Column | Type | Notes |
|---|---|---|
| `source_name` | `TEXT` | e.g. `company_tickers`, `submissions_main`, `submissions_pagination`, `current_feed` |
| `source_key` | `TEXT` | e.g. `global`, `cik:320193`, `file:CIK0000320193-submissions-001.json` |
| `raw_object_id` | `TEXT` | Latest successful bronze snapshot |
| `last_success_at` | `TIMESTAMPTZ` | |
| `last_sha256` | `TEXT` | Nullable |
| `last_etag` | `TEXT` | Nullable |
| `last_modified_at` | `TIMESTAMPTZ` | Nullable |
| `last_acceptance_datetime_seen` | `TIMESTAMPTZ` | Nullable |
| `last_accession_number_seen` | `TEXT` | Nullable |

## sec_company_sync_state Schema

Primary key: `cik`

| Column | Type | Notes |
|---|---|---|
| `cik` | `BIGINT` | Primary key |
| `tracking_status` | `TEXT` | `active`, `paused`, `bootstrap_pending`, `historical_complete`, `error` |
| `bootstrap_completed_at` | `TIMESTAMPTZ` | Nullable |
| `last_main_sync_at` | `TIMESTAMPTZ` | Nullable |
| `last_main_raw_object_id` | `TEXT` | Nullable |
| `last_main_sha256` | `TEXT` | Nullable |
| `latest_filing_date_seen` | `DATE` | Nullable |
| `latest_acceptance_datetime_seen` | `TIMESTAMPTZ` | Nullable |
| `pagination_files_expected` | `INTEGER` | Nullable |
| `pagination_files_loaded` | `INTEGER` | Nullable |
| `pagination_completed_at` | `TIMESTAMPTZ` | Nullable |
| `next_sync_after` | `TIMESTAMPTZ` | Nullable |
| `last_error_message` | `TEXT` | Nullable |

## sec_reconcile_finding Schema

| Column | Type | Notes |
|---|---|---|
| `reconcile_run_id` | `TEXT` | Parent run id |
| `cik` | `BIGINT` | |
| `scope_type` | `TEXT` | `reference`, `cik`, `accession` |
| `object_type` | `TEXT` | `company`, `address`, `former_name`, `manifest`, `filing` |
| `object_key` | `TEXT` | Object identifier inside the scope |
| `drift_type` | `TEXT` | Specific mismatch type |
| `expected_value_hash` | `TEXT` | SEC truth hash |
| `actual_value_hash` | `TEXT` | Silver hash |
| `severity` | `TEXT` | `high`, `medium`, `low` |
| `recommended_action` | `TEXT` | `reference_resync`, `cik_resync`, `accession_resync`, `manual_review` |
| `status` | `TEXT` | `detected`, `queued_for_resync`, `resolved`, `unresolved`, `suppressed` |
| `detected_at` | `TIMESTAMPTZ` | |
| `resolved_at` | `TIMESTAMPTZ` | Nullable |
| `resync_run_id` | `TEXT` | Nullable |

## Function Signatures

```python
def targeted_resync(
    scope_type: str,           # "reference", "cik", or "accession"
    scope_key: str,            # e.g. "company_tickers_exchange", "320193", "0001140361-26-013192"
    include_artifacts: bool = True,
    include_text: bool = True,
    include_parsers: bool = True,
    force: bool = True,
) -> ResyncResult:
    ...

def full_reconcile(
    cik_list: list[int] | None = None,
    sample_limit: int | None = None,
    include_reference_refresh: bool = True,
    auto_heal: bool = True,
) -> ReconcileResult:
    ...
```

`targeted_resync` forces a fresh SEC download, preserves bronze history, and rebuilds only
affected silver and gold scope.

`full_reconcile` detects drift across the tracked universe, writes `sec_reconcile_finding`,
and if `auto_heal=True` launches targeted resync for each mismatch.

## Workflow 0: Initial Bootstrap

Frequency: once per environment; repeated when a new CIK universe is onboarded.

1. Run reference sync (Workflow 1) first; persist both reference snapshots to bronze.
2. Determine the bootstrap CIK universe.
3. Insert or update `sec_company_sync_state` with `tracking_status = 'bootstrap_pending'`.
4. Fetch `CIK##########.json` for each target CIK.
5. Persist raw submissions JSON to bronze; write `sec_source_checkpoint`.
6. Upsert `sec_company`, `sec_company_address`, `sec_company_former_name`, `sec_company_submission_file`, and recent rows in `sec_company_filing`.
7. Compare `filings.files` to `sec_company_submission_file`; enqueue missing pagination files.
8. Fetch every missing pagination file; upsert older filing rows.
9. Mark `pagination_completed_at` and `bootstrap_completed_at` only after all pagination files loaded successfully.
10. Enqueue artifact fetch, text extraction, and parsing per configured form families and retention windows.

## Workflow 1: Reference Sync

Frequency: daily.

1. Download `company_tickers.json`.
2. Download `company_tickers_exchange.json`.
3. Persist both raw files to bronze; compute hashes.
4. Compare to `sec_source_checkpoint`.
5. If neither changed, record a skipped `sec_sync_run` and stop.
6. If either changed, replace current-state slice of `sec_company_ticker` for that source snapshot.
7. Add newly discovered CIKs to `sec_company_sync_state`.
8. Do not delete historical bronze snapshots; only replace silver current-state rows.

## Workflow 2: Company Submissions Refresh

Triggers: `bootstrap_full`, `bootstrap_recent_10`, `daily_incremental`, `targeted_resync`.

1. Resolve target CIKs from load mode (explicit list, tracked universe, daily index impact, or resync scope).
2. Download `CIK##########.json`.
3. Persist raw JSON to bronze; update `sec_source_checkpoint`.
4. If hash, ETag, and effective latest acceptance timestamp unchanged: record skipped run, update `last_main_sync_at`, stop.
5. If changed, upsert `sec_company`, `sec_company_address`, `sec_company_former_name`, `sec_company_submission_file`, `sec_company_filing` (recent rows).
6. Detect new or changed filings by new accession numbers or changed mutable columns.
7. Enqueue downstream artifact fetch, text extraction, and parsing only for those accessions.
8. Compare pagination manifest to `sec_company_submission_file`; enqueue only missing or changed files.
9. Update `sec_company_sync_state`: `last_main_sync_at`, `last_main_raw_object_id`, `last_main_sha256`, `latest_filing_date_seen`, `latest_acceptance_datetime_seen`, `pagination_files_expected`, `next_sync_after`.

## Workflow 3: Pagination Backfill

Trigger: when `sec_company_submission_file` contains new files.

1. Download `CIK##########-submissions-###.json`.
2. Persist raw JSON to bronze; update `sec_source_checkpoint`.
3. If pagination file hash unchanged, skip reparsing.
4. Parse filing rows from the pagination file.
5. Upsert into `sec_company_filing` on `accession_number`.
6. Increment `pagination_files_loaded` for the CIK on success.
7. Mark `pagination_completed_at` when `pagination_files_loaded == pagination_files_expected`.
8. If a previously known pagination file is no longer in the manifest, keep the bronze snapshot but treat the refreshed manifest as current-state only after a successful full manifest refresh for that CIK.

## Workflow 8: Targeted Resync

Triggers: manual operator request, failed or partial load recovery, suspected SEC correction.

1. Select scope: reference source, one CIK, or one accession number.
2. Force a fresh SEC download even if stored checkpoints match.
3. Persist the new raw snapshot to bronze.
4. Rebuild affected silver rows from the fresh authoritative source.
5. Requeue artifact fetch, text extraction, and parsing only for affected accessions.
6. Preserve all previous bronze snapshots and parser outputs.
7. Update checkpoints and sync state only after resync completes successfully.

## Workflow 9: Full Reconciliation

Triggers: scheduled monthly or quarterly run; after a known SEC schema or content change.

1. Rerun reference sync against live SEC sources.
2. Rerun main submissions sync for the full tracked CIK universe or a sampled cohort.
3. Build reconcile staging rowsets for company metadata, addresses, former names, manifest, and filings.
4. Compare staged live SEC truth to silver current state; write `sec_reconcile_finding`.
5. Respect `history_mode`: `recent_only` compares metadata and recent filings only; `full_history` compares full manifest and filing set too.
6. Heal drift via Workflow 8: metadata drift -> CIK resync; manifest drift -> CIK resync with manifest refresh; one isolated filing drift -> accession resync; multiple filing drifts or any manifest drift -> CIK resync.
7. Produce persisted results from `sec_sync_run` and `sec_reconcile_finding`.

## Current State of runtime.py (What Needs Fixing)

`targeted-resync` in bronze_capture mode:
- `scope_type="reference"`: returns empty writes (no-op, incomplete)
- `scope_type="cik"`: calls `_capture_submissions_scope` with `include_pagination=True` (works)
- `scope_type="accession"`: raises `WarehouseRuntimeError` with "does not yet support accession scope"

`full-reconcile` in bronze_capture mode:
- Calls `_capture_submissions_scope` for the given cik_list only; no reconcile comparison or `sec_reconcile_finding` writes exist anywhere in the codebase.

Neither command writes to any of the four sync control tables. All four tables are absent from `silver.py`.

## New Files To Create

`edgar_warehouse/reconcile.py` — entry points:
- `run_reference_resync(context, scope_key)` -> writes bronze, updates `sec_source_checkpoint`
- `run_cik_resync(context, cik)` -> bronze + silver for one CIK including pagination
- `run_accession_resync(context, accession_number)` -> bronze + silver for one accession
- `build_reconcile_findings(context, cik_list, run_id)` -> compare SEC truth to silver, return rows
- `write_reconcile_findings(db, rows)` -> insert into `sec_reconcile_finding`
- `heal_findings(context, findings)` -> dispatch targeted resync per finding

## Acceptance Criteria

- `sec_sync_run`, `sec_source_checkpoint`, `sec_company_sync_state`, `sec_reconcile_finding` tables exist in the silver DuckDB database after `SilverDatabase` is created.
- Every `run_command` call for `targeted-resync` and `full-reconcile` inserts a row into `sec_sync_run` with final status `succeeded` or `failed`.
- `targeted-resync` with `scope_type="reference"` downloads and checkpoints both reference files.
- `targeted-resync` with `scope_type="accession"` rebuilds the single accession row in `sec_company_filing` without modifying other rows for that CIK.
- `full-reconcile` with `auto_heal=False` writes `sec_reconcile_finding` rows without modifying silver data.
- `full-reconcile` with `auto_heal=True` calls targeted resync for each `detected` finding and updates finding status to `queued_for_resync` then `resolved`.
- A company with `tracking_status='bootstrap_pending'` after Workflow 0 completes must have `bootstrap_completed_at` set and `tracking_status='active'`.
- After Workflow 3, `pagination_files_loaded == pagination_files_expected` for all fully loaded CIKs and `pagination_completed_at` is non-null.

## Verification

Test file: `tests/test_warehouse_reconcile.py` (NEW)

Key test cases:
- `test_sync_control_tables_exist`: assert all four tables present after `SilverDatabase()` init.
- `test_targeted_resync_reference`: run targeted-resync for `company_tickers_exchange`; assert `sec_source_checkpoint` row written.
- `test_targeted_resync_cik`: run for CIK 320193; assert `sec_company_sync_state` updated and `sec_sync_run` row with status `succeeded`.
- `test_targeted_resync_accession`: run for a known accession; assert single `sec_company_filing` row updated.
- `test_full_reconcile_no_heal`: run with `auto_heal=False`; assert `sec_reconcile_finding` rows written with status `detected`.
- `test_full_reconcile_auto_heal`: run with `auto_heal=True`; assert findings transition to `resolved`.
- `test_bootstrap_sets_completed_at`: after bootstrap workflow, CIK has `bootstrap_completed_at` non-null.
- `test_pagination_completion_flag`: after pagination backfill, `pagination_completed_at` set when counts match.
