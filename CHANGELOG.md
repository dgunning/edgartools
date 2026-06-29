# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [5.40.1] - 2026-06-29

### Fixed

- **8-K last item no longer absorbs the SIGNATURES block** — the SIGNATURES section following the last reported item (e.g. Item 5.02 on Meta's `0001628280-25-058337`) leaked into that item's text because `_EIGHT_K_SECTION_PATTERNS` had no `'signatures'` entry, leaving the pattern extractor with no terminal boundary. Additionally, the bold-child header strategy (Strategy 3b) was gated to 10-K only, missing Workiva-style SIGNATURES headings rendered with `font-weight:700` on a child `<span>` (not the paragraph itself), and a new strategy (5b) covers plain-text `font-weight:400` SIGNATURES headings used by some filers (e.g. JPMorgan). The SIGNATURES block is now accessible as `ek.document.sections.named("signatures")` and is excluded from `ek.items`. (edgartools-papt, GH #879)
- **10-K `TenK[item]` no longer merges adjacent Part III items** — on 10-Ks that incorporate Part III by reference with sparse markup (e.g. Tesla FY2022 `0000950170-23-001409`), `Item 10` absorbed the `ITEM 11. EXECUTIVE COMPENSATION` header and body (687 chars) while `Item 11` returned empty, and Part III items were missing from `.items` entirely. The section vocabulary now includes Part III Items 10–14 and Part IV Item 16, and a bold-child header strategy recognizes item headers rendered as bold text inside a paragraph (not a standalone heading) so each item's boundary is detected even when Part III is a compact "see proxy" stub. Items 10–14 are now independently extractable and listed in `TenK.items`; the pattern-merge step runs the same validation/guardrails as TOC sections and is gated so complete-TOC filings and non-10-K forms pay no cost. (edgartools-01x4, GH #880)
- **S-1 / 424B `.sections` no longer misattribute content across boundaries** — three fixes to the title-based section engine that surfaced on Airbnb's IPO prospectuses (S-1 `0001193125-20-294801`, 424B4 `0001193125-20-315318`): (1) the boundary selector now requires a section's end anchor to be declared at-or-after it in the TOC, so an out-of-order sub-block anchor (Airbnb's "Glossary of Terms", listed before MD&A but anchored inside it) no longer truncates MD&A to ~100 chars; (2) 424B now shares S-1's full prospectus vocabulary — a final IPO prospectus repeats the entire S-1 body, so without the narrative sections (MD&A, Business, Management, …) the authoritative-TOC span split and `dilution` swallowed ~900KB; (3) a trailing-financials rescue clamps the last narrative section ("Experts" / "Dilution") at the untitled financial-statements (F-pages) block it previously absorbed. (edgartools-ti82, GH #878)

## [5.40.0] - 2026-06-26

Semantic section extraction reaches proxy statements, registration statements, and prospectuses — `ProxyStatement`, `RegistrationS1`, and `Prospectus424B` now expose Reg S-K sections as section-scoped text over the shared title-based engine. Also adds 13F amendment-type and Form D relationship surfaces, reorganizes the offerings package (with back-compat shims), and fixes a batch of section-boundary and offerings-classification bugs.

### Added

- **Semantic section extraction for proxy statements** — `ProxyStatement.sections` (a dict of named `ProxySection`s) and `ProxyStatement.section(name)` expose Schedule 14A / Reg S-K sections (`proxy_summary`, `corporate_governance`, `compensation_discussion_and_analysis`, `pay_versus_performance`, `audit_matters`, `security_ownership`, …) as section-scoped text. DEF 14A / PRE 14A now route through the title-based section engine; sections are labelled when heading/TOC anchors resolve and fall back to a single `full` section otherwise (no content loss). (edgartools-x341, GH #867)
- **Semantic section extraction for registration statements and prospectuses** — `RegistrationS1.sections` / `Prospectus424B.sections` and `.section(name)` expose Reg S-K sections (`prospectus_summary`, `risk_factors`, `use_of_proceeds`, `mda`, `business`, `management`, `underwriting`, …) over the shared title-based engine, same labelled-or-`full` contract. (edgartools-ybth, GH #866)
- **Named-section API surface on `Document`** — section objects now carry a `kind`, are reachable via `named()`, and named sections such as `.signatures` surface in `document.sections`. (edgartools-nqzc)
- **Form D related-person relationships exposed on `Person`** — `Person.relationships` (e.g. `["Executive Officer", "Director", "Promoter"]` from `<relatedPersonRelationshipList>`) and `Person.relationship_clarification`. The relationship is the analytically meaningful part of the related-persons section; previously only names and addresses were surfaced. Also shown in `FormD` rich rendering and `to_context()`. (edgartools-0dpz, GH #874)
- **13F amendment type exposed on `ThirteenF`** — `is_amendment`, `amendment_type` (`"RESTATEMENT"` | `"NEW HOLDINGS"` | `None`), `amendment_number`, and full `amendment_info` (confidential-treatment fields). The distinction is load-bearing for correctness: a `NEW HOLDINGS` 13F-HR/A discloses only previously-confidential positions and must be *unioned* with the original, whereas a `RESTATEMENT` *replaces* it — superseding the original by a `NEW HOLDINGS` amendment silently drops the real portfolio. (edgartools-preg, GH #872)

### Changed

- **Offerings package reorganized** into `crowdfunding` / `exempt` / `prospectus` sub-packages (e.g. Form C, Form D, and the 424B/S-1 prospectus surfaces each split into their own modules). Existing `from edgar.offerings.* import ...` paths keep resolving via back-compat shims. (edgartools-n094)

### Fixed

- **`ProxyStatement.voting_proposals` no longer emits text fragments as proposals on merger proxies** — on some DEFM14A filings the extractor lifted numbered items out of an "Incorporation by Reference" / exhibit-list section (e.g. Veeco showed proposals numbered 2 and 3 whose text was 8-K item references). Proposal extraction is now anchored to the proxy's actual matters-to-be-voted-on structure. (edgartools-7pga, GH #875)
- **8-K item sections no longer truncated at an internal bold sub-heading** — `_find_section_end` only closed a section at a header that is a real section boundary (Item/PART/SIGNATURE/EXHIBIT/…); internal bold sub-headings (e.g. "Adoption of Fiscal Year 2027 Variable Compensation Plan") previously cut Item 5.02 short, dropping the item body. (edgartools-koq3, GH #871)
- **10-K MD&A (Item 7) recovered when incorporated by reference into an untitled "Financial Section"** — deferred-heading re-attribution plus supplement-start detection recover the MD&A and financial statements for Workiva-style layouts (XOM, JPM, Chevron), without sweeping the exhibit index into Item 7. (edgartools-rv86 / edgartools-gegs, GH #873)
- **`RegistrationS1.underwriting.lead_manager` no longer returns garbage table text** — a "Shares Eligible for Future Sale" lock-up table was misclassified as an allocation table, leaking the row label "Earliest Date Available for Sale in the Public Market" as the lead underwriter; names are now validated at the source and in the S-1 consumer (ABNB resolves to "Morgan Stanley & Co. LLC"). (GH #868)
- **Mixed primary+secondary IPO 424B4 no longer misclassified as `PIPE_RESALE`** — the classifier now overrides to `IPO` inside the PIPE-resale branch when a 424B1/424B4 asserts its own offering is an IPO. (GH #869)
- **Agent (Workiva) TOC parser now recovers Item 9C and Signatures** — keys the generic parser found but the agent path missed on some 10-Ks. (edgartools-rbsx, GH #837 follow-up)

## [5.39.1] - 2026-06-22

### Fixed

- **SGML header parser no longer drops fields after an empty-value top-level key** — an empty-value key like `CONFIRMING COPY:` was misread as a section header, dropping every following field (incl. `FILED AS OF DATE`) so `FilingSGML.filing_date` returned `None`. (edgartools-sg9k)
- **`ShelfLifecycle.total_offering_capacity` recovered from misparsed EX-107 fee tables** — the parser picked the registration fee, or a column-misaligned cell, as `total_offering_amount` for a class of Exhibit 107 layouts, surfacing genuine shelves as null capacity. (edgartools-xn7e)
- **Fee rate parsed correctly for per-$1,000,000 and leading-decimal cells** — `$153.10 per $1,000,000` and `$.0000927` no longer leave `FeeTableSecurity.fee_rate` orders of magnitude too large; dilution tables no longer double-prefix `$` on values that already embed the sign.

## [5.39.0] - 2026-06-21

424B offering extraction now consumes the machine-readable EX-FILING FEES inline-XBRL exhibit it already parsed but previously ignored — wiring it into deal sizing and offering-type classification, adding an IPO offering type, and exposing classifier provenance — plus an lxml rewrite of the exhibit parser and two fixes for offline / local-storage use of historic pre-HTML SGML filings.

### Added

- **`Deal.gross_proceeds` reads the authoritative EX-FILING FEES total** (`ffd:TtlOfferingAmt`) when the cover-page and pricing-table text paths are missing or implausible, sizing the 424B2/424B5 debt/note and ATM shapes those paths miss. (edgartools-s9uo)
- **Offering-type classification consults the EX-FILING FEES security type** (`ffd:OfferingSctyTp`) before falling through to `unknown`: debt → `debt_offering`, equity → `firm_commitment` (low confidence), rights → `rights_offering`. The exhibit is only fetched on the otherwise-`unknown` path. (edgartools-2l2i)
- **New `OfferingType.IPO`** — a 424B1/424B4 whose cover asserts "this is an initial public offering" now classifies as `ipo` instead of being folded into `firm_commitment`; shelf takedowns and follow-ons referencing a past IPO stay `firm_commitment`. (edgartools-ejk5)
- **Offering-type provenance on `Prospectus424B` and `Deal`** — public `offering_type_confidence`, `offering_type_signals` (incl. `xbrl_security_type:*` markers), and `offering_type_sub_type`, also serialized by `Deal.to_dict()`, so consumers can tier values by how the type was determined. (edgartools-drzj)

### Changed

- **EX-FILING FEES inline-XBRL extraction migrated from BeautifulSoup to lxml** — ~15× faster per exhibit (output verified identical across 119 real exhibits), and the exhibit is now fetched at most once per filing rather than potentially twice on the unknown path.

### Fixed

- **Deal size no longer reports the `$1,000` per-note denomination artifact** — a plausibility floor (calibrated: artifacts cluster at exactly $1,000, real deals are ≥ $100k) suppresses these, superseded by the XBRL total where an exhibit exists. (edgartools-s9uo)
- **Multi-`<span>` security titles keep their whitespace** — the lxml extractor no longer mashes titles spanning inline elements into runs like `"Series APerpetual Stride"`.
- **`ShelfLifecycle.takedowns` is returned in chronological order** as its contract promised; previously a newest-first `_related` made `avg_days_between_takedowns` negative and `days_since_last_takedown` read the oldest takedown as the most recent. (edgartools-y22m)
- **`filing.text()` works offline for historic pre-HTML text-only filings** — a tightly-scoped path returns the primary `<TEXT>` body straight from locally-parsed SGML for that shape (a `<FILENAME>`-less, non-HTML/XML primary with no `TEXT-EXTRACT` sibling) instead of re-downloading; every other filing is unchanged. Also adds `FilingSGML.text()` for offline plain-text extraction of the primary document. (edgartools-0rvh)
- **Local storage no longer misses boundary filings whose feed date differs from the filed-as-of date** — `resolve_local_filing_path()` now scans adjacent day-folders on read (accession numbers are globally unique), wired into `Filing.sgml()`, `full_text_submission()`, and the batch checkers; the local-miss log is downgraded to `DEBUG`. (edgartools-a3ej)

## [5.38.0] - 2026-06-20

A batch of offerings/prospectus extraction improvements — derived shelf-lifecycle signals, registration fee-table capacity recovery (including pre-2022 inline "Calculation of Registration Fee" tables), and more reliable lead-underwriter/placement-agent extraction on 424B prospectuses — plus an HTTP/1.1 transport default with a public HTTP/2 opt-in, 8-K item/date fixes, and a 13F portfolio fix.

### Changed
- **HTTP/1.1 is now the default transport** for the internal HTTP client (previously HTTP/2). HTTP/2 multiplexes every request over a single TCP connection, so a mid-stream reset from cloud egress fails all in-flight requests at once — surfacing as intermittent `h2.exceptions.InvalidBodyLengthError` / `httpx.RemoteProtocolError: ConnectionTerminated` that crash long fan-out jobs. SEC's ~9 req/s rate limit means HTTP/2's multiplexing offers no real upside here.
- **`EightK.date_of_report` / `SixK.date_of_report` now always return a `datetime.date`** (or `None` when the filing header has no period of report), instead of a formatted string like `'December 20, 2024'`. Consumers no longer need to parse mixed date/string types. (edgartools-83gh)

### Added
- **Public HTTP/2 toggle** so consumers no longer need to reach into `HTTP_MGR.httpx_params`. Set `EDGAR_USE_HTTP2=true` (env var) or call `configure_http(http2=True)` at runtime to opt back into HTTP/2; `get_http_config()` now reports the current `http2` setting.
- **Pre-2022 inline registration fee tables are now parsed** — before the EX-FILING FEES (Exhibit 107) regime (~pre-2022), registration statements carried the "Calculation of Registration Fee" table inline in the S-3/S-1 body with no exhibit to parse, so `extract_registration_fee_table()` (and shelf/424B fee-capacity) returned `None` for every such filing. The inline body table is now read directly: the registered capacity is taken from the table's aggregate offering price, and indeterminate Rule 457(r) shelves resolve to a deferred fee. Verified across consumer, medical-device, biotech, energy, financial, tech, and REIT issuers. (edgartools-9q82)
- **Derived lifecycle signals on `ShelfLifecycle`** — exposes signals consumers were re-deriving by hand: `status` (registered/effective/expired/withdrawn), `is_effective` / `is_automatic_shelf` / `is_withdrawn` / `is_re_registered`, `program_mode` and `days_since_last_takedown`, `continuity` (continuous/lapsed, computed gap-aware across generations, with a `has_registration_gap` data-quality flag), and `program_age_days`. The continuity logic distinguishes a Rule 415(a)(6) renewal (effective before the prior shelf expired) from a post-gap revival, so a revived shelf is never mislabelled as continuously registered. (edgartools-2w5y)

### Fixed
- **`EightK.items` no longer under-reports items** the new section parser silently missed. When the parser detects only some items (e.g. only Item 9.01 on a filing that also carries an Item 1.05 cybersecurity body), `.items` now unions the parser result with the chunked primary-document parser so the present item is listed. The `eightk['1.05']` / `eightk['Item 1.05']` accessor is also fixed to fall through to the text-based extractor instead of returning the chunked parser's `None` for a key-format mismatch. (edgartools-83gh)
- **`get_thirteenf_portfolio()` now returns populated holdings** instead of always an empty DataFrame. It contained a dead column-rename block and then sorted by a `value_usd` column that never existed, so the trailing `KeyError` was swallowed and an empty frame returned for every real filing. It now uses the single canonical PascalCase infotable schema (`Issuer`, `Cusip`, `Value`, …) shared by all parse paths, and adds a `pct_value` column. (edgartools-i5wx)
- **Shelf expiry is anchored on current effectiveness, not filing date** — `ShelfLifecycle` now derives the shelf's expiration from its current effective date (Rule 415's three-year window) rather than the original filing date, fixing mis-dated expiries that left recent takedowns stranded past a too-early expiry. (edgartools-fu3x)
- **Lead underwriter / placement agent extraction on 424B prospectuses** — `Prospectus424B` underwriting/`lead_manager` now recovers the lead agent from 424B2 structured-note covers, best-efforts and ATM equity covers, and inline agency language ("engaged <firm> … as placement agent"); stitches firm names that wrap across cover-grid lines (e.g. `Ladenburg` → `Ladenburg Thalmann`); and filters out garbage table-of-contents/title text that previously leaked in as the underwriter name. (edgartools-2h4c, edgartools-zzr4)
- **Registration fee-table capacity recovery** — fee-table extraction now recovers the offering amount from split-tag table headers (where header words are broken across inline tags), and, for registration amendments (S-3/A, F-3/A, POS AM) that omit the fee exhibit, recovers capacity from the original registration in the same file-number family. (edgartools-zxnj)

## [5.37.0] - 2026-06-19

A batch of fixes across insider-ownership footnote handling and 10b5-1 plan detection, document search snippet highlighting, BDC/Form C/N-PORT data access, TTM quarterly derivation, and date/currency formatting, plus an ISO 4217 currency column on XBRL facts and the Form C parser's migration to lxml.

### Added

- **`currency` column on the XBRL facts DataFrame** — `xbrl().facts.to_dataframe()` now includes a `currency` column with each fact's ISO 4217 code (e.g. `USD`, `HKD`) resolved from its unit measure. Non-USD filers tag monetary facts with opaque unit ids such as `UNIT_STANDARD_HKD_MNUSOXGRF0O9R60JINVDUQ`, which were exposed verbatim in `unit_ref` and made currency-based filtering and display unreliable; the raw `unit_ref` is preserved, while `currency` gives a usable code. Per-share monetary units report their numerator currency, and non-monetary units (shares, pure, custom) resolve to `None` rather than a misleading value. ([#850](https://github.com/dgunning/edgartools/issues/850))

### Fixed

- **Form 4/5 transaction footnotes are now attributed per transaction** — footnote references attach to many transaction sub-elements (security title, transaction date, shares, price, post-transaction amounts), but the extractor previously collected them only from `<transactionCoding>`, so `TransactionActivity.footnote_ids` / `.footnotes_text` came through empty for most filings. The extractor now gathers footnote IDs from the whole transaction (deduplicated), so per-transaction footnote reasoning — including `is_10b5_1_plan` — works directly rather than relying on the filing-wide fallback.
- **Document search snippets highlight the correct characters** — `SearchResult.snippet` highlights `context[start_offset:end_offset]`, but text, whole-word, and regex search stored absolute text offsets against a context string that was truncated (with `…` markers) around the match, so any match after the leading context window highlighted the wrong characters. Offsets are now computed relative to the returned context. ([#860](https://github.com/dgunning/edgartools/pull/860), [#862](https://github.com/dgunning/edgartools/pull/862))
- **Table search snippets highlight the match, not the whole table** — the semantic `table:<term>` search built a result whose end offset was the full table length against a context truncated to ~200 chars, so `SearchResult.snippet` wrapped the entire truncated context in `**…**` for any table longer than 200 characters. The match is now located within the table and a correct context window is produced, consistent with text and regex search.
- **Rule 10b5-1 plan detection now uses the official Form 4/5 checkbox when present** — ownership summaries honor the structured `aff10b5One` value before falling back to footnote text. When the checkbox is absent (e.g. pre-2023 filings), `has_10b5_1_plan` now scans the filing's full footnote set instead of relying solely on per-transaction footnote attribution, which is frequently empty. The fallback matcher no longer confuses the separate anti-fraud Rule 10b-5 with Rule 10b5-1 trading plans while recognizing common spacing and dash variants. ([#863](https://github.com/dgunning/edgartools/issues/863))
- **`edgar` package logger no longer leaks log output in unconfigured applications** — the package-root logger had no `NullHandler`, so when an application had not configured logging itself, edgartools warnings fell back to Python's `logging.lastResort` handler and were written to stderr. This was especially harmful in MCP / stdio environments, where stray stderr output corrupts the protocol stream. A `NullHandler` is now attached to the `edgar` logger per the Python logging HOWTO for libraries, keeping edgartools silent until the application opts into logging. ([#856](https://github.com/dgunning/edgartools/issues/856))
- **XBRL-absent log messages downgraded from warning to debug** — amended filings (`/A`) and filings with no XBRL attachments are normal, expected cases; the "no XBRL data" messages they produced are now logged at `DEBUG` rather than `WARNING`, so they no longer alarm users during routine processing. ([#857](https://github.com/dgunning/edgartools/issues/857))
- **BDC data sets download again after SEC URL move** — the SEC relocated the DERA BDC data-set files from `/files/structureddata/data/` to `/files/datastandardsinnovation/data/`, which made `fetch_bdc_dataset()` and related functions fail with 404; the base URL now points to the new location.
- **`FormC.filer_information.ccc` no longer duplicates the CIK** — the Form C parser read the `filerCik` element into both `cik` and `ccc`; `ccc` now reads the actual `filerCcc` element (always redacted to `XXXXXXXX` in disseminated filings) and is `Optional`, returning `None` when absent.
- **`FormC.filer_information.live_or_test` is no longer always `False`** — the parser looked for a `testOrLive` element under `filer`, but the schema places `liveTestFlag` under `filerInfo`; LIVE filings now correctly report `True` (older `testOrLive` documents remain supported).
- **TTM Q4 derivation no longer produces wrong/negative values for discrete-quarter reporters** — when a concept is reported as discrete quarters with no cumulative 9-month YTD fact (common for BDCs and investment companies), `TTMCalculator` derives Q4 as `FY - (Q1+Q2+Q3)`. It previously selected the three input quarters by their `fiscal_period` label, but the SEC tags comparative facts in re-filings with the *filing's* fiscal period, so the same calendar quarter could appear labeled Q1, Q2 and Q3 across successive 10-Qs — producing a wrong, often negative Q4 (e.g. GAIN `InvestmentCompanyDividendDistribution`: `57.2M - 3×28.8M = -29.2M`). Quarters are now selected by distinct calendar period (dedup by `period_end`, latest periodic filing wins), and derivation is skipped when a discrete Q4 is already reported. This affects `quarterize()`, TTM calculations, and quarterly statement views. ([#848](https://github.com/dgunning/edgartools/issues/848))
- **`format_currency_short` rolls up to the next unit at magnitude boundaries** — a value just under 1B (>= ~999.95M) rounded to `1,000.0` within the millions bucket and rendered as the nonsensical `$1,000.0M` instead of `$1.0B`; it now promotes to the billions unit when the millions mantissa rounds up to 1,000.
- **`datefmt` no longer crashes on `None` or non-date values** — the display-only date helper called `value.strftime` on its non-string branch unconditionally, so a `None` (e.g. a former name's open-ended `to` date, or a missing `date_of_change`) raised `AttributeError` and took down the whole header/former-name table render. It now returns `""` for `None`, formats `date`/`datetime` objects, and degrades to `str(value)` for anything unexpected. (Complements the unrecognized-string pass-through fix in #859.)
- **`datefmt` no longer crashes on unrecognized date strings** — the helper parsed only `YYYYMMDD`, `YYYYMMDDHHMMSS` and `YYYY-MM-DD` strings and called `str.strftime` on everything else, raising `AttributeError: 'str' object has no attribute 'strftime'` for any other value (e.g. `2022/03/04`, a non-zero-padded date, or an empty string). Unrecognized strings are now returned unchanged so date display in filing-header and former-name tables degrades gracefully instead of crashing.
- **`reverse_name` handles a generational suffix between surname and given name** — SEC's `LAST SUFFIX FIRST` ordering can place a suffix (`III`, `Jr`, …) immediately after the surname and before the given name (e.g. the PPG insider `ROBERTS III CHRIS`); `reverse_name()` treated it as part of the given name and produced `Iii Chris Roberts`. Leading suffix tokens are now pulled out of the given-name parts, so the name renders as `Chris Roberts III`.

### Changed

- **Form C parsing migrated from BeautifulSoup to lxml** — `FormC.from_xml` now uses the same lxml parsing pattern as the fund reports, with verified field-level parity across all Form C variants (C, C-U, C-AR, C-TR). Optional fields on the Form C models now declare explicit `None` defaults.

## [5.36.0] - 2026-06-09

A batch of robustness fixes across insider-ownership context, 6-K exhibit decoding, fund/N-PORT filing access, Schedule 13D/G, and XBRL depreciation standardization, plus an internal restructure of the ownership module. No public API changes.

### Added

- **`form='N-PORT'` resolves to `NPORT-P`** — `get_filings(form='N-PORT')` and related queries now match the actual SEC form type (`NPORT-P`) via a form-name alias, so the intuitive name returns results instead of an empty set. ([#843](https://github.com/dgunning/edgartools/issues/843))

### Fixed

- **`Ownership.to_context()` no longer crashes on string share values** — Form 3/4/5 filings whose share amounts carried footnote references or other non-numeric text raised a `TypeError` when building the AI context string; the value is now coerced safely so `to_context()` always returns a string. ([#846](https://github.com/dgunning/edgartools/issues/846))
- **`SixK.text()` no longer crashes on bytes exhibit content** — 6-K exhibits whose `Attachment.download()` returns `bytes` raised `TypeError: a bytes-like object is required, not 'str'` in the legacy HTML parser's `<TEXT>` check; the parser now decodes bytes first, so bytes and str inputs parse identically. Non-UTF-8 exhibits (cp1252/latin-1, common in older filings) decode correctly via a cp1252→latin-1 fallback instead of emitting replacement characters. ([#844](https://github.com/dgunning/edgartools/issues/844))
- **`SixK.text()` skips binary exhibits** — `.xlsx` and `.zip` attachments are now classified as binary so `SixK.text()` no longer attempts to decode them as HTML/text. ([#844](https://github.com/dgunning/edgartools/issues/844))
- **`Fund(ticker).get_filings(series_only=True)` now isolates the series** — the flag previously returned filings beyond the requested series; series filtering is now applied correctly. ([#843](https://github.com/dgunning/edgartools/issues/843))
- **Corrected a dead `N-PORT` entry in `FILER_TYPE_DOMESTIC_FORMS`** — the stale entry meant N-PORT filer-type filtering matched nothing. ([#843](https://github.com/dgunning/edgartools/issues/843))
- **Schedule 13D/G `obj()` returns a partial object instead of silent `None`** — a parsing gap previously caused `filing.obj()` to return `None` for some 13D/G filings; it now returns a partial object so callers get the data that did parse rather than nothing, and the `to_context()` navigation hints for these filings were corrected. ([#840](https://github.com/dgunning/edgartools/issues/840), [#841](https://github.com/dgunning/edgartools/issues/841))
- **`OtherDepreciationAndAmortization` no longer breaks standardized cash flow** — filers reporting D&A under the `OtherDepreciationAndAmortization` concept had the primary D&A line dropped from the standardized cash-flow statement and the concept misclassified as non-operating income in XBRL standardization. The line is now retained and classified correctly, with the orphan-fold dedup hardened against duplicate facts. ([#839](https://github.com/dgunning/edgartools/issues/839))
- **Pinned `httpxthrottlecache <0.5.0`** to avoid a breaking httpx2 fork in the 0.5.x line.

### Changed

- **Internal: `edgar/ownership/ownershipforms.py` split into focused submodules** — the 2,279-line module was decomposed into `models`, `core`, `tables`, `table_containers`, `owners`, `summary_records`, `summary`, `forms`, and `text_render` (each under 600 lines). `ownershipforms.py` remains a backward-compatibility shim re-exporting every previously public name, and the `edgar.ownership` package surface is unchanged — verified by a new public-API guard test. Pure structural refactor with no behavior change.

## [5.35.1] - 2026-06-04

10-K section detection and agent TOC parsing receive two targeted fixes that close gaps introduced in 5.34.0.

### Fixed

- **Spurious Part IV Item 1/1A keys no longer appear in 10-K section maps** — the section detector emitted duplicate entries for Items 1 and 1A under the Part IV heading of certain 10-Ks; the keys are now dropped so lookups return the correct Part I sections. ([#836](https://github.com/dgunning/edgartools/issues/836))
- **Agent TOC parsers no longer drop Item 1 on title-only rows** — when a TOC row contained only a title with no page number or hyperlink, the parser silently skipped Item 1; the row is now accepted and keyed correctly. ([#837](https://github.com/dgunning/edgartools/issues/837))

## [5.35.0] - 2026-06-02

BDC non-accrual extraction no longer depends on a filer phrasing its footnotes exactly the way our whitelist expected, and a parsing gap is now surfaced as a warning rather than read as a confirmed zero.

### Added

- **`edgar.__version__`** — the installed version is now exposed at the package root (`import edgar; edgar.__version__`), following the standard `pkg.__version__` convention so downstream consumers can detect which version they have without reading `edgar.__about__` or running `pip show`. ([#794](https://github.com/dgunning/edgartools/issues/794))
- **`NonAccrualResult.warnings`** — flags a portfolio that produced no non-accrual signal from any extraction layer, and recognized flags that resolved no investments, so an LLM consumer never mistakes a parsing gap for a confirmed zero. Surfaced in `to_context`, mirroring the `Section.warnings` pattern.

### Fixed

- **BDC non-accrual footnote detection is now robust to wording drift** — the exact-phrase affirmative-pattern whitelist silently dropped any footnote a filer didn't phrase as an enumerated sentence. MAIN changed "Non-accrual *and* non-income producing…" to "…*or*…" and its 10-Q returned an empty list; PSEC's verb-less "Investment on non-accrual status as of the reporting date" matched nothing. The binary regex gate is replaced with a layered classifier (mention → negation → explicit pattern → structure-corroborated short label) that accepts short footnotes linked to specific investment facts regardless of exact phrasing, while long rollforward/policy footnotes stay excluded by length. Real-world impact: PSEC 0 → 5 non-accrual investments, GBDC now extracts footnote-level detail, MAIN/ARCC/FSK unchanged. ([#835](https://github.com/dgunning/edgartools/issues/835))

## [5.34.0] - 2026-06-02

SEC section extraction is now form-aware by design: form structure is declarative data rather than 10-K-shaped heuristics, link-less-TOC bank filings (Goldman Sachs, Citigroup) extract their items correctly, and wrong-content sections are flagged instead of trusted.

### Added

- **`Section.markdown()` now works on TOC-detected sections** — slices the section HTML and renders structure-preserving markdown (tables, lists) instead of falling back to flat text. Completes the `Section.markdown()` work from 5.32.0.
- **Per-form section schema** — each form's extraction rules live in a declarative schema (`form_schema.py`) instead of branches in the TOC analyzer; supporting a new form is now a table entry.
- **Body-header item recovery** — recovers canonical items from link-less-TOC 10-Ks (Goldman Sachs: 13 garbage sections → 21 correct items). Fires only when the linked-TOC parse is incomplete, so well-formed filings are untouched.
- **`Section.warnings`** — flags sections whose content size is anomalous (truncated or over-captured) instead of returning them at high confidence.

### Fixed

- **`TenQ['Item 1']` returned Legal Proceedings instead of Financial Statements** — pre-header 10-Q items were keyed without their Part prefix, so lookups fell through to Part II.
- **Fund `get_company()` silently returned `None`** — SEC now types fund CIKs as numeric (`225323.0`), which broke key matching; CIKs are normalized through `int` so all forms key identically.
- **`TenK.items` now returns canonical SEC order** (`1, 1A, … 16`) on all paths, not detection order.
- **Bare 10-K item keys get their canonical part prefix** inferred from the item number; `"Item 8" in sections` still works.
- **Filer-specific item suffixes (e.g. Caterpillar "Item 1D") are accepted** instead of dropped as non-canonical.
- **Descriptive free-text and bare Part labels no longer leak as sections** in the generic TOC path.
- **`'part'` no longer false-matches inside words** like "counterparties" when inferring Part context.
- **TOC analyzer logs internal failures** instead of silently degrading to the generic scraper.

### Changed

- **Refreshed bundled reference data** — `ct.pq` (CUSIP→ticker, 13F rendering) refreshed from SEC Fails-to-Deliver and merged to preserve coverage (68,512 CUSIPs); `company_tickers.parquet` (ticker↔CIK resolution) refreshed as a clean mirror of SEC's current data (10,365 entries).

## [5.33.0] - 2026-05-29

### Added

- **`Filing.search()` highlights matched query terms in its output** — search results now mark the terms that matched within each section, so you can see *why* a section was returned rather than just *that* it was. Complements the BM25/regex section-index fix shipped for the same issue in 5.32.0. ([#765](https://github.com/dgunning/edgartools/issues/765))

### Fixed

- **`Section.tables()` returned each table up to ~24× on TOC-detected sections** — `Section._extract_section_html` walked the section subtree with `iterwalk` and re-serialized *every* collected element via `tostring()`. Because `tostring()` already includes an element's full subtree, a `<table>` nested under collected ancestors was emitted once for itself plus once inside each ancestor, and `_get_tables_from_toc_section` then wrapped each copy as a distinct `TableNode`. AAPL's 10-K Item 8 returned 123 tables for 34 unique; deeply nested 20-F sections hit ~24× per table. Only top-level collected elements are serialized now (a parent's serialization already covers its descendants), so each table appears exactly once. `Section.text()` is byte-identical before and after — no content drift. ([#826](https://github.com/dgunning/edgartools/issues/826), reporter @HonzaCuhel)

- **XBRL statements rendered duplicate rows when a concept had repeated presentation arcs** — duplicate presentation arcs pointing at the same concept produced repeated lines in `render()`. Arcs to the same concept are now de-duplicated, with roll-forward (beginning/ending balance) arcs exempted so cash-flow and equity roll-forwards still render both their opening and closing balance rows. ([#825](https://github.com/dgunning/edgartools/issues/825))

- **Embedded tables inside XBRL `TextBlock` report cells were dropped** — SGML/HTML tables nested within a TextBlock disclosure are now rendered in the report cell instead of being silently omitted. ([#755](https://github.com/dgunning/edgartools/issues/755))

- **13F value-unit (thousands vs dollars) was inferred from a global filing-date cutoff** — the thousands/dollars scale is now detected per-filing from the filing's own data rather than a date heuristic, fixing misscaled holding values for filings near the cutoff boundary.

## [5.32.0] - 2026-05-28

### Added

- **`xbrl.calculation_linkbase()` DataFrame** — exposes the per-filing calculation linkbase as one row per parent→child arc, with signed weight, role URI, taxonomy attribution (us-gaap vs filer extension), and SEC menucat classification. Enables external pipelines (e.g., bank revenue disaggregation, REIT rental income rollups) to build per-filer concept hierarchies without re-parsing `_cal.xml`. Layer 1 of the GH #766 implementation plan; the parser was already producing this data on `CalculationTree`/`CalculationNode`, this is a DataFrame projection over existing output. ([#766](https://github.com/dgunning/edgartools/issues/766))

- **`Statement.extension_arcs()`** — surfaces filer-authored concepts that participate in a statement's calculation linkbase but are absent from its presentation tree, i.e. concepts that silently drop from `render()` output today. Opt-in via `Statement.extension_arcs(include_values=False)`; default mode returns one `ExtensionArc` per concept (structural), `include_values=True` emits one per (concept, context) with the instance value attached. The existing `render()` path is untouched. Layer 2 of GH #766. Ground-truth verified on JPM FY2023 10-K cash flow (`jpm:NetChangeInAdvancesToandInvestmentsInSubsidiaries`, `jpm:NetBorrowingsFromSubsidiaries` — both calc-present, presentation-absent). ([#766](https://github.com/dgunning/edgartools/issues/766))

- **`Section.markdown()` accessor** — closes the gap between `Section.text()` (item-aware but flattens tables and bullet lists) and `Filing.markdown()` (preserves structure but whole-document only). Per-item chunkers / RAG pipelines can now get structure-preserving markdown scoped to a single section. Pattern/heading-detected sections render the cached node tree via `MarkdownRenderer`; TOC-detected sections currently fall back to `Section.text()` to avoid corrupting adjacent-section markup (full TOC support tracked as a follow-up). Real-filing regression on AAPL 8-K Item 9.01 exhibit table locks in the pipe-table contract. ([#833](https://github.com/dgunning/edgartools/pull/833), contributor @HonzaCuhel)

### Fixed

- **`StreamingParser` dropped 20%+ of text from `<span>`-wrapped paragraphs on large filings** — for SEC filings crossing the 10 MB streaming threshold (so most ~30–110 MB 10-Ks/20-Fs), `filing.text()` silently returned output 20%+ shorter than the non-streaming path. Two compounding bugs in the `iterparse` loop: `elem.clear()` ran on every event (both start and end), and ran on every element regardless of whether an enclosing structural element (`<p>`, `<h1>`–`<h6>`, `<section>`) had finished reading its children. Since SEC filings wrap virtually every word in `<span style="…">`, the inner `<span>`'s end event cleared `.text`/`.tail` before the enclosing `<p>` could read them — paragraphs came out empty, with no warning. Clearing now runs only on `end` events and is gated on a new `_content_depth` counter (mirroring the existing `_table_depth` gate). A separate gate prevents `<p>`/`<h*>`/`<section>` inside `<td>` from being emitted twice. ([#830](https://github.com/dgunning/edgartools/pull/830), contributor @kevinchiu)

- **`HTTP_MGR` had no default timeout — stalled requests could block workers indefinitely** — the internal `httpx` client was constructed without a timeout, so a stalled upstream or slow TLS handshake could pin a worker on an uninterruptible socket read syscall. Downstream users observed processes running 50+ minutes past their job budget on a single request. `get_http_mgr()` now sets `Timeout(30.0, connect=10.0)` by default; `EDGAR_HTTP_TIMEOUT` (seconds) configures it statically and the existing `configure_http(timeout=...)` runtime API still works. Callers that need unbounded waits can opt out explicitly. ([#831](https://github.com/dgunning/edgartools/pull/831), contributor @kevinchiu)

- **13F-HR `holdings` merged Put/Call positions into the underlying equity row** — `ThirteenF.holdings` grouped by CUSIP alone, so Put/Call rows aggregated into the same security's equity row and the `PutCall` column was lost on the merged result. Categories also used uppercase `PUT`/`CALL` while SEC XML emits title-case `Put`/`Call`, so the categorical conversion silently dropped those values too. Group key now includes `PutCall` when the column exists; category labels match SEC XML. Regression verified on SG Capital Management 13F-HR/A (3 distinct Put positions preserved in the aggregated view). ([#824](https://github.com/dgunning/edgartools/issues/824))

- **`import edgar` emitted `DeprecationWarning` on every startup** — the legacy HTML modules (`edgar.files.html_documents`, `edgar.files.html`, `edgar.files.htmltools`) emitted warnings at module top, and edgartools' own startup cascade imports them, so the warnings fired on every fresh import. Downstream test suites running under `-W error` (a recommended pytest setup) had to install warning filters just to let `import edgar` succeed. The deprecation signal moved from module top to per-class `__init__`, so internal callers don't trip the warning while user-instantiated legacy classes still do. ([#832](https://github.com/dgunning/edgartools/pull/832), contributor @kevinchiu)

- **`Filing.search()` / `Filing.grep()` returned nothing on pre-2002 plain-text filings** — `Filing.search()` raised `AssertionError` and `Filing.grep()` returned 0 matches on plain-text filings (e.g. PCG's 1999 10-K). Both relied on attachment iteration that finds nothing because SGML decomposition emits empty shells for text-only filings. `sections()` now falls back to chunking `filing.text()` on `<PAGE>` markers or blank lines when `html()` is None, and `grep()` falls back to `filing.text()` when no attachment yields usable text. ([#819](https://github.com/dgunning/edgartools/issues/819))

- **TOC analyzer fabricated phantom Items on 10-Q filings** — `TOCAnalyzer` had three 10-K-shaped heuristics that fired regardless of form: it accepted any bare number 1–15 as an item identifier in preceding-`<td>` siblings (so a page-number cell like `<td>8</td>` became "Item 8"); it mapped any "financial statements" link to "Item 8" (correct for 10-K, wrong for 10-Q where Financial Statements is Part I, Item 1); and it sorted using a 10-K-shaped section-order table. All three heuristics are now form-guarded. ([#827](https://github.com/dgunning/edgartools/pull/827), contributor @HonzaCuhel)

- **`SearchResults` panel labels conflated BM25 rank with section index** — `SearchResults.__rich__` used the enumeration rank of the sorted display as the panel title, so the same numeric label meant different things in the BM25 and regex paths (BM25 sorts by score, regex preserves original order). "0" in BM25 output was the top-scoring section while "0" in regex output was the first section that matched, and the two were rarely the same. Panels now display `DocSection.loc` — the section's index in `filing.sections()` — consistently across search methods, so callers can index back into the corpus regardless of search mode. ([#765](https://github.com/dgunning/edgartools/issues/765))

### Documentation

- **`calculation_linkbase()` and `Statement.extension_arcs()` documented** alongside Phase 1 and Phase 2 of the GH #766 implementation, including the difference from presentation linkbase and worked examples on real filings. ([#766](https://github.com/dgunning/edgartools/issues/766), Phase 3)

## [5.31.5] - 2026-05-21

### Fixed

- **`xbrl.facts.to_dataframe()` mislabeled Q2/Q3 as Q3/Q4 for 52/53-week fiscal-year filers (JNJ, PFE, AAPL, COST)** — the XBRL instance parser's `_quarter_for_date` classified the fiscal quarter from the raw calendar month of the period end. 52/53-week issuers pin quarter ends to a weekday near the calendar quarter boundary, so the period_end can drift into the first days of the following month — JNJ Q2 2023 ended 2023-07-02, Q3 2023 ended 2023-10-01 — bucketing those facts into the next quarter. The EntityFacts layer already handled this via `calculate_fiscal_year_for_label`, but the XBRL parser has an independent fiscal classification path feeding `xbrl.facts.to_dataframe()` and `query().by_fiscal_period(...)`, silently misclassifying quarterly data for any RAG / analytics pipeline reading raw facts. End dates in the first 7 days of a month are now treated as belonging to the previous month for quarter classification; the 7-day window covers max drift for Sunday-nearest (≤3 days), Saturday-nearest (≤1 day), and last-Sat/Sun (no drift) patterns with safety margin. ([#816](https://github.com/dgunning/edgartools/issues/816), reporter @kmatosli)

## [5.31.4] - 2026-05-21

### Fixed

- **Empty income statement on 16-week-quarter filers (CAVA, RRGB)** — quarterly period selection bucketed durations as 80-100 days or 150-285 days, leaving CAVA's 111-day Q1 in a dead zone. The selector now anchors on `filing.period_of_report`. ([#822](https://github.com/dgunning/edgartools/issues/822), reporter @mkdeak)

- **`TenK.business` silently returned Part II MD&A content on GS's 2025 10-K** — the cross-Part lookup happily returned a mislabeled `part_ii_item_1` key. Item lookup is now constrained to the SEC-canonical Part per item. ([#821](https://github.com/dgunning/edgartools/issues/821), reporter @FlorinAndrei)

- **Viewer `ConceptRow.numeric_value` returned wrong values on ADI 2019 and ADSK 2019 10-Ks** — `primary_period` is now form-aware (annual forms prefer the longest `"X Months Ended"` duration), and `class="th"` spacer cells are dropped from body rows so column positions align. ([#818](https://github.com/dgunning/edgartools/issues/818), reporter @mpreiss9)

- **`Filing.search()` raised a bare `AssertionError` on pre-2001 SGML/text filings** — replaced with a descriptive `ValueError` pointing users at `filing.text()`. ([#819](https://github.com/dgunning/edgartools/issues/819), reporter @shenker)

### Added

- **10-K section patterns for Item 1B (Unresolved Staff Comments) and Item 1C (Cybersecurity)** — closes the gap left when the same SEC rulemaking added 8-K Item 1.05 and 20-F Item 16K patterns. ([#813](https://github.com/dgunning/edgartools/pull/813), contributor @HonzaCuhel)

## [5.31.3] - 2026-05-17

### Fixed

- **`viewer.financial_statements` returned wrong income statement for filings with multi-row period headers** (e.g. ADI 2019 10-K mislabeled annual columns as quarterly). The R*.htm header parser was rewritten to walk `<thead>` row by row and filter footnote markers. Affected most 10-K/10-Q filings silently. ([#812](https://github.com/dgunning/edgartools/issues/812), reporter @mpreiss9)

- **`Financials.get_net_income()` returned wrong value (often wrong sign) for filers reporting a net loss with a separate noncontrolling-interest line** — for Micron Q2 2013 returned +$2M (the NCI row) instead of -$286M. Also fixes IFRS 20-F filers whose row label isn't "Net income" (e.g. Barclays "Profit after tax"). Concept lookup is now exact and IFRS-aware. ([#814](https://github.com/dgunning/edgartools/issues/814), reporter @wei-jianlin)

## [5.31.2] - 2026-05-15

### Fixed

- **`FundReport.options_data()` crashed with `TypeError: bad operand type for abs(): 'NoneType'` on N-PORT filings whose nested forwards had null USD amounts** — `edgar/funds/reports.py:1011-1012` cast `fwd.amount_sold` / `fwd.amount_purchased` through `abs()` when the corresponding `currency_*` field equalled `'USD'`, but valid N-PORT XBRL can pair a stated USD currency with a null amount — every option-on-forward in such a filing tripped the crash before any data was returned. The documented public API was effectively unusable for any fund whose options referenced such a forward (reproducer: GOF NPORT-P). Both assignments now guard on `amount_* is not None`; the exchange-rate calculation just below was already safe via Python's short-circuiting. Defensive grep across the file confirmed lines 1011-1012 were the only unguarded `abs()` calls. ([#811](https://github.com/dgunning/edgartools/issues/811), reporter @HristoRaykov)

- **`viewer.concept_rows[i].numeric_value` silently returned a prior-year value when the primary reporting period had no fact for the row** — `ConceptRow.numeric_value` (and the sibling `Concept.value` accessor on the concept graph) returned `parse_numeric(next(iter(self.values.values())))` — the first entry of the values dict, which was populated only for periods that had a non-empty cell. When the primary (leftmost) reporting period had no value, the singular accessor silently returned whichever period happened to be first in the dict, masking missing-period as a prior-year value. Most visible on the ABT 2019 10-K income statement: `concept_rows[16]` (`us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTax`) returned `34.0` (the 2018 value) because ABT had no 2019 discontinued-ops fact. Tracks `primary_period` on `ConceptRow` (populated by the R*.htm parser from `period_headers[0]`) and resolves `numeric_value` against it explicitly, returning `None` when the primary period has no value. `Concept.value` in `concept_graph.py` got the same fix — same antipattern, same underlying row data, user-visible via the concept graph's Rich/text rendering. ([#810](https://github.com/dgunning/edgartools/issues/810), reporter @mpreiss9)

- **`FundFeeNotice` crashed with `AttributeError: 'list' object has no attribute 'get'` on per-class 24F-2NT filings** — `xmltodict`-style parsing returns repeated `annualFilingInfo` blocks as a list, but every typed accessor (`fund_name`, `series`, `aggregate_sales`, etc.) called `.get()` on the result. ~2% of recent 24F-2NT filings — including all five BNY Mellon family filings — file one block per share class, so the first call into the data object raised before any data was returned. The data model now iterates every `annualFilingInfo` block: typed financial properties (`aggregate_sales`, `net_sales`, `redemptions_current_year`, `registration_fee`, `total_due`, …) sum across blocks; metadata properties (`fund_name`, `fiscal_year_end`, `investment_company_act_file_number`) read from `block[0]` (identical across blocks); `series` deduplicates by `seriesId`. A new `FundClassFee` dataclass + `is_per_class` flag + `class_fees` list expose the per-share-class breakdown. The `_parse_float` helper now also handles accounting-parens notation `(NNN)` → `-NNN`, which appears in `redemptionCreditsAvailableForUseInFutureYears`. Backwards-compatible: every existing property keeps the same return shape; the fund total invariant `aggregate_sales == sum(cf.aggregate_sales for cf in class_fees)` is verified against BNY Mellon Research Growth Fund. (edgartools-8ohs)

- **`viewer.concept_report.currency_scaling` returned wrong scales for filers using non-Apple header formats** — `ConceptReport.currency_scaling` was derived from a narrow text match on the R*.htm `<th class='tl'>` header (`$ in millions` / `$in millions`). Filers using `In Millions`, `(in millions)`, `USD ($) in Millions`, or `Dollars in Millions` silently fell through to the default of `1`, producing scaling that disagreed across statements within a single filing (ALGN balance sheet vs income statement) and wrong values for whole multi-year ranges (ABNB showing `1` for 2023/2024 when the actual scale is millions). `ViewerReport.currency_scaling` now derives the scale from the XBRL `decimals` attribute on monetary facts mapped to the report's role in the presentation linkbase — filer-mandated and uniform (`-6` → millions, `-3` → thousands, `0` → units). The text-match value is retained as a fallback when XBRL is unavailable. The resolved scale is mirrored back onto `ConceptReport.currency_scaling` so existing code reading it via the concept-report path also benefits. Same precedent as GH #799 (level enrichment from XBRL). ([#807](https://github.com/dgunning/edgartools/issues/807), reporter @mpreiss9)

## [5.31.1] - 2026-05-12

### Fixed

- **Schedule 13D/13G silently dropped CUSIPs with the new `<issuerCusips>` wrapper** — SEC began wrapping `<issuerCusipNumber>` inside an `<issuerCusips>` container element on some Schedule 13D/13G filings (e.g. CIK 1906837 13D, CIK 1425851 13G). The parser's BS4 `recursive=False` lookup at the top-level only matched the flat layout, so `subject_company.cusip` came back as `''` whenever the wrapper was present. Parsing now falls back to a recursive lookup when the flat probe misses, handling both wire formats. ([#802](https://github.com/dgunning/edgartools/issues/802), PR [#803](https://github.com/dgunning/edgartools/pull/803) by @HristoRaykov)

- **Schedule 13D/13G event-date attribute name mismatch** — `Schedule13D` exposed the triggering-event date as `date_of_event` while `Schedule13G` exposed it as `event_date`, breaking duck-typing across a mixed list of 13D/13G filings and forcing callers to use `getattr` / `hasattr`. Both classes now accept either name; the underlying attribute is unchanged, so existing code keeps working. ([#804](https://github.com/dgunning/edgartools/issues/804), PR [#805](https://github.com/dgunning/edgartools/pull/805) by @0ywfe)

- **Spurious `DocumentTooLargeError` from `StreamingParser` on legitimate documents** — The streaming HTML parser accumulated `len(etree.tostring(elem))` on every lxml `iterparse` `end` event. Because `tostring` serializes the full subtree and `end` fires for every closing tag, nested elements were counted multiple times — large nested HTML could trip `max_document_size` even though the source document was under the limit. The per-event accumulator is also redundant: `HTMLParser._parse` already validates `len(html.encode("utf-8"))` against `max_document_size` before invoking streaming mode. The accumulator and its state are removed; size is now checked once at the top of `StreamingParser.parse()` and the same encoded bytes are reused for `iterparse`. ([#806](https://github.com/dgunning/edgartools/pull/806) by @kevinchiu)

## [5.31.0] - 2026-05-08

### Added

- **`include_quarterly` parameter on stitched XBRLS statements** — `XBRLS.from_filings()` previously emitted a single column per filing, preferring YTD/annual over the discrete-quarter period when both existed in the source XBRL (Issue #475 design). This created a parity gap with single-filing `XBRL`, which surfaces both. The new opt-in `include_quarterly=False` parameter on `XBRLS.get_statement()`, `StitchedStatement`, and `statements.income_statement()` / `cashflow_statement()` causes each 10-Q to contribute both a 90-day discrete column and the YTD column, and each 10-K to contribute both an annual column and its embedded Q4 column. Distinct from `discrete_quarters` (v5.30.3) which derives quarterly cash-flow values by subtraction; this surfaces facts already in the filing. Default behavior is preserved. Has no effect on Balance Sheet (instant periods only). ([#780](https://github.com/dgunning/edgartools/issues/780), reporter @AhmedShaker12)

### Fixed

- **`viewer.financial_statements` silently dropped income statements miscategorized in `FilingSummary.xml`** — AbbVie's 2021 10-K placed `Consolidated Statements of Earnings` under `MenuCategory='Uncategorized'` instead of `'Statements'` — a filer mistake that EdgarTools faithfully reflected, so the income statement disappeared from `viewer.financial_statements` while comparable 2019/2020/2022-2025 filings worked fine. The viewer now returns the union of FilingSummary `MenuCategory='Statements'` and MetaLinks `groupType='statement'`, deduplicated by HTML filename, in filing-position order. MetaLinks reflects XBRL taxonomy classification and is more reliable than filer-provided menu metadata. ([#797](https://github.com/dgunning/edgartools/issues/797), reporter @mpreiss9)

- **`viewer.concept_rows[*].level` always returned 0** — Modern SEC R*.htm files don't encode hierarchy in the rendered HTML — empirically verified across 10 diverse 2025 10-Ks (AAPL, ABT, JPM, WMT, XOM, VZ, MSFT, GS, PFE, BRK.B): zero `plN` class tokens on primary statements, almost no `padding-left` styles, no row nesting. The canonical source is the XBRL **presentation linkbase**, which the existing parser already loads as `xbrl.presentation_trees[role].all_nodes[concept_id].depth`. The viewer now lazy-loads the parsed XBRL on first `concept_rows` access and populates `ConceptRow.level` from the presentation tree, normalized so the smallest depth observed in a report becomes 0. For the issue's canary case (ABT balance sheet) the level distribution went from `{0: 45}` to `{0: 15, 1: 26, 2: 4}`. ([#799](https://github.com/dgunning/edgartools/issues/799), reporter @mpreiss9, investigation by @tjhub1983)

- **`XBRLS.from_filings(list, filter_amendments=True)` crashed with `AttributeError`** — The signature accepts `Union[Filings, List[Filing]]` and defaults `filter_amendments=True`, but the implementation called `filings.filter()` unconditionally — raising `AttributeError: 'list' object has no attribute 'filter'` whenever a plain list was passed. The implementation now branches on whether the input has a `.filter` method; for plain lists it falls back to a form-suffix check that drops forms ending in `/A`. (edgartools-6k96)

## [5.30.3] - 2026-05-06

### Fixed

- **`facts.time_series()` returned duplicate rows from fuzzy concept matching** — When called with a fully-qualified XBRL concept like `us-gaap:NetIncomeLoss`, the underlying `by_concept` query defaulted to fuzzy substring matching, so `us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic` was silently included alongside it, producing duplicate rows for the same reporting period. `time_series()` now passes `exact=':' in concept`, so qualified names match exactly while bare names (`'Revenue'`) retain fuzzy/label discovery. ([#795](https://github.com/dgunning/edgartools/issues/795), PR [#798](https://github.com/dgunning/edgartools/pull/798) by @tjhub1983)

- **Quarterly Q4 NetIncomeLoss off by ~1000× when proxy XBRL contained corrupt metadata** — DX's 2026 DEF 14A disclosed historical NetIncomeLoss figures with `fiscal_year=null, fiscal_period=null`, including a single FY 2025 value with a 1000× scaling error (319,065 instead of 319,066,000). The corrupt fact entered the ANNUAL duration bucket in `TTMCalculator._derive_q4_from_fy` and won the `period_end` dedup because the proxy was filed after the 10-K, producing a Q4 2025 value of −133,387,935 instead of +185,359,000. The TTM calculator now (a) requires valid `fiscal_period` (FY/Q3/Q2) for inputs to each derivation method, and (b) prefers periodic-report sources (10-K/Q, 20-F, 40-F, 6-K and amendments) over proxy/registration forms when deduplicating. ([#796](https://github.com/dgunning/edgartools/issues/796))

- **DFIN-generated TOCs produced unprefixed item keys** — TOCs from DFIN's filing tool (e.g., Microsoft 10-K) place `PART I`/`PART II` headers in text-only `<tr>` rows without anchor links. The previous parser iterated flat over `<a>` links and only updated `current_part` from a parsed link's text, so it never saw the part headers and produced keys like `"Item 1"` instead of `"part_i_item_1"`. The parser now walks rows in document order so text-only rows update part context for item links that follow.

- **Non-standard duration stubs distorted "Three Recent Periods" view** — PLTR's latest 10-Q exposes a 30-day stub context (`duration_2026-03-01_2026-03-31`, classified as `'Period'`) alongside the normal Q1 and FY durations. `get_period_views()` sorted all duration periods by end date and took the top 3, so the stub landed at `period_keys[0]` with no statement data and produced an all-null column. Period view generation now filters to durations whose `classify_duration()` bucket is a standard reporting period (Quarterly, Semi-Annual, Nine Months, Annual).

## [5.30.2] - 2026-04-29

### Fixed

- **`get_filings(filing_date=(start, end))` crashed with TypeError** — `Entity.get_filings` declared `filing_date: Optional[Union[str, Tuple[str, str]]]` but the underlying parser only handled the colon-separated string form. The tuple form crashed every CIK with `TypeError: strptime() argument 1 must be str, not tuple` before any HTTP request. `extract_dates` now accepts both `(start, end)` tuples and lists, with `None` in either slot meaning "open" (matching the existing `"start:"` / `":end"` string-form semantics). ([#794](https://github.com/dgunning/edgartools/issues/794))

- **Duplicate revenue rows when `RevenuesAbstract` is an additional virtual-tree root** — In ~35% of companies whose learned virtual trees contain `RevenuesAbstract` as an additional root alongside `IncomeStatementAbstract`, the rendered income statement showed Revenue twice — once promoted under `IncomeStatementAbstract`, once again as a child of the second root. The duplicate-root guard previously checked only top-level concepts; it now walks the tree recursively via `_collect_concepts` and prunes duplicate subtrees, preserving abstract containers only when they still hold unique descendants. ([#789](https://github.com/dgunning/edgartools/issues/789), PR [#790](https://github.com/dgunning/edgartools/pull/790) by @ghedo44)

- **Orphan section re-introduced Revenue under "Additional Financial Items"** — As a follow-up to the #789 fix, the orphan dedup at the income-statement assembly layer was matching by display label only (`existing_labels`). When the canonical promotion produced an item with label "Total Revenue" while the orphan candidate fact carried the raw label "Revenue", the dedup missed the match and re-added Revenue under `AdditionalItems`. `_collect_labels` now tracks both labels and concepts so the orphan check `(label or concept) in existing_labels` matches by either form.

## [5.30.1] - 2026-04-29

### Fixed

- **TTM income statement values labeled with wrong fiscal year for interim quarters** — When SEC re-filed comparative facts in next year's 10-Q (e.g., AGNC's Q1 2024 fact re-tagged with fiscal_year=2025 in a 2025 10-Q), `_deduplicate_by_period_end` kept the latest filing's version, and the TTM trend builder labeled the window with that comparative-shifted fiscal year. The result was duplicate column labels ("Q3 2025" appearing twice) that collided in the rendering layer's dict-keyed mapping, causing `Company('AGNC').income_statement(periods=12, period='ttm')` to display Q3 2024's TTM value under the "Q3 2025" column. The TTM calculator now derives the label fiscal year from `period_end + FYE` instead of the (potentially comparative-tagged) `as_of_fact.fiscal_year`. ([#793](https://github.com/dgunning/edgartools/issues/793))

- **Quarterly facts dropped for non-calendar FYE companies** — Fixed regression introduced in 5.30.0 where the schedule-fact filter from #781 incorrectly rejected Q1/Q2/Q3 facts for companies with non-calendar fiscal year ends (ADSK, WMT, NVDA, CSCO, MSFT). `Company('ADSK').income_statement(periods=4, annual=False)` returned only Q4 across years instead of Q1–Q4 of the most recent fiscal year. The fiscal-year/period-end validator is now FYE-aware. ([#779](https://github.com/dgunning/edgartools/issues/779))

- **`facts.time_series()` returned indistinguishable rows for overlapping periods** — When a company reported the same concept in both quarterly and YTD form (e.g., AGNC's `NetIncomeLoss` for `period_end=2025-06-30` had a 3-month Q2 row and a 6-month H1 YTD row), `time_series()` returned both with identical `period_end / fiscal_period / fiscal_year`, leaving users no way to tell them apart. Output now includes `period_start` and a derived `duration_days` column. ([#792](https://github.com/dgunning/edgartools/issues/792))

- **`download_submissions` not importable from `edgar.storage`** — Error messages in `edgar/reference/company_dataset.py` instructed users to run `from edgar.storage import download_submissions`, but the function was defined in `edgar/storage/_local.py` without being added to that module's `__all__`, so the star-import in `edgar/storage/__init__.py` did not re-export it. The advertised import path now works. ([#791](https://github.com/dgunning/edgartools/issues/791))

### Added

- **8-K item filtering in `search_filings()`** — `search_filings()` now accepts an `items` parameter that is forwarded server-side to EFTS, enabling structured Item-based queries without falling back to client-side filtering (which previously lost the long tail to pagination caps). The `query` parameter is now optional when `items` is provided, supporting pure-structured lookups such as `search_filings(forms="8-K", items="1.05", start_date="2023-12-01", end_date="2024-12-31")` for cybersecurity disclosures.

### Changed

- **`GrepResult` repr/str unified via rich panel** — `GrepResult.__repr__` now renders the same Rich Panel as `__repr_html__`, replacing the old compact `"GrepResult('pattern', N matches)"` summary. `__str__` has been removed; calling `str(result)` falls back to `__repr__`. Callers that want the prior plain-text dump should call `result.to_context()` explicitly.

## [5.30.0] - 2026-04-15

### Added

- **Proxy season analysis** — New `ProxySeason` and `ProxyContest` classes for grouping proxy filings by season and detecting contested elections. Market-wide discovery via `proxy_contests()` ([#773](https://github.com/dgunning/edgartools/issues/773))

- **Proxy HTML data extractors** — Extract structured data from DEF 14A proxy statements:
  - Summary Compensation Table (SCT) with executive pay details
  - CEO pay ratio with footnote cross-validation
  - Voting proposals with vote requirements and recommendations
  - Beneficial ownership tables
  - Director compensation tables
  - Audit fees by category

- **Full-text search enhancements** — Enriched EFTS search with relevance scores, aggregations, filtering, and pagination. New `.grep()` method for universal content search across filings

### Fixed

- **Fiscal year labels for non-calendar FYE companies** — Statement period labels for companies with early fiscal year ends (Jan–Mar) now use the industry-standard convention, matching the SEC, Bloomberg, and company earnings releases. NVIDIA Q3 ending Oct 2025 is now labeled "Q3 2026" (FY2026), not "Q3 2025" ([#779](https://github.com/dgunning/edgartools/issues/779))

- **Empty statements from forward-looking schedule data** — Companies like CLSK with XBRL-tagged footnote disclosures (expected amortization schedules) no longer produce phantom future periods that displace real quarterly data ([#781](https://github.com/dgunning/edgartools/issues/781))

- **Missing XBRL instance from SEC** — Fetch XBRL instance directly from SEC when local feed file lacks it ([#778](https://github.com/dgunning/edgartools/issues/778))

- **XBRL parsing for bytes content** — Hardened XBRL parser to handle bytes content and missing entity info without errors

- **Concept panel display in `viewer.search()`** — Restored section separator newlines inside Concept panels that were incorrectly removed in v5.29.0 ([#776](https://github.com/dgunning/edgartools/issues/776))

### Performance

- **Replace BeautifulSoup with lxml for proxy HTML** — Faster and more memory-efficient HTML parsing for proxy statement extraction

## [5.29.0] - 2026-04-12

### Added

- **`exact` parameter for `FactQuery.by_date_range()`** — New `exact=True` option matches facts with period dates exactly equal to the specified date, instead of the default `<=`/`>=` range behavior ([#767](https://github.com/dgunning/edgartools/issues/767))

- **`Company.reit_subtype` property** — New property distinguishes equity REITs from mortgage REITs by checking for mortgage-related XBRL concepts in the company's filings

- **Filing agent fingerprinting** — Detect the filing agent (Donnelley, EDGAR Online, Workiva, Toppan Merrill) from HTML structure patterns, enabling agent-aware document parsing

- **Agent-aware TOC parsing** — Table of contents section detection now uses agent-specific parsing strategies for the top 4 filing agents, improving section extraction accuracy

- **TOC section detection evaluation suite** — Evaluation harness for measuring TOC section detection quality across a corpus of filings

### Fixed

- **Extra newlines in `viewer.search()` output** — Removed spurious blank lines between sections in `Concept` panel display ([#768](https://github.com/dgunning/edgartools/issues/768))

- **`business_category` misclassifications** — Corrected 4 classification patterns for more accurate company categorization ([#774](https://github.com/dgunning/edgartools/issues/774))

- **YTD periods missing `fiscal_period` classification** — Year-to-date periods in XBRL facts now receive proper fiscal period labels ([#771](https://github.com/dgunning/edgartools/issues/771))

- **61 cash flow `gaap_mappings` defaulting to section totals** — Corrected mappings that incorrectly pointed to section-level totals instead of specific line items

- **Duplicate facts in XBRL DataFrame** — Deduplicate identical facts in `facts.to_dataframe()` output ([#769](https://github.com/dgunning/edgartools/issues/769))

- **`period_of_report` triggering network calls** — Resolved unintended network requests when accessing `period_of_report` for local storage users

### Performance

- **Cache parsed lxml tree** — Eliminate redundant HTML parsing by caching the parsed lxml tree across document operations

## [5.28.5] - 2026-04-08

### Fixed

- **HTML markup in disclosure DataFrame output** — `to_dataframe()` now strips HTML from XBRL TextBlock facts in disclosure/notes statements, producing clean plain text instead of raw markup. Uses the existing `_is_html`/`html_to_text` utilities. Includes regression test ([#762](https://github.com/dgunning/edgartools/issues/762))

- **Missing DividendsEquity standard concept for equity statement** — Added `DividendsEquity` to the equity vocabulary (`gaap_mappings.json`, `section_membership.json`, `display_names.json`), fixing GOOGL's `AdjustmentsToAdditionalPaidInCapitalDividendsInExcessOfRetainedEarnings` being unmapped on the equity statement ([#763](https://github.com/dgunning/edgartools/issues/763))

- **Entity rich display alignment** — `Entity` rich display now follows the same design language as `Company`, ensuring consistent visual presentation

### Documentation

- **Equity statement data layers guide** — New guide explaining why face statement totals, component breakdowns, and disclosure note values differ across XBRL data layers

## [5.28.4] - 2026-04-05

### Fixed

- **Q/YTD/FY period labels missing from equity and comprehensive income** — Equity and comprehensive income statements now receive the same Q1/Q2/Q3/Q4/YTD/FY column labels applied to income and cash flow statements ([#759](https://github.com/dgunning/edgartools/issues/759))

- **Incorrect StockRepurchasesEquity mapping** — Removed erroneous `StockRepurchasesEquity` standard concept mapping for tax withholding on vested shares, which caused misclassification on equity statements ([#760](https://github.com/dgunning/edgartools/issues/760))

- **Schedule 13D/G total\_shares and total\_percent overcounting** — Changed aggregation from `sum()` to `max()` to correctly represent reported totals rather than double-counting across rows

- **13F-HR TXT parser for pre-2013 filings** — Rewrote the 13F-HR TXT parser to use column-position extraction, added regex fallback and decimal handling, achieving ~93% coverage of pre-2013 filings ([#476](https://github.com/dgunning/edgartools/issues/476))

- **Standard concept name misspellings** — Corrected misspellings in standard concept names ([#758](https://github.com/dgunning/edgartools/issues/758))

### Documentation

- Document pre-2013 TXT format support and 93% coverage in 13F guides

## [5.28.3] - 2026-04-03

### Fixed

- **Wrong quarter labels for non-calendar fiscal years** — Quarter labels in financial statement columns now use the company's fiscal year end month instead of hardcoded calendar months. Affects companies like AAPL (Sep FY), WMT (Jan FY), NKE (May FY) ([#752](https://github.com/dgunning/edgartools/issues/752))

- **Period-type suffixes always present on DataFrame columns** — `to_dataframe()` now always includes period-type suffixes (Q1/Q2/Q3/Q4/YTD/FY) on all duration columns, not just when end dates collide ([#753](https://github.com/dgunning/edgartools/issues/753))

- **Incorrect Q4 fiscal year label for Jan-Mar FYE companies** — Companies with fiscal years ending in January through March (e.g., WMT) now receive the correct Q4/FY label rather than a label belonging to the following calendar year ([#754](https://github.com/dgunning/edgartools/issues/754))

- **Capex extraction broken by label regex** — Capital expenditure extraction now uses XBRL concept names (`PaymentsToAcquirePropertyPlantAndEquipment`, etc.) instead of fragile label regex matching, making it robust across filings with varied label text ([#756](https://github.com/dgunning/edgartools/issues/756))

## [5.28.2] - 2026-04-02

### Added

- **FDUS investment parser** — Add support for FDUS BDC investment parsing ([#747](https://github.com/dgunning/edgartools/issues/747))

### Fixed

- **business_category misclassifications** — Fix ETFs, SPACs, commodity trusts, and BDCs being misclassified. Adds SPAC name pattern detection, "ETF" name check for crypto/commodity ETFs, SIC 6200s fund/trust heuristic, removes over-broad "CAPITAL CORP" BDC name pattern, and uses authoritative 814- file number for BDC detection ([#561](https://github.com/dgunning/edgartools/issues/561))

- **to_dataframe() missing columns** — `to_dataframe()` now includes both quarterly and YTD columns when a filing contains both, instead of silently dropping one ([#743](https://github.com/dgunning/edgartools/issues/743))

- **13F values not normalized** — Normalize 13F holdings values to dollars across all periods ([#749](https://github.com/dgunning/edgartools/issues/749))

- **obj() routing for Schedule 13D/G** — `obj()` now correctly routes SC 13D/G forms to Schedule13D/13G parsers ([#748](https://github.com/dgunning/edgartools/issues/748))

- **find_ticker() wrong result** — Fix wrong company ticker returned for CIK 1506307 ([#745](https://github.com/dgunning/edgartools/issues/745))

- **download_filings in Jupyter** — Support `download_filings` in Jupyter notebook environments ([#744](https://github.com/dgunning/edgartools/issues/744))

- **reverse_name** — Replace with improved implementation for more accurate name reversal

- **Punctuation normalization** — Fix handling of digits and percent signs in text extraction

### Documentation

- Improve SEC Viewer guide with images, ConceptGraph section, and nav entry

## [5.28.1] - 2026-03-31

### Fixed

- **TOC section detection for split-link filings** — Filings where TOC item labels and descriptive titles link to different anchors (e.g., TSLA 10-K) now validate anchor targets against expected section headings, picking the correct anchor ([#742](https://github.com/dgunning/edgartools/issues/742))

- **Non-accrual extraction false positives** — Footnotes that explicitly deny non-accrual status (e.g., "there were no investments on non-accrual status") are no longer treated as positive matches. Replaced naive substring matching with two-stage negation-then-affirmation classification. Scored 50/50 on synthetic variations

- **Non-accrual period resolution** — `extract_nonaccrual()` now uses `filing.period_of_report` as anchor for period selection instead of picking the max instant date, which could resolve to filing dates or DEI dates instead of balance sheet dates. ARCC now correctly resolves to 2025-12-31

## [5.28.0] - 2026-03-30

### Added

- **FilingViewer — SEC Interactive Data Viewer** — New `FilingViewer` class provides access to the SEC's interactive XBRL viewer for any filing. Parses MetaLinks.json for concept-level metadata, extracts R*.htm viewer reports, and exposes structured period headers, numeric values, and scaling information

- **ConceptGraph — navigable XBRL knowledge graph** — New `ConceptGraph` class builds a traversable graph of XBRL concepts and their relationships, enabling structured navigation across the taxonomy hierarchy

- **BDC non-accrual extraction** — New `extract_nonaccrual()` function in `edgar.bdc.nonaccrual` extracts non-accrual investment data from BDC XBRL filings using three layered strategies: XBRL footnotes (investment-level detail), custom XBRL concepts (rate only), and standard us-gaap aggregate fallback

- **to_markdown() for LLM drill-down** — Notes, disclosures, and financial drill-down objects now expose `to_markdown()` for LLM-optimized output ([#732](https://github.com/dgunning/edgartools/issues/732))

- **compare_context() for LLM-based validation** — New method on XBRL objects for cross-validating parsed values against SEC viewer output using an LLM judge

- **Cross-validation bridge between SEC Viewer and XBRL parser** — `FilingViewer` and the XBRL parser can now be reconciled programmatically, with `to_dataframe()` and diagnostic outputs for systematic validation

- **MetaLinks.json parser** — Full parser for the SEC XBRL viewer's MetaLinks.json metadata file, exposing concept-level role, label, and calculation arc data

### Fixed

- **Abbreviations and inline spacing preserved in iXBRL text extraction** — Text extraction from iXBRL documents no longer splits abbreviations like `U.S.` into `U. S.` or `D.C.` into `D. C.`. Affects all inline XBRL filings ([#734](https://github.com/dgunning/edgartools/issues/734))

- **TOC part metadata parsing** — Table of contents part metadata is now correctly extracted ([#737](https://github.com/dgunning/edgartools/issues/737)) — contributed by external PR

- **Ruff code quality: 533 issues resolved** — Full codebase pass fixing lint, f-string, and style issues including a `LinkBlock.get_text()` f-string bug ([#740](https://github.com/dgunning/edgartools/issues/740))

### Documentation

- New SEC Viewer guide with full API reference for `FilingViewer` and `ConceptGraph`
- BDC guide updated with non-accrual analysis section and examples
- AI integration docs updated with expanded `to_context()` and `to_markdown()` coverage

## [5.27.0] - 2026-03-28

### Added

- **Dedicated 6-K data object** — New `SixK` class replaces the `CurrentReport` alias for Form 6-K (Report of Foreign Private Issuer). Extracts cover page metadata (commission file number, report month, annual report form, content description), provides exhibit access, press release filtering, and IFRS financials when present. Includes `to_context()` with cover page text at `full` detail level

- **S-1/F-1 registration statement data object** — New `RegistrationS1` class for S-1 and F-1 registration statements with cover page extraction, prospectus section access, and amendment support

- **DRS draft registration statement data object** — New `DraftRegistrationStatement` class for confidential draft registration statements (DRS/DRS-A)

- **Generic XML filing data object** — New `XmlFiling` class for XML+XSLT SEC forms (X-17A-5, TA-1, TA-2, SBSE, ATS-N-C, CFPORTAL, etc.) with automatic XSLT rendering

- **24F-2NT fund fee notice data object** — New `FundFeeNotice` class for annual notices of securities sold by registered investment companies

- **497K fund summary prospectus data object** — New `Prospectus497K` class for 497K fund summary prospectus filings

- **F-1/F-1A foreign registration support** — `RegistrationS1` now accepts F-1 and F-1/A forms for foreign private issuer IPO registrations

- **F-3 foreign shelf registration support** — `RegistrationS3` now accepts F-3, F-3/A, and F-3ASR forms

- **EightK improvements** — New `content_type` property classifying 8-K filings (earnings, cybersecurity, restructuring, etc.), `is_amendment` property, `get_exhibit()` and `get_exhibits()` methods, and context-aware `to_context()` that adjusts available actions based on content type

### Fixed

- **8-K section boundary captures full body text** — HTMLParser section detection now correctly extends section boundaries past table-wrapped item headings to include all body paragraphs until the next section ([#733](https://github.com/dgunning/edgartools/issues/733))

- **gaap_mappings: PaymentsToDevelopSoftware and PaymentsForSoftware** — Both were incorrectly mapped to `NetCashFromInvestingActivities` (section total) instead of `PurchaseOfIntangibleAssets` (component line item) ([#739](https://github.com/dgunning/edgartools/issues/739))

- **Infinite recursion in html() for XML-primary filings** — `html()` no longer recurses when the primary document of S-1/S-3 filings is XML rather than HTML

- **MunicipalAdvisorForm assert narrowed** — Assert restricted to MA-I only; MA form now routes to `XmlFiling`

### Documentation

- New data object guides: Form 6-K, S-1, DRS, EFFECT, 24F-2NT, XML filings
- F-3 foreign shelf registration forms added to S-3 guide
- MCP docs rewritten with real examples and corrected setup instructions

## [5.26.1] - 2026-03-26

### Fixed

- **MCP tool definitions: `outputSchema` removed** — `outputSchema` was included in all MCP tool definitions, which is not part of the MCP protocol spec. Claude Desktop rejected every tool call, blocking all MCP usage entirely. Removing the field restores full MCP functionality ([#735](https://github.com/dgunning/edgartools/issues/735))

- **`edgar_notes` next-steps reference** — `edgar_notes` referenced a non-existent tool name in its `next_steps` guidance; corrected to a valid tool

- **`edgar_screen` state filter silently dropped** — State filter was silently discarded on queries that specified only an exchange (no SIC code), causing state-filtered screening to return unfiltered results

- **`edgar_compare` growth metrics broken** — Growth metric calculation failed because `time_series` fetched insufficient periods; fetch count increased to ensure enough data points are available

### Improved

- **MCP documentation reorganised** — `ai-integration.md` split into five focused pages (`ai/index.md`, `ai/mcp-setup.md`, `ai/mcp-tools.md`, `ai/mcp-workflows.md`, `ai/skills.md`) for easier navigation. Parameter defaults and required-field annotations corrected across all pages

## [5.26.0] - 2026-03-25

### Added

- **CORRESP/UPLOAD correspondence support** — New `Correspondence` and `CorrespondenceThread` classes parse SEC correspondence filings with automatic classification (company_response, acceleration_request, sec_comment, review_complete, no_review) and metadata extraction (file number, referenced form, fiscal year). `Filing.correspondence()` works on any filing type to find related SEC review threads via file number

- **Point-in-Time mode for EntityFacts** — `EntityFacts.to_dataframe()` now accepts a `pit_mode` parameter that includes `filing_date` and `form_type` columns, enabling lookahead-bias-free backtesting by filtering on `filing_date <= as_of_date` ([#697](https://github.com/dgunning/edgartools/issues/697))

- **S-3 shelf registration data object** — New `RegistrationS3` class with fee table extraction from EX-FILING FEES exhibits (Exhibit 107) supporting 5 HTML format variations, `ShelfLifecycle` with shelf capacity and offering capacity properties, prospectus section access with 16 section patterns, and auto-shelf detection for well-known seasoned issuers ([#728](https://github.com/dgunning/edgartools/issues/728))

- **TTM unification on EntityFacts** — Unified TTM access on `EntityFacts` with streamlined `Company` delegation. TTM-ready facts are cached for performance. Quarter labels now use fiscal year (PR [#721](https://github.com/dgunning/edgartools/pull/721), ghedo44)

### Fixed

- **TOC named-anchor targets** — Table-of-contents anchor matching centralized and now correctly resolves named-anchor targets ([#727](https://github.com/dgunning/edgartools/pull/727))

- **Revenue in income statement dedup** — Revenue now included in the promoted income statement deduplication set

- **Shares concepts preserved in statements** — Shares-denominated concepts (EPS, shares outstanding) are no longer dropped from income statements during unit filtering (PR [#725](https://github.com/dgunning/edgartools/pull/725), ghedo44)

- **TypeError in `_get_statement_concepts`** — Fixed crash when statement type is `None` by using `or ''` fallback instead of relying on `dict.get()` default

- **Unit filter documentation** — Docstrings updated to reflect native-unit filtering behavior

### Improved

- **EntityFacts memory usage reduced 27%** — String interning deduplicates high-repetition fields (taxonomy, unit, fiscal_period, form_type, concept) from ~99K objects to ~1.6K. Per-concept work hoisted out of per-fact loop, dimensions default changed to `None`, period index key caching added. Measured on AAPL: 20.5 MB → 15.0 MB

### Data

- Bundled ticker and CUSIP reference data refreshed (10,652→10,769 tickers, deduplicated CUSIPs)

## [5.25.1] - 2026-03-19

### Added

- **BDC health metrics** — `PortfolioInvestments` now exposes `nonaccrual_fair_value`, `non_accrual_rate`, `pik_investments`, `pik_fair_value`, and `pik_exposure` properties. Non-accrual data is extracted from the entity-level XBRL concept `us-gaap:FairValueOptionLoansHeldAsAssetsAggregateAmountInNonaccrualStatus`. Rich display shows color-coded non-accrual and PIK summary lines

### Fixed

- **Pickle serialization of XBRL objects** — Replaced `weakref` with strong references in `Note`, `StatementLineItem`, `FilingSummary`, and `WeakCache`. Weak references caused `pickle.dumps()` to fail on these objects, breaking caching and multiprocessing workflows

## [5.25.0] - 2026-03-18

### Added

- **Statement-to-note drill-down** — Navigate from any financial statement line item to the note that explains it. `balance_sheet['Cash and cash equivalents'].note` returns the related `Note` object via a lazy-built reverse index that maps XBRL concepts to notes — the same mechanism the SEC's own EDGAR viewer uses

- **`Note` and `Notes` classes** — First-class objects for financial statement notes, built from FilingSummary.xml hierarchy. Access via `tenk.notes` or `tenq.notes`. Browse by number (`notes[5]`), title (`notes['Debt']`), or fuzzy search (`notes.search('revenue')`). Each note exposes `.tables`, `.policies`, `.details`, `.text`, `.html`, `.expands` (which statement lines it explains), and `.to_context()` for AI consumption

- **`StatementLineItem`** — Lightweight wrapper returned by `Statement.__getitem__` with `.label`, `.concept`, `.note` (most relevant note), `.notes` (all related), and `.values`. Uses `__slots__` for minimal memory footprint

- **`Statement.search()`** — Fuzzy search for statement line items with ranked results (exact > startswith > word match > substring). Complements the exact-match `__getitem__`. Consistent with the `Notes.search()` pattern

- **`Statement.report` property** — Links to the FilingSummary `Report` for HTML table access. Enables `note.tables[0].report.to_dataframe()` for HTML-extracted DataFrames alongside the XBRL path

- **`RenderedStatement.__getitem__`** — Look up rows by exact label (case-insensitive) on rendered statements

- **`edgar_notes` MCP tool** — New tool for AI agents to drill into notes and disclosures by company and topic. Returns structured note content, related statement lines, and child table data. Surfaces the detail behind financial statement numbers that no other SEC MCP server exposes

- **`CompanyReport.notes`** — Cached property on TenK/TenQ providing hierarchical notes access from report objects

- **`TenK.to_context(focus=...)` / `TenQ.to_context(focus=...)`** — Focus mode generates cross-cutting context for specific topics (e.g., `focus='debt'`), pulling statement line items, note content, and policies together

- **Role type definitions from schema** — XBRL parser now extracts human-readable role definitions from taxonomy schemas, improving statement and note titles

### Improved

- **XBRL memory optimizations** — Label role URI strings are now interned via `sys.intern()`, eliminating ~10,000 duplicate URL string allocations per filing. `comparison_data` removed from `RenderedStatement.metadata` (was stored but never read back). Duplicate `_collect_note_concepts` tree walks eliminated in `expands_statements`

- **`Statement.__getitem__` is now exact-match only** — Previously used substring fallback that could silently return wrong rows for ambiguous queries like `stmt['Total']`. Now returns the correct match or `None`. Use `stmt.search()` for fuzzy lookups

### Fixed

- **Drill-down required notes pre-load** — Accessing `stmt['Debt'].note` before `tenk.notes` produced empty results because notes were built without FilingSummary. Now the XBRL object stores its FilingSummary during `from_filing()` so the lazy notes builder always gets the full hierarchy

## [5.23.3] - 2026-03-15

### Fixed

- **Duplicate rows from XBRL concept renames** — When companies switch XBRL concepts between years (e.g. AAPL switching from `aapl:` company extension to `us-gaap` concepts), Comprehensive Income and other statements showed duplicate rows with complementary NaN values. A new `_merge_complementary_rows()` pass detects adjacent same-label rows with non-overlapping period values and merges them into a single row

- **EntityFacts duplicate labels from orphan concept renames** — Balance sheet from `get_facts()` showed duplicate rows (e.g. Accounts Receivable, Inventory, Accounts Payable) when a concept rename caused the same data to appear in both the main tree and the Additional Items section. Orphan facts whose label already exists in the main tree are now skipped

- **EarningsRelease scale detection** — Scale was incorrectly detected as "billions" for companies like GOOG because `Scale.detect()` matched bare words like "billion" in narrative text. Now uses parenthetical patterns `(in millions)` / `(dollars in millions)` which appear near financial tables ([#693](https://github.com/dgunning/edgartools/issues/693))

- **EarningsRelease cash flow misclassification** — GOOG EPS showed $0.00 because a 34-row cash flow table was misclassified as income statement due to "net income" and "accrued revenue share" keywords. Added strong cash flow keywords and expanded row scan range from 20 to 40 rows ([#700](https://github.com/dgunning/edgartools/issues/700))

- **IdentityNotSetException swallowed by SGML fallback** — Missing EDGAR identity now raises a clear `IdentityNotSetException` instead of silently falling back to the homepage index ([#707](https://github.com/dgunning/edgartools/issues/707))

- **ComprehensiveIncome Resolver Fallback for Historical Filings** — `comprehensive_income()` now returns a `Statement` for older filings (pre-2015) that embed OCI data within the equity rollforward statement. The resolver falls back to the equity statement when it contains CI concepts. Affected companies include IBM, GE, Ford, and TSLA for 10-K filings from 2009-2013 ([#706](https://github.com/dgunning/edgartools/issues/706))

- **14 Jupyter notebooks broken by recent API changes** — Updated all notebooks to use current API patterns ([#708](https://github.com/dgunning/edgartools/issues/708))

### Added

- **Foreign filer support in `get_financials()`** — Falls back to 20-F (foreign private issuers) and 40-F (Canadian filers) when no 10-K exists. `get_quarterly_financials()` falls back to 6-K. Companies like AZN, TM, TD now return financials

- **`clear_company_facts_cache()`** — New public function to free memory from previously loaded EntityFacts objects in long-running processes

### Improved

- **Company class memory footprint** — Company facts cache reduced to 1 entry (~25MB ceiling), `FinancialFact` uses `slots=True`, SIC/ticker resolution deferred to statement-build time to avoid unnecessary submissions downloads ([#705](https://github.com/dgunning/edgartools/issues/705))

- **EarningsRelease exhibit selection** — `from_filing()` now tries multiple EX-99.* exhibits when the first one lacks an income statement, instead of always using EX-99.1

- **`Company.facts` cached** — Changed from `@property` to `@cached_property` to prevent redundant `get_facts()` calls

## [5.23.0] - 2026-03-11

### Added

- **424B Prospectus Parser** — New multi-phase parser for 424B prospectus filings (424B1 through 424B8). Extracts cover page data, classifies offering types (firm commitment, ATM, best efforts, PIPE resale, structured notes, debt offerings, and more), and parses underwriting terms, selling stockholder tables, and structured note payoff details. Access via `filing.obj()` on any 424B filing ([9975dd67](https://github.com/dgunning/edgartools/commit/9975dd67))

- **Deal Object** — `Deal` provides a normalized summary of a 424B prospectus including issuer, security type, pricing, aggregate proceeds, underwriters, and key dates. Condenses complex prospectus data into a single structured object ([1035846a](https://github.com/dgunning/edgartools/commit/1035846a))

- **ShelfLifecycle Object** — `ShelfLifecycle` traces a shelf registration (S-3) through its full lifecycle: original filing, effectiveness date, takedowns (424B filings), amendments, and expiration. Computes review period, cadence metrics, and remaining capacity ([0057e00d](https://github.com/dgunning/edgartools/commit/0057e00d))

- **XBRL Filing Fees Extraction** — 424B filings that embed XBRL fee exhibits are now parsed, extracting fee tables, total offering amounts, and registration fees ([64abd16d](https://github.com/dgunning/edgartools/commit/64abd16d))

- **Selling Stockholders** — Extracts selling stockholder tables with numeric properties (`shares_before`, `shares_offered`, `shares_after`, `pct_before`, `pct_after`), warrant support, and `to_dataframe()` output ([3987131d](https://github.com/dgunning/edgartools/commit/3987131d))

- **to_context() for AI Workflows** — `Prospectus424B.to_context()` and `ShelfLifecycle.to_context()` produce condensed text summaries suitable for LLM context windows ([f3b6d283](https://github.com/dgunning/edgartools/commit/f3b6d283))

### Fixed

- **XBRLS Detailed View Overwriting Totals** — Dimensional segment rows in stitched statements were overwriting parent total values (e.g., Goodwill 7,970M replaced by segment 650M). Stitching now skips `is_dimension` rows so totals are preserved ([#687](https://github.com/dgunning/edgartools/issues/687)) ([be898b30](https://github.com/dgunning/edgartools/commit/be898b30))

- **Filer Type Classification** — ~955 companies lack `state_of_incorporation` data, causing `filer_type` to return `None`. Now infers filer type from recent filing forms: 40-F → Canadian, 20-F/6-K → Foreign, 10-K/10-Q → Domestic. Also classifies ADR deposits, UITs, investment company funds, and crowdfunding issuers ([#562](https://github.com/dgunning/edgartools/issues/562)) ([7e827bc4](https://github.com/dgunning/edgartools/commit/7e827bc4), [be898b30](https://github.com/dgunning/edgartools/commit/be898b30))

- **Small Business Form Hyphens** — Corrected form names `10KSB` → `10-KSB`, `10QSB` → `10-QSB` to match SEC EDGAR data format ([eeea01d4](https://github.com/dgunning/edgartools/commit/eeea01d4))

- **Document Stitching Dimension Skip** — Stitching dimension skip now applies unconditionally since the stitcher uses concept as dict key and cannot yet differentiate segments from totals when both share the same concept ([eeea01d4](https://github.com/dgunning/edgartools/commit/eeea01d4))

- **424B Parser Bug Fixes** — 17 bugs fixed across two review passes covering cover page extraction, table classification, offering type detection (424B4 classification improved from 0% → 100%), and selling stockholder table detection ([73f594cf](https://github.com/dgunning/edgartools/commit/73f594cf), [1180e8d0](https://github.com/dgunning/edgartools/commit/1180e8d0), [962766bf](https://github.com/dgunning/edgartools/commit/962766bf), [58dc4afb](https://github.com/dgunning/edgartools/commit/58dc4afb))

### Performance

- **424B HTML Parsing** — Parse HTML once per 424B prospectus instead of 4 times, reducing parse time significantly ([3eb81c12](https://github.com/dgunning/edgartools/commit/3eb81c12))

- **ShelfLifecycle Speed** — Lifecycle construction now uses SGML `file_number` and skips full filing loads, making lifecycle queries substantially faster ([466a80bb](https://github.com/dgunning/edgartools/commit/466a80bb))

### Changed

- **CI Test Matrix** — Reduced test matrix from 4 Python versions to 3.10 and 3.13 only ([6d6674de](https://github.com/dgunning/edgartools/commit/6d6674de))

- **Fast Test Suite Cleanup** — Moved 195 misclassified network tests out of the fast test suite and fixed `xbrl_balance_weight` network tests leaking into fast tests ([fb8a8974](https://github.com/dgunning/edgartools/commit/fb8a8974), [e31e8d38](https://github.com/dgunning/edgartools/commit/e31e8d38))

## [5.22.0] - 2026-03-08

### Added

- **Data-Driven Concept Mappings** — Replaced hand-maintained `gaap_mappings.json` (2,077 tags, 96 concepts) with a data-driven `concept_mappings.json` built from analysis of 32,240 real SEC filings (2,770 tags, 234 concepts). Each entry carries embedded metadata: display name, section, is_total flag, confidence, company count, temporal consistency, and industry overrides ([bd73e838](https://github.com/dgunning/edgartools/commit/bd73e838))

- **Industry-Aware XBRL Standardization** — Industry overrides (769 entries mapped across Fama-French 48 industries) automatically resolve 42 ambiguous tags and correct 725 is_total signals per industry. SIC codes are now mapped to FF48 industry codes for automatic industry detection when parsing filings ([bd73e838](https://github.com/dgunning/edgartools/commit/bd73e838))

- **150 IFRS Tag Mappings** — Added 150 `ifrs-full_` prefixed tag mappings for international filer standardization, improving coverage for 20-F filers. Verified on Novo Nordisk 20-F: 93% income statement, 78% balance sheet, 76% cash flow coverage ([d643805c](https://github.com/dgunning/edgartools/commit/d643805c))

- **Standardization Integrated into Stitching** — Industry-aware standardization is now threaded through the multi-filing stitching system, giving consistent concept normalization across all historical filing periods ([48b1fa30](https://github.com/dgunning/edgartools/commit/48b1fa30))

### Fixed

- **XBRL Stitching: Same-Label Row Merging** — When companies switch XBRL concepts between fiscal years (e.g., `aapl:DerivativeInstrument` to `us-gaap:CashFlowHedge`), the presentation tree now merges duplicate rows with complementary period values using value-agreement as a safety guard ([#572](https://github.com/dgunning/edgartools/issues/572)) ([031d1042](https://github.com/dgunning/edgartools/commit/031d1042))

- **XBRL Stitching: Concept Alias Merging** — Concept name variant detection now uses pairwise matching with two guards (substring containment + value agreement) to correctly coalesce aliased totals (e.g., Disney's `*ContinuingOperations` → plain variant) without incorrectly merging unrelated sub-items ([#642](https://github.com/dgunning/edgartools/issues/642)) ([fa4f457b](https://github.com/dgunning/edgartools/commit/fa4f457b))

- **XBRL Stitching: Equivalent Standard Concepts** — Introduces `_EQUIVALENT_STANDARD_CONCEPTS` to unify rows where companies changed between economically identical concepts (e.g., `CashAndCashEquivalents` vs `CashAndMarketableSecurities`) that map to different standard concepts ([#610](https://github.com/dgunning/edgartools/issues/610)) ([aec58dca](https://github.com/dgunning/edgartools/commit/aec58dca))

- **XBRL Stitching: Missing Statement Handling** — Stitching no longer aborts when a filing lacks the requested statement type (e.g., VALE 20-F filings without a cash flow presentation role). The period is now skipped gracefully ([#683](https://github.com/dgunning/edgartools/issues/683)) ([d799120a](https://github.com/dgunning/edgartools/commit/d799120a))

- **Dimensional Total Synthesis** — When a concept has only dimensional facts (e.g., DIS `CostOfGoodsAndServicesSold` broken into Service + Product on ProductOrServiceAxis) with no non-dimensional total, the correct aggregate is now computed by summing the dimensional members ([#646](https://github.com/dgunning/edgartools/issues/646)) ([0ba5bc52](https://github.com/dgunning/edgartools/commit/0ba5bc52))

- **IFRS Statement Misclassification** — IFRS filers like SNY had `income_statement()` and `comprehensive_income()` resolving to the same statement. Fixed by adding IFRS concept classification in Phase 1, removing ambiguous overlap, and adding P&L role pattern with IFRS scoring boost ([#673](https://github.com/dgunning/edgartools/issues/673)) ([a2fd8225](https://github.com/dgunning/edgartools/commit/a2fd8225))

- **Preferred Sign Applied in to_dataframe()** — `Statement.to_dataframe()` now defaults to `presentation=True`, matching the sign conventions shown in Rich rendering. `StitchedStatement.to_dataframe()` also preserves and applies `preferred_sign`, including contra accounts like Treasury Stock on the balance sheet ([#669](https://github.com/dgunning/edgartools/issues/669)) ([2d795630](https://github.com/dgunning/edgartools/commit/2d795630))

- **Document.to_markdown() Import Error** — Fixed incorrect import path `markdown_renderer` → `markdown` in `Document.to_markdown()` ([#684](https://github.com/dgunning/edgartools/issues/684)) ([b6107ef8](https://github.com/dgunning/edgartools/commit/b6107ef8))

- **Document.to_json() AttributeError** — `Document.to_json()` no longer raises `AttributeError: 'str' object has no attribute 'to_dict'` when `xbrl_data` is stored as a dict. The parser now assigns the fact list directly ([#685](https://github.com/dgunning/edgartools/issues/685)) ([e8e6e695](https://github.com/dgunning/edgartools/commit/e8e6e695))

- **Standardization Bug Fixes** — Resolved 5 correctness bugs: Coal/Mines SIC range overlap, incorrect ambiguity flag on override, O(n²) linear scan replaced with O(1) dict lookup, dual `ReverseIndex` singleton, and raw data mutation on `statement_type` field ([d681caec](https://github.com/dgunning/edgartools/commit/d681caec))

- **Non-Numeric Value Comparison Guard** — `_merge_same_label_line_items` no longer crashes with `TypeError` when XBRL fact values are strings (e.g., Boeing, Carrier). The numeric tolerance check is now wrapped in a try/except ([03b8d4c6](https://github.com/dgunning/edgartools/commit/03b8d4c6))

- **Regression Test Updates** — Updated 7 regression test files for current API: `financials.cashflow_statement()` method call, `Statement.role_or_type` attribute, `abs()` for preferred_sign-affected COGS assertions, and `xbrl_data` list format ([78ae478e](https://github.com/dgunning/edgartools/commit/78ae478e))

## [5.21.1] - 2026-03-06

### Fixed

- **8-K Table Scale Detection** — The 8-K parser now detects table scale (e.g., "in thousands") from preceding paragraph nodes, not just the table header, producing correct financial values ([#633](https://github.com/dgunning/edgartools/issues/633)) ([9f920af3](https://github.com/dgunning/edgartools/commit/9f920af3))

- **Local Storage Check in full_text_submission()** — `full_text_submission()` now checks local storage before downloading from SEC, avoiding unnecessary network calls when filings are already cached locally ([#681](https://github.com/dgunning/edgartools/issues/681)) ([0cdde2f3](https://github.com/dgunning/edgartools/commit/0cdde2f3))

- **Dimensional Member Hierarchy in to_dataframe()** — Statement `to_dataframe()` now preserves the dimensional member hierarchy, maintaining the correct parent-child relationships for XBRL dimensions ([4f5797d1](https://github.com/dgunning/edgartools/commit/4f5797d1))

### Docs

- **get_fact() Examples Corrected** — Fixed `get_fact()` documentation examples to use valid XBRL concept names ([#618](https://github.com/dgunning/edgartools/issues/618)) ([d768a049](https://github.com/dgunning/edgartools/commit/d768a049))

## [5.21.0] - 2026-03-05

### Added

- **MCP Streamable HTTP Transport** — The MCP server now supports remote deployment via Streamable HTTP transport in addition to stdio. Start with `edgartools-mcp --transport streamable-http --port 8000` for team servers, registry listings, and containerized deployments. Clients connect with a simple URL instead of launching a subprocess. stdio remains the default and is unchanged ([2aa48f71](https://github.com/dgunning/edgartools/commit/2aa48f71))

- **edgar_proxy MCP Tool** — New tool for DEF 14A proxy statement data including executive compensation and pay-vs-performance ([2a39871b](https://github.com/dgunning/edgartools/commit/2a39871b))

- **edgar_fund MCP Tool** — New tool for fund, ETF, BDC, and money market fund data with actions for lookup, search, portfolio, and more ([a531baa8](https://github.com/dgunning/edgartools/commit/a531baa8))

- **MCP Analysis Prompts** — Added fund_analysis, filing_comparison, and activist_tracking pre-built analysis workflows ([6e446997](https://github.com/dgunning/edgartools/commit/6e446997))

- **Structured Error Classification in MCP** — Tool errors are now classified with error codes, user-friendly messages, and actionable suggestions ([3a65e37a](https://github.com/dgunning/edgartools/commit/3a65e37a))

- **AI Skills Expansion** — Added error recovery patterns, BDC/MMF coverage, and statement hierarchy documentation to AI skills ([291f679c](https://github.com/dgunning/edgartools/commit/291f679c))

### Fixed

- **Recent IPO Tickers Not Resolving** — `Company(ticker)` now falls back to the live SEC `company_tickers.json` when a ticker is missing from the bundled parquet data. The live data is fetched at most once per session and cached, so existing tickers still resolve instantly with no network call ([#676](https://github.com/dgunning/edgartools/issues/676)) ([8caca1a3](https://github.com/dgunning/edgartools/commit/8caca1a3))

- **Refreshed Bundled Ticker Data** — Updated `company_tickers.parquet` from 10,532 to 10,652 tickers, adding 302 new tickers including recent IPOs ([e7e2076c](https://github.com/dgunning/edgartools/commit/e7e2076c))

- **MCP Runtime Bugs** — Fixed issues across proxy, ownership, company, and prompts tools including None proxy handling, Decimal(0) falsiness, and missing tool registrations ([78c83d4c](https://github.com/dgunning/edgartools/commit/78c83d4c), [59c1c4f3](https://github.com/dgunning/edgartools/commit/59c1c4f3), [883a4d1a](https://github.com/dgunning/edgartools/commit/883a4d1a))

- **None balance_sheet Guard** — Protected against None balance_sheet in issue 412 regression tests ([e7dde317](https://github.com/dgunning/edgartools/commit/e7dde317))

- **README Images on PyPI** — Switched to absolute URLs so images render correctly on PyPI ([7f1d3eb7](https://github.com/dgunning/edgartools/commit/7f1d3eb7))

### Changed

- **Test Suite Consolidation** — Deleted 18 redundant test files and reduced 6,200 lines. Added VCR cassettes for 17 metadata tests. CI matrix reduced from 12 to 6 jobs ([474179f9](https://github.com/dgunning/edgartools/commit/474179f9), [85cd6db7](https://github.com/dgunning/edgartools/commit/85cd6db7))

- **MCP Documentation** — Updated docs for all 11 tools and 7 prompts, added HTTP transport setup guide ([5cc4fea1](https://github.com/dgunning/edgartools/commit/5cc4fea1))

## [5.20.2] - 2026-03-04

### Fixed

- **Homepage Fallback When SGML Unavailable** — When the SEC returns empty content for a filing's full submission text (.txt), `Filing.sgml()` now falls back to the filing's homepage index page instead of raising an exception. The fallback provides document attachments with valid URLs for `html()`, `xml()`, `xbrl()`, and `text()`. Network errors and permanent errors (identity, not-found) still propagate correctly ([#674](https://github.com/dgunning/edgartools/issues/674))

- **Cache Bypass Actually Works Now** — The 5.20.1 retry-with-cache-bypass for empty SGML responses was silently ineffective because `httpxthrottlecache` reuses a single client instance, ignoring `bypass_cache` after initial creation. The retry now uses a direct `httpx` request that completely bypasses the cache layer ([#672](https://github.com/dgunning/edgartools/issues/672))

- **BDC Pipe-Separated Investment Identifiers** — Recent BDC filings (e.g., Blue Owl) use pipe-separated format (`Company | Type | Issuer Category`) for investment identifiers instead of comma-separated. The parser now handles both formats

## [5.20.1] - 2026-03-03

### Fixed

- **Empty SEC Responses Permanently Cached** — Empty or error responses from SEC SGML endpoints were stored in the local cache indefinitely, meaning subsequent requests would silently return empty content rather than retrying against the network. The fetcher now detects empty/error payloads and retries once with cache bypass before giving up ([#672](https://github.com/dgunning/edgartools/issues/672)) ([45574373](https://github.com/dgunning/edgartools/commit/45574373))

- **Automatic Cache Clear on Upgrade** — On first run after upgrading to 5.20.1, the local SGML cache is automatically cleared once to remove any stale empty responses that were cached under prior versions. No manual intervention required ([45574373](https://github.com/dgunning/edgartools/commit/45574373))

- **Graceful Test Skip on Transient SEC Responses** — Network tests that exercise SGML downloads now detect transient empty responses from SEC and skip with an informative message instead of failing the suite ([4fc4a889](https://github.com/dgunning/edgartools/commit/4fc4a889))

## [5.20.0] - 2026-03-02

### Added

- **Fund Data Object Improvements** — Performance, cohesion, and memory safety improvements across fund data objects ([0b020c3](https://github.com/dgunning/edgartools/commit/0b020c3))

- **`fact_id` in XBRL Facts DataFrame** — The unique fact identifier is now exposed in the XBRL facts DataFrame for traceability and cross-referencing ([0785b87](https://github.com/dgunning/edgartools/commit/0785b87))

### Fixed

- **SGML Parser Diagnostic Errors** — "Unknown SGML format" errors now include content previews, response length, and pattern-specific messages for rate limiting, empty responses, and SEC error pages ([bf8a58a](https://github.com/dgunning/edgartools/commit/bf8a58a))

- **BDC Test Reliability** — Switched BDC integration tests from ARCC to Blue Owl (CIK 1812554) due to ARCC's latest 10-K returning empty content from SEC ([84c58ee](https://github.com/dgunning/edgartools/commit/84c58ee))

### Documentation

- **Fund Entity Guide** — Added comprehensive fund entity guide, updated data-objects index, and created fund AI skill YAML ([140aaa2](https://github.com/dgunning/edgartools/commit/140aaa2))

---

## Older Releases

For releases **prior to 5.20.0** (5.19.1 and earlier, including all 4.x and 3.x history), see [CHANGELOG-archive.md](CHANGELOG-archive.md).
