# Spec: Gold Star Schema (Module 6)

## Status

IN PROGRESS. gold.py dimension and fact schemas defined in feature/silver-gold-phase-a-c
worktree. Gold generators for the remaining 6 dimensions and 5 facts, plus full Snowflake
export coverage, need implementation.

## References

- Read spec-contracts.md first
- Source: specification.md lines 127-210 (Snowflake export contract), 318-351 (gold
  contract), 839-856 (gold architecture)
- Implementation: edgar_warehouse/gold.py in silver-gold-phase-a-c worktree

## Tables Owned By This Module

### Dimensions (10)

| Table                       | Description                                          |
|-----------------------------|------------------------------------------------------|
| gold.dim_date               | Calendar spine; date_key = YYYYMMDD int              |
| gold.dim_company            | Issuer/registrant dimension; one row per CIK         |
| gold.dim_form               | Filing form type and family                          |
| gold.dim_filing             | One row per accession number; bridges company + form |
| gold.dim_party              | Conformed actor dimension (persons, entities)        |
| gold.dim_security           | Security/instrument dimension for ownership filings  |
| gold.dim_ownership_txn_type | Ownership transaction codes (acquisition/disposal)   |
| gold.dim_geography          | State/country reference for addresses and offices    |
| gold.dim_disclosure_category| Adviser disclosure categories from Form ADV          |
| gold.dim_private_fund       | Private fund reference from Form ADV Schedule D      |

### Facts (6)

| Table                              | Description                                         |
|------------------------------------|-----------------------------------------------------|
| gold.fact_filing_activity          | One row per filing event; joins company, form, date |
| gold.fact_ownership_transaction    | One row per Form 3/4/5 reported transaction         |
| gold.fact_ownership_holding_snapshot | Period-end holdings from Form 4/5               |
| gold.fact_adv_office               | Adviser office records from Form ADV Part 1A        |
| gold.fact_adv_disclosure           | Adviser disclosure items from Form ADV              |
| gold.fact_adv_private_fund         | Private fund records from Form ADV Schedule D       |

## Surrogate Key Rules

Source: specification.md lines 345-350.

1. Deterministic int64 keys via SHA-256 of the natural key string, truncated to int64.
   Function: `_det_key(value: str) -> int` in gold.py.
2. Type 2 SCD: business key + attribute-hash change detection; effective_from /
   effective_to columns bracket validity. No SCD-2 columns exist yet in any dimension.
3. Fact rebuilds are idempotent by natural key (delete-then-reinsert pattern).
4. dim_company shortcut: company_key = cik directly (CIK is a stable SEC integer).
5. Legacy gold.sec_* names are compatibility views only, not canonical storage.

## Dimensions

### dim_date

- Grain: one row per calendar day
- Natural key: full_date (date)
- Surrogate key: date_key = YYYYMMDD integer (no hash needed; unique by construction)
- Range: derived from MIN/MAX filing_date in sec_company_filing
- Attributes: year, month, day, quarter, day_of_week, is_weekend
- Status: IMPLEMENTED in gold.py

### dim_company

- Grain: one row per CIK (Type 1; no history tracking yet)
- Natural key: cik (int64)
- Surrogate key: company_key = cik
- Source silver table: sec_company
- Attributes: entity_name, entity_type, sic, sic_description, state_of_incorporation,
  fiscal_year_end, last_sync_run_id
- Status: IMPLEMENTED in gold.py

### dim_form

- Grain: one row per distinct form string
- Natural key: form (string)
- Surrogate key: form_key = _det_key(form)
- Source silver table: sec_company_filing (DISTINCT form values)
- Attributes: form, form_family (10-K, 10-Q, 8-K, ownership, proxy, other)
- Status: IMPLEMENTED in gold.py

### dim_filing

- Grain: one row per accession number
- Natural key: accession_number
- Surrogate key: filing_key = _det_key(accession_number)
- Source silver table: sec_company_filing
- FK references: company_key -> dim_company, form_key -> dim_form, date_key -> dim_date
- Attributes: accession_number, cik, form, filing_date, report_date, is_xbrl, size
- Status: IMPLEMENTED in gold.py

### dim_party

- Grain: one row per reporting person/entity in ownership filings
- Natural key: CIK or name-based hash for non-CIK parties
- Note: conformed actor dimension shared across ownership and ADV facts
- Status: PENDING - schema not defined; no source silver data yet

### dim_security

- Grain: one row per security/instrument; natural key: issuer_cik + security_type
- Source: ownership filing silver tables (pending)
- Status: PENDING

### dim_ownership_txn_type

- Grain: one row per transaction code (A/D codes from Forms 3/4/5)
- Source: static reference data
- Status: PENDING

### dim_geography

- Grain: one row per state/country code; source: reference data + ADV addresses
- Status: PENDING

### dim_disclosure_category

- Grain: one row per ADV disclosure category; source: Form ADV Part 1A section 11
- Status: PENDING

### dim_private_fund

- Grain: one row per private fund; natural key: adviser_cik + fund_id
- Source: Form ADV Schedule D (pending)
- Status: PENDING

## Facts

### fact_filing_activity

- Grain: one row per filing event (one per accession number)
- Natural key: accession_number
- Fact key: _det_key(accession_number)
- FK dimensions: company_key, filing_key, date_key, form_key
- Source silver table: sec_company_filing
- Degenerate dimensions carried: accession_number, cik, form, filing_date, report_date,
  is_xbrl
- Status: IMPLEMENTED in gold.py

### fact_ownership_transaction

- Grain: one row per reported ownership transaction from Forms 3/4/5
- Natural key: accession_number + sequence_number
- FK dimensions: company_key, date_key, form_key, party_key, security_key,
  ownership_txn_type_key
- Source silver tables: ownership transaction tables (pending silver implementation)
- Status: PENDING - schema not defined in gold.py

### fact_ownership_holding_snapshot

- Grain: one row per period-end holding position
- Natural key: accession_number + security_key + holding_type
- FK dimensions: company_key, date_key, party_key, security_key
- Source silver tables: ownership holding tables (pending silver implementation)
- Status: PENDING - schema not defined in gold.py

### fact_adv_office

- Grain: one row per adviser office record from Form ADV Part 1A
- Natural key: adviser_cik + office_sequence
- FK dimensions: company_key, date_key, geography_key
- Source silver tables: ADV silver tables (pending silver implementation)
- Status: PENDING - schema not defined in gold.py

### fact_adv_disclosure

- Grain: one row per disclosure item from Form ADV Part 1A section 11
- Natural key: adviser_cik + disclosure_category_code + as_of_date
- FK dimensions: company_key, date_key, disclosure_category_key
- Source silver tables: ADV silver tables (pending silver implementation)
- Status: PENDING - schema not defined in gold.py

### fact_adv_private_fund

- Grain: one row per private fund per filing
- Natural key: adviser_cik + fund_id + filing_date
- FK dimensions: company_key, date_key, private_fund_key
- Source silver tables: ADV Schedule D tables (pending silver implementation)
- Status: PENDING - schema not defined in gold.py

## Snowflake Export Contract

Source: specification.md lines 127-210.

AWS writes one Parquet package per business table per run into a dedicated Snowflake
export bucket. The Snowflake sync task reads the export bucket and calls the single
public wrapper: CALL EDGARTOOLS_GOLD.REFRESH_AFTER_LOAD(workflow_name, run_id).

Export bucket path pattern:
  {table_path}/business_date={business_date}/run_id={run_id}/{table_name}.parquet

The 8 SNOWFLAKE_EXPORT_TABLES from runtime.py (key = Snowflake table name,
value = export path prefix):

| Key                 | Path Prefix          | Maps To Gold Table             |
|---------------------|----------------------|--------------------------------|
| COMPANY             | company              | dim_company                    |
| FILING_ACTIVITY     | filing_activity      | fact_filing_activity           |
| OWNERSHIP_ACTIVITY  | ownership_activity   | fact_ownership_transaction     |
| OWNERSHIP_HOLDINGS  | ownership_holdings   | fact_ownership_holding_snapshot|
| ADVISER_OFFICES     | adviser_offices      | fact_adv_office                |
| ADVISER_DISCLOSURES | adviser_disclosures  | fact_adv_disclosure            |
| PRIVATE_FUNDS       | private_funds        | fact_adv_private_fund          |
| FILING_DETAIL       | filing_detail        | dim_filing                     |

Current gold.py write_gold_to_snowflake_export only handles COMPANY and FILING_ACTIVITY.
The remaining 6 export paths need wiring once the corresponding gold tables are built.

Snowflake objects that consume these packages:
- database: EDGARTOOLS_DEV / EDGARTOOLS_PROD
- schemas: EDGARTOOLS_SOURCE (staging), EDGARTOOLS_GOLD (curated business tables)
- status view: EDGARTOOLS_GOLD_STATUS

## Implementation Plan

### Already in gold.py (silver-gold-phase-a-c worktree)

- Surrogate key helper: _det_key() using SHA-256 truncated to int64
- Form family derivation: _form_family()
- PyArrow schemas: _DIM_COMPANY_SCHEMA, _DIM_FORM_SCHEMA, _DIM_DATE_SCHEMA,
  _DIM_FILING_SCHEMA, _FACT_FILING_ACTIVITY_SCHEMA
- Build functions: _build_dim_company, _build_dim_form, _build_dim_date,
  _build_dim_filing, _build_fact_filing_activity
- Public API: build_gold(), write_gold_to_storage(), write_gold_to_snowflake_export()
- Snowflake export: COMPANY and FILING_ACTIVITY only

### Pending implementation

1. Schemas and build functions for 6 remaining dimensions:
   dim_party, dim_security, dim_ownership_txn_type, dim_geography,
   dim_disclosure_category, dim_private_fund

2. Schemas and build functions for 5 remaining facts:
   fact_ownership_transaction, fact_ownership_holding_snapshot,
   fact_adv_office, fact_adv_disclosure, fact_adv_private_fund

3. SCD-2 version columns (effective_from, effective_to, is_current) on dimensions
   that require history tracking (dim_company, dim_party at minimum)

4. Expand write_gold_to_snowflake_export to cover all 8 SNOWFLAKE_EXPORT_TABLES

5. Wire build_gold() into runtime.py RunContext so gold is built and written on
   every bronze_capture+ mode run

6. runtime.py: add gold write step to the step-by-step run orchestration

## Acceptance Criteria

1. dim_company row count equals sec_company row count in the silver DuckDB database
2. fact_filing_activity row count equals sec_company_filing row count in silver
3. Every fact_filing_activity row has a matching company_key in dim_company
4. Every fact_filing_activity row has a matching date_key in dim_date
5. All surrogate keys are unique within each dimension table (no collisions)
6. build_gold() is idempotent: calling it twice with the same silver state returns
   identical tables
7. write_gold_to_snowflake_export produces one Parquet file per SNOWFLAKE_EXPORT_TABLES
   entry per run under the correct path pattern
8. write_gold_to_storage produces one Parquet file per table under
   gold/{table_name}/run_id={run_id}/{table_name}.parquet
9. Empty silver database returns empty Arrow tables with correct schemas (no crash)

## Verification

Test files to create:

- tests/test_warehouse_gold.py (NEW)
  - test_dim_company_matches_sec_company: row count equality, no null company_key
  - test_fact_filing_activity_matches_sec_company_filing: row count equality
  - test_dim_date_covers_filing_range: min/max date_key spans all filing dates
  - test_surrogate_key_uniqueness: all dim keys unique in each dimension table
  - test_build_gold_idempotent: two calls return identical tables
  - test_build_gold_empty_silver: returns empty tables with correct schemas
  - test_snowflake_export_paths: verify path pattern and file presence for 8 tables

- tests/test_warehouse_e2e_smoke.py (NEW)
  - test_e2e_bronze_to_gold: full pipeline from bronze capture through gold write,
    assert at least 1 row in dim_company and fact_filing_activity
  - test_e2e_snowflake_export_written: assert all 8 export packages written to
    export bucket after a successful run
