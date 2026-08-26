# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **`get_financials()` no longer goes quiet on a filing that has no XBRL.** A company whose latest annual report predates SEC's 2009-2011 XBRL phase-in got a `Financials` object back — a truthy one, so the documented `if financials is not None:` guard passed — whose `income_statement()`, `balance_sheet()` and `cash_flow_statement()` then all returned `None` with nothing said at any level. `Company(104599).get_financials()`, Circuit City's 2008 10-K, is the case. That path now emits a `FutureWarning` naming the filing and raises `XBRLFilingWithNoXbrlData` in 6.0; set `EDGARTOOLS_STRICT_ERRORS=1` for the 6.0 behaviour today. The object itself is unchanged in 5.x, so nothing you branch on today moves.

  `XBRLFilingWithNoXbrlData` was never actually raised anywhere, which is why this was silent: the two `except` clauses written for it — in `Financials.extract` and `Filing.xbrl` — were dead code that read as handling. Both are gone, and the error is raised for the first time. `filing.xbrl()` still answers `None` for a filing without XBRL, quietly, in 5.x and in 6.0: that is a true absence rather than a failure.

### Fixed

- **`FundSeries.get_filings()` answered with the whole trust's filings.** It delegated to the fund company, and a trust files one NPORT-P per series per quarter under one CIK, so the newest belonged to whichever sibling filed last. Vanguard's Extended Market Index (S000002841) and 500 Index (S000002839) both returned 325 filings topped by `0000036405-26-000325` — the 500 Index report — giving the fund that excludes the S&P 500 that index as its portfolio. It now resolves through browse-edgar. (GH #1143)

## [5.53.0] - 2026-08-25

### Changed

- **httpx is now capped below 0.29.** httpx upstream has been dormant since 0.28.1 (December 2024) and stopped accepting issues in February 2026, so any future release on PyPI would be unexpected and should not be adopted automatically. Installs resolve to 0.28.1 exactly as before; the planned successor is the httpx2 migration in 6.0.

- **Filing homepage parsing is about 9x faster.** The filing index page — the source of `filing.attachments`, `filing.homepage.get_filers()` and the filing dates — was parsed with BeautifulSoup's pure-Python `html.parser`; it now uses lxml, measured at 15.8ms to 1.8ms across the five tracked homepage fixtures. Output is unchanged: the whole parse of every fixture, down to each attachment's size and each filer's identification lines, is pinned against a baseline captured from the previous implementation. A blank or truncated index page still yields a homepage with nothing on it rather than raising.

  `FilingHomepage(...)` and `Attachments.load(...)` take an lxml tree now, from the new `edgar.attachments.parse_homepage_html(html)`. Both still accept a BeautifulSoup, and `FilingHomepage(soup=...)` still works, with a `DeprecationWarning`; both go in 6.0. Neither is on the path you take through `filing.homepage`.
- **R-file report rendering parses about 20x faster.** `filing.reports`, `TenK.reports` and `Report.view()`/`.text()` parsed each R-file with BeautifulSoup's pure-Python `html.parser`; they now use lxml, measured at 438ms to 22ms over the 42 R-files of a tracked AAPL 10-Q. End to end the render is 1.8x faster (1217ms to 680ms) — the remaining time is table layout, not parsing. Output is unchanged: the rendered text of all 42 reports is pinned against a baseline captured from the previous implementation, covering both the ordinary single-table path and the embedded-table path added for issue #755.

- **Note text extraction is about 6x faster.** The narrative and table text behind `note.to_context()` and `notes.to_markdown()` was parsed with BeautifulSoup's pure-Python `html.parser`; it now uses lxml, measured at 477ms to 80ms over 16 real note TextBlocks from three filers. The emitted text is unchanged, which matters more here than the speed: this is what an LLM reads. Narrative in both modes, the per-table markdown render, and every table's aligned plain text are pinned character-for-character against a baseline captured from the previous implementation.
- **DRS underlying-form detection is about 7x faster, and stops warning about the filings it handles.** A `DRS`/`DRS-A` filing only says "DRS" in its metadata — the real form (S-1, F-1, 20-F, Form 10) has to be read off the cover page — and that read was done with BeautifulSoup; it now uses lxml, measured at 1481ms to 197ms over 12MB of real filings. Modern DRS filings are inline XBRL, and BeautifulSoup printed an `XMLParsedAsHTMLWarning` for every one of them: three of the eight filings in the new corpus warned before this change and none do now. Detection is unchanged, pinned against a baseline captured from the previous implementation over seven real filings — a genuine S-1, three 8-Ks from 2001, 2004 and 2008, a 20-F and two modern iXBRL filings — plus seventeen inputs written for the ways lxml and BeautifulSoup disagree about text.

- **Fund reference data resolves its download URL about 14x faster.** `get_fund_reference_data()`, `find_fund()` and the class/series lookups behind them start by reading the SEC's investment-company series-and-class listing page to find the current CSV, and that page was parsed with BeautifulSoup's pure-Python `html.parser`; it now uses lxml, measured at 13.1ms to 0.9ms on the live 96KB page. The URL it resolves is unchanged, pinned against a baseline captured from the previous implementation over the real listing page as SEC served it plus forty-one inputs written for the ways lxml and BeautifulSoup disagree. One shape that the SEC page cannot have — a table written with no closing `</th>`, `</td>` or `</tr>` tags at all — now yields the CSV link that lxml recovers from it, where BeautifulSoup found nothing.
- **Registration fee tables parse about 8x faster, and stop warning about inline-XBRL exhibits.** `S1.fee_table`, `S3.fee_table`, `total_offering_amount`, `net_fee_due` and `securities` all come from an EX-FILING FEES (Exhibit 107) attachment — or, for pre-2022 registration statements, from the "Calculation of Registration Fee" table inline in the document body — and both were parsed with BeautifulSoup; they now use lxml, measured at 281ms to 37ms over 2.2MB of real exhibits and filings. BeautifulSoup printed an `XMLParsedAsHTMLWarning` for every inline-XBRL exhibit, which the module suppressed by hand; that suppression is gone because the warning no longer exists. Output is unchanged, pinned against a baseline captured from the previous implementation over the eighteen documents the existing fee-table verification covers — fourteen Exhibit 107 attachments from 2022-2025, two of them genuine inline XBRL, and four whole pre-EX-107 registration statements from 2018-2021 — plus forty inputs written for the ways lxml and BeautifulSoup disagree about text.
- **Fund identifier resolution is about 8x faster.** `find_fund()` given a class ID resolves it to a company CIK and then reads that company's series listing, and both pages were parsed with BeautifulSoup's pure-Python `html.parser`; they now use lxml, measured at 45ms to 5.7ms over 187KB of real browse-edgar pages. Output is unchanged: the full parse of twelve committed pages — five fund families from five to fifty series and up to seventy-three classes, a company with no series at all, and an identifier that matches nothing — is pinned against a baseline captured from the previous implementation, alongside thirty-six inputs written for the ways lxml and BeautifulSoup disagree about text.
- **Note markdown rendering is about 5.6x faster.** The LLM-optimised markdown behind `note.to_context()` and `notes.to_markdown()` — the pass that merges a filer's lone `$` or `%` cell back into the figure beside it, drops XBRL metadata tables, deduplicates repeated tables and picks each table's title — was built with BeautifulSoup's pure-Python `html.parser`; it now uses lxml, measured at 1585ms to 282ms over 2.2MB of real note TextBlocks. Output is unchanged, which matters more than the speed here because this is what an LLM reads: all sixteen notes from three filers render byte-for-byte as before, alongside 62 inputs written for the ways lxml and BeautifulSoup disagree about text, tree shape and malformed markup.

  One shape changes, in your favour. A table whose `<th>`, `<td>` and `<tr>` are never closed — `<table><tr><th>Item<th>Amount<tr><td>Revenue<td>$1,000` — was nested inside its own first cell by `html.parser`, so every cell swallowed the rest of the table and a two-by-two table rendered as a single column reading "Amount Revenue $1,000". lxml closes the tags the way a browser does and reads back the table the filer wrote. Note this is the opposite direction to the XML leniency issue: here lxml is the forgiving one.
- **An unreachable fund series/class parser was removed.** `get_series_and_classes_from_sec()` had no callers anywhere in the library, was never exported, and appeared in no documentation; `parse_series_and_classes_from_html()` was reachable only from it. Instrumenting every public fund entry point — `find_fund()` by ticker, series ID and class ID, `get_fund_with_filings()`, and `series.get_filings()` — confirmed neither ever runs. The live series listing is parsed by `_parse_series_table()`, which is unaffected. Its test fixture went with it: a April 2025 capture of a page SEC has since restructured, which the surviving parser cannot read.
- **497K summary-prospectus extraction is about 7x faster.** The fee tables, expense examples, performance tables and fund metadata behind `Prospectus497K` were read through BeautifulSoup; they now use lxml directly, measured at 458ms to 68ms over seventeen real 497K filings. BeautifulSoup was already parsing these with libxml2 underneath, so what goes is its Python object tree rather than the parse itself. Output is unchanged, pinned against a baseline captured from the previous implementation over that corpus — seventeen different fund families across 2012, 2016, 2020, 2023 and 2025 — plus thirty-five inputs written for the ways lxml and BeautifulSoup disagree about text.
- **Form 10-D header parsing is about 6x faster.** `TenD.issuing_entity`, `.depositor`, `.sponsors`, `.distribution_period` and `.security_classes` were read with BeautifulSoup's pure-Python `html.parser`; they now use lxml, measured at 178ms to 28ms over nineteen real 10-D filings. Output is unchanged, pinned against a baseline captured from the previous implementation over that corpus — CMBS, auto lease, auto receivables, RMBS and structured-products trusts, from 2006 through 2025 — plus thirty-two inputs written for the ways lxml and BeautifulSoup disagree about text. One shape that no SEC 10-D has — a class table written with no closing `</th>`, `</td>` or `</tr>` tags at all — now yields the two class names the filer wrote, where BeautifulSoup nested the rows and ran them together.

- **Fund company and filing lookup is about 8x faster, and `edgar/funds/data.py` is off BeautifulSoup entirely.** The browse-edgar company page behind `get_fund_with_filings()` and `FundSeries.get_filings()` — the fund's name, CIK, identifying information, addresses and each page of its filings — was parsed with BeautifulSoup's pure-Python `html.parser`; it now uses lxml, measured at 70.6ms to 8.5ms over 303KB of real company pages. Output is unchanged: the full parse of six real company pages, carrying up to a hundred filings each, is pinned against a baseline captured from the previous implementation, alongside thirty-one inputs written for the ways the two libraries disagree.

  Three answers change. A page whose `<td>` and `<tr>` are never closed now reads the row the filer wrote rather than gluing the form type to the cell beside it (`N-CSR`, not `N-CSRDocuments`); libxml2 closes the tags where `html.parser` nested them. A company page with no `companyInfo` block, or none of the filings table, still raises `AttributeError` from the same place, but the message names lxml's method rather than BeautifulSoup's. Neither shape occurs on a page SEC actually serves.

- **Four remaining readers moved off BeautifulSoup.** Subsidiary exhibits (`TenK.subsidiaries`), the SEC forms listing (`list_forms()`), the bulk-feed directory listing, and 40-F plain-text extraction now parse with lxml. Output is unchanged, pinned against a baseline captured from the previous implementation over the existing fixtures — 153 subsidiaries across three EX-21 exhibits, the forms page, and a real feed directory listing.

- **R-file concept extraction is about 13x faster.** The concept-annotated rows behind `ViewerReport.concept_rows` — the tie between a rendered R-file row and its XBRL concept id — were parsed with BeautifulSoup's pure-Python `html.parser`; they now use lxml, measured at 408ms to 32ms over the 42 R-files of a tracked AAPL 10-Q. Output is unchanged: every field of all 620 rows across 44 real reports is pinned against a baseline captured from the previous implementation, including the column-position work behind issues #810, #812 and #818. Two shapes that cannot occur in an SEC-generated R-file — a table nested inside a row's label anchor, and an unclosed `<th>` — now parse the way lxml recovers rather than the way BeautifulSoup did; both are asserted explicitly.

- **Filing header parsing is about 7x faster.** `Filing.index_headers` parsed the header page with BeautifulSoup's pure-Python `html.parser`; it now uses lxml, measured at 460µs to 66µs per header across the tracked header corpus. Output is unchanged — the full parsed model is pinned against a baseline captured from the previous implementation. Malformed input behaves as before, including the `IndexError` an empty page has always raised.

- **`PressRelease.text()` now reads through the modern parser.** Output changes slightly, all of it in your favour: the old path leaked raw `<img>` markup into the text and left `&amp;` undecoded as a literal "amp", both of which are gone. Across 12 real 8-K press releases no word is lost that is not one of those artifacts. Table cells no longer repeat the `$` that filers put in their own column; the figures and the header's units are unchanged.

- **`PressRelease.to_markdown()` now renders through the modern parser too, and its images finally resolve.** `.text()` moved to `edgar.documents` already; the markdown view was the last part of a press release still going through the legacy `edgar.files` stack, via `MarkdownContent.from_html` -> `HtmlDocument`. It delegates to `Attachment.markdown()` now, the same supported renderer `Filing.markdown()` uses. The visible win is images: the old path emitted a root-relative `![alt](/ex99-1_001.jpg)` that resolves to nothing, and you now get the absolute archive URL. Headings and bold survive the trip where they used to be flattened, and no content is lost — across four real press releases from two filers the word counts match to within half a percent, the difference being GFM escaping and the added structure. An attachment with no usable HTML renders an empty panel rather than raising the `AttributeError` the old path died with.

  This was the last production caller of `HtmlDocument`, which is now referenced nowhere outside `edgar/files/` itself, so `edgar/_markdown.py` no longer imports `edgar.files` at all — a step towards that package's removal in 6.0. What still reaches into the legacy stack is `get_clean_html`, at two call sites, both of them behind the already-deprecated `include_page_breaks=True` flag. A static check pins the `edgar/_markdown.py` half: if the dependency comes back, the suite fails.

- **`SixK` exhibit text now reads through the modern parser.** `_get_exhibit_content` rendered 6-K exhibits with the legacy `edgar.files` document; it now uses `parse_html(html).text()`, the same renderer behind the modern document's own repr. Verified over fifteen real 6-K filings from 2025Q2 by comparing words rather than lengths: prose is equal or better, and the residue is dominated by legacy's own defects, which the modern parser does not have — words split at a line wrap ("forward-" / "looking") and glued neighbours ("visitwww.aunainvestors.com"). Nothing is truncated on even a 3.2MB exhibit. This landed deliberately after the `<br>` and wide-table fixes below, so cover-page line breaks and full table columns were already in place.

### Fixed

- **Pre-2013 13F TXT infotables silently lost rows to column bleed.** When a filing's data lines do not honour the `<S>`/`<C>` marker-line offsets, the fixed-width CUSIP slice started past the true value or picked up trailing digits from 12-digit zero-padded values, and the 9-character gate then rejected every such row: Gilder Gagnon Howe's 2008-Q4 filing parsed 5 of its 217 declared entries. The marker spec is now treated as a hint — when the exact slice fails, a tolerance window is searched for a checksum-valid candidate, with token-boundary starts outranking mid-token windows. Recovered against cover-page Entry Totals confirmed at SEC: 192 (was 15), 194 (was 20), 215 of 217 (was 5), and Berkshire's 2008-Q4 regains its lost Wellpoint row, 108 of 108. The parser also reconciles its row count against the filing's own Entry Total and warns on shortfall, so any future silent-loss mode surfaces instead of emitting plausible wrong data. (GH #1072)
- **A fund series asked for its filings answered with the whole trust's.** `FundSeries.get_filings()` delegated straight to `self.fund_company.get_filings(...)`, and a trust files one NPORT-P per series per quarter under one CIK, so the newest filing it returned belonged to whichever sibling series filed last. Vanguard's Extended Market Index (S000002841) and 500 Index (S000002839) both answered with the same 325 filings topped by the same accession, `0000036405-26-000325` — the 500 Index report — so the fund that excludes the S&P 500 by construction reported the S&P 500 as its portfolio. It now resolves through SEC browse-edgar with the series ID in the CIK slot, the path GH #888 established for `Fund.get_filings(series_only=True)`, and an unresolvable series yields no filings rather than the trust's, for the reason #888 settled: an empty answer is correct for a series with nothing on file, a sibling's data never is. An ETF's synthetic `ETF_<cik>` series stands for the whole registrant and still asks its company. `Fund.get_filings()`'s documented trust-wide default is unchanged, and `series_only=True` still narrows it.
- **`edgar_ownership(analysis_type="fund_portfolio")` listed no positions for any fund.** `_get_fund_holdings` iterated `ThirteenF.holdings` directly, and iterating a DataFrame yields its column names, so every attribute probe missed and nothing was appended. On Berkshire Hathaway's Q2 2026 13F-HR (`0001193125-26-352200`) the MCP returned `holdings_count: 29` beside `holdings: []`, hiding Apple's 227,917,808 shares at $65,950,296,923. (GH #1136)
- **`eightk["Item 9.99"]`, `twentyf["Item 20"]` and `fortyf["No Such Section"]` answered `None` in silence.** A lookup for an item a filing does not have is supposed to say so: it emits a `FutureWarning` naming what edgartools 6.0 will do, and raises `SectionNotFoundError` today if you set `EDGARTOOLS_STRICT_ERRORS=1`. `CompanyReport.__getitem__` does that, and `TenK`/`TenQ` do it — but `CurrentReport` (8-K), `TwentyF` (20-F) and `FortyF` (40-F) each overrode `__getitem__`, rewrote the miss path, and dropped the call. All three returned a bare `None` with no warning in either mode, so a 20-F or 8-K user got no migration notice at all, and `report[item]` would not have started raising in 6.0 for those forms as documented. All three now behave as the base class always did, verified against real filings of each form in both error modes.

  `.get()` is unaffected and stays silent, as it must — it promises a default rather than a complaint, and it is the migration target. If a bare `None` is what you want from these lookups, `report.get("Item 9.99")` keeps giving it to you without the warning.

  The three were independent mistakes with one cause: the base class's `report_lookup_miss` call is invisible at the override site, so each reimplementation of the miss path dropped it without anyone noticing.

- **A note holding an empty table took the whole note down.** `note.to_context()` and `notes.to_markdown()` render through `edgar.markdown.process_content` when optimising for an LLM, and that raised `TypeError: 'NoneType' object is not iterable` whenever the disclosure contained a `<table>` with no usable rows — no `<tr>` at all, only width-grid layout rows, or cells outside any row. `html_to_json()` documents its first return value as a list of text blocks but handed back `None` in three places; it now returns an empty list, which is what its own docstring always promised, so the prose around the table renders instead of the note failing. Output for filings whose tables do have rows is unchanged, verified byte-for-byte across sixteen real Apple, JPMorgan and Coca-Cola note TextBlocks.

- **A filing's text stopped at the first deeply nested table, losing everything after it.** lxml's parser discards anything nested deeper than 256 elements — silently, with no exception and nothing in its error log — and the parser this library builds did not lift that limit. 2000s-era filings nest layout tables that deep: a 2003 S-1 reaching depth 284 returned 137,419 words from `filing.text()` where 151,924 were present, about 10% of the document, all of it the tail. Sections, markdown and every other text consumer lost the same content. The limit is now lifted, which is what BeautifulSoup always did — `html.parser` has no depth limit and bs4's own lxml treebuilder lifts it too — so the readers moved to lxml for 6.0 are not lossy on these filings either. Across 282 filing fixtures this recovers text in one and changes nothing in the rest, at no cost in parse time.

- **`FilingHomepage.get_filers()` returned an empty list for every filing.** It searched the filer block by `id="filerDiv"`, but SEC emits `class="filerDiv"`, so the selector never matched and the method returned before parsing anything — since 2024-05-28. The filer panel was missing from the homepage display for the same reason. Filer names, CIKs, identification lines and mailing/business addresses now come back, and a Form 4 correctly reports both its issuer and its reporting owner. A filer's name also no longer keeps its role suffix on some forms and not others: SEC writes an ordinary filer's role as plain text but a Form 4's as a link, and only the plain spelling was being stripped.

- **A 10-K item lookup spelled in capitals came back empty.** `tenk["ITEM 7"]` and `get_item_with_part("Part II", "ITEM 7")` returned `None` while `"Item 7"` and `"item 7"` returned the section, because `TenK` matched the spelling case-sensitively in two places — deriving the item number, and mapping it to a friendly section name. The legacy parser underneath had been absorbing this, so removing it (below) made the gap visible. `TenQ`, `TwentyF` and `EightK` were already case-insensitive here. (GH #454)

- **A line break the filer wrote was dropped, gluing the words either side.** A `<br>` between two inline elements — the shape of every 6-K and 8-K cover page — was pruned as an empty node, so `UNITED STATES<br/>SECURITIES AND EXCHANGE COMMISSION` came back as `UNITED STATESSECURITIES AND EXCHANGE COMMISSION`. `<br>` between bare text was never affected. Exelon's 8-K of 2005-04-27 regains two line breaks; its text is otherwise unchanged, at the same 2,629 characters.

- **A table's sparse label column, and the `%` or `)` a filer put in a cell of its own, no longer vanish.** Two rules in the same renderer. A column holding one real value in eight rows — a signature block's `Date: June 30, 2025`, an exhibit list's `Exhibit`/`No.` headers — scored below the spacing threshold and was discarded, so its text was in `to_dataframe()` and nowhere in `text()`. Separately, filers split the currency mark, the percent sign and the parenthesis closing a negative number into cells of their own; those scored as spacing too, and were dropped before they could be merged back, so `(175,207)` rendered as `(175,207` and `93.55 %` as `93.55`. Affix cells now survive the filter and merge into the figure they belong to, in either direction.

- **Wide tables silently lost real columns.** The text renderer scored each column of a table, sorted the scores highest-first, and kept only the top eight. Because of that ordering the discarded columns were not the right-hand edge but whichever scored lowest anywhere in the table, so a 21-column segment table rendered without its `Corporate and unallocated` and `Total` headers, and a 10-column voting table dropped the `% Withheld` figure altogether — 6.45 was in `to_dataframe()` and nowhere in `text()`. Every column that clears the content threshold is now rendered; per-column width is still bounded by `table_max_col_width`.

- **A word came back split across lines when the filer bolded one of its letters.** Filers routinely put an acronym's initials in their own `<font>` runs; where those sit inside a `<div>` styled `display:inline`, `Document.text()` emitted each run as its own block. Aardvark Therapeutics' 8-K of 2025-04-01 rendered "(Hunger Elimination or Reduction Objective)" one letter to a line. Such a div now reads as a paragraph — unless it wraps a table or another block, which is how iXBRL containers hold whole statements.

### Removed

- **`edgar._markdown.fix_markdown()`, `edgar._markdown.html_to_markdown()` and `MarkdownContent.from_html()`.** `fix_markdown` repaired run-together Item headings in markdown and had no caller anywhere — not in the library, not internally, only in its own test. The other two went dead this release: `MarkdownContent.from_html()` was the sole caller of `html_to_markdown()`, and its own last caller was `PressRelease.to_markdown()`, which moved to `Attachment.markdown()` when press releases came off the legacy parser (above). `edgar._markdown` is private and appears in no documentation, so none of this is reachable through the public API. `MarkdownContent` itself, `convert_table`, `markdown_to_rich` and `text_to_markdown` are unaffected — construct `MarkdownContent(markdown, title)` directly, which is what the remaining callers do. Nothing that resolves today stops resolving.

- **`edgar.datatools.table_tag_to_dataframe()`.** It converted a BeautifulSoup table tag to a DataFrame and had no callers anywhere in the library, the tests or the docs — it existed only to be migrated. `edgar.datatools` is not exported from `edgar`, so this is not reachable through the public API.

- **`edgar.abs.distribution`.** `DistributionReport`, `DistributionMetrics` and `ReportTable` parsed the HTML distribution exhibit of a Form 10-D, and were never reachable: the module was not exported from `edgar.abs`, nothing in the library imported it, and it had no tests and no documentation. `edgar/abs/__init__.py` had recorded it as deferred at roughly 42% extraction accuracy and preserved "for future work" — work that has not happened, so it goes rather than being carried into 6.0. Its validation harness, `scripts/validate_distribution_report.py`, goes with it. `TenD` and everything else in `edgar.abs` are unaffected. Nothing that resolves today stops resolving.

- **The legacy-parser fallbacks under item lookup on 10-K, 10-Q, 20-F and 8-K.** `report["Item 7"]` and `get_item_with_part()` used to try the modern parser and then, on a miss, read the filing again with `edgar.files`. Measured over ~2,110 lookups on filings from 2001 to 2025, those paths were reached 86 times and produced content on none of them, so they are gone. `TenK.id_parse_document()` and `TenQ.id_parse_document()` are removed with them. A lookup for an item a filing does not have no longer raises `TypeError`, which is what `TenK` did here; every report type now answers `None` and warns that 6.0 will raise `SectionNotFoundError` instead. Three report types were still answering `None` in silence and are fixed above. The deprecated public `chunked_document` property is unaffected and still available until 6.0.

- **The legacy parser's contribution to `EightK.items`.** The item list unioned three detectors; the middle one read the filing again with `edgar.files`. Compared as item SETS — the only comparison that can catch a union quietly dropping a member — across 391 8-K filings from 1995 to 2026, it contributed a unique item to none of them: identical to the surviving detectors on 275, a strict subset on 101, and blind on 82. `.items` still unions the new parser's section tree with the text-based extractor, so item lists are unchanged, including on the pre-2004 and minimal-HTML filings the text extractor exists for.

## [5.52.0] - 2026-08-22

### Added

- **`edgar.settings` — a real home for connection settings and SEC identity.** The access modes (`NORMAL`, `CAUTION`, `CRAWL`), `EdgarSettings`, `set_identity`, `get_identity` and `get_edgar_data_directory` now live in `edgar.settings` rather than in `edgar.core` beside quarter math, HTML sniffing and thread helpers. Nothing breaks: `edgar.core` re-exports every one of those names as the *same objects*, so `isinstance` and identity comparisons are unaffected, as is `from edgar import set_identity, CAUTION`. The `edgar.core` re-exports are removed in 6.0; see `docs/upgrade/6.0.md`.

### Changed

- **`TenK.items`, `TenQ.items` and `TwentyF.items` no longer fall back to the deprecated legacy parser**, and now report exactly what the modern parser detects. Across a 115-filing corpus spanning 1996 to 2026 this changed the item list on zero filings, for all of 10-K, 10-Q, 20-F and 8-K. Item *lookup* — `report["Item 7"]`, `get_item_with_part()` — still has the legacy parser as a fallback but no longer depends on it: every lookup in that corpus is now answered by the modern parser, down from 15 `report["Item N"]` and 4 part-qualified ones.

- **A fund's reference-data lookup now says when it failed, unless it failed by being offline.** `_build_hierarchy_from_mf_tickers` falls back to the bare identifier when `get_fund_reference_data()` is unavailable, but caught every cause of that with `except Exception: pass` — so a network error, an SEC page restructure and a changed CSV shape were indistinguishable from "this class has no name". It now splits on `is_unreachable()`: offline degrades quietly, everything else degrades loudly with the exception type and message. The returned value is unchanged either way.

- **`get_latest_bdc_report_year()` no longer offers a hardcoded 2024 as though it were a finding.** Both BDC probe loops ask whether a year or quarter exists by fetching a URL; a 404 comes back as a response, so reaching the `except` meant the probe got no answer at all — and each loop then stated a conclusion it had not earned, one returning the fallback year and the other `[]`, which reads as "SEC published none". Both now split on `is_unreachable()` and say which case they are in, with return values unchanged. Live, the year resolves to 2026. Two reference modules also move to SEC's migrated `data-research/sec-markets-data/*` addresses, and a new network-marked contract suite watches the datasets themselves, naming the source that moved when one does.

### Fixed

- **`get_operating_cash_flow()` returned `None` for Apple, and took free cash flow down with it.** It searched the cash flow statement for five label patterns written against the *standardized* vocabulary; Apple labels the line "Cash generated by operating activities", which matches none of them, so the method returned `None` for every Apple filing and `get_free_cash_flow()` followed it silently. The filers it did work for worked by coincidence of house style. Operating cash flow is now found by XBRL concept through the standardization store first, as `get_revenue()` and `get_capital_expenditures()` already were, with the label patterns kept as a fallback for unmapped or custom tags. Apple's latest 10-Q now returns $82,627,000,000, and the five issuers that already worked are unchanged. Reported in #1083.

- **Every fund series and class name came back as a bare identifier, and nothing said why.** SEC turned a dataset page into a 301 whose `Location` is a bare path, which the standard permits (RFC 7231 §7.1.2), and every manual redirect hop passed that header straight into the next request — so httpx got a URL with no scheme and raised `UnsupportedProtocol`, which `edgar/funds/data.py` swallowed. `find_fund("KINCX").name` returned `"C000013712"` instead of `"Advisor Class C"`. `redirect_url()` now resolves the header against the URL that produced it via `httpx.URL.join`, applied to all five hops, so relative and protocol-relative Locations both work. SEC is mid-migration, so this closes the class rather than the one address.

- **A 10-Q's Part II items were judged against Part I's expectations and told they were truncated.** The size guardrail keyed its expectations on the bare item number, but a 10-Q has two Item 1s — Financial Statements in Part I at around 90,000 characters, and Legal Proceedings in Part II, often a pointer of a few hundred. Part II's was measured against Part I's floor of 18,009 and flagged as likely truncated: 38 of the 65 size warnings the fixture corpus produced were false alarms on correctly-extracted sections. Bands may now be written per Part; the 10-Q's are Part I's Items 1 and 2 and Part II's Exhibits, with the numbers unchanged, since they were measurements of Part I all along. Part II's Items 1 and 2 are left unenforced — they run from 74 to 12,718 characters, and no floor separates "the filer said nothing" from "the anchor missed the body". A warning's character count now matches what `section.text()` returns.

- **A section the filer answered with a cross-reference was reported as a truncated extraction.** An Item 8 that says the financial statements are filed under Item 15 is a faithful extraction of a pointer, not a truncation, but the undersize warning sent callers to debug a parser that had done its job. All five undersized Item 8s in the fixture corpus are pointers — NVIDIA at 207 characters, Netflix 268, IBM 250, Oracle 158, CIK 915358 at 112 — so the diagnosis was wrong in every case. An undersized section is now tested for a deferral first and a pointer gets an incorporation-by-reference warning naming where the content lives. Confidence is still reduced, so what callers receive is unchanged; only what they are told about it. Reported in #927.

- **Two items of a 10-Q returned the identical text, with nothing to say which one was wrong.** Procter & Gamble's table of contents points its Item 5 and Item 6 rows at the same body anchor, so both sliced to the same 2,628 characters and Item 5's "Other Information" answered with Item 6's exhibit list. The collision resolver re-points such an item at its own body heading, and here it had none to work with: P&G builds each header as a two-cell table row, which renders with nothing between the number and the title, while the body scan required a space. A period may now stand in for that separator, though not when a digit follows it, which keeps an 8-K's "Item 5.02" from reading as a bare Item 5. The two items now return their own 306 and 2,320 characters, and across a 115-filing corpus this is the only filing whose sections change.

- **`get_item_with_part()` returned the wrong text on some 10-Qs, from two separate faults.** ExxonMobil puts Item 1 in a table and writes its other six as headings, but the strategy that reads item headers out of table cells only ran when fewer than half the form's items had been found — so it was held shut by the very headers that could never supply the missing one, and Part I Item 1 is the entire financial-statement section. Procter & Gamble's fault was different: the code filling in items a TOC omitted compared bare item numbers, so a TOC naming one of the two Item 1s was read as naming both. Both cases fell through to an older extractor that answered with 222,536 characters for a section of 975. Six sections across four filings are recovered, and no section changed its boundaries.

- **An item whose title runs long was not recognised as a heading at all.** Header detection refuses to treat anything over fifteen words as a header, which is reasonable for unlabelled text and wrong for labelled text — several of the SEC's own canonical item titles are longer, Item 5's at seventeen words among them, so the cap rejected precisely the longest *real* headers. On one 2016 annual report Item 5 was the only item of twenty that went missing. A filing's own "Item N" or "PART N" label now waives the length test; unlabelled long text and prose cross-references are treated as before.

- **Older 10-Ks lost Items 4 and 14, because each has carried two titles and only the modern one was recognised.** Item 4 was "Submission of Matters to a Vote of Security Holders" until Dodd-Frank gave it to mine safety in 2011; exhibits were Item 14 until the 2003 renumbering moved them to Item 15. Both older headers were found and then discarded for having the wrong title. Both titles are now recognised alongside the modern ones, and a modern filing's Items 14 and 15 are unaffected.

- **An item that numbers its own subsections no longer stops at the first of them.** A filer dividing Item 14 with "Item 14(a)(1):", "Item 14 (a)(2):" and "Item 14 (a)(3):" headers was handing the extractor three things that look like item headers, and the item ended at one — on a 1999 annual report that dropped the schedules and the whole exhibit index. An item marker carrying a parenthesized sub-designation and no title is now read as a subdivision. Related: a bare "SIGNATURES" line now ends a section regardless of how the heading detector scored it, so seven sections across 10-K, 10-Q, 20-F and 8-K stop at the signature page instead of running to the end of the document.

- **`Item 9A(T)` was unmatchable, so a cohort of 2007–2010 annual reports had no controls-and-procedures section.** `9A(T)` was the SEC's transitional designation for a smaller reporting company's internal-control report, and `ITEM 9A(T). CONTROLS AND PROCEDURES` hit an item-header pattern whose punctuation vocabulary had no `(` in it — so the match died after the number and the section was never created, though the header itself was found. An item number may now carry a parenthesized designation, across 10-K, 10-Q and 20-F alike.

- **A 10-Q whose "PART II" marker is styled on an inner element lost its whole Part II.** Some filers, Goldman Sachs among them, render the marker as an unstyled paragraph wrapping a bold span, a shape the extractor only recognised for 10-K and 8-K. The damage was larger than one missing marker: each item header is assigned to the last part seen, so with no Part II boundary every later header stayed Part I and the Part II patterns then rejected their own headers — Items 5 and 6 were being found and thrown away. A bare "SIGNATURES" line is now recognised on 10-Q too, which stops Item 6 running past the end of the exhibit list; three further filings gained a correctly bounded Item 6 from that, ExxonMobil's among them.

- **Item headers that wrap across two lines are now found.** A header reading `<td>ITEM 5. OPERATING` / `AND FINANCIAL REVIEW AND PROSPECTS</td>` carries a newline in the middle of its title. In HTML that is just whitespace, but the section patterns join words with `.*`, which does not cross one — so which items a filing lost came down to how each pattern happened to be written: Item 4's uses `\s+` and matched, Item 5's uses `.*` and did not. Header text is now normalized before matching, recovering Items 5, 6, 11, 12 and 15–16F on a 2010 20-F, Items 6 and 11 on a 2016 20-F, and Item 7A on a 1999 10-K. A table-of-contents row can also no longer outrank the real body header for the same item.

- **Filings from before about 2002 returned no items at all from the modern parser.** Those filings are preformatted text in minimal HTML, so they parse to a container-and-text tree with no headings and no paragraphs — and every header strategy drew its candidates from headings, section nodes, bold paragraphs or table cells, leaving no candidate source at all however well the patterns matched. Bare text nodes are now read as headers, using each node's first line, since one node carries both the heading and the body that follows it. A 2001 10-K and a 2001 20-F recover their Item 7; across a 121-filing corpus this was the last remaining difference between the modern and legacy parsers on these forms.

## [5.51.0] - 2026-08-19

### Performance

- **Parsing the current-filings feed is 6.1x faster**, measured on a real 100-entry page (9.6ms to 1.6ms). Most of that is invisible behind the network round trip when you fetch one page, but `get_all_current_filings()` pages through the whole feed and pays it every time. Output is byte-identical; the entries, their order, and their fields are unchanged.

- **Parsing an EFFECT filing is 9.0x faster** — 242µs to 27µs per submission, measured over 39 real EFFECT documents from four quarters, with every parsed field identical before and after. EFFECT notices are small, so the win only shows at volume; a day's worth of them is a few thousand filings.

- **Parsing a Form 3, 4 or 5 is 2.7x faster** — 3.35ms to 1.25ms per filing, measured over 69 real ownership filings from five quarters, with every parsed field identical before and after: holdings, transactions, footnotes, signatures, issuer and all 126 reporting owners. The XML layer itself is 28x faster to parse and 4.8x faster to read; what is left is the DataFrame construction, which now dominates. `Form4.transactions` on a portfolio of insider filings is where this shows.

- **Reading a filing's report index is 6.9x faster** — 16.2ms to 2.4ms per `FilingSummary.xml`, measured over 31 real filings (10-K, 10-Q, 8-K, 20-F, 2021 to 2025) carrying 1,823 reports between them, with every report, input file and supplemental file identical before and after. This is the parse behind `filing.reports` and behind the note lookup in `TenK.notes`.

- **Parsing a 13F cover page is 5.7x faster** — 717µs to 125µs per primary document, measured over 36 real 13F-HR, 13F-HR/A and 13F-NT filings from 2022 to 2025, with every field identical before and after: manager, address, summary totals, other managers and amendment metadata. This is the parse behind `ThirteenF.filing_manager`, `.total_value` and `.other_managers`.

- **Parsing a Form 144 notice is 3.1x faster** — 3.74ms to 1.20ms per notice, measured over 31 real 144 and 144/A filings from 2022 to 2025, with every field identical before and after: filer, issuer, address, both securities tables and the notice signature.

- **Parsing a Form D notice is 8.8x faster** — 2.04ms to 0.23ms per notice, measured over 42 real D and D/A filings from 2022 to 2025, with every field identical before and after: issuer, all 145 related persons and their relationships, the offering sections, sales-compensation recipients and signatures.

- **Parsing an MA-I municipal advisor filing is 2.9x faster** — 3.89ms to 1.33ms per filing, measured over 40 real MA-I and MA-I/A filings from 2021 to 2026, with every field identical before and after: filer, contact, notification addresses, applicant and other names, all advisory offices and their addresses, the full employment history and the signature. MA-I mixes three namespaces in one document, so more of the work stays in the local-name fallback than it does for the single-namespace forms.

- **Parsing a Schedule 13D or 13G is 4.2x faster** — 2.41ms to 0.57ms per document, measured over 125 real SCHEDULE 13D, 13D/A, 13G and 13G/A filings from all four quarters of 2025, with every parsed field identical before and after: issuer and security info, all reporting persons with their voting and dispositive power, the 13D items 1-7, the 13G items 1-10 and the signatures. Structured XML for these forms only exists from the 2024-12-18 SEC mandate onward; older filings still come back from the SGML header with `has_structured_data == False`.

### Fixed

- **A Form 4 whose XML the SEC did not write quite correctly came back as raw markup instead of a rendered form.** `BeautifulSoup(xml, "xml")` parses with `recover=True`, so for years edgartools read filings like AAR CORP's 2004-02-04 Form 4 — which carries a mangled `<nonDerivativeTable ativeTable>` attribute — without anyone noticing they were malformed. The move to lxml made parsing strict, and `filing.sgml().text()` on those filings went back to dumping `<ownershipDocument>` tags. `xmltools.parse_xml` now recovers exactly as bs4 did, which restores the behaviour for every form migrated so far, not just Forms 3/4/5. A document with no markup at all is still an error.

- **A person's name raised `TypeError` whenever they had no middle name.** `Name.full_name` built the middle segment as `(' ' + middle_name) or ''`, so the concatenation ran before the fallback could apply and a missing middle name crashed instead of being skipped. Municipal advisor filings hit this constantly — the parser feeds that field straight from the XML, which simply omits `<middleName>`. Michael NMN Tym Jr. still reads as `Michael NMN Tym Jr.`, since `NMN` is data the SEC writes, not an absence.

- **`str(person)` printed the first name twice** instead of the full name. `repr()` was always correct, which is why Rich tables and notebook output looked right while string interpolation did not.

- **Every disclosure answer on an MA-I municipal advisor filing read `False`, no matter what the filing said.** 40 of the 45 disclosure booleans were read with `child_value()`, which looks for a `<value>` child element — but MA-I disclosure elements carry the answer as their own text, so the lookup always came back empty and a filing disclosing a felony charge reported clean, indistinguishable from one that actually is. Found by a 40-filing corpus comparison during the lxml migration and present long before it; every disclosure class and `Disclosures.any()` now reads the answer the SEC actually wrote.

- **Five more MA-I disclosure fields were hardwired `False` because the parser asked for element names the SEC schema does not use.** Three of the five are the SEC's own misspellings — `isIndependentRelatioship`, `isTrusteeApointed`, `isViloatedIndustryStandard` — which is exactly why the mismatch was easy to miss; the parser searched for the correctly-spelled names and found nothing in any of 40 corpus documents. It now asks for what the SEC writes, with comments guarding each misspelling so nobody corrects them back into brokenness.

- **`Form144.contact` was `None` on every filing.** The parser searched for `<contact>` under `<filer>` when the SEC writes it as a sibling under `<filerInfo>`, and even given the right element it read children named `name`, `phone` and `email` where the schema names them `contactName`, `contactPhoneNumber` and `contactEmailAddress` — two mistakes, each sufficient alone. All 31 corpus filings returned `None`; the SEC's own checked-in sample, whose contact block is populated, now parses.

- **A Form D issuer's previous names vanished when the SEC wrote them with the `<previousName>` spelling.** The previous-name lists were read only through `<value>` children, but 7 of 42 sampled filings from 2022–2025 use `<previousName>` instead, so a renamed company like Shepherd's Finance, LLC parsed as never having been renamed — an empty list, never an error. Both spellings are now read, and the literal `None` placeholder the SEC writes for "no previous names" is filtered under either one.

- **Reading `associated_bd_name` off a Form D sales-compensation recipient raised `AttributeError`.** The constructor line was `self.associated_bd_name: associated_bd_name` — a colon where an equals belongs, a bare annotation that binds nothing — so the value was parsed correctly, passed correctly, and dropped at the moment of assignment. The sibling CRD line was written correctly, which is what made the typo invisible.

- **`SecForms.load()` returned an object that raised a bewildering `SyntaxError` on use.** It wrapped `list_forms()`, which already returns a `SecForms`, so the forms table ended up nested one level too deep and every read of it went through the wrong `__getitem__` into a pandas query expression. `SecForms.load().get_form("1-A")` now returns Form 1-A, the Regulation A Offering Statement.

## [5.50.1] - 2026-08-18

### Fixed

- **The HTTP cache was wiped twice on every `import edgar`, so it never survived a process.** The two "one-time" import-time cache clears (#457 locale fix, #672 empty-response fix) each kept their marker file inside `_tcache` — the directory the other one `rmtree`s — so each import deleted the other's marker and both clears fired forever, from v5.20.1 onward. Short-lived processes re-downloaded everything from SEC each run, and a wipe landing on a concurrent edgar process's in-flight cache write crashed it with `FileNotFoundError`. Markers now live in `<edgar-data-dir>/.migrations`, outside the cleared directory, and all migrations run as a single pass that clears at most once; the legacy in-cache marker is honored, so upgrading performs at most one final clear. (GH #1051)

## [5.50.0] - 2026-08-18

### Fixed

- **`Company.get_facts()` re-downloaded companyfacts on every call, and the 30s `/submissions` TTL never took effect.** Cache rules were keyed off `SEC_BASE_URL` alone, but httpxthrottlecache matches the request host against that key, and `re.match(r'.*www\.sec\.gov', 'data.sec.gov')` is `None` — so a fresh process logs `No patterns matched data.sec.gov` and pays full network cost every time. Keys now come from `httpx.URL(...).host`, one per host, matched exactly, which also restores caching for custom mirrors. Requires `httpxthrottlecache>=0.6.1`. (GH #989)

- **`FilingSGML.html()` crashed with `UnicodeDecodeError` on filings whose primary document is a PDF.** The binary guard existed but never fired: `is_binary()` compared the raw extension against a lowercase list, so a file named `.PDF` answered False and its bytes went to a bare UTF-8 decode. Three ways to fail open lived in that one path — the case-sensitive compare, a malformed `"png"` entry that matched nothing, and the binary-extension table defined twice with the same typo in both copies. Classification now goes through the attachment's normalized extension, and `html()` and `xml()` route through the decoder that already carried the right contract, including a NUL-byte sniff for what the extension table misses. Ten filings in a 1993–2026 crawl hit this, every one a 40-17G, CERT or 40-24B2/A. (#1047)

- **`FilingSGML.text()` returned raw XML for XML-primary forms beyond ownership — and could take hours doing it.** The HTML sniff asks whether `<p>`, `<div` or `<span` appears anywhere in the string, which inside a 143MB NPORT-P instance is a certainty, so one filing was walked node by node for about an hour and a half; a sniff miss on an X-17A-5 or 24F-2NT returned the markup verbatim, which is why the same bug looked different on different filings. XML documents now get their own branch, keyed on both an XML declaration and a non-`<html>` root — both halves load-bearing, since an iXBRL 10-K opens with `<?xml` and then `<html>`, and a 1994 filing opens with `<PAGE>`, which reads as a root element. The 143MB filing now answers in 2.4 seconds. What `text()` returns for unrenderable XML is unchanged: the document, verbatim. (#1047)

- **`FilingSGML.text()` on pre-1997 filings leaked the era's SGML table dialect — `<TABLE>`, `<CAPTION>`, `<S>`, `<C>` and footnote tags — into the text.** Dialect tags occupying whole lines are dropped whole, so no column moves; inline footnote references are rewritten width-neutrally, `<F2>` becoming `[F2]`, which keeps every fixed-width table aligned. The patterns are deliberately tight, because 1990s filings use a bare `<` as a less-than sign and blanket angle-bracket deletion would eat real content. (#1047)

- **A truncated submission — a download that failed partway, a cut-off local file — parsed "successfully" as zero documents, and `text()` returned `None`.** EDGAR always closes `<DOCUMENT>`, so an unterminated one is structural proof of a cut, and parsing now raises `ValueError` saying how many complete documents preceded the cut and to re-download or clear the cached copy. The header's `PUBLIC DOCUMENT COUNT` is also checked against what was parsed, with a warning on a marked deficit. Both tolerances in that check are measured rather than assumed: complete dissemination files routinely ship one fewer `<DOCUMENT>` block than they declare — Apple's full 10-K declares 103 and ships 102 — so off-by-one stays silent, and a pre-2004 header-only artifact legitimately carries no documents at all. (#1049)

### Performance

- **`FilingSGML.text()` on table-heavy filings peaks ~170MB lower and runs ~13% faster.** Profiling a 25MB ABS-15G whose single table holds 66,929 rows and 1.6 million cells attributed the ~60x peak-memory amplification to the render path materialising the grid as millions of unslotted dataclass instances, each paying for a `__dict__` it never uses. `Cell` and `MatrixCell` now declare `__slots__`, and the parser only retains its copy of the original HTML when section detection is on, since only the section extractors read it. Peak RSS on the profiled filing drops from 1.51GB to 1.34GB with byte-identical output. The remaining amplification is the render pipeline rebuilding the same grid several times over, which is tracked for the 6.0 performance pass. (#1048)

## [5.49.0] - 2026-08-15

### Changed

- **BDC investment parsing now recognizes structured Schedule of Investments labels and normalizes trailing numeric XBRL disambiguators out of `investment_type`.** The original label remains available in `identifier`, so separate tranches remain distinguishable while grouping by investment type is stable. Fourteen more BDC tickers parse their investment types, and two label shapes that previously yielded a company name of `'Specialty finance'` or `'Class AA'` now return the issuer. (GH #990)

### Fixed

- **`Item 1C` (Cybersecurity) and `Item 16` were missing from filings whose table of contents omitted them.** A TOC is something the filer wrote, not a manifest, and items go missing from it routinely — Part III when it is incorporated by reference from the proxy, Item 16 because it is optional and usually empty, Item 1C because it was new in 2023 and templates lagged. The parser already handled this by augmenting a successful TOC result with items found in the body, but the check deciding whether that pass was worth running asked only whether Part III was complete. Part III is complete on nearly every filing, so the pass was skipped nearly always, and the items a TOC actually omits were the ones nobody got: `TenK.items` on Bank of America, JPMorgan and Tesla listed no Item 1C, and American Express, Chevron and Johnson & Johnson no Item 16, on filings where the parser had already found them and thrown the result away. Item 1C has been mandatory since December 2023, so this was most modern 10-Ks rather than a corner case. The check now asks whether the TOC named every item the form defines. Sections are also merged by item rather than by section key, so the same item cannot arrive twice under the two naming conventions the detectors use (`part_ii_item_7` and `mda` are both Item 7). Across the parity corpus this closes seven 10-K filings and one 10-Q, with no filing losing an item and no measurable change in parse time.

- **A 10-K that writes `Item 1:  Business` reported one section instead of fifteen.** The 10-K section vocabulary accepted a period between an item number and its title, or nothing — `Item 1. Business` and `Item 1 Business` — but not the colon, hyphen or em dash that filers also use. That is not one missing pattern: a filer picks a separator and uses it for the whole document, so all 23 item patterns failed together, and the pattern extractor is the *last* strategy the detector tries, after the table of contents, the cross-reference index and headings have all declined. Two filings in our corpus came back with a single section each — `TenK.items` was `['Item 8']` where the legacy parser found 15 and 20 items — and everything else was reachable only through the deprecated `ChunkedDocument` fallback, so the 6.0 deletion would have taken the content with it. The separator now lives in one place for 10-K, 10-Q and 20-F and admits `.`, `:`, `;`, `-`, `–` and `—`; 10-Q and 20-F already took the dash, and nothing was checking that 10-K agreed. Across the parity corpus this recovers 32 items on three filings and loses none, moving 10-K section coverage from +0.1% to +2.8% against the parser it replaces.

- **A 20-F could report four sections where it has eighteen.** The section extractor finds headers in layers — semantic headings first, then bold paragraphs, table cells and plain paragraphs as fallbacks — and it stopped after the first layer as soon as *any* header mentioned an item. On filer-agent HTML where heading detection promotes a lot of styled text and few real headings, that test passed on almost nothing: one 2010 20-F was gated by three headings, one of which was a sentence reading "Please refer to Item 6.E…". The fallbacks that find its fifteen actual item headers never ran. The gate now asks whether the form's item *structure* has been found — a share of the items the form defines — rather than whether one item was mentioned anywhere. Across the parity corpus this closes 14 of the 26 sections a 20-F filing lost, with no filing losing any.

- **`TwentyF.items` read the deprecated parser first, and disagreed with `twentyf['Item 5']`.** Item lookup has read the new parser for some time while the item *list* read the legacy `ChunkedDocument`, so the two could describe the same filing differently. `.items` now reads the new parser and falls back to the legacy one only when the new parser finds nothing, matching `TenK`, `TenQ` and `CurrentReport`. Items also come back deduplicated and in canonical SEC order (`Item 4` before `Item 4A` before `Item 5`, `Item 16A` before `Item 19`) on both paths; previously the legacy path returned them in whatever order the document produced. On two filings in the corpus the new parser still finds fewer items than the legacy one, and those are tracked.

- **`report.items` warned you about `chunked_document`, an attribute you never touched.** `TenK`, `TenQ`, `TwentyF` and `CurrentReport` try the new parser first and fall back to the legacy `ChunkedDocument`, and those fallbacks read the *public* deprecated property — so a plain `twentyf.items` emitted `chunked_document is deprecated` about a choice that was ours, not yours. 20-F got it on every call, because at the time 20-F took the legacy path first. If you run `-W error::DeprecationWarning`, that was not a warning but an exception. Internal paths now use a private accessor and say nothing; asking for `chunked_document` yourself still warns.

- **Three report classes had silently lost that deprecation entirely.** `TenK`, `TenQ` and `CurrentReport` each overrode `chunked_document` to change how it was built, and an override that replaces the property also replaces the `warnings.warn` inside it — so their users got no notice that the attribute disappears in 6.0, which is the population the deprecation exists for. Construction now happens in `_chunked_document`, the warning lives in exactly one place, and a test asserts no subclass can take it away again.

## [5.48.0] - 2026-08-12

### Added

- **`edgar.exceptions` — one exception vocabulary, four branches.** There were 27 exception classes across ten packages with no shared base and no cross-package inheritance, of which exactly two were reachable from the top level, so `except` had to name a type from whichever module happened to raise. There is now a root, `EdgarError`, and four branches that answer the question a caller actually has: `TransportError` (we could not get an answer from SEC), `NotFoundError` (you named a thing and it does not exist), `ParsingError` (we got bytes and could not build the object), `ValidationError` (your input was wrong before we asked). The distinction between the first two is the one that matters most — an outage and an empty result must never arrive as the same value. **Nothing changed about what is raised today**: every existing class was re-based into the tree or kept as a deprecated alias for the same object, so `except StatementNotFound:` and `pytest.raises(SECFilingNotFoundError)` still work. The branches also inherit the builtin they replace — `ValidationError` is a `ValueError`, `NotFoundError` is a `LookupError` — so the `except ValueError:` you wrote against our 135 raw `ValueError` raises keeps working as those convert. Deprecated spellings warn and are removed in 6.0: `StatementNotFound`, `NoCompanyFactsFound`, `SECFilingNotFoundError`, `InvalidDateException`, `IdentityNotSetException`, `TooManyRequestsException`, `DataObjectException`.

- **A missing-attachment lookup raises `AttachmentNotFoundError`** rather than a bare `KeyError`. It *is* a `KeyError`, so existing handlers are unaffected.

- **`EDGARTOOLS_STRICT_ERRORS=1` runs 6.0's error behaviour today.** The changes that would otherwise be a break are available behind the flag, so you can port before 6.0 lands rather than after. It turns on both halves of that change: the network wrap below, and the four silent-`None` conversions under **Deprecated**. Check it yourself with `edgar.exceptions.strict_errors_enabled()`.

- **`report.get(item, default)` on every company report.** The counterpart to `report[item]`, and the reason that one can start raising in 6.0: a lookup whose only form raises leaves the "I'll take it if it's there" caller wrapping a one-liner in try/except. It never warns — it is the migration target, and warning there would give the users who took our advice the same noise as the users who ignored it.

- **Under strict, an httpx failure that survived every retry becomes a `TransportError`.** `httpx.ReadTimeout` and friends were propagating verbatim out of `get_with_retry`, `stream_with_retry`, `post_with_retry` and `inspect_response`, which made a dependency's exception types part of our public contract by accident — and made any future HTTP-client change a breaking one for every `except` clause naming them. The wrap happens once at the boundary, carries `.status_code` (`None` when we never got an answer at all) and `.url`, and always chains the original as `__cause__`, so nothing is lost for debugging. This is a 6.0 flip because user code may be catching `httpx.HTTPError` around our calls; without the flag, nothing changes. `TRANSPORT_ERRORS` now catches both eras, so code written against it needs no revisiting.

- **`edgartools` ships a PEP 561 `py.typed` marker, so its type hints now reach your type checker.** The README has said "type hints throughout" for a long time and it was true of the source and false of the installed package: without the marker, mypy refuses to look inside `edgar` at all — `Skipping analyzing "edgar": module is installed, but missing library stubs or py.typed marker` — and every symbol degrades to `Any`. `Company(cik_or_ticker=[1, 2, 3])` type-checked clean against 5.47.0; it now reports `Argument "cik_or_ticker" to "Company" has incompatible type "list[int]"; expected "str | int"`. Nothing in the library changed — this makes the annotations already there visible, and it is why the typing work behind them was worth doing. Pyright users saw types already, because it reads library source by default; mypy and stub-strict configurations did not.

### Deprecated

- **Four calls that answer `None` for a failure now say what they will raise in 6.0.** Each emits a `FutureWarning` naming the exception, and raises it today under `EDGARTOOLS_STRICT_ERRORS=1`: `tenk["Item 99"]` becomes `SectionNotFoundError`, `find("123456-99")` on a malformed accession becomes `ValidationError`, `filing.obj()` on a form we model whose data will not read becomes `DataObjectError`, and `TenK.document` on a parse failure raises the parser's own `ParsingError`. **The legitimate `None`s are untouched**: `filing.obj()` on a form edgartools does not model, and `filing.xbrl()` on a filing without XBRL, are answers about the world rather than failures — and that distinction is the entire point. `TenK.document` had collapsed "this filing has no HTML" and "this filing has HTML we could not read" into the same value; every sibling report class already let the parse failure through. **Each of these warns once per call site, not once per filing** — the per-filing detail (which accession, which items it does have) stays on the exception that strict mode raises, so a loop over a corpus of ten thousand filings gets one warning rather than ten thousand. See the new [error-handling guide](https://edgartools.readthedocs.io/en/latest/guides/error-handling/).

### Fixed

- **`docs/guides/current-filings.md` told you to catch the builtin `ConnectionError`.** Nothing in the HTTP layer raises it, so that handler has never fired. It is `TransportError`.

- **`NoCompanyFactsFound` carried a message nobody could read.** Its `__init__` called `super().__init__()` with no arguments and set `self.message` instead, so `str(exc)` was the empty string — three raise sites whose message never reached a traceback, a log line, or a user. It is now `CompanyFactsNotFoundError` and builds its message through the base class, which makes the empty case unrepresentable rather than merely fixed.

- **An EFTS outage was reported as "there is no filing at that accession".** `resolve_accession()` wrapped its fetch in `except Exception: return None`, and `None` from that function routes the caller to the quarterly index — the correct answer for a pre-2001 accession and a wrong turn during an SEC outage, with the only trace at DEBUG. Transport failures now propagate; a malformed response still returns `None`, which is what that arm was for. This closes the sibling left open by the `edgartools-tg7y` fix, which fixed the same shape in `edgar/funds/core.py`.

## [5.47.0] - 2026-08-10

### Added

- **`edgar` now declares `__all__` — 110 names — so the supported API is answerable.** There was no way to tell an API from an accident: 141 names were reachable from the top level, including `Optional` and `partial` (imported for annotations) and `Document`, the *legacy* `edgar.files` parser, which is a different class from `edgar.documents.Document` and is removed in 6.0. Names left out stay importable; 6.0 makes them private. **`from edgar import *` is narrower** — it no longer yields those 31 names. Direct imports are unaffected.

- **`Filing.text(include_images=True)` and `Document.text(include_images=True)` emit an `[Image: <alt or filename>]` placeholder per image.** This completes the text half of GH #886: a `TextExtractor` flag existed but never fired on a real filing, because SEC filers wrap `<img>` in a paragraph and the paragraph branch returned without descending to it. NVIDIA's 10-K now marks both its images, including the Item 5 stock performance graph whose five-year return comparison has no table beside it. Off by default, so the text feeding sections, search and embeddings stays image-free. (GH #886)

### Changed

- **Cash flow is `cash_flow_statement()` on every object.** It had three spellings — `Company.cash_flow()`, `Financials.cashflow_statement()`, `xbrl.statements.cash_flow_statement()` — and only `Company` accepted all three: of the 16 classes exposing `income_statement()`, `EntityFacts` and `CurrentPeriodView` had no `cash_flow_statement()` at all. It now matches `income_statement()` and `balance_sheet()` everywhere. The old spellings emit a `DeprecationWarning` and are removed in 6.0; see `docs/upgrade/6.0.md`. Three internal callers were still on the old name, which turned that warning into noise the caller could not act on — `EntityFacts.cash_flow_statement(period='ttm')`, spelled canonically, told the user to stop using `cashflow_statement()`, and every MCP filing read did the same. `FilingViewer.compare_context()` also disagreed with itself: it keyed its viewer-report table on the old spelling while looking the method up on the object, so the canonical name silently returned "(No viewer report found)". Both spellings now take the canonical path.

- **`Filing.markdown()` and `Attachment.markdown()` now render through `edgar.documents`.** They were the last public rendering methods still on the legacy `edgar.files` pipeline, which has no image node at all — `MarkdownRenderer.render` handles text blocks, tables, headings and page breaks, and drops everything else. Every `<img>` in every filing vanished silently. NVIDIA's FY2026 10-K now renders both of its images, including the Item 5 stock performance graph whose five-year return comparison exists only as a chart. Relative `src` values are resolved against the filing's SEC archive directory, so the markdown carries working absolute links rather than bare sibling file names. Output also differs where the two renderers disagree on tables; a parity ratchet pins the numeric content of both. (GH #886)

- **`Filing.text()` truncated long table cells at 200 characters, with no ellipsis to show it had happened.** It rendered its document with `rich_to_text(document, width=500)`, but `Document` is not a rich renderable, so rich fell back to `repr()` — and `Document.__repr__` is hardcoded `text(table_max_col_width=200)`. The `500` never reached the table renderer. On Apple's FY2024 10-K that cost 1,434 characters across 8 chunks (whitespace collapsed, so wrapping does not account for it), including 300 characters of the unrecognized-tax-benefits disclosure: `$22.0 billion, of which $10.8 billion, if recognized, would impact the Company's effective tax rate`. Seven of eight 10-K fixtures lost content with no ellipsis marker. `Filing.text()` now calls `document.text(table_max_col_width=500)` directly, which also drops the rich round-trip — a 400 KB string was being rendered through a console and stripped of ANSI to recover text the extractor had already produced. Rendering is 4.5× faster (6.61s → 1.46s across 8 filings).

- **Image `alt` text leaked into `Filing.text()` as unlabelled prose.** `ImageNode.text()` returned `alt`, which `ParagraphNode.text()` aggregates, so the bare string `nvidialogoa10.jpg` appeared inline in NVIDIA's 10-K text with nothing marking it as an image. `alt` describes an image rather than being text the filer wrote, and on SEC filings it is usually just the source file name; it no longer contributes to text. Callers that want images represented ask explicitly — see `include_images` below.

### Deprecated

- **`include_page_breaks` and `start_page_number` on `Filing.markdown()` and `Attachment.markdown()`.** Page-break rendering exists only in the legacy renderer, so passing `include_page_breaks=True` routes the whole document through it and forfeits images and the newer table rendering — the flag selects a renderer, not a feature. It still works and now emits a `DeprecationWarning`; both parameters go in 6.0 alongside `edgar.files`. There is no replacement: the `edgar.documents` builder treats page-break `<hr>`s and page-number containers as print chrome and discards them.

### Removed

- **`edgar.xbrl.analysis` — 2,098 lines of Altman Z, Beneish M, Piotroski F, Montier C and a ratios engine, none of it reachable and none of it working.** `FinancialMetrics.__init__` raised `AttributeError: 'function' object has no attribute 'to_dataframe'` on the first statement it touched: it read `statements.balance_sheet` without calling it, so the truthiness check always passed and `.to_dataframe()` ran against a bound method. All three statement loads had it, and `statements.cash_flow` was not a name that existed at all. Nothing imported the package — no `__init__.py`, `fraud.py` was the only consumer of `metrics.py` and nothing consumed `fraud.py`, `ratios.py` stood alone, and there were no tests, no docs and no entry in `edgar.__all__`. It arrived on 2025-04-12 in the XBRL2→xbrl rename and only ruff sweeps have touched it since. Removing a subtree that could not be constructed is not a behaviour change, which is why it does not wait for 6.0. If these metrics are wanted they should be built against the current `Statement`/`Facts` API rather than revived. (`edgartools-07lk.12.1`)

### Fixed

- **`LLP`, `LLLP` and `PLLC` were missing from the entity name heuristic entirely.** The strict keyword set carried `LP`, `LLC` and `LTD` but not the partnership forms beside them, so 340 `LLP`, 759 `LLLP` and 26 `PLLC` filers had no name signal. The 1,300-odd `ALL PRO … LLLP` real-estate partnerships were only ever detected by the accidental `L P` inside `AL|L P|RO` — removing that accident is what surfaced them.

- **Non-US legal forms went unrecognised by the entity name heuristic.** `SIEMENS AG`, `AIRBUS SE`, `ABN AMRO BANK N.V.`, `ASTRAZENECA AB`, `COLOPLAST A/S`, `BREMBO S.P.A.` and `ADS-TEC HOLDING GMBH` all read as no-signal names, because the keyword sets carried a US-centric handful and the strict path splits on `\W+` — so it sees `{S, A}` where the name says `S.A.`, and `{N, V}` where it says `N.V.`. Legal forms are now matched as the final token of the name, with punctuation stripped, so `N.V.`, `NV`, `A/S` and `S.P.A.` resolve to one entry each: 313 of the 7,990 companies in the ticker file were undetected by name, now 163, and across SEC's full 1,054,270-name filer list 2,510 more filers are identified. Terminal-only is what makes the two-letter forms safe — anywhere else `AS` is English and `SE` is Spanish. `ASA`, `KK`, `AD` and `PT` were measured and deliberately left out: "Åsa" is a Nordic given name, so `HEDIN ASA` and `ASK ASA` are people in SEC's LAST FIRST order, and `ROGERS HUGH A.D.`, `GROOM BENJAMIN P.T.` and `NGAI ANTHONY K.K.` are trailing initials. Five individuals in the whole filer list still read as companies through this path — all of the shape `DAVIES JOHN A.B.` — against 2,510 correct identifications.

- **Six individuals were classified as companies because their names contain "l p".** The name heuristic carried the spaced legal suffix `L P` as a loose substring, and a substring does not care where a word ends: "Michael P." is `MICHAE|L P|.`, and so are "Daniel Paul", "Jill P. Meyer", "O'NEIL PATRICK" and "MICHAEL PHILIP". All six reported filers came back with `is_individual == False`. `L L C` had the identical defect one keyword over and went unreported — "MICHAEL L COOPER" is `MICHAE|L L C|OOPER` — so both now match on whole words. The keyword set's own comment claimed its members were long or punctuated enough to be safe as substrings; these two never were. Removing the accidental `L P` match also removed the only name signal three real companies had, all of them `S.A.` — the strict path splits on `\W+` and so sees `{S, A}` where the name says `S.A.` — so the punctuated form joins `L.P.` and `L.L.C.` in the set. Reported by @mwtarnowski. (GH #1019)

- **A table data row rendered only the first line of each cell, discarding the rest.** Header rows were expanded line by line; data rows went through a formatter that did `content.split('\n')[0]`. Both text renderers had the same split — the Rich path paired `overflow="fold"` for headed columns with `overflow="ellipsis"` for headerless ones. Filers from the 1990s and 2000s wrap an entire document in a single-cell layout table, so the cut discarded the filing: Autoliv's 2001 DEFR14A rendered 20,523 characters instead of 83,316, losing its "DEAR STOCKHOLDER" cover letter from an 18,759-character cell. Modern filings lost less but still lost — Apple's FY2024 10-K gains 843 characters of non-whitespace content, AbbVie's 2,828. Exposed rather than caused by the exhibit-index fix, which reclassified three of Autoliv's layout tables from header rows to data rows and so moved them onto the truncating path. (`edgartools-j8bs`)

- **Table lines carried trailing padding to the last column's full width.** Harmless when a tall cell paid it once; now that multi-line cells expand to one line each it is paid per line. Trimmed, which makes rendered text substantially smaller with identical content — Autoliv is 53,278 characters against 83,316 before the truncation bug existed, carrying 39,420 non-whitespace characters against 39,307.

- **A 424B cover-role label matched mid-sentence and named a firm from the next line.** `Placement Agent` was matched anywhere in the cover slice, so Calidi's offering-table footnote — "...the exercise of any of the Common Warrants, or any of the Placement Agent / Warrants." — yielded a placement agent named "Warrants." The labels are cover-grid cells and must now start a line. The footnote was always in the filing; it only became visible once table cells stopped being truncated to their first line.

- **`FilingSGML.text()` truncated long table cells at 200 characters, exactly as `Filing.text()` did.** Both rendered through `rich_to_text(document, width=500)`, which goes via `Document.__repr__` and its hardcoded `table_max_col_width=200`, so the 500 never reached the table renderer. `Filing.text()` was fixed first and this call site was missed, which left the two paths disagreeing — they are asserted equal by `test_filing_text_baseline.test_both_paths_agree`. Both now call `document.text(table_max_col_width=500)`. On Apple's FY2023 10-K the SGML path recovers 6,394 characters, including a tax disclosure that had been cut mid-sentence at "gross unrecognized tax benefits was $19.5 billion, of which $9.5 billion, if recognized, would impact Apple"; Bank of America's 424B2 recovers 9,135, including its automatic-call terms.

- **A debt schedule laid out two-up lost almost all of its rows.** UnitedHealth's FY2024 10-K prints two debt series side by side — `$750 3.5%, Feb 2024 | 750 | $850 5.8%, Mar 2036 | 838` — so every data row names two *different* maturity years, and `_is_header_row`'s multi-year branch read that as a 2024-vs-2036 comparison header. 35 of the table's 40 rows were classified as headers, leaving 3 data rows: the rendered filing kept 2 of 66 maturities and 16 of 66 coupon rates while the surrounding narrative stayed intact, so the output read as complete. Neither existing guard applied — the date-range guard needs a full `March 1, 2024—March 31, 2024` span, and `_has_prose_cell` needs a cell of 100+ characters where these are short numeric cells. A row carrying currency amounts or thousands-grouped figures is now treated as data however many years it names; bare decimals deliberately do not count, since those appear in legitimate header labels where a dollar amount never does. All 66 maturities and coupon rates now render.

- **A row of decimals, and a row of ranges, were both read as table headers.** Two more branches of `_is_header_row` were missing the kind of figures veto the two-up debt schedule needed, and each one collapsed a table that reads as complete without it. UnitedHealth's FY2024 10-K lost two of the three months in its Item 5 buyback table — `November 30, 2024 | 0.9 | 593.39 | 0.9 | 38.7` — because a single date matches the period-header pattern and that branch's list of data indicators recognised `$`, thousands separators and parenthesised negatives but not a plain decimal; it was the only one of three near-identical patterns in the function to omit it, and October survived only because its price cell carried a stray `$`. The same filing lost three of the five rows of its stock-option assumptions table, including `Expected volatility | 25.5% - 30.7% | 29.7% - 30.6% | 30.6% - 30.8%`, because a cell holding a *range* was counted as text: the numeric test stripped `$%,()` and dropped `.` and `-`, leaving the spaces around the dash, and `'255  307'.isdigit()` is False. `Forfeiture rate 5.0%` survived precisely because a single value is not a range, so the rendered table kept the rows nobody asks about. The effect is far wider than the filing it was found on: across the parity corpus the numeric content lost against the legacy renderer falls 18%, with Microsoft's 10-Q going from 68 lost values to 8, its 10-K from 57 to 15, Amazon's from 34 to 13 and Meta's from 53 to 39, and Apple's 10-K now losing nothing at all. A third branch, `year_cells >= 2`, had the same gap and had never been seen to fire; a schedule laid out `2024 | $1,000 | 2025 | $2,000` fires it, so it now carries the veto too. (`edgartools-y264`)

- **`Document.to_markdown()` dropped the exhibit index from 10-K filings.** Every exhibit row was classified as a header row — `_is_header_row` reads any date as evidence of a period column, and exhibit descriptions are full of them ("dated as of June 25, 2019") — leaving no data rows for the renderer to emit. On AbbVie's FY2024 10-K the index is back: 62 "incorporated by reference" rows, and the rendered document grows from 436,060 to 452,668 characters.

- **Table cell text gained a space wherever inline markup split a value.** `_extract_text` inserted one between any two adjacent text fragments, so AbbVie's FY2024 10-K, which writes each exhibit number across two `<a>` tags, rendered `10.10` as `10.1 0` — present but unfindable. Separation now derives from block boundaries only, so `<div>Exhibit</div><div>Number</div>` still reads as two words.

## [5.46.0] - 2026-08-07

### Changed

- **On a multi-filer filing, `Filing.cik` and `Filing.company` now name the issuer rather than whichever filer the quarterly index listed first.** Accession lookups go through EDGAR full-text search before falling back to the quarterly index, and the two order a filing's filers differently. `find("0001918704-25-005439")` was `(70858, 'BANK OF AMERICA CORP /DE/')` and is now `(1682472, 'BofA Finance LLC')`. `all_ciks` and `all_entities` still return every filer; single-filer filings are unaffected.

- **`edgar.xbrl.facts.FactQuery.to_dataframe()` returned a different column set depending on which rows matched.** Columns now follow the query's configuration rather than its results. On Foot Locker's FY2024 10-K, `.limit(5)` returned five fewer columns than the same query unlimited, dropping `balance`, `currency`, `decimals`, `unit_ref` and `weight` because those rows were null. Unpopulated columns come back null, and an empty result carries the full column set. (GH #929)

- **`httpxthrottlecache` is no longer capped below 0.5.0.** The cap existed because 0.5.0 briefly required the `httpx2` fork; 0.6.0 makes `httpx` and `httpx2` optional extras, so the dependency is now `httpxthrottlecache[httpx]>=0.6.0` and edgartools stays on plain `httpx`. The extra is required rather than cosmetic — from 0.6.0 the package installs neither transport by default.

- **Removed the `HttpxThrottleCache._get_httpx_transport_params` monkeypatch.** It was added when the upstream method dropped `verify`, leaving users behind SSL-inspecting proxies unable to disable verification. Upstream extracts `verify` itself now, so the patch was redundant — and a liability, since shadowing an upstream method silently reverts any later fix to it. A test pins the behaviour it protected.

- **`EntityFactsParser._parse_date` no longer swallows every exception type.** It caught bare `Exception` and returned `None`; it now catches `ValueError` and `TypeError`, the two a date parse can legitimately raise. Malformed and non-string input still yields `None`, but an unanticipated failure surfaces instead of being silently absorbed once per fact. (GH #981, thanks @joseturegano)

### Fixed

- **The bundled CUSIP→ticker mapping carried 1,843 symbols with a literal `XXXX` appended, and the 13F parsers rendered them rather than dropping them.** `get_ticker_from_cusip("G3421J106")` returned `'FERGXXXX'` instead of `'FERG'`, so a Ferguson position in a 13F info table displayed a symbol that resolves to nothing — wrong data on the page, not a blank cell. The upstream dataset has been regenerated with all 1,843 recovered, and the merge that builds the bundled file now drops anything not shaped like a symbol. That also clears 534 corporate-action artifacts inherited from older vintages (`Q999SPNOFF`, `3977PAYRTS`, `**********`, bare CUSIP fragments), none of which ever resolved. Coverage rises from 68,512 to 68,830 CUSIPs. (GH #978, thanks @MRileyLeBay)

- **Sections ended at the next item *number* rather than the next section in document order, so filings that group their items out of numeric order lost sections and mislabelled others.** Morgan Stanley's FY2024 10-K (`0000895421-25-000200`) files Items 1B-5 behind the financial statements: Item 1A ran 673,015 characters, swallowing MD&A, the statements and the controls items at confidence 0.95, and Items 1B and 5 were absent. Item 1A is now 73,167 characters and both missing items are present.

- **Sections detected by heading patterns ran past their own end into the next item.** A section ends at the next item's header, but filers wrap that header in a container that begins earlier, so the container was attached whole with everything it held. On Wells Fargo's FY2024 10-K (`0000072971-25-000094`) 20 of 23 sections carried a foreign item heading, and Item 8 came back as 3,329 characters spanning Items 9 through 9C; it is now 374.

- **Wells Fargo's 10-K published its exhibit list as the financial statements.** The filing writes each item heading as a standalone one-row table, which the parser classifies as a header row, leaving `.rows` empty — and the table strategy scanned only `.rows`. Matching fell through to bare-title keywords, so the `FINANCIAL STATEMENTS` heading inside Item 15's exhibit list claimed the `financial_statements` key with 42,462 characters of wrong content. Header rows are now scanned too; the filing yields all 23 items.

- **Citigroup's 10-K items were unreachable by their canonical keys.** Its FY2024 10-K (`0000831001-25-000029`) maps items to printed page ranges in a cross-reference index rather than labelling them in the body, and the parse stopped at the first `</table>` — recovering 14 of 22 items and silently losing all of Part III. The index now continues across adjacent tables and is used to build sections, so `part_ii_item_7` opens on MD&A with 473,576 characters against 234,483 under the old `mda` key.

- **10-K items came back as raw HTML on filings that use a Cross Reference Index.** `TenK.__getitem__` returned `CrossReferenceIndex.extract_item_content()` straight through, and that method yields HTML by contract while every other branch of the same lookup returns text. On Citigroup's FY2024 10-K (`0000831001-25-000029`) `obj['Item 1']` gave 1,685,461 characters of markup; it now gives 218,550 characters of text. A caller parsing the returned markup will need to stop. (GH #821)

- **Numbered index rows fabricated 10-K items.** Freddie Mac's FY2025 10-K mapped every `part_*_item_N` onto an MD&A table caption at full confidence — `obj['Item 11']` returned 30K characters opening on "Table 11 - Other Investments Portfolio" — because the bare row numbers of the MD&A's "List of Tables" fed the generic TOC scan as item numbers. Bare numbers are now ignored when the containing table's header names the numbering without an "Item" column. (GH #918)

- **A two-column table of contents read one column's page number as the other column's item number, inventing a section that truncated MD&A.** Both columns share one HTML row, and the scan for an item label walked back across the gap to take the left column's page number. On Ambac's FY2022 10-K (`0000874501-23-000040`) that produced a phantom `part_ii_item_10` anchored inside MD&A, cutting Item 7 from 158,411 to 149,459 characters. The scan now stops at the column boundary.

- **`Document.to_dataframe()` raised on every real annual and quarterly report.** It failed on 10 of the 11 filings in the 6.0 performance corpus with three different pandas and numpy errors; the only one that worked was a single-table ABS-15G. A filing's tables do not share a schema — Meta's FY2024 10-K has 71 tables whose column indexes run 1 to 17 levels deep — which pandas cannot align. Tables are now flattened to single-level string columns before stacking.

- **A table whose first header text repeats built its row index out of every matching column, giving `None`-padded tuples instead of labels.** `TableNode.to_dataframe()` moved the label column into the index by *label*, and filings repeat a header across spacer columns routinely, so a row label came back as `('Gross written premiums by line of business:', None, None)`. A two-dimensional match raised `Index data must be 1-dimensional`, breaking Tesla's FY2023 10-K. The first column is now taken by position.

- **Comparing a document node with a deep copy of itself raised `RecursionError` instead of returning an answer.** `Node` was a plain dataclass, so the generated `__eq__` recursed through `parent` and `children`. The per-instance `id` uuid normally decides the comparison first, but `copy.deepcopy` preserves it, so `a == copy.deepcopy(a)` walked back on itself. Nodes now compare by identity; nothing observable changes for existing callers, and nodes are hashable again.

- **A beneficial-ownership table was read as the underwriting syndicate, so `lead_manager` returned the column header `'Before Offering'` and a roster of directors.** Both tables have a name column beside a share-count column, so an ownership table satisfied the structural test. On Learn CW Investment Corp's S-1 (`0001140361-21-010426`) five directors were listed ahead of the one real underwriter; it now returns `Evercore Group L.L.C.` alone. Tables whose header region names beneficial ownership are skipped.

- **An underwriter filing as a *division* of its broker-dealer was rejected as parser junk, so `lead_manager` returned `None` on every filing it led.** The name guard's allowlist of permitted lowercase tokens had no entry for `division` or the article `a`, so `EF Hutton, division of Benchmark Investments, LLC` failed on that one token. On Unicycive Therapeutics' S-1/A (`0001213900-21-035033`) the sole underwriter was the rejected name and the filing reported none; it now returns EF Hutton.

### Performance

- **Section extraction is 4.4x faster on the benchmark corpus** — 20.8s to 4.7s across ten filings, with every extracted section unchanged. Anchor resolution ran a full-document XPath per lookup: Morgan Stanley's 9.8MB 10-K made 92 lookups against one tree, 3,854ms and 60% of the stage, two-thirds of them re-resolving an id already looked up. One indexing pass now serves every lookup, and content collection starts at the anchor rather than the document root.

- **A filing was md5'd once per section to rebuild a cache key that could not have changed.** Navigation-link filtering resolves its patterns through a cache keyed by an md5 of the entire filing. Extracting all 22 sections of Morgan Stanley's 9.8MB 10-K hashed it 44 times — 430.7MB hashed to answer a question about 9.8MB — and the answer was the same every time. Patterns are resolved once per document now: the sections stage drops 31%, 4.3s to 3.0s.

- **`Company.get_facts()` spent about 15% of its wall-clock re-deriving dates that were already ISO-8601.** `EntityFactsParser._parse_date` tried `datetime.strptime` first, so the ISO fast path already sitting in the function was never reached — `strptime` takes a locale lock per call, ~3.6us against ~0.10us. WMT, HD, MCD, NKE, LOW and TGT make 364,523 date calls for 139,284 facts. ISO is tried first now. (GH #981, thanks @joseturegano)

- **`filing.obj()` on a registration statement downloaded its whole file-number family looking for a fee exhibit that could not be there.** Each sibling was probed through `filing.attachments`, which fetches the entire `.txt` submission. Learn CW's S-1 (`0001140361-21-010426`) transferred 12.2MB for a 2.4MB filing and found nothing — Exhibit 107 postdates it. Siblings filed before that regime are no longer probed, and probing stops at the first match.

## [5.45.1] - 2026-08-03

Three section-extraction fixes, all reported against 5.44.x with reproductions. Each returned wrong content at full confidence with no warning, so a caller had no signal anything was off.

### Fixed

- **10-K item map shifted by one slot, so each item returned the previous item's body** — Foot Locker's FY2024 10-K (`0001437749-25-009620`) gave Item 6's five-year financial data for `obj['Item 7']` and the MD&A under `Item 7A`; Items 2 and 9B were missing. The body-header scan takes each item's nearest *preceding* anchor, but Novaworks nests the anchor inside the heading, so every item took the previous one's. It failed silently — every anchor was real. (GH #923)

- **10-K item map emitting codes that do not exist in Reg S-K** — Foot Locker's FY2013 10-K (`0001144204-14-019510`) returned `Item 2P`, `Item 3L`, `Item 8C` and eleven more, each phantom splitting the real item's content; `Item 1` ran to 275,435 chars, now 3,340. TOC rows split label and title across cells, so `"Item 4Mine Safety Disclosures"` read the title's initial as a suffix. A suffix letter is never followed by a lowercase letter, which now decides it. (GH #923)

- **Two-column tables of contents put items under the wrong Part** — Ambac's FY2022 10-K (`0000874501-23-000040`) returned 538,701 chars for `obj['Item 7']`, roughly 70% of it Items 8 through 15, and dropped Item 4. Its TOC interleaves two columns, so one running part context saw both columns' Part headers, scrambling the order boundaries are sorted by. Columns are now read one at a time; Item 7 is 158,411 chars. (GH #924)

### Acknowledgements

- The three section-extraction fixes above were all reported, with reproductions, by **g-carmichael**.

## [5.45.0] - 2026-08-02

Text extraction correctness in `edgar/documents`. Two things before upgrading:

- **Extracted text changes for nearly every filing.** Seven whitespace defects are fixed and one spacing heuristic retired, so `Filing.text()`, markdown and section slices will differ from 5.44.x. Almost all of it is repair, but cached text, stored hashes and embeddings will need regenerating.
- **Filings over 10MB were losing most of their text.** Anything you processed above that size — bank and insurer 10-Ks, N-PX, ABS — is incomplete.

### Changed

- **`ParagraphNode.text()` no longer spaces adjacent inline elements by tag name.** An allowlist invented a space between any two adjacent inline elements, corrupting the Item headings section matchers key on (`Item 1A. RI SK FACTORS`). It is replaced by three signals that read the boundary: a CSS gap, a fixed-width marker box, a standalone list or checkbox glyph. Of 245 spaces removed across 57 fixtures, 222 are confirmed repairs; two elements with no signal at all are now joined, the deliberate cost.

### Fixed

- **Documents over 10MB parsed by a second, lossy pipeline** — filings above 10MB took a separate parser that dropped text hosted directly in `<div>`s. Citigroup's FY2024 10-K returned 830K chars against 1.81M, missing MD&A, Risk Factors and Financial Statements entirely, and that path was slower than the one it relieved. It is removed; every document now takes one pipeline. `streaming_threshold` remains as a deprecated no-op.
- **Words glued together in extracted text** — seven passes deleted boundary whitespace instead of collapsing it, destroying the word gap before anything downstream could recover it: `TheFederal Reserve`, `threereportable business segments`, `•MacBook Pro 16-in.`, `Yes☒` on a dozen large-cap cover pages. Morgan Stanley's FY2024 10-K alone had ~490. Boundary whitespace is now collapsed and never deleted; genuinely unspaced splits stay glued.
- **Bullets and bare enumerators promoted to headings** — a filer who put a bullet glyph in its own span got a `HeadingNode` out of it, so 23.6% of all headings were glyphs or bare enumerators (Meta's FY2024 10-K: 180 of 296). They surfaced through `doc.headings`, through markdown as `### •`, and through document search. Header detection now requires content that could be a heading.
- **`text()` on very large tables taking hours** — a dimension pass ran before the grid existed and rescanned an empty structure once per preceding row. Fannie Mae's `0000310522-18-000010` took **1h12m, now 24.1s**, byte-identical.
- **Header-only pre-2004 submissions failing, then failing silently** — EDGAR sometimes serves the `.hdr.sgml` artifact as a submission's text file (`0000950123-96-000525`), which was rejected outright. Behind it, Schedule 13D/G filers arrive under `<FILED-BY>` rather than `<FILER>`, so once routed the filing parsed "successfully" with zero filers and a `None` CIK.
- **XBRL extraction warning untraceable** — it went to the root logger with no document context, and sat inside a `try:` that turned a raising log handler, the standard way to locate a warning, into a parse failure. It now logs to `edgar.documents.parser` with the exception type and a content preview.

### Acknowledgements

- The streaming-pipeline, large-table and pre-2004 header fixes came from **Michael Grüning** (TU Ilmenau), out of the same 7-million-filing crawl that produced the 5.44.0 cluster.


## [5.44.1] - 2026-07-31

### Fixed

- **`filing["Item 7"]` hung indefinitely on some 10-Ks** — `CrossReferenceIndex.has_index()` matched the cross-reference heading, then probed for the index table with a single regex nesting six lazy quantifiers under `DOTALL` against the *entire* filing HTML. Where the heading matched but the table shape did not, it backtracked catastrophically: on ODP Corp's FY2025 10-K (5.6MB) the call did not finish within 45 seconds. A successful match returned instantly, so only the non-matching case was affected. It is reached from `TenK.__getitem__`, so any item lookup on an affected 10-K hung — and because `re` holds the GIL throughout, one such filing froze every other thread in the process, presenting as a whole-process hang rather than one slow filing. Detection is now anchored to the index table `_find_index_table()` already locates and scans it row by row, which is linear. Bounding the search window alone was not enough: on dense markup the old pattern exceeded 10s at 3.6K chars, so any fixed window stayed exploitable. GE and Citigroup still detect and parse unchanged. (GH #928)
- **10-Q items rebuilt from cross-references to the 10-K** — ICE's Q3 2024 10-Q returned 101K chars for `obj['PART II, Item 1']`, opening mid-sentence inside the MD&A's cross-reference to "Item 1 'Business — Regulation' … in our 2023 Form 10-K" (same shape on CSCO and CTSH 10-Qs). The TOC anchor was correct, but the correctly-anchored Legal Proceedings stub is under 200 chars, which trips the short-section rescue; the rescue's on-heading check demanded the *10-K* title for the item number (Item 1 → BUSINESS), misjudged the 10-Q text, and then regex-hunted the raw HTML document-wide, matching the cross-reference. A text opening with the item's own "ITEM N" heading now counts as correctly anchored whatever the form, and the rescue's search is bounded to the window between the section's start and end anchors — its premise is an anchor that landed just before the body, so the real heading is never behind the anchor. Thanks to @sf1tzp for the diagnosis and the fix. The second half of #918 — Freddie Mac's numbered "List of Tables" index rows fabricating `part_*_item_N` anchors from bare row numbers — is unfixed and that issue stays open. (GH #918)

## [5.44.0] - 2026-07-29

### Fixed

- **10-K Item 7A silently duplicating Item 7** — Regions Financial's FY2021 10-K (`0001281761-22-000016`) returned Item 7's 194K-char MD&A for `obj['Item 7A']`, at full confidence with no warning: the TOC links only page numbers, and both items start on page 41, so they collided on one anchor. Colliding items are now re-resolved from their own body headings, bounded so a boundary can't invert. (GH #920)
- **Workiva 10-K items mis-anchored or dropped** — Tesla's FY2023 10-K returned 145K chars for `TenK['Item 3']` (should be 1,165). Workiva gives a row's "Item N." label link a different href than its title link, and the label hrefs are broken, so items anchored in the wrong place or vanished when their title wasn't in the keyword vocabulary. Each TOC row is now resolved as a whole. (GH #915)
- **`edgartools[ai]` installing an incompatible `mcp`** — mcp 2.0.0 removed the decorator-based `Server` API that `edgar/ai/mcp/server.py` binds at import, so an unpinned resolve made `edgartools-mcp` fail to start. Capped at `mcp>=1.12.3,<2.0.0` until the server is ported. (GH #917)
- **`FilingSGML.text()` returning raw XML for ownership forms** — Forms 3/4/5 have an `<ownershipDocument>` XML primary, which failed the is-it-HTML check and came back as tag soup on the SEC's highest-volume form type. Ownership XML is now detected by root element and rendered through `Ownership.to_html()`. `Filing.text()`/`.html()` are deliberately untouched — their contracts are load-bearing (see the d216a934 revert).
- **Unterminated HTML comments crashing text extraction** — 1990s filings open with `<!--DOCTYPE HTML PUBLIC ...>` (a typo for `<!DOCTYPE`), and lxml treats the stray `<!--` as running to end of input, so the tree came back empty and `text()` raised `HTMLParsingError` (0001034670-01-500017). Unterminated comments are now closed at end-of-line; verified byte-identical across a 44-filing corpus.
- **`FilingSGML.text()` returning mojibake for PDF-only filings** — UPLOAD comment letters with a scanned-PDF primary were decoded as UTF-8, yielding pages of replacement characters that poisoned search and markdown downstream. Binary primaries are now detected before any decode: `text()` returns the SEC's TEXT-EXTRACT sibling when present, otherwise `None`.
- **8-K `.items` dropping items** — two causes. 2005-era filings glue an item header onto a horizontal rule (`------Item 4.02 Non-Reliance...`), which the line-anchored regex missed (GMAC 0000040729-05-000026); and when the HTML strategies returned a partial set, the text strategy was never consulted (Cimarex 0001047469-05-006981). Headers are now matched after a rule, and all three strategies are unioned. Validated on 66 modern 8-Ks with no spurious items.
- **SGML header parser leaking a stale subheader** — 1999–2005 headers that follow a nested `FILER` block with a flat top-level section carried the old subheader into the new one, emitting `Subheader ... not found` warnings and dropping that section's values; on 1990s `FORMER COMPANY` entries the same leak raised `KeyError`. The subheader now resets per section, flat lines are captured, and the warning carries the accession number.
- **Filings from 1993 Q1–1994 Q2 unreachable** — `available_quarters()` hardcoded EDGAR's start as 1994 Q3, so `get_by_accession_number()` and `get_filings()` structurally rejected earlier periods even though SEC's full-index serves back to 1993 Q1 (verified; 1992 returns errors). The boundary and the open-ended `filing_date` default now start at 1993 Q1.
- **Corrupt `colspan` exhausting memory** — filing 0001193125-06-185884 carries `colspan="376967340"`; the matrix allocated that many cells per row, reaching hundreds of GB (~700 GB reported from a 7M-filing crawl) before being killed. Spans are now clamped (colspan ≤ 1000, rowspan ≤ 10000) with a 2000-column cap and grid-bounded placement loops. Parses in ~4s at 0.3 GB.
- **Nested tables reprocessed by every ancestor** — rows and cells were collected with descendant searches (`.//tr`, `.//td`), so a row nested N deep was processed once per ancestor: on 0000880195-09-000191 (8,207 tables, 26 deep) rows were processed 11.3× over, turning `FilingSGML.text()` into a 3-hour call and duplicating inner cells into outer tables. Traversal is now scoped to each table's own rows. Parses in ~7s.

### Acknowledgements

- The last eight fixes above all came from a single report by **Michael Grüning** (TU Ilmenau), who crawled roughly 7 million SGML filings from 1993–2009 and 2018 and sent back nine clustered defect classes with accession numbers. Whole-archive sweeps surface failure modes that a fixture corpus of modern, well-formed filings structurally cannot, and every one of these had been latent for years. Our thanks for the report and for the follow-up crawl that verified the fixes.

## [5.43.1] - 2026-07-27

### Fixed

- **497K fee-waiver / net-expense mix-up** — for fee tables using the standard "After Fee Waiver and Reimbursement" wording, `ShareClassFees.fee_waiver` held the net expense ratio and `net_expenses` was `None` (ProShares UltraPro QQQ: `waiver=0.84` where the true waiver is 0.13). Net expenses are now matched first and the waiver normalized to a signed reduction, so `total_annual_expenses + fee_waiver == net_expenses`. (GH #912)
- **497K fee values corrupted by footnote markers** — a marker sharing the value cell was glued to the number (John Hancock's `"0.67 1"` → `0.671`), and `"(0.37%)"` came back `None`; every percentage field was affected, not just the waiver. The parser now unwraps parenthesised negatives and takes the leading numeric token before a marker, while dates, labels and period headers still parse as `None`. (GH #912)
- **TTM EPS stale trailing year** — `income_statement(period='ttm')` gave GOOGL basic EPS of 9.45 for Q2 2026 instead of 20.16, varying with the requested period count: windows were labelled by SEC `fiscal_year`, which tags a re-filed comparative quarter with the *filing's* year, so two collided and the older won. Labels now derive from `period_end`. Per-share values also render with 2 decimals. (GH #910)
- **`series_only=True` ignored for series and class IDs** — `Fund("S000026864").get_filings(..., series_only=True)` returned the umbrella trust's 444 filings where `Fund("VCLT")` for the same fund returned 26; `_target_series_id` was set only on the ticker path, so the call fell through to trust-wide delegation. It is now backfilled from the resolved hierarchy, so ticker, series ID and class ID agree. (GH #909)
- **Quarterized cash flow dropped every negative quarter** — `TTMCalculator.quarterize()` returned only Q1 for concepts like `NetCashProvidedByUsedInInvestingActivities` (12 quarters instead of ~48 for GOOGL), because `_is_positive_concept` substring-matched `'cash'` and treated negative flows as data-quality errors. Cash flow and `IncreaseDecreaseIn*` lines are now signed; GOOGL FY2024 investing reconciles to the reported −45.536B. (GH #907)
- **10-K items overflowing to end-of-document** — where the TOC anchored only a subset of items, Coeur Mining's FY2025 `TenK['Item 7']` ran 257K chars to the director signatures with Items 7A/8/9A/10/11 embedded. Body-header recovery now union-merges the items the TOC missed (TOC wins conflicts), the bold check accepts split-span headers, and a guardrail flags any section embedding a later item's header. Standard filers parse byte-identically. (GH #904)
- **10-Q sections outside the form's item range** — Freddie Mac's Q1 2026 10-Q returned a phantom `part_i_item_6` (165K chars) at full confidence with no warning. The 10-Q `FormSchema` now declares per-part item ranges (Part I: 1–4, Part II: 1–6) and validation flags anything outside them, appending a warning and reducing confidence rather than dropping content. (GH #905)

## [5.43.0] - 2026-07-19

### Added

- **`RegistrationS3.sections` / `.section()` for S-3 shelf registrations** — `filing.obj()` for an S-3 now exposes section-scoped Reg S-K access (`risk_factors`, `use_of_proceeds`, `plan_of_distribution`, `selling_stockholders`, …), the same surface `RegistrationS1` and `Prospectus424B` already provide. Previously S-3 fell through to the non-title-based default schema and could not be section-scoped, blocking RAG/NLP workflows over shelf registrations. A new `S3_SCHEMA` covering `S-3`, `S-3/A`, and `S-3ASR` reuses the shared S-1 prospectus vocabulary; a short filing with no resolvable titles falls back to a single `full` section (no content lost), and item-based forms (8-K, 10-K, …) are untouched. (GH #877)

### Fixed

- **PP&E silently missing from the EntityFacts balance sheet** — `Company('GE').get_facts().balance_sheet()` omitted Property, Plant & Equipment entirely for FY2021 onward. GE stopped reporting `us-gaap:PropertyPlantAndEquipmentNet` after FY2020 and now presents the net line only under a company-specific extension tag that the SEC companyfacts API does not expose, so the standardized statement built the row empty and dropped it. The builder now reconstructs standard 'Net' balance-sheet lines from component concepts the filer still reports (PP&E as `PropertyPlantAndEquipmentGross − AccumulatedDepreciation…`), matched to each displayed period by `period_end` — GE's components survive only as prior-year-end comparatives in later 10-Qs, tagged Q1–Q3 of the following fiscal year, never FY. A period already reporting the concept directly is untouched, and every component must be present or the period is skipped (no gross-as-net). The operating-lease ROU asset GE folds into its extension line renders on its own standardized row. The XBRL path (`get_financials().balance_sheet()`) was unaffected. (GH #894)
- **Text following an inline-XBRL fact is no longer dropped from `filing.text()`** — the `edgar.documents` parser silently lost the text after an `ix:nonfraction`'s closing tag, usually the unit word and the rest of the sentence, so "$95.2 billion, of which substantially all will be paid" rendered as a bare "$ 95.2". `_get_element_text` collected each child's text but never its lxml `.tail`; it now captures that trailing text (including after skipped `ix:exclude` children, whose content is still dropped). On NVIDIA's FY2026 10-K, scale words ('billion'/'million') and trailing clauses are recovered across dozens of facts; filings without the inline-container pattern render byte-for-byte unchanged. (GH #898)
- **MCP resource reads no longer fail with `Unknown resource`** — the MCP SDK passes registered resource handlers a Pydantic `AnyUrl`, which did not compare equal to the string literals the handler matched against, so every listed resource URI failed to read even though it listed correctly. Incoming URIs are now normalized to strings before matching. (GH #897)

### Performance

- **HTML document parsing is 18–23% faster** — `parse_html()` no longer eagerly renders the full document text on every parse. Document statistics (`text_length`, `table_count`, …) are computed lazily on first access to `metadata.statistics` rather than during post-processing, and two hot preprocessing regexes (repeated-`<br>` collapsing and sentence-spacing repair) were rewritten to avoid backtracking. Measured 583 ms vs 726 ms (Apple 10-K) through 1,534 ms vs 1,871 ms (Oracle 10-K); rendered output is unchanged, verified by SHA-256 digest of the full rendered text. (GH #900)

## [5.42.0] - 2026-07-09

### Added

- **`RegistrationS4` data object for S-4 / F-4 registrations** — `filing.obj()` now returns a typed object for merger/acquisition/de-SPAC registrations, exposing the standard registration field surface (`cover_page`, `fee_table`, `total_offering`, `net_fee`, `securities`, …) plus `is_foreign` (F-4) and an `offering_type` classifier. Covers S-4, S-4/A, F-4, F-4/A. (GH #876)
- **`GET /health` liveness endpoint on the MCP HTTP server** — when the MCP server runs in HTTP transport mode it now exposes an unauthenticated `GET /health` returning `{"status": "ok", "version": <server version>}`, giving container orchestrators (Docker `HEALTHCHECK`, Kubernetes liveness/readiness probes) a cheap liveness signal without the full MCP handshake that the `/mcp` endpoint requires. (GH #882)

### Fixed

- **`get_concept()` stale-tag data** — for companies that switched GAAP tags (e.g. NVDA/AMZN moving capex from `PaymentsToAcquirePropertyPlantAndEquipment` to `PaymentsToAcquireProductiveAssets`), `get_concept()` now picks the most recent fact *across all synonyms* instead of returning the first, stale one; `return_metadata=True` also carries the resolved `period`/`period_end`/`filing_date`. An explicit `period=` still resolves by priority. (GH #892)
- **`get_ttm_revenue()` / `get_ttm_net_income()` stale values** — these now evaluate every candidate concept and use the one whose TTM window ends most recently, instead of the first that resolves; tag-migrated companies are corrected (NVDA `$10.9B`→`$253.5B`, GOOG no longer a year behind). Adds a `TTMMetric.is_stale` flag (and warning) when the newest quarter lags the reference date. (GH #893)
- **10-K section `.item` / `.part` metadata** — sections detected by the pattern extractor (e.g. small-cap 10-Ks that split the `Item 7.` fragment from its MD&A title) now resolve their part and item instead of returning `None`, so semantic keys like `mda`/`business` carry correct `.item`/`.part`. (GH #891)
- **10-Q `Part I / Item 4` heading leak** — Controls and Procedures no longer absorbs the trailing "PART II — OTHER INFORMATION" heading; the legitimate "PART C — OTHER INFORMATION" heading of S-1/N-1A/N-2 filings is left intact. (GH #883)
- **`Fund()` ticker/Class-ID collision** — ETF tickers starting with "C" that have real SEC series/class registration (CIBR, CQQQ, COPX, CARZ, CALF, …) now resolve; `fund.company`/`.series`/`.share_class` return the object or `None` per their contract instead of raising `AttributeError`. (GH #889, #890)

## [5.41.0] - 2026-07-07

### Security

- **`Attachments.query()` no longer uses `eval()`** — filter strings were passed to `eval()` with builtins reachable, allowing arbitrary code execution. Queries are now evaluated against a restricted AST; disallowed input raises `ValueError` and legitimate queries are unchanged. (GH #884)

### Fixed

- **`Fund.get_filings(series_only=True)` now actually filters to the fund's series** — it silently returned the whole umbrella trust's filings (a sibling series' data). It now resolves the series via SEC browse-edgar, pushing the form filter server-side so even large funds (e.g. `VOO`) return reliably, and returns an empty `Filings` rather than the trust when nothing matches. (GH #888)
- **Form 4/5 `obj()` no longer crashes when a transaction has no `<transactionCoding>`** — the missing `Code` column raised `AttributeError`, making the whole filing unreachable. Uncoded transactions now degrade to `TransactionType=None` in both the non-derivative and derivative tables. (GH #887)
- **Images (`<img>`) are no longer dropped from the new parser's markdown** — `Document.to_markdown()` now renders images as `![alt](url)` (resolving relative `src` against the document URL when known); `TextExtractor` gains an opt-in `include_images` placeholder. `Filing.markdown()` still uses the legacy parser and is tracked separately. (GH #886)
- **`get_revenue()` / `get_net_income()` / `get_operating_income()` no longer return a prior-year value on multi-duration 10-Qs** — the getters picked the period column positionally, but `to_dataframe()` columns aren't recency-ordered. They now order by period metadata (current reporting period first). Annual filings and balance-sheet getters are unaffected. (GH #885)
- **`Company.reit_subtype` no longer mislabels net-lease equity REITs as mortgage** — a stale/trivial interest line flipped equity REITs like `WPC` to `mortgage`. Classification now compares the magnitude of property income against net interest income (mortgage only when interest is at least 10% of property income). (GH #854)

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
