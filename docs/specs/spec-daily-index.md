# Spec: Daily Index & Checkpoint (Module 3)

## Status

PARTIALLY IMPLEMENTED. Bronze daily index fetch, checkpoint upsert, and catch-up loop
exist in runtime.py. Silver DDL and checkpoint read/write methods exist in silver.py.
The `stg_daily_index_filing` parse-and-stage step (`merge_daily_index_filings`) exists
in silver.py but is NOT yet called from runtime.py after fetching the raw index bytes.
The `distinct_cik_count` and `distinct_accession_count` columns are defined and wired
in the upsert SQL but are never populated by the catch-up path (values remain NULL).

## References

- Read spec-contracts.md first for shared conventions
- Source: specification.md lines 352-417, 480-550, 1282-1298
- Code: edgar_warehouse/runtime.py, edgar_warehouse/silver.py lines 100-180, 515-655

## Tables Owned By This Module

| Table | Description |
|---|---|
| `stg_daily_index_filing` | One row per filing line from `form.YYYYMMDD.idx`; staging layer for downstream CIK/accession work-set derivation |
| `sec_daily_index_checkpoint` | One row per expected business date; tracks fetch status and content metrics |

## Canonical Source

URL pattern:

```
https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{quarter}/form.YYYYMMDD.idx
```

Timing and business-day rules:

- Daily indexes are updated nightly starting about 10:00 p.m. America/New_York
- The build usually completes within a few hours
- Business date `D` is eligible for canonical loading at 06:00 America/New_York on `D + 1`
- Expected business days are Monday-Friday excluding US federal holidays
- The current Atom feed is optional acceleration only, not authoritative daily discovery

## stg_daily_index_filing Schema

Primary key: `(business_date, accession_number)`

| Column | Type | Notes |
|---|---|---|
| `sync_run_id` | `TEXT` | Generated |
| `raw_object_id` | `TEXT` | Generated |
| `source_name` | `TEXT` | Fixed `daily_form_index` |
| `source_url` | `TEXT` | Exact SEC URL |
| `business_date` | `DATE` | Date represented by the file |
| `source_year` | `SMALLINT` | Derived from `business_date` |
| `source_quarter` | `SMALLINT` | Derived from `business_date` |
| `row_ordinal` | `INTEGER` | 1-based line order after header |
| `form` | `TEXT` | SEC raw field |
| `company_name` | `TEXT` | SEC raw field |
| `cik` | `BIGINT` | SEC raw field |
| `filing_date` | `DATE` | SEC raw field |
| `file_name` | `TEXT` | SEC raw field |
| `accession_number` | `TEXT` | Derived from `file_name` |
| `filing_txt_url` | `TEXT` | Derived archive URL |
| `record_hash` | `TEXT` | Row hash |
| `staged_at` | `TIMESTAMPTZ` | Generated |

## sec_daily_index_checkpoint Schema

Primary key: `business_date`

| Column | Type | Notes |
|---|---|---|
| `business_date` | `DATE` | Primary key |
| `source_name` | `TEXT` | Fixed `daily_form_index` |
| `source_key` | `TEXT` | `date:YYYY-MM-DD` |
| `source_url` | `TEXT` | Exact SEC URL |
| `expected_available_at` | `TIMESTAMPTZ` | 06:00 America/New_York on next calendar day |
| `first_attempt_at` | `TIMESTAMPTZ` | Nullable |
| `last_attempt_at` | `TIMESTAMPTZ` | Nullable |
| `attempt_count` | `INTEGER` | |
| `raw_object_id` | `TEXT` | Nullable |
| `last_sha256` | `TEXT` | Nullable |
| `row_count` | `INTEGER` | Nullable |
| `distinct_cik_count` | `INTEGER` | Nullable |
| `distinct_accession_count` | `INTEGER` | Nullable |
| `status` | `TEXT` | See status values below |
| `error_message` | `TEXT` | Nullable |
| `finalized_at` | `TIMESTAMPTZ` | Nullable |
| `last_success_at` | `TIMESTAMPTZ` | Nullable |

### Checkpoint Status Values

| Status | Meaning |
|---|---|
| `pending` | Default; date not yet attempted |
| `running` | Fetch in progress |
| `waiting_for_publish` | Date is a business day but file not yet available |
| `skipped_non_business_day` | Date falls outside Monday-Friday or on a US federal holiday |
| `succeeded` | File fetched and staged successfully |
| `failed_retryable` | Fetch failed; eligible for retry |
| `failed_terminal` | Fetch failed; not retryable |

## Function Signatures

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

- If `start_date` is omitted, start from the next expected business day after the last
  successful checkpoint
- If `end_date` is omitted, use the latest eligible finalized business date
- Stop on first unresolved expected business date

```python
def load_daily_form_index_for_date(
    target_date: date,
    force: bool = False,
) -> DailyIndexLoadResult:
    ...
```

- Skip non-business dates
- Write one checkpoint row per business date
- Stage one `stg_daily_index_filing` dataset for that date
- Derive impacted CIK and accession work sets

```python
def catch_up_daily_form_index(
    end_date: date | None = None,
    force: bool = False,
) -> DailyIndexCatchupResult:
    ...
```

- Load dates in ascending order
- Do not skip gaps
- Stop on first unresolved expected date

## Workflow 1A: Daily Index Discovery

Trigger: `daily_incremental`

1. Determine the expected business-date range from `sec_daily_index_checkpoint`.
2. Load missing or requested daily `form.YYYYMMDD.idx` files in ascending date order.
3. Persist each raw file to bronze and update `sec_daily_index_checkpoint`.
4. Parse rows into `stg_daily_index_filing`.
5. Filter staged rows to the tracked universe by `cik`.
6. Derive impacted CIK and accession work sets.
7. Stop on the first unresolved expected business date.
8. Use the impacted CIK and accession sets to drive downstream submissions refresh
   and artifact fetch.

## Implementation Notes

### What exists in runtime.py

- `_capture_daily_index_file`: downloads the raw `.idx` bytes from SEC and writes a
  bronze object; returns `(write_record, [cik, ...])` — the CIK list comes from
  `_extract_impacted_ciks_from_daily_index` which parses the raw bytes
- `_build_daily_index_url`: constructs the canonical URL from a `date`
- `_capture_catch_up_daily_form_index`: iterates business days from last successful
  checkpoint up to `end_date`; calls `_capture_daily_index_file` per date; calls
  `db.upsert_daily_index_checkpoint` for both success and `failed_retryable` outcomes;
  skips non-business days and already-succeeded dates
- Command dispatch wiring exists for `load-daily-form-index-for-date` and
  `catch-up-daily-form-index`; the daily-incremental path inside `_capture_bronze_raw`
  also calls `upsert_daily_index_checkpoint` per date

### What exists in silver.py

- DDL for both `stg_daily_index_filing` and `sec_daily_index_checkpoint` (lines 105-144)
- `merge_daily_index_filings(rows, sync_run_id)`: upserts parsed rows into
  `stg_daily_index_filing`; exists and is complete
- `upsert_daily_index_checkpoint(row)`: full insert-or-update with attempt counter
- `get_daily_index_checkpoint(business_date)`: single-row lookup
- `get_last_successful_checkpoint_date()`: returns most recent succeeded date
- `get_pending_checkpoint_dates(up_to_date)`: returns pending/failed_retryable dates

### What is NOT yet wired

- `merge_daily_index_filings` is defined but never called from runtime.py; raw bytes
  are fetched and bronze-written, but rows are not yet parsed and staged into
  `stg_daily_index_filing`
- `distinct_cik_count` and `distinct_accession_count` are never populated in the
  catch-up or incremental checkpoint upsert calls (sent as None)
- `finalized_at` is never set in any current upsert path
- `first_attempt_at` is never set (only `last_attempt_at` is written)
- `waiting_for_publish` and `skipped_non_business_day` status values are defined in the
  spec but not emitted by the current runtime

## Acceptance Criteria

1. For any given business date `D`, after `load_daily_form_index_for_date(D)`:
   - `sec_daily_index_checkpoint` has exactly one row with `business_date = D` and
     `status = 'succeeded'`
   - `stg_daily_index_filing` contains at least one row with `business_date = D`
   - `row_count` in the checkpoint matches the count of rows in `stg_daily_index_filing`
     for that date

2. For a non-business date, `load_daily_form_index_for_date` sets
   `status = 'skipped_non_business_day'` and writes no `stg_daily_index_filing` rows.

3. `catch_up_daily_form_index(end_date=D)` processes all un-succeeded business dates up
   to `D` in ascending order and stops at the first failure without skipping ahead.

4. `distinct_cik_count` and `distinct_accession_count` in the checkpoint row match the
   actual distinct counts in `stg_daily_index_filing` for that date.

5. `first_attempt_at` is set on the first attempt and not overwritten on retries.

6. A date that is already `succeeded` is not re-fetched unless `force=True`.

## Verification

Files to inspect:

- `edgar_warehouse/runtime.py` -- `_capture_daily_index_file`,
  `_capture_catch_up_daily_form_index`, `_capture_bronze_raw` (daily-incremental branch)
- `edgar_warehouse/silver.py` -- `merge_daily_index_filings`,
  `upsert_daily_index_checkpoint`, `get_last_successful_checkpoint_date`

Test file: `tests/test_storage_sec_hosting.py`

Key assertions to add:

```python
# After load_daily_form_index_for_date for a known date with real data:
checkpoint = db.get_daily_index_checkpoint("2024-01-02")
assert checkpoint["status"] == "succeeded"
assert checkpoint["row_count"] > 0
assert checkpoint["distinct_cik_count"] > 0

filings = db.get_daily_index_filings("2024-01-02")
assert len(filings) == checkpoint["row_count"]
assert all(r["source_name"] == "daily_form_index" for r in filings)
```
