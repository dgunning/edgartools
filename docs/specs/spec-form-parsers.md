# Spec: Form-Family Parsers (Module 5)

## Status

NOT STARTED. BLOCKED on Module 4 (spec-artifact-text-parser.md) — parsers require
filing artifacts to exist in bronze before they can fetch and extract document content.
Do not begin implementation until `sec_artifact` rows exist for the target accession
numbers and the artifact fetch pipeline is operational.

## References

- Read spec-contracts.md first (bronze/silver/gold contracts, incremental rules)
- Read spec-artifact-text-parser.md (blocking dependency — Module 4)
- Source: specification.md lines 950-1048 (silver table schemas)
- Source: specification.md lines 318-351 (gold contract — canonical fact tables)

---

## Tables Owned By This Module

### Silver tables (7 total)

| Table | Form family | Rows per filing |
|---|---|---|
| `sec_ownership_reporting_owner` | 3, 4, 5 | One row per owner |
| `sec_ownership_non_derivative_txn` | 3, 4, 5 | One row per non-derivative transaction |
| `sec_ownership_derivative_txn` | 3, 4, 5 | One row per derivative transaction |
| `sec_adv_filing` | ADV family | One row per filing |
| `sec_adv_office` | ADV family | One row per office location |
| `sec_adv_disclosure_event` | ADV family | One row per disclosure event |
| `sec_adv_private_fund` | ADV family | One row per private fund |

### Gold facts powered by these tables (5 total)

| Gold fact | Source silver tables |
|---|---|
| `gold.fact_ownership_transaction` | non_derivative_txn + derivative_txn + reporting_owner |
| `gold.fact_ownership_holding_snapshot` | non_derivative_txn + derivative_txn + reporting_owner |
| `gold.fact_adv_office` | sec_adv_office |
| `gold.fact_adv_disclosure` | sec_adv_disclosure_event |
| `gold.fact_adv_private_fund` | sec_adv_private_fund |

Supporting gold dimensions: `dim_party`, `dim_security`, `dim_ownership_txn_type`,
`dim_geography`, `dim_disclosure_category`, `dim_private_fund`.

---

## Ownership Forms: 3, 4, 5

Form 3 reports initial ownership. Form 4 reports changes in ownership. Form 5 is an
annual report of changes not previously reported. All three share the same XML schema
and are parsed by the same ownership parser.

### sec_ownership_reporting_owner Schema

| Column | Type | Notes |
|---|---|---|
| `accession_number` | `TEXT` | Foreign key to sec_filing |
| `owner_index` | `SMALLINT` | 1-based owner ordinal within the filing |
| `owner_cik` | `BIGINT` | Nullable |
| `owner_name` | `TEXT` | |
| `is_director` | `BOOLEAN` | Nullable |
| `is_officer` | `BOOLEAN` | Nullable |
| `is_ten_percent_owner` | `BOOLEAN` | Nullable |
| `is_other` | `BOOLEAN` | Nullable |
| `officer_title` | `TEXT` | Nullable |

Primary key: `(accession_number, owner_index)`

### sec_ownership_non_derivative_txn Schema

| Column | Type | Notes |
|---|---|---|
| `accession_number` | `TEXT` | Foreign key to sec_filing |
| `owner_index` | `SMALLINT` | Foreign key component to reporting_owner |
| `txn_index` | `SMALLINT` | Row ordinal within the filing |
| `security_title` | `TEXT` | |
| `transaction_date` | `DATE` | Nullable |
| `transaction_code` | `TEXT` | |
| `transaction_shares` | `NUMERIC(28,8)` | Nullable |
| `transaction_price` | `NUMERIC(28,8)` | Nullable |
| `acquired_disposed_code` | `TEXT` | `A` or `D`, nullable |
| `shares_owned_after` | `NUMERIC(28,8)` | Nullable |
| `ownership_nature` | `TEXT` | Nullable |
| `ownership_direct_indirect` | `TEXT` | Nullable |

Primary key: `(accession_number, owner_index, txn_index)`

### sec_ownership_derivative_txn Schema

Same 12 columns as sec_ownership_non_derivative_txn plus five derivative-specific columns:

| Column | Type | Notes |
|---|---|---|
| `accession_number` | `TEXT` | Foreign key to sec_filing |
| `owner_index` | `SMALLINT` | Foreign key component to reporting_owner |
| `txn_index` | `SMALLINT` | Row ordinal within the filing |
| `security_title` | `TEXT` | |
| `transaction_date` | `DATE` | Nullable |
| `transaction_code` | `TEXT` | |
| `transaction_shares` | `NUMERIC(28,8)` | Nullable |
| `transaction_price` | `NUMERIC(28,8)` | Nullable |
| `acquired_disposed_code` | `TEXT` | `A` or `D`, nullable |
| `shares_owned_after` | `NUMERIC(28,8)` | Nullable |
| `ownership_nature` | `TEXT` | Nullable |
| `ownership_direct_indirect` | `TEXT` | Nullable |
| `conversion_or_exercise_price` | `NUMERIC(28,8)` | Nullable |
| `exercise_date` | `DATE` | Nullable |
| `expiration_date` | `DATE` | Nullable |
| `underlying_security_title` | `TEXT` | Nullable |
| `underlying_security_shares` | `NUMERIC(28,8)` | Nullable |

Primary key: `(accession_number, owner_index, txn_index)`

---

## ADV Forms

ADV forms report investment adviser registrations and amendments. The parser handles
all ADV-family variants. Source format varies: some filings are XML, others are HTML
or plain text. The `source_format` column captures what was actually parsed.

### sec_adv_filing Schema

| Column | Type | Notes |
|---|---|---|
| `accession_number` | `TEXT` | Primary key and foreign key to sec_filing |
| `cik` | `BIGINT` | |
| `form` | `TEXT` | `ADV`, `ADV-E`, `ADV-H`, `ADV-NR`, `ADV-W` |
| `adviser_name` | `TEXT` | Nullable |
| `sec_file_number` | `TEXT` | Nullable |
| `crd_number` | `TEXT` | Nullable |
| `effective_date` | `DATE` | Nullable |
| `filing_status` | `TEXT` | Nullable |
| `source_format` | `TEXT` | `xml`, `html`, `text`, `pdf`, `unknown` |

### sec_adv_office Schema

| Column | Type | Notes |
|---|---|---|
| `accession_number` | `TEXT` | Foreign key to sec_adv_filing |
| `office_index` | `SMALLINT` | 1-based ordinal |
| `office_name` | `TEXT` | Nullable |
| `city` | `TEXT` | Nullable |
| `state_or_country` | `TEXT` | Nullable |
| `country` | `TEXT` | Nullable |
| `is_headquarters` | `BOOLEAN` | Nullable |

Primary key: `(accession_number, office_index)`

### sec_adv_disclosure_event Schema

| Column | Type | Notes |
|---|---|---|
| `accession_number` | `TEXT` | Foreign key to sec_adv_filing |
| `event_index` | `SMALLINT` | 1-based ordinal |
| `disclosure_category` | `TEXT` | |
| `event_date` | `DATE` | Nullable |
| `is_reported` | `BOOLEAN` | Nullable |
| `description` | `TEXT` | Nullable |

Primary key: `(accession_number, event_index)`

### sec_adv_private_fund Schema

| Column | Type | Notes |
|---|---|---|
| `accession_number` | `TEXT` | Foreign key to sec_adv_filing |
| `fund_index` | `SMALLINT` | 1-based ordinal |
| `fund_name` | `TEXT` | Nullable |
| `fund_type` | `TEXT` | Nullable |
| `jurisdiction` | `TEXT` | Nullable |
| `aum_amount` | `NUMERIC(28,2)` | Nullable |

Primary key: `(accession_number, fund_index)`

---

## Parser Architecture

### Files To Create

```
edgar_warehouse/parsers/__init__.py      -- parser dispatch by form family
edgar_warehouse/parsers/ownership.py    -- Form 3/4/5 XML parser
edgar_warehouse/parsers/adv.py          -- ADV family parser
```

### Parser Dispatch Rules

| Form type codes | Parser module |
|---|---|
| `3`, `3/A`, `4`, `4/A`, `5`, `5/A` | `parsers/ownership.py` |
| `ADV`, `ADV/A`, `ADV-E`, `ADV-E/A`, `ADV-H`, `ADV-H/A`, `ADV-NR`, `ADV-W`, `ADV-W/A` | `parsers/adv.py` |

`__init__.py` exposes a `get_parser(form_type)` function that returns the appropriate
parser callable. Unknown form types raise `ValueError`.

### Incremental Rules

Rerun a parser when either of the following changes:
1. The `raw_hash` of the source artifact row in `sec_artifact` changes (content changed)
2. The `parser_version` constant at the top of the parser module is incremented

Parser version is a plain integer stored as a column in the silver tables. When the
parser version is bumped, rows with the old version are treated as stale and replaced
on the next run.

### Input Contract

Each parser receives a dict with:
- `accession_number` (str)
- `artifact_content` (bytes or str) — fetched from `sec_artifact.raw_content`
- `source_format` (str) — derived from `sec_artifact.content_type`

Parsers return a dict keyed by table name with a list of row dicts. The dispatch layer
writes rows to DuckDB using upsert-on-natural-key semantics.

---

## Acceptance Criteria

### Ownership (Forms 3/4/5)

1. Given a known Form 4 accession number, `ownership.py` produces at least one row in
   `sec_ownership_reporting_owner` and at least one row in
   `sec_ownership_non_derivative_txn`.
2. Owner CIK in the parsed row matches the issuer CIK cross-referenced from
   `sec_filing`.
3. Re-running the parser with identical input does not create duplicate rows.

### ADV Forms

1. Given a known ADV or ADV/A accession number, `adv.py` produces at least one row in
   `sec_adv_filing` with a non-null `adviser_name`.
2. `source_format` is populated with one of the five allowed values
   (`xml`, `html`, `text`, `pdf`, `unknown`), never NULL.
3. Re-running the parser with identical input does not create duplicate rows.

---

## Verification

Test files to create:

```
tests/test_ownership_parsing.py    -- unit tests against fixture XML documents
tests/test_adv_parsing.py          -- unit tests against fixture ADV documents
tests/test_ownership_hosting.py    -- integration: end-to-end ownership pipeline
tests/test_adv_hosting.py          -- integration: end-to-end ADV pipeline
```

Unit tests use local fixture files (no network). Integration tests require the bronze
artifact pipeline (Module 4) to be operational.

Key assertions for unit tests:
- Assert specific column values from a known fixture, not just `is not None`
- Assert row count equals expected transaction count for the fixture filing
- Assert that a malformed or empty XML document raises a parser-level exception with
  a message that includes the accession number
