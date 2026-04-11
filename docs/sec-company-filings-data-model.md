# SEC Company And Filings Data Model

## Scope

This document models the SEC company lookup and company submissions flows that edgartools uses for:

- ticker to CIK resolution
- company metadata
- company filing metadata
- older filing pagination files
- optional current-filings feed ingestion

It is intentionally scoped to the sources used by:

- `edgar/reference/tickers.py`
- `edgar/entity/data.py`
- `edgar/entity/submissions.py`
- `edgar/current_filings.py`

It does not attempt to model XBRL facts, filing attachments, document parsing, or mutual fund-specific reference files.

## Source Inventory

- `https://www.sec.gov/files/company_tickers.json`
- `https://www.sec.gov/files/company_tickers_exchange.json`
- `https://data.sec.gov/submissions/CIK##########.json`
- `https://data.sec.gov/submissions/CIK##########-submissions-###.json`
- `https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom`

## Design Notes

- Use `BIGINT` for CIK in warehouse tables, but preserve the zero-padded raw CIK text in staging if you need exact raw replay.
- Normalize repeating arrays into child tables instead of storing pipe-delimited strings. The repo's compact `COMPANY_SCHEMA` can be recreated later as a view.
- Cast SEC `0/1` flags to `BOOLEAN`.
- Cast `filingDate`, `reportDate`, `filingFrom`, and `filingTo` to `DATE`.
- Cast `acceptanceDateTime` and current-feed `updated` to `TIMESTAMPTZ`.
- Treat empty strings as `NULL` for nullable text/date fields.
- Keep fields the raw SEC payload exposes even when the current edgartools object model drops them, notably `ownerOrg`, `lei`, `filmNumber`, `core_type`, and foreign-address detail.

## Final Data Model

### `sec_company`

| Column | Type | Notes |
|---|---|---|
| `cik` | `BIGINT` | Primary key |
| `name` | `TEXT` | Current SEC entity name |
| `entity_type` | `TEXT` | From `entityType` |
| `sic` | `INTEGER` | Nullable |
| `sic_description` | `TEXT` | From `sicDescription` |
| `category` | `TEXT` | `<br>` normalized to the string `space-pipe-space` |
| `owner_org` | `TEXT` | Present in raw submissions payloads and cassettes |
| `ein` | `TEXT` | Nullable |
| `lei` | `TEXT` | Nullable |
| `description` | `TEXT` | Nullable |
| `website` | `TEXT` | Nullable |
| `investor_website` | `TEXT` | Nullable |
| `phone` | `TEXT` | Nullable |
| `flags` | `TEXT` | Nullable |
| `fiscal_year_end` | `CHAR(4)` | `MMDD` format, nullable |
| `state_of_incorporation` | `TEXT` | Nullable |
| `state_of_incorporation_description` | `TEXT` | Nullable |
| `insider_transaction_for_owner_exists` | `BOOLEAN` | From SEC `0/1` |
| `insider_transaction_for_issuer_exists` | `BOOLEAN` | From SEC `0/1` |
| `is_company` | `BOOLEAN` | Derived from the repo's `_classify_is_individual()` logic |

### `sec_company_ticker`

One row per ticker mapping from either reference files or exploded submissions arrays.

| Column | Type | Notes |
|---|---|---|
| `cik` | `BIGINT` | Foreign key to `sec_company.cik` |
| `ticker` | `TEXT` | Raw ticker as published by SEC |
| `lookup_ticker` | `TEXT` | Uppercased ticker with `.` normalized to `-` |
| `base_ticker` | `TEXT` | Portion before first `-`; used by repo lookup fallback |
| `company_name` | `TEXT` | `title`, `name`, or exchange-file `name` depending on source |
| `exchange` | `TEXT` | Nullable |
| `source_name` | `TEXT` | `company_tickers`, `company_tickers_exchange`, or `submissions` |

Recommended key: `PRIMARY KEY (cik, ticker, source_name)`

### `sec_company_address`

| Column | Type | Notes |
|---|---|---|
| `cik` | `BIGINT` | Foreign key to `sec_company.cik` |
| `address_type` | `TEXT` | `mailing` or `business` |
| `street1` | `TEXT` | Nullable |
| `street2` | `TEXT` | Nullable |
| `city` | `TEXT` | Nullable |
| `state_or_country` | `TEXT` | Nullable |
| `state_or_country_description` | `TEXT` | Nullable |
| `zip_code` | `TEXT` | Nullable |
| `is_foreign_location` | `BOOLEAN` | Nullable |
| `foreign_state_territory` | `TEXT` | Nullable |
| `country` | `TEXT` | Nullable |
| `country_code` | `TEXT` | Nullable |

Recommended key: `PRIMARY KEY (cik, address_type)`

### `sec_company_former_name`

| Column | Type | Notes |
|---|---|---|
| `cik` | `BIGINT` | Foreign key to `sec_company.cik` |
| `ordinal` | `SMALLINT` | Array position from `formerNames[]` |
| `former_name` | `TEXT` | From `formerNames[].name` |
| `valid_from` | `DATE` | Repo trims timestamp strings to the first 10 chars |
| `valid_to` | `DATE` | Repo trims timestamp strings to the first 10 chars |

Recommended key: `PRIMARY KEY (cik, ordinal)`

### `sec_company_submission_file`

One row per older-filings pagination file listed under `filings.files`.

| Column | Type | Notes |
|---|---|---|
| `cik` | `BIGINT` | Foreign key to `sec_company.cik` |
| `file_name` | `TEXT` | Example: `CIK0000320193-submissions-001.json` |
| `file_url` | `TEXT` | Derived as `SEC_DATA_URL + '/submissions/' + file_name` |
| `filing_count` | `INTEGER` | From `filingCount` |
| `filing_from` | `DATE` | From `filingFrom` |
| `filing_to` | `DATE` | From `filingTo` |

Recommended key: `PRIMARY KEY (cik, file_name)`

### `sec_company_filing`

One row per filing in `filings.recent` plus the older pagination files merged by edgartools.

| Column | Type | Notes |
|---|---|---|
| `accession_number` | `TEXT` | Primary key |
| `cik` | `BIGINT` | Foreign key to `sec_company.cik` |
| `filing_date` | `DATE` | From `filingDate` |
| `report_date` | `DATE` | From `reportDate`, nullable |
| `acceptance_datetime` | `TIMESTAMPTZ` | Parsed from ISO timestamp with `Z` to `+00:00` |
| `act` | `TEXT` | Nullable |
| `form` | `TEXT` | Filing form |
| `core_type` | `TEXT` | Present in raw payloads; not persisted by current parser |
| `file_number` | `TEXT` | Nullable |
| `film_number` | `TEXT` | Present in raw payloads; not persisted by current parser |
| `items` | `TEXT` | Nullable |
| `size_bytes` | `BIGINT` | From `size` |
| `is_xbrl` | `BOOLEAN` | From `isXBRL` |
| `is_inline_xbrl` | `BOOLEAN` | From `isInlineXBRL` |
| `primary_document` | `TEXT` | Raw SEC filename |
| `primary_doc_description` | `TEXT` | Nullable |

### `sec_current_filing_feed`

Optional real-time cache for the current-filings Atom feed. This is separate from the company submissions JSON.

| Column | Type | Notes |
|---|---|---|
| `accession_number` | `TEXT` | Part of composite key |
| `accepted_at` | `TIMESTAMPTZ` | Parsed from Atom `updated` |
| `filing_date` | `DATE` | Parsed from Atom `summary` |
| `form` | `TEXT` | Parsed from Atom `title` |
| `company_name` | `TEXT` | Parsed from Atom `title` |
| `cik` | `BIGINT` | Parsed from Atom `title` |
| `status` | `TEXT` | Parsed from Atom `title`; repo extracts it but drops it |
| `size_text` | `TEXT` | Parsed from Atom `summary`; repo regex sees it but drops it |
| `title_raw` | `TEXT` | Raw Atom `title` |
| `summary_raw` | `TEXT` | Raw Atom `summary` |

Recommended key: `PRIMARY KEY (accession_number, accepted_at)`

## Derived View To Match The Repo's Compact Company Dataset

The repo's `COMPANY_SCHEMA` in `edgar/reference/company_dataset.py` is a compact projection, not the full raw model. Recreate it as a view:

```sql
create view vw_sec_company_dataset_compact as
select
    lpad(c.cik::text, 10, '0') as cik,
    c.name,
    c.is_company,
    c.sic,
    c.sic_description,
    string_agg(distinct t.ticker, '|' order by t.ticker) as tickers,
    string_agg(distinct t.exchange, '|' order by t.exchange) as exchanges,
    c.state_of_incorporation,
    c.state_of_incorporation_description,
    c.fiscal_year_end,
    c.entity_type,
    c.ein
from sec_company c
left join sec_company_ticker t
    on t.cik = c.cik
group by
    c.cik, c.name, c.is_company, c.sic, c.sic_description,
    c.state_of_incorporation, c.state_of_incorporation_description,
    c.fiscal_year_end, c.entity_type, c.ein;
```

## Raw To Final Mapping

### `company_tickers.json`

| Raw column | Transformation / modifications | Final table.column |
|---|---|---|
| `cik_str` | Cast to `BIGINT` for normalized storage | `sec_company_ticker.cik` |
| `ticker` | Store as-is | `sec_company_ticker.ticker` |
| `ticker` | Uppercase and replace `.` with `-` | `sec_company_ticker.lookup_ticker` |
| `ticker` | Split at first `-`; if no `-`, keep ticker unchanged | `sec_company_ticker.base_ticker` |
| `title` | Store as source company name | `sec_company_ticker.company_name` |

Notes:

- In repo code, `_get_company_tickers_raw()` converts `cik_str` to `int`.
- `get_company_cik_lookup()` adds a base-symbol lookup for tickers like `BRK-B`.
- Set `sec_company_ticker.source_name` to the literal `company_tickers` for rows loaded from this file.

### `company_tickers_exchange.json`

| Raw column | Transformation / modifications | Final table.column |
|---|---|---|
| `cik` | Cast to `BIGINT` if loaded as text | `sec_company_ticker.cik` |
| `ticker` | Store as-is | `sec_company_ticker.ticker` |
| `ticker` | Uppercase and replace `.` with `-` | `sec_company_ticker.lookup_ticker` |
| `ticker` | Split at first `-`; if no `-`, keep ticker unchanged | `sec_company_ticker.base_ticker` |
| `name` | Store as source company name | `sec_company_ticker.company_name` |
| `exchange` | Store as-is | `sec_company_ticker.exchange` |

Notes:

- Set `sec_company_ticker.source_name` to the literal `company_tickers_exchange` for rows loaded from this file.

### Submissions top-level: `CIK##########.json`

| Raw column | Transformation / modifications | Final table.column |
|---|---|---|
| `cik` | Cast to `BIGINT` | `sec_company.cik` |
| `name` | Store as-is | `sec_company.name` |
| `entityType` | Store as-is | `sec_company.entity_type` |
| `sic` | Empty string to `NULL`, else cast to `INTEGER` | `sec_company.sic` |
| `sicDescription` | Store as-is | `sec_company.sic_description` |
| `category` | Replace `<br>` with the string `space-pipe-space` | `sec_company.category` |
| `ownerOrg` | Store as-is | `sec_company.owner_org` |
| `ein` | Store as-is | `sec_company.ein` |
| `lei` | Store as-is | `sec_company.lei` |
| `description` | Store as-is | `sec_company.description` |
| `website` | Store as-is | `sec_company.website` |
| `investorWebsite` | Store as-is | `sec_company.investor_website` |
| `phone` | Store as-is | `sec_company.phone` |
| `flags` | Store as-is | `sec_company.flags` |
| `fiscalYearEnd` | Store as-is | `sec_company.fiscal_year_end` |
| `stateOfIncorporation` | Store as-is | `sec_company.state_of_incorporation` |
| `stateOfIncorporationDescription` | Store as-is | `sec_company.state_of_incorporation_description` |
| `insiderTransactionForOwnerExists` | Cast `0/1` to `BOOLEAN` | `sec_company.insider_transaction_for_owner_exists` |
| `insiderTransactionForIssuerExists` | Cast `0/1` to `BOOLEAN` | `sec_company.insider_transaction_for_issuer_exists` |
| Entire company record | Apply repo `_classify_is_individual()` and invert | `sec_company.is_company` |

### Submissions arrays: `tickers[]` and `exchanges[]`

| Raw column | Transformation / modifications | Final table.column |
|---|---|---|
| `tickers[]` | Explode array to one row per ticker | `sec_company_ticker.ticker` |
| `tickers[]` | Uppercase and replace `.` with `-` | `sec_company_ticker.lookup_ticker` |
| `tickers[]` | Split at first `-`; if no `-`, keep ticker unchanged | `sec_company_ticker.base_ticker` |
| Parent `cik` | Copy parent value to each exploded ticker row | `sec_company_ticker.cik` |
| Parent `name` | Copy parent value to each exploded ticker row | `sec_company_ticker.company_name` |
| `exchanges[]` | Align by array ordinal with `tickers[]`; if missing, leave `NULL` | `sec_company_ticker.exchange` |

Notes:

- Set `sec_company_ticker.source_name` to the literal `submissions` for rows exploded from the submissions payload.

### Submissions addresses: `addresses.mailing` and `addresses.business`

| Raw column | Transformation / modifications | Final table.column |
|---|---|---|
| `addresses.{mailing|business}.street1` | Explode into one row per address type | `sec_company_address.street1` |
| `addresses.{mailing|business}.street2` | Explode into one row per address type | `sec_company_address.street2` |
| `addresses.{mailing|business}.city` | Explode into one row per address type | `sec_company_address.city` |
| `addresses.{mailing|business}.stateOrCountry` | Rename to snake case | `sec_company_address.state_or_country` |
| `addresses.{mailing|business}.stateOrCountryDescription` | Rename to snake case | `sec_company_address.state_or_country_description` |
| `addresses.{mailing|business}.zipCode` | Rename to snake case | `sec_company_address.zip_code` |
| `addresses.{mailing|business}.isForeignLocation` | Cast `0/1` or `null` to `BOOLEAN` | `sec_company_address.is_foreign_location` |
| `addresses.{mailing|business}.foreignStateTerritory` | Rename to snake case | `sec_company_address.foreign_state_territory` |
| `addresses.{mailing|business}.country` | Store as-is | `sec_company_address.country` |
| `addresses.{mailing|business}.countryCode` | Rename to snake case | `sec_company_address.country_code` |

Notes:

- Derive `sec_company_address.address_type` from the object path segment: `mailing` or `business`.

### Submissions former names: `formerNames[]`

| Raw column | Transformation / modifications | Final table.column |
|---|---|---|
| `formerNames[].name` | Explode array to one row per former name | `sec_company_former_name.former_name` |
| `formerNames[].from` | Repo truncates ISO timestamp to first 10 chars, then cast to `DATE` | `sec_company_former_name.valid_from` |
| `formerNames[].to` | Repo truncates ISO timestamp to first 10 chars, then cast to `DATE` | `sec_company_former_name.valid_to` |

Notes:

- Set `sec_company_former_name.ordinal` from the 1-based array position of each `formerNames[]` element.

### Submissions pagination files: `filings.files[]`

| Raw column | Transformation / modifications | Final table.column |
|---|---|---|
| `filings.files[].name` | Store as-is | `sec_company_submission_file.file_name` |
| `filings.files[].name` | Prepend `SEC_DATA_URL + '/submissions/'` | `sec_company_submission_file.file_url` |
| Parent `cik` | Copy parent value to each file row | `sec_company_submission_file.cik` |
| `filings.files[].filingCount` | Cast to `INTEGER` | `sec_company_submission_file.filing_count` |
| `filings.files[].filingFrom` | Cast to `DATE` | `sec_company_submission_file.filing_from` |
| `filings.files[].filingTo` | Cast to `DATE` | `sec_company_submission_file.filing_to` |

### Submissions filing rows: `filings.recent`

| Raw column | Transformation / modifications | Final table.column |
|---|---|---|
| `accessionNumber` | Rename to snake case | `sec_company_filing.accession_number` |
| Parent `cik` | Copy parent value to each filing row | `sec_company_filing.cik` |
| `filingDate` | Parse `%Y-%m-%d` to `DATE` | `sec_company_filing.filing_date` |
| `reportDate` | Empty string to `NULL`, else cast to `DATE` | `sec_company_filing.report_date` |
| `acceptanceDateTime` | Replace trailing `Z` with `+00:00`, parse ISO string to `TIMESTAMPTZ` | `sec_company_filing.acceptance_datetime` |
| `act` | Empty string to `NULL` | `sec_company_filing.act` |
| `form` | Store as-is | `sec_company_filing.form` |
| `core_type` | Empty string to `NULL` | `sec_company_filing.core_type` |
| `fileNumber` | Empty string to `NULL` | `sec_company_filing.file_number` |
| `filmNumber` | Empty string to `NULL` | `sec_company_filing.film_number` |
| `items` | Empty string to `NULL` | `sec_company_filing.items` |
| `size` | Cast to `BIGINT` | `sec_company_filing.size_bytes` |
| `isXBRL` | Cast `0/1` to `BOOLEAN` | `sec_company_filing.is_xbrl` |
| `isInlineXBRL` | Cast `0/1` to `BOOLEAN` | `sec_company_filing.is_inline_xbrl` |
| `primaryDocument` | Store as-is | `sec_company_filing.primary_document` |
| `primaryDocDescription` | Empty string to `NULL` | `sec_company_filing.primary_doc_description` |

### Current filings Atom feed

| Raw column | Transformation / modifications | Final table.column |
|---|---|---|
| `entry.title` | Parse `"FORM - COMPANY (CIK) (STATUS)"`, extract form | `sec_current_filing_feed.form` |
| `entry.title` | Parse `"FORM - COMPANY (CIK) (STATUS)"`, extract company name | `sec_current_filing_feed.company_name` |
| `entry.title` | Parse `"FORM - COMPANY (CIK) (STATUS)"`, extract CIK and cast to `BIGINT` | `sec_current_filing_feed.cik` |
| `entry.title` | Parse `"FORM - COMPANY (CIK) (STATUS)"`, extract status | `sec_current_filing_feed.status` |
| `entry.title` | Store raw title for replay/debugging | `sec_current_filing_feed.title_raw` |
| `entry.summary` | Parse `Filed:` token to `DATE` | `sec_current_filing_feed.filing_date` |
| `entry.summary` | Parse `AccNo:` token | `sec_current_filing_feed.accession_number` |
| `entry.summary` | Parse `Size:` token; keep raw text | `sec_current_filing_feed.size_text` |
| `entry.summary` | Store raw summary for replay/debugging | `sec_current_filing_feed.summary_raw` |
| `entry.updated` | Parse ISO timestamp to `TIMESTAMPTZ` | `sec_current_filing_feed.accepted_at` |

## Implementation Crosswalk

The model above is based on the repo's actual parsing and lookup behavior:

- `edgar/reference/tickers.py`
  - loads bundled parquet or `company_tickers.json`
  - normalizes CIKs
  - builds exact and base-symbol ticker lookup dictionaries
- `edgar/entity/data.py`
  - parses submissions top-level metadata
  - truncates former-name timestamp strings to dates
  - converts `filings.recent` to a typed table
- `edgar/entity/submissions.py`
  - downloads `CIK##########.json`
  - merges older pagination files when present locally
- `edgar/current_filings.py`
  - parses the Atom feed title and summary fields

## Recommended Indexes

- `sec_company(cik)`
- `sec_company_ticker(lookup_ticker)`
- `sec_company_ticker(base_ticker)`
- `sec_company_ticker(cik, source_name)`
- `sec_company_filing(cik, acceptance_datetime desc)`
- `sec_company_filing(cik, form, acceptance_datetime desc)`
- `sec_company_filing(file_number)`
- `sec_current_filing_feed(accepted_at desc)`

## Practical Use

If the goal is "latest filings for a company", the fastest path is:

1. Resolve ticker from `sec_company_ticker.lookup_ticker` or `sec_company_ticker.base_ticker`
2. Join to `sec_company.cik`
3. Query `sec_company_filing` by `cik`
4. Sort by `acceptance_datetime desc`

That matches the repo behavior more closely than sorting only by `filing_date`.
