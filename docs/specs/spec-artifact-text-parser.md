# Spec: Artifact, Text & Parser Pipeline (Module 4)

## Status

NOT STARTED. Two new files must be created:
- `edgar_warehouse/artifacts.py` -- filing artifact fetch and attachment registration
- `edgar_warehouse/text_extraction.py` -- text extraction pipeline

DDL for all four owned tables already exists in `edgar_warehouse/silver.py` (lines 146-199).
Merge methods and runtime wiring are absent and must be added.

## References

- Read `docs/specs/spec-contracts.md` first for shared data contracts and runtime conventions
- Source: `specification.md` lines 873-949, 1049-1066, 1370-1421, 1509-1528
- Live DDL: `edgar_warehouse/silver.py` lines 146-199
- Runtime dispatch: `edgar_warehouse/runtime.py` lines 560-620

---

## Tables Owned By This Module

| Table | Purpose |
|---|---|
| `sec_raw_object` | One row per fetched raw artifact stored to object storage |
| `sec_filing_attachment` | One row per document listed on a filing index page |
| `sec_filing_text` | One row per normalized text extraction of a primary document |
| `sec_parse_run` | Tracks parser execution status and version for every dispatch |

---

## sec_raw_object Schema

One row per fetched raw artifact. Primary key: `raw_object_id`.

| Column | Type | Notes |
|---|---|---|
| `raw_object_id` | TEXT | Primary key |
| `source_type` | TEXT | `reference`, `submissions`, `pagination`, `filing_index`, `filing_document`, `attachment`, `current_feed` |
| `cik` | BIGINT | Nullable for non-company assets |
| `accession_number` | TEXT | Nullable |
| `form` | TEXT | Nullable |
| `source_url` | TEXT | Original SEC URL |
| `storage_path` | TEXT | Object storage path |
| `content_type` | TEXT | MIME type if known |
| `content_encoding` | TEXT | Nullable |
| `byte_size` | BIGINT | Nullable |
| `sha256` | TEXT | Content hash |
| `fetched_at` | TIMESTAMPTZ | Fetch timestamp |
| `http_status` | INTEGER | Expected `200` for successful persisted fetches |
| `source_last_modified` | TIMESTAMPTZ | Nullable |
| `source_etag` | TEXT | Nullable |

---

## sec_filing_attachment Schema

One row per document listed on the filing page or attachment index.
Primary key: `(accession_number, document_name)`.

| Column | Type | Notes |
|---|---|---|
| `accession_number` | TEXT | Foreign key to `sec_company_filing` |
| `sequence_number` | TEXT | SEC sequence field, nullable |
| `document_name` | TEXT | Raw filename |
| `document_type` | TEXT | Example: `EX-10.1`, `GRAPHIC`, `XML`, `4` |
| `document_description` | TEXT | Nullable |
| `document_url` | TEXT | SEC archive URL |
| `is_primary` | BOOLEAN | True if this is the primary document |
| `raw_object_id` | TEXT | Foreign key to `sec_raw_object` once downloaded; null before fetch |
| `last_sync_run_id` | TEXT | Added in live DDL; tracks which sync run last wrote this row |

Note: the live DDL in `silver.py` adds `last_sync_run_id TEXT` not present in the spec table.
Treat it as live-authoritative; do not remove it.

---

## sec_filing_text Schema

One row per normalized text extraction. Primary key: `(accession_number, text_version)`.

| Column | Type | Notes |
|---|---|---|
| `accession_number` | TEXT | Foreign key |
| `text_version` | TEXT | Extraction pipeline version string (e.g. `v1`) |
| `source_document_name` | TEXT | Usually the primary document filename |
| `text_storage_path` | TEXT | Object storage path for extracted text |
| `text_sha256` | TEXT | Hash of normalized text |
| `char_count` | INTEGER | Text length |
| `extracted_at` | TIMESTAMPTZ | Extraction time |

---

## sec_parse_run Schema

Tracks parser execution and reprocessing. Primary key: `parse_run_id`.

| Column | Type | Notes |
|---|---|---|
| `parse_run_id` | TEXT | Primary key |
| `accession_number` | TEXT | Nullable for batch jobs |
| `parser_name` | TEXT | Example: `ownership_v1`, `adv_v1`, `generic_text_v1` |
| `parser_version` | TEXT | Semantic version or git SHA |
| `target_form_family` | TEXT | `ownership`, `adv`, `generic`, `xbrl`, etc. |
| `status` | TEXT | `queued`, `running`, `succeeded`, `failed`, `skipped` |
| `started_at` | TIMESTAMPTZ | Nullable |
| `completed_at` | TIMESTAMPTZ | Nullable |
| `error_code` | TEXT | Nullable |
| `error_message` | TEXT | Nullable |
| `rows_written` | INTEGER | Nullable -- present in spec but absent from live DDL; must be added in migration |

Note: `rows_written` appears in the spec schema but is missing from the current `silver.py` DDL.
An `ALTER TABLE sec_parse_run ADD COLUMN IF NOT EXISTS rows_written INTEGER;` migration is required.

---

## Workflow 5: Filing Artifact Fetch

**Trigger:** for selected form families; for all filings when full archive hosting is desired;
on analyst demand via `targeted-resync` with `scope_type = accession`.

**Steps:**
1. Fetch the filing homepage / index page for the accession number
2. Enumerate all attachments (primary document + exhibits)
3. Persist index HTML and each document to bronze object storage
4. Populate `sec_filing_attachment` rows (upsert on primary key)
5. Mark each persisted artifact in `sec_raw_object`

**Incremental rule:** fetch artifacts only for accession numbers that are new, changed,
explicitly resynced, or within a configured backfill policy. Skip if `raw_object_id` is
already populated and the `sha256` matches.

**Runtime wiring required:** `runtime.py targeted-resync` currently raises
`WarehouseRuntimeError` for `scope_type = accession` (line 606). Artifact fetch must
add a handler branch for `scope_type = "accession"` that invokes `artifacts.fetch_filing_artifacts`.

---

## Workflow 6: Text Extraction

**Trigger:** after the primary document for an accession is present in `sec_raw_object`.

**Steps:**
1. Identify the primary document from `sec_filing_attachment` where `is_primary = true`
2. Load raw bytes from object storage via `storage_path`
3. Convert HTML, XML, TXT, or SGML to normalized plain text
4. Persist normalized text to silver object storage
5. Insert or replace a row in `sec_filing_text`

**Incremental rule:** re-extract only when the source document `sha256` in `sec_raw_object`
changes, or when the `text_version` pipeline version string advances.

---

## Workflow 7: Parser Execution

**Trigger:** based on form family and parser availability; runs after Workflow 6 completes
for the relevant accession.

**Steps:**
1. Select filings by form family (e.g. `ownership`, `adv`, `xbrl`, `generic`)
2. Dispatch the appropriate named parser with the raw bytes and extracted text
3. Write results to gold tables (form-specific or generic)
4. Record a `sec_parse_run` row with status, timing, and `rows_written`

**Incremental rule:** rerun only when the filing `raw_object_id` sha256 changes, or when
`parser_version` advances relative to the last `sec_parse_run` row for that
`(accession_number, parser_name)` pair with `status = succeeded`.

---

## Generic Approach For Unparsed Forms

For any form without a dedicated parser, the following 7-step fallback applies:

1. Persist the filing metadata in `sec_company_filing`
2. Persist all raw artifacts in `sec_raw_object`
3. Register all documents in `sec_filing_attachment`
4. Extract normalized text into `sec_filing_text`
5. Run a generic parser that extracts:
   - title
   - section headers
   - tables
   - key-value candidates
6. Store parser execution in `sec_parse_run`
7. Add a form-specific gold parser only if analysis needs justify it

This ensures no data is blocked on parser availability.

---

## Reprocessing Strategy

### Parser change procedure

1. Increment `parser_version` in the parser module
2. Select affected filings by `form` / `target_form_family`
3. Rerun from bronze raw (do not re-download SEC artifacts)
4. Write new gold outputs alongside old outputs (new version column or new rows)
5. Rebuild derived marts and views after gold writes complete

### Source data change procedure

1. Force a fresh download for the affected source scope
2. Persist the new raw source to bronze as a new immutable snapshot
3. Update current-state silver rows for affected keys
4. Rerun downstream text extraction and parser jobs only where the upstream raw sha256 changed
5. Retain old bronze snapshots and old gold outputs for auditability

---

## New Files To Create

### `edgar_warehouse/artifacts.py`

Owns all logic for Workflows 5:

- `fetch_filing_artifacts(context, accession_number)` -- fetches index, enumerates
  attachments, persists to bronze, writes `sec_raw_object` and `sec_filing_attachment` rows
- `merge_raw_object(conn, row)` -- upsert helper for `sec_raw_object`
- `merge_filing_attachment(conn, row)` -- upsert helper for `sec_filing_attachment`
- Must accept the standard `SyncContext` / `WarehouseContext` passed throughout runtime.py

### `edgar_warehouse/text_extraction.py`

Owns all logic for Workflow 6:

- `extract_text_for_accession(context, accession_number, text_version)` -- loads primary
  document, converts to normalized text, persists to silver, writes `sec_filing_text`
- `merge_filing_text(conn, row)` -- upsert helper for `sec_filing_text`
- Must support HTML, XML, TXT, and SGML source documents
- Reuse or delegate to `edgar` library HTML/text extraction utilities where available

Parser dispatch (Workflow 7) may live in a separate `parsers/` subpackage or in a
`edgar_warehouse/parse_runner.py` file; that is deferred to the parser module spec.

---

## Acceptance Criteria

1. For a known accession number (e.g. Apple 10-K `0000320193-23-000106`):
   - After Workflow 5, `sec_filing_attachment` contains at least one row with `is_primary = true`
   - `sec_raw_object` contains a row with `http_status = 200` and a non-null `sha256`
2. After Workflow 6 on the same accession:
   - `sec_filing_text` contains exactly one row with `char_count > 0`
   - `text_sha256` matches the sha256 of the stored text file
3. Rerunning Workflow 6 with the same `text_version` and unchanged source produces no new row
   (idempotent; existing row is retained unchanged)
4. After Workflow 7 with a generic parser:
   - `sec_parse_run` contains one row with `status = succeeded` and `rows_written >= 0`
5. `targeted-resync` with `scope_type = accession` no longer raises `WarehouseRuntimeError`

---

## Verification

Test files to create under `tests/warehouse/`:

| File | Covers |
|---|---|
| `test_filing_artifact_fetch.py` | Workflow 5 steps, idempotency, `sec_raw_object` and `sec_filing_attachment` assertions |
| `test_text_extraction_pipeline.py` | Workflow 6 HTML/XML/TXT paths, `sec_filing_text` row assertions, version-gate skipping |
| `test_parse_run_tracking.py` | Workflow 7 parse run recording, status transitions, reprocessing version bump |

All tests that touch the database must use an in-memory DuckDB fixture consistent with the
DDL in `silver.py`. Network calls must be covered by VCR cassettes.
