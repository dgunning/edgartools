# Private Credit Evidence Access Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven development to execute this plan task-by-task with a review after each task.

**Goal:** Let MCP clients identify, search and read a specific SEC filing document or exhibit, and preserve document identity when they arrive through filing URLs or full-text search.

**Architecture:** Add one `edgar_document` MCP tool over existing `Filing.attachments`, `Attachment.markdown()` / `text()` and `Filing.grep()` APIs. Extend `GrepMatch` with additive character offsets and reuse the existing continuation cursor/cache for long document results. Extend `edgar_filing` and `edgar_text_search` with attachment metadata, then update MCP instructions, skill guidance and documentation.

**Tech Stack:** Python, existing MCP `@tool` registry and `ToolResponse`, SEC filing attachments, `edgar.ai.mcp.tools.continuation`, pytest, local SEC filing fixtures.

## Global Constraints

- Compatibility is additive: do not remove or rename existing MCP parameters or response keys.
- `edgar_document` accepts an accession number or a URL whose scheme is HTTPS, host is exactly `www.sec.gov` and path starts `/Archives/`; never fetch an arbitrary host.
- A requested sequence number, filename or exhibit type must resolve to the specific attachment. Ambiguous exhibit-type matches return candidates; they never choose the first match or fall back to the parent filing.
- Each document response includes the filing identity and source URL. Unreadable documents retain their identity and URL and return an `unreadable_reason`.
- Readable document text is paged at no more than 6,000 characters. Cursors use existing versioned JSON helpers, size limits, query identity and result fingerprints.
- Search results include a document-bound locator with `document` and `char_offset`. `GrepMatch.char_offset` is additive and defaults to `None` for existing callers.
- Keep extraction descriptive. Do not infer legal protections, reconstruct complete agreement histories or claim a BDC exhibit belongs to a portfolio borrower.
- Do not implement the deferred exhibit-reference parser, DERA maturity/lien enrichment or borrower-name parsing fix in this phase.
- Do not edit `CHANGELOG.md`; use changelog fragments under 500 characters with a project reference.
- Do not commit cassettes over 10 MB. Keep SEC network tests sequential and use local fixtures or VCR for deterministic coverage.

---

### Task 1: Repair continuation consistency and notes reuse

**Files:**
- Modify: `edgar/ai/mcp/tools/fund.py`
- Modify: `edgar/ai/mcp/tools/notes.py`
- Test: `tests/test_mcp_bdc_portfolio.py`
- Test: `tests/test_mcp_bdc_nonaccrual.py`
- Test: `tests/test_mcp_notes_read_paging.py`

**Interfaces:**
- BDC page cursors continue to use the existing `fingerprint()` and `check_fingerprint()` API, but fingerprint serialized evidence fields rather than identifiers alone.
- Notes parsing is cached in `results_cache` under accession number and `edgar.__version__`; callers still receive source metadata from the current `Filing` selection.

- [ ] **Step 1: Add the stale-cursor regression.** Start a portfolio page with one holding, keep its identifier and ordering, change its fair value before the continuation call, and assert the continuation returns `CURSOR_STALE`. Add the same stable-identifier mutation check for non-accrual evidence.
- [ ] **Step 2: Run the focused tests and confirm the stale-cursor assertions fail against identifier-only fingerprints.**
- [ ] **Step 3: Change both BDC fingerprints to cover the serialized fields returned to MCP, including nullable monetary values, type and footnote text where present.**
- [ ] **Step 4: Add a notes continuation test that resolves two fresh filing objects for the same accession, follows a table or context cursor, and asserts the expensive `filing.obj()` extraction happens once while the second response contains the next page.**
- [ ] **Step 5: Run the focused BDC and notes/read paging tests; confirm cursor identity mismatch behavior and existing page shapes remain valid.**
- [ ] **Step 6: Commit as `fix(mcp): fingerprint BDC evidence and reuse parsed notes`.**

### Task 2: Add exact character offsets to grep matches

**Files:**
- Modify: `edgar/search/grep.py`
- Test: `tests/test_grep_locator.py`

**Interfaces:**
- `GrepMatch` gains `char_offset: Optional[int] = None` after its existing fields.
- `_grep_text()` sets `char_offset` to the start index of each literal or regex match in the original input text.

- [ ] **Step 1: Add tests asserting the literal match in `"ABC covenant XYZ"` has offset `4`, the regex match in `"A\nCOVENANT; later"` has offset `2`, and a directly constructed legacy `GrepMatch("EX-10.1", "term", "term")` has `char_offset is None`.**
- [ ] **Step 2: Run `tests/test_grep_locator.py` and confirm the new offset assertions fail before implementation.**
- [ ] **Step 3: Populate offsets in both branches of `_grep_text()` without changing context formatting or match ordering.**
- [ ] **Step 4: Run `tests/test_grep_locator.py`, `tests/test_v530_coverage.py` and `tests/issues/regression/test_issue_819_search_grep_on_text_filings.py`.**
- [ ] **Step 5: Commit as `feat(search): include source offsets in grep matches`.**

### Task 3: Implement `edgar_document` list, search and read

**Files:**
- Create: `edgar/ai/mcp/tools/document.py`
- Modify: `edgar/ai/mcp/server.py` (`_import_tools` registration only)
- Modify: `edgar/_filings.py` (exact filename targeting and markdown-aligned grep offsets)
- Test: `tests/test_mcp_document.py`

**Interfaces:**
- Register `edgar_document(action, accession_number=None, url=None, document=None, query=None, regex=False, include_all=False, around=None, cursor=None, limit=20)` with actions `list`, `search` and `read`.
- Resolve a document selector by exact sequence number, exact filename or document type. If a type matches more than one attachment, return `AMBIGUOUS_DOCUMENT` with candidate identities.
- `list` returns sequence, filename, type, description, size, primary/readable flags and URL; hide XBRL and R-file noise unless `include_all=True`. `list` and `search` page records with `limit` (default 20, maximum 50) and the normal `page.next_cursor` response shape.
- `search` calls `Filing.grep()` and returns matches with `location`, `match`, `context` and a locator `{document, char_offset}` tied to one exact attachment. Its cursor binds query, regex mode, document filter and `include_all`.
- Search accumulation has a fixed match and match-span cap; overly broad queries return a useful narrowing error before pagination or cache storage.
- `Filing.grep()` gains an optional markdown-rendered search mode for document locators, and exact filename filters take precedence over exhibit-type substring matching so offsets map to the document returned by `read`.
- `read` selects the attachment by `document` or the document in `around`; render with `markdown()` then `text()`, page at 6,000 characters and return `next_cursor` for the next page. `around` accepts `{document, char_offset}` and centers the first page on that locator where document boundaries permit. Do not allow `around` and `cursor` together. Its cursor binds accession and exact document identity.
- All successful responses contain `filer` and `source`, including `selected_by` (`accession` or `url`) and the exact document URL when one document is selected; unreadable reads return attachment identity, URL and `unreadable_reason` without interpreting empty content as absence of evidence.
- Cache document text and search results by accession, document identity and extractor/library version. Fingerprints cover returned text/records, not just document identities. Cursors bind action, accession, document, query/filter and fingerprint.

- [ ] **Step 1: Add tests for registration/schema and `list` metadata using a real local AAPL 10-Q exhibit fixture; assert the selected exhibit identity and the filed text names `Timothy D. Cook`.**
- [ ] **Step 2: Add selection and security tests: exact sequence and filename resolve; ambiguous `EX-10` returns `AMBIGUOUS_DOCUMENT` and candidates; missing documents return `DOCUMENT_NOT_FOUND`; non-SEC hosts, HTTP URLs and paths outside `/Archives/` return `INVALID_URL`.**
- [ ] **Step 3: Add search and read tests using local attachment text: match offsets produce a locator for the correct filename; search result paging honors `limit`; `around` returns surrounding text; two cursor text pages are at most 6,000 characters and have no overlap or omission; changed search records or text return `CURSOR_STALE`.**
- [ ] **Step 4: Add silence checks for unreadable PDF/image content and invalid action/required arguments; assert identity, URL and a useful error/reason are returned.**
- [ ] **Step 5: Run `tests/test_mcp_document.py` and observe the missing-tool failures before implementation.**
- [ ] **Step 6: Implement URL parsing without making requests to the supplied URL, exact attachment selection, default filtering, search locators, readable-text paging and standard cursor errors.**
- [ ] **Step 7: Run `tests/test_mcp_document.py`, `tests/test_mcp_server.py` and the relevant attachment/grep tests.**
- [ ] **Step 8: Commit as `feat(mcp): add filing document and exhibit access`.**

### Task 4: Preserve document identity in filing and EFTS results

**Files:**
- Modify: `edgar/ai/mcp/tools/filing.py`
- Modify: `edgar/ai/mcp/tools/text_search.py`
- Test: `tests/test_mcp_document_routing.py`

**Interfaces:**
- `edgar_filing` keeps its existing context response and adds `period_of_report`, filing `url` and a `document_hint` for a supplied SEC document URL. The hint includes the URL filename and matched sequence when present; next steps point to `edgar_document` with the accession and exact document identity.
- Each `edgar_text_search` hit adds `file_type`, `file_description` and `document_id` from its existing `EFTSResult` fields. Its next step points to `edgar_document` using accession and document ID when one is available.

- [ ] **Step 1: Add tests for an SEC exhibit URL that assert the `edgar_filing` response retains the filename, accession, matched attachment sequence, period and filing URL. Add a URL whose filename is not in the attachment list and assert its unmatched hint stays explicit.**
- [ ] **Step 2: Add a text-search test with a concrete `EFTSResult` carrying `file_type="EX-10.1"`, `file_description="Credit Agreement"` and `document_id="credit-agreement.htm"`; assert all three survive serialization and the next step routes to `edgar_document`.**
- [ ] **Step 3: Run the focused tests and confirm each new field assertion fails before implementation.**
- [ ] **Step 4: Add the response fields without changing existing keys or parsing document bytes from the caller-provided URL.**
- [ ] **Step 5: Run `tests/test_mcp_document_routing.py` and relevant MCP tool tests.**
- [ ] **Step 6: Commit as `feat(mcp): preserve document identity in filing search`.**

### Task 5: Document and expose the recovery-document workflow

**Files:**
- Modify: `edgar/ai/mcp/server.py` (tool count and workflow instructions)
- Modify: `edgar/ai/mcp/tools/filing.py` and `edgar/ai/mcp/tools/text_search.py` (tool examples and routing descriptions)
- Modify: `edgar/ai/mcp/tools/fund.py`, `edgar/ai/mcp/tools/notes.py` and `edgar/ai/mcp/tools/reader.py` (valid selector-preserving continuation examples)
- Modify: `edgar/ai/skills/reports/skill.yaml` (document/exhibit discovery pattern)
- Modify: `docs/ai/mcp-tools.md`
- Modify: `edgar/ai/mcp/docs/MCP_QUICKSTART.md`
- Modify: `docs/ai/mcp-workflows.md`
- Modify: `tests/test_mcp_docs_examples.py`
- Create: `changelog.d/private-credit-document-access.added.md`
- Modify: `changelog.d/private-credit-bdc-evidence.added.md` and `changelog.d/bdc-portfolio-borrower-name.fixed.md` to add a valid project reference

**Interfaces:**
- Server instructions list 14 tools and route exhibit search results to `edgar_document`; instructions distinguish filing sections (`edgar_read`) from specific documents (`edgar_document`).
- Docs show accession-pinned list/search/read examples, the required selector repetition on cursor calls, the incorporated-by-reference limitation and the distinction between filer and underlying borrower.
- Example-schema tests parse every marked JSON tool-call example from the docs and every tool description, then check tool registration, allowed and required parameters, action enums and conditional selector/document requirements. The existing manually maintained `DOCUMENTED_EXAMPLES` list is removed.
- Skill guidance tells agents how to identify an exhibit, search it and read around a locator without implying legal interpretation.
- Changelog fragments remain under 500 characters and end with a reference to the Private Credit Evidence Access project design.

- [ ] **Step 1: Add machine-readable `{"tool": ..., "arguments": {...}}` JSON call examples to `docs/ai/mcp-tools.md` and the descriptions for `edgar_fund`, `edgar_notes`, `edgar_read`, `edgar_filing`, `edgar_text_search` and `edgar_document`; every continuation example repeats its original filing selector.**
- [ ] **Step 2: Add a failing test that extracts every marked JSON example from `docs/ai/mcp-tools.md`, rejects missing required/conditional selectors and accepts only registered tool arguments and enum values.**
- [ ] **Step 3: Run the docs-example test and confirm it fails on a deliberately omitted required selector.**
- [ ] **Step 4: Update server instructions/tool count, tool descriptions, reports skill YAML, MCP tools docs, quickstart and workflows with the recovery-document flow and its limits.**
- [ ] **Step 5: Replace the manual examples list with validation of all marked examples; preserve the existing tests that prove unknown keys and invalid enum values fail.**
- [ ] **Step 6: Add the Phase 2 changelog fragment and add project references to the two Phase 1 fragments; verify each stays within the 500-character cap and run `scripts/release/assemble_changelog.py --check`.**
- [ ] **Step 7: Run focused tests for document tool registration, examples, skill YAML, MCP routing and the Phase 1 continuation regressions fixed in Task 1.**
- [ ] **Step 8: Commit as `docs(mcp): expose the recovery-document workflow`.**

### Final verification

- [ ] Run `.venv/bin/python -m pytest tests/test_grep_locator.py tests/test_mcp_document.py tests/test_mcp_document_routing.py tests/test_mcp_docs_examples.py tests/test_mcp_selection.py tests/test_mcp_continuation.py tests/test_mcp_bdc_portfolio.py tests/test_mcp_bdc_nonaccrual.py tests/test_mcp_notes_read_paging.py tests/test_mcp_server.py tests/test_mcp_intent_tools.py -q` with network-marked tests run only as bounded, sequential invocations.
- [ ] Run `.venv/bin/python scripts/release/assemble_changelog.py --check`.
- [ ] Run `.venv/bin/python -m ruff check` on changed Python files if Ruff is installed.
- [ ] Confirm no generated cassette exceeds 10 MB, `CHANGELOG.md` is unchanged and the working tree contains only this feature's intended changes plus pre-existing `.agents-context` material.
