# SEC Hosting Verification Plan

This document turns [specification.md](C:/work/projects/edgartools/specification.md) into a concrete verification plan for EdgarTools.

It follows the repo rules in [verification-guide.md](C:/work/projects/edgartools/docs/verification-guide.md) and [verification-constitution.md](C:/work/projects/edgartools/docs/verification-constitution.md):

- assert specific values, not just existence
- make recorded verification the default for network-dependent behavior
- add live smoke verification for upstream drift
- add silence checks for bad or missing input
- treat documented examples as runnable verification

## Definition Of Done

The SEC hosting implementation is not done until it has:

- one ground-truth assertion for each major workflow in the spec
- one verified documented example in `tests/test_documented_examples.py`
- one silence check for each ingestion/parser boundary
- recorded verification for every network-backed workflow
- at least one live smoke test for each SEC endpoint family
- regression coverage for each bug found during implementation

## Proposed Verification Files

These are the test modules that should be added for the implementation.

| Test file | Tier | Markers | Purpose |
|---|---|---|---|
| `tests/test_reference_sync.py` | 0 / 1 | `fast`, selective `vcr` if live reference download is exercised | Verify ticker normalization, base ticker lookup, CIK casting, and exchange mapping |
| `tests/test_company_submissions_sync.py` | 1 | `network`, `vcr` | Verify `sec_company`, `sec_company_address`, `sec_company_former_name`, `sec_company_submission_file`, and `sec_company_filing` from `CIK##########.json` |
| `tests/test_company_pagination_backfill.py` | 1 | `network`, `vcr` | Verify `CIK##########-submissions-###.json` merge behavior and accession deduplication |
| `tests/test_current_filings_sync.py` | 1 | `network`, `vcr` | Verify current-feed ingestion into `sec_current_filing_feed`, including status and size extraction |
| `tests/test_storage_sec_hosting.py` | 0 / 1 | explicit `fast` and `network`, `vcr` where needed | Verify bronze object registration, hashes, storage path determinism, and idempotent raw ingest |
| `tests/test_filing_artifact_fetch.py` | 1 | `network`, `vcr` | Verify filing index fetch, attachment discovery, primary-document detection, and raw-object linkage |
| `tests/test_text_extraction_pipeline.py` | 0 / 1 | `fast` | Verify deterministic text extraction from HTML, XML, TXT, and SGML fixtures |
| `tests/test_ownership_hosting.py` | 0 / 1 | explicit `fast`; selective `network`, `vcr` | Verify ownership parser outputs into `sec_ownership_reporting_owner`, `sec_ownership_non_derivative_txn`, and `sec_ownership_derivative_txn` |
| `tests/test_adv_hosting.py` | 1 | explicit `network`, `vcr` | Verify ADV raw capture, source-format detection, and gold-table writes |
| `tests/test_parse_run_tracking.py` | 0 | `fast` | Verify `sec_parse_run` lifecycle, versioning, failure capture, and rerun behavior |
| `tests/test_documented_examples.py` | 0 / 1 | match example type | Verify the documented hosting/query examples promised by the spec |
| `tests/issues/regression/test_issue_<id>_<slug>.py` | 0 / 1 | `regression` plus explicit marker | Lock in each bug found during implementation |

Notes:

- `tests/test_reference_sync.py` will auto-match the repo's fast pattern because of `test_reference`.
- `tests/test_company_submissions_sync.py` and `tests/test_company_pagination_backfill.py` will auto-match network because of `test_company`.
- `tests/test_adv_hosting.py`, `tests/test_storage_sec_hosting.py`, and `tests/test_parse_run_tracking.py` should use explicit markers because the filename alone will not be auto-classified reliably.

## Verification By Spec Workflow

| Spec workflow | Required verification |
|---|---|
| Reference Sync | exact ticker and exchange mapping, lookup normalization, duplicate/idempotent upsert checks |
| Company Submissions Sync | exact company metadata values, former-name counts, pagination-file counts, filing metadata row integrity |
| Pagination Backfill | merged filing counts, accession-number uniqueness, stable ordering after merge |
| Filing Artifact Fetch | attachment count, primary-document filename, URL construction, missing attachment failure path |
| Text Extraction | deterministic normalized text hash and character count, expected heading presence |
| Parser Execution | successful parse tracking, failed parse tracking, rerun/version behavior |
| Ownership Parser | exact owner names, transaction dates, codes, shares, prices, and direct/indirect ownership values |
| ADV Parser | exact adviser identity fields, office rows, disclosure rows, source-format detection, partial-section silence checks |

## Ground-Truth Assertions

Use specific values already validated against the repo and live SEC payloads where possible.

### Reference Sync

- `AAPL -> 320193`
- `MSFT -> 789019`
- `NVDA -> 1045810`
- `AAPL` exchange resolves to `Nasdaq`
- `BRK.B` normalization resolves through lookup normalization rules

### Company Submissions

- AAPL company name is `Apple Inc.`
- AAPL `entity_type` is `operating`
- AAPL `sic` is `3571`
- AAPL `state_of_incorporation` is `CA`
- AAPL former names count is `3`
- AAPL pagination file `CIK0000320193-submissions-001.json` has `filing_count = 1219`

### Latest Filings Ordering

For AAPL, ordering by `acceptance_datetime desc` should yield the current submissions ordering, not just `filing_date` ordering. A recorded test should assert the first accession sequence from the cassette.

### Ownership

Reuse existing ownership values already covered elsewhere in the repo where possible:

- Form 4 `0001209191-20-055264` has derivative transaction type `derivative_purchase`, shares `196.356`, value `43750.08036`
- Form 3 `0001562180-25-001814` yields position `Executive Vice President` and total shares `50257.0`

### ADV

When the first ADV fixtures are recorded, verify by hand and lock in:

- `adviser_name`
- `form`
- one office row
- one disclosure row or explicit empty-state behavior
- detected `source_format`

## Fixture And Cassette Inventory

### Reuse Existing Local Fixtures

These should be reused instead of inventing new synthetic examples.

| Asset | Existing path | Use |
|---|---|---|
| Ownership Form 3 XML | `data/ownership/form3.snow.xml` | Fast parser verification |
| Ownership Form 3 non-derivative XML | `data/form3.snow.nonderiv.xml` | Fast parser verification |
| Ownership Form 4 XML | `data/form4.snow.xml` | Fast parser verification |
| Form 144 XML sample | `data/144/EDGAR Form 144 XML Samples/Sample 144.xml` | Text/artifact pipeline verification |
| SGML filing sample | `data/sgml/0001213900-25-032135.txt` | Attachment/text extraction verification |

### New Recorded Fixtures To Add

These should be committed as either static files in `tests/fixtures/` / `tests/data/` or VCR cassettes in `tests/cassettes/`.

| Asset | Suggested path | Notes |
|---|---|---|
| `company_tickers.json` sample | `tests/data/sec/reference/company_tickers.json` | Include AAPL, MSFT, NVDA, BRK-B cases |
| `company_tickers_exchange.json` sample | `tests/data/sec/reference/company_tickers_exchange.json` | Must include exchange mapping |
| AAPL submissions JSON | `tests/data/sec/submissions/CIK0000320193.json` | Base company/submissions verification |
| MSFT submissions JSON | `tests/data/sec/submissions/CIK0000789019.json` | Multi-pagination verification |
| NVDA submissions JSON | `tests/data/sec/submissions/CIK0001045810.json` | Former-name coverage |
| AAPL pagination JSON | `tests/data/sec/submissions/CIK0000320193-submissions-001.json` | Backfill merge verification |
| Current-feed Atom sample | `tests/data/sec/current_feed/current_feed_atom.xml` | Status and size extraction verification |
| AAPL Form 4 filing index | `tests/data/sec/filing_index/0001140361-26-013192/index.json` | Attachment discovery |
| AAPL Form 4 primary XML | `tests/data/sec/filings/0001140361-26-013192/form4.xml` | Ownership/raw/text verification |
| One Form 5 sample | `tests/data/sec/ownership/form5/<accession>.xml` | Missing in current fixture set |
| One ADV sample | `tests/data/sec/adv/adv/<accession>/*` | First structured ADV fixture |
| One ADV-E sample | `tests/data/sec/adv/adve/<accession>/*` | First amendment or representative fixture |

### New Cassettes To Add

Use `@pytest.mark.vcr` for these.

| Cassette scope | Suggested cassette behavior |
|---|---|
| Reference download | Record the SEC reference files once, then replay |
| AAPL submissions fetch | Record `CIK0000320193.json` fetch |
| Pagination backfill | Record one pagination-file fetch |
| Current-feed fetch | Record one current Atom page |
| Filing artifact fetch | Record one filing index JSON and one headers page |
| ADV fetch | Record one ADV and one ADV-E filing fetch |

Each cassette should carry a recording date comment and the accession numbers it covers.

## Silence Checks

Every ingestion boundary should verify failure behavior explicitly.

| Area | Silence check |
|---|---|
| Reference sync | bad ticker or missing exchange row returns empty result or informative error, not silent `None` |
| Submissions sync | malformed or truncated submissions JSON fails loudly with accession or CIK context |
| Pagination merge | duplicate accession numbers are de-duplicated intentionally, not inserted twice |
| Artifact fetch | missing index or missing primary document raises a useful error |
| Text extraction | unsupported content type produces `skipped` parse run, not silent success |
| Ownership parser | malformed XML records a failed `sec_parse_run` row with parser metadata |
| ADV parser | partial or missing sections still produce traceable parse output or failed parse-run rows |

## Acceptance Mapping

This maps the acceptance criteria in [specification.md](C:/work/projects/edgartools/specification.md) to the proposed verification files.

| Specification acceptance criterion | Verification files |
|---|---|
| reference sync loads `AAPL`, `MSFT`, and `NVDA` correctly | `tests/test_reference_sync.py` |
| submissions sync loads AAPL company metadata and filings | `tests/test_company_submissions_sync.py` |
| latest filings query matches SEC `acceptance_datetime` order | `tests/test_company_submissions_sync.py`, `tests/test_company_pagination_backfill.py` |
| bronze storage contains exact copies with hashes | `tests/test_storage_sec_hosting.py` |
| text extraction runs on `10-K`, `4`, and `ADV` family filing | `tests/test_text_extraction_pipeline.py`, `tests/test_adv_hosting.py` |
| ownership parser writes normalized Form 4 rows | `tests/test_ownership_hosting.py` |
| ADV parser writes `sec_adv_filing` rows | `tests/test_adv_hosting.py` |
| parser runs are tracked in `sec_parse_run` | `tests/test_parse_run_tracking.py` |

## Execution Order

Use this order during implementation:

1. Add fixture-based fast verification for raw transforms and DDL-adjacent logic.
2. Add VCR-backed verification for reference, submissions, pagination, current feed, and artifact fetch.
3. Add ownership parser verification using existing local XML fixtures plus one live recorded filing.
4. Add ADV parser verification with newly recorded ADV and ADV-E fixtures.
5. Add `tests/test_documented_examples.py` entries for the documented hosting queries.
6. Add regression tests for every bug found during implementation.

## Command Cadence

During implementation:

```bash
hatch run test-fast
```

Before merging:

```bash
hatch run test-network
hatch run test-regression
```

For targeted development:

```bash
hatch run test-fast -- tests/test_reference_sync.py
hatch run test-network -- tests/test_company_submissions_sync.py
hatch run test-network -- tests/test_adv_hosting.py
```

## Important Repo-Specific Notes

- Do not rely on `filing_date` for "latest filings" verification. The hosting query must verify `acceptance_datetime`.
- Prefer existing real SEC examples already used elsewhere in the repo before introducing new fixtures.
- `tests/test_documented_examples.py` does not exist yet even though the verification docs expect it. Creating it should be part of this work.
- ADV verification will need the most new fixture work because the repo currently recognizes ADV forms but does not yet parse them into a dedicated object model.
