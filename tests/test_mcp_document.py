"""Fast contract tests for the ``edgar_document`` MCP tool.

All SEC lookup is monkeypatched. The Apple exhibit content comes from the
checked-in attachment fixture, so these tests exercise the real attachment
markdown/text renderers without network access.
"""
from __future__ import annotations

import pytest
from pathlib import Path

from edgar._filings import Filing
from edgar.ai.mcp.tools import continuation
from edgar.ai.mcp.tools.continuation import ResultCache


ACCESSION = "0000320193-25-000073"
FIXTURE = Path(__file__).parent / "fixtures/attachments/aapl/20250329/a10-qexhibit32103292025.htm"


class FakeAttachment:
    def __init__(
        self,
        sequence: str,
        filename: str,
        doc_type: str,
        text: str | None,
        *,
        description: str = "",
        size: int = 10,
        ixbrl: bool = False,
        markdown: str | None = None,
        unreadable_error: str | None = None,
    ):
        self.sequence_number = sequence
        self.document = filename
        self.document_type = doc_type
        self.description = description or doc_type
        self.display_description = description or doc_type
        self.size = size
        self.ixbrl = ixbrl
        self._text = text
        self._markdown = markdown
        self._unreadable_error = unreadable_error
        self.path = f"/Archives/edgar/data/320193/000032019325000073/{filename}"

    @property
    def url(self):
        return f"https://www.sec.gov{self.path}"

    @property
    def empty(self):
        return not self.document

    @property
    def extension(self):
        return Path(self.document).suffix

    def is_text(self):
        return self.extension.lower() in {".htm", ".html", ".txt", ".xml", ".xbrl", ".xsd"}

    def is_html(self):
        return self.extension.lower() in {".htm", ".html"}

    def is_binary(self):
        return self.extension.lower() in {".pdf", ".jpg", ".png"}

    def markdown(self):
        if self._unreadable_error:
            raise OSError(self._unreadable_error)
        return self._markdown

    def text(self):
        if self._unreadable_error:
            raise OSError(self._unreadable_error)
        return self._text


class FakeAttachments(list):
    pass


class LocalFiling(Filing):
    """Filing for these tests whose repr never consults the SEC."""

    def __repr__(self):
        return f"LocalFiling({self.accession_number})"


def make_filing(attachments):
    filing = LocalFiling(
        cik=320193,
        company="Apple Inc.",
        form="10-Q",
        filing_date="2025-05-02",
        accession_no=ACCESSION,
    )
    filing._test_attachments = FakeAttachments(attachments)
    return filing


@pytest.fixture
def setup_tool(monkeypatch):
    """Install a no-network Filing."""
    attachments = [
        FakeAttachment("1", "apple.htm", "10-Q", "cover text", description="Quarterly report", ixbrl=True),
        FakeAttachment("4", "a10-qexhibit32103292025.htm", "EX-32.1", "CEO Timothy D. Cook"),
        FakeAttachment("5", "agreement-a.htm", "EX-10.1", "needle one\nneedle two"),
        FakeAttachment("6", "agreement-b.htm", "EX-10.2", "needle three"),
        FakeAttachment("7", "R1.htm", "XML", "generated report"),
        FakeAttachment("8", "instance.xml", "EX-101.INS", "xbrl data", ixbrl=True),
        FakeAttachment("9", "scan.pdf", "EX-99.1", None),
    ]
    filing = make_filing(attachments)
    monkeypatch.setattr(Filing, "attachments", property(lambda self: self._test_attachments))
    monkeypatch.setattr("edgar.find", lambda **kwargs: filing)
    return filing, attachments


@pytest.fixture(autouse=True)
def isolate_mcp_caches(monkeypatch):
    monkeypatch.setattr(continuation, "text_cache", ResultCache(max_entries=16, max_bytes=2_000_000))
    monkeypatch.setattr(continuation, "results_cache", ResultCache(max_entries=16))


@pytest.mark.fast
def test_server_import_registers_document_tool():
    from edgar.ai.mcp.server import _import_tools
    from edgar.ai.mcp.tools.base import TOOLS

    _import_tools()

    assert "edgar_document" in TOOLS
    schema = TOOLS["edgar_document"]["schema"]
    assert {"action", "accession_number", "url", "document", "query", "around", "cursor"}.issubset(
        schema["properties"]
    )


@pytest.mark.fast
@pytest.mark.asyncio
async def test_reads_local_aapl_exhibit_and_reports_identity(monkeypatch):
    from edgar.ai.mcp.tools.document import edgar_document
    from edgar.attachments import Attachment

    contents = FIXTURE.read_text()
    exhibit = Attachment(
        sequence_number="4",
        description="Section 1350 certifications",
        document=FIXTURE.name,
        ixbrl=False,
        path=f"/Archives/edgar/data/320193/000032019325000073/{FIXTURE.name}",
        document_type="EX-32.1",
        size=len(contents),
    )
    exhibit.content = contents
    filing = make_filing([exhibit])
    monkeypatch.setattr(Filing, "attachments", property(lambda self: self._test_attachments))
    monkeypatch.setattr("edgar.find", lambda **kwargs: filing)

    result = await edgar_document(action="read", accession_number=ACCESSION, document="EX-32.1")

    assert result.success is True, result.error
    assert "Timothy D. Cook" in result.data["text"]
    assert result.data["document"]["filename"] == FIXTURE.name
    assert result.data["source"]["selected_by"] == "accession"
    assert result.data["source"]["document_url"].endswith(FIXTURE.name)
    assert result.data["filer"] == {"cik": 320193, "name": "Apple Inc."}
    assert "BDC filing" in result.data["evidence_scope_note"]


@pytest.mark.fast
@pytest.mark.asyncio
async def test_list_has_metadata_provenance_note_and_hides_noise(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    result = await edgar_document(action="list", accession_number=ACCESSION)

    assert result.success is True, result.error
    assert [doc["filename"] for doc in result.data["documents"]] == [
        "apple.htm", "a10-qexhibit32103292025.htm", "agreement-a.htm", "agreement-b.htm", "scan.pdf"
    ]
    exhibit = result.data["documents"][1]
    assert exhibit["sequence"] == "4"
    assert exhibit["sequence_number"] == "4"
    assert exhibit["document_type"] == "EX-32.1"
    assert exhibit["type"] == "EX-32.1"
    assert exhibit["primary"] is False
    assert exhibit["is_primary"] is False
    assert exhibit["readable"] is True
    assert exhibit["url"].endswith(exhibit["filename"])
    assert "incorporated by reference" in result.data["incorporated_by_reference_note"].lower()
    assert "BDC filing" in result.data["evidence_scope_note"]
    assert result.data["source"]["selected_by"] == "accession"
    assert result.data["filer"]["name"] == "Apple Inc."
    assert result.data["documents"][0]["filename"] == "apple.htm"
    assert result.data["documents"][0]["is_primary"] is True


@pytest.mark.fast
@pytest.mark.asyncio
async def test_list_include_all_exposes_xbrl_and_r_files(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    result = await edgar_document(action="list", accession_number=ACCESSION, include_all=True)

    names = {doc["filename"] for doc in result.data["documents"]}
    assert {"R1.htm", "instance.xml"}.issubset(names)


@pytest.mark.fast
@pytest.mark.asyncio
@pytest.mark.parametrize("selector", ["4", "a10-qexhibit32103292025.htm", "EX-32.1"])
async def test_exact_sequence_filename_and_type_selectors(setup_tool, selector):
    from edgar.ai.mcp.tools.document import edgar_document

    result = await edgar_document(action="read", accession_number=ACCESSION, document=selector)

    assert result.success is True, result.error
    assert result.data["document"]["filename"] == "a10-qexhibit32103292025.htm"


@pytest.mark.fast
@pytest.mark.asyncio
async def test_qualified_exhibit_type_does_not_match_longer_type(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    setup_tool[0]._test_attachments.append(FakeAttachment("10", "longer.htm", "EX-10.10", "longer agreement"))
    result = await edgar_document(action="read", accession_number=ACCESSION, document="EX-10.1")

    assert result.success is True, result.error
    assert result.data["document"]["filename"] == "agreement-a.htm"


@pytest.mark.fast
@pytest.mark.asyncio
async def test_ambiguous_exhibit_prefix_returns_candidates(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    setup_tool[0]._test_attachments.append(FakeAttachment("10", "base-agreement.htm", "EX-10", "base agreement"))
    result = await edgar_document(action="read", accession_number=ACCESSION, document="EX-10")

    assert result.success is False
    assert result.error_code == "AMBIGUOUS_DOCUMENT"
    candidate_names = {c["filename"] for c in result.data["candidates"]}
    assert candidate_names == {"agreement-a.htm", "agreement-b.htm", "base-agreement.htm"}
    assert "instance.xml" not in candidate_names


@pytest.mark.fast
@pytest.mark.asyncio
async def test_missing_document_never_falls_back_to_parent(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    result = await edgar_document(action="read", accession_number=ACCESSION, document="not-filed.htm")

    assert result.success is False
    assert result.error_code == "DOCUMENT_NOT_FOUND"


@pytest.mark.fast
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://www.sec.gov/Archives/edgar/data/320193/000032019325000073/",
        "https://sec.gov/Archives/edgar/data/320193/000032019325000073/",
        "https://www.sec.gov.evil.test/Archives/edgar/data/320193/000032019325000073/",
        "https://www.sec.gov/ix?doc=/Archives/edgar/data/320193/000032019325000073/x.htm",
    ],
)
async def test_invalid_urls_are_rejected_before_filing_lookup(monkeypatch, url):
    from edgar.ai.mcp.tools.document import edgar_document

    def unexpected_lookup(**kwargs):
        pytest.fail("Invalid supplied URLs must be rejected before find()")

    monkeypatch.setattr("edgar.find", unexpected_lookup)
    result = await edgar_document(action="list", url=url)

    assert result.success is False
    assert result.error_code == "INVALID_URL"


@pytest.mark.fast
@pytest.mark.asyncio
async def test_url_filename_selects_document_and_source_records_url_selection(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    url = f"https://www.sec.gov/Archives/edgar/data/320193/000032019325000073/agreement-a.htm"
    result = await edgar_document(action="read", url=url)

    assert result.success is True, result.error
    assert result.data["document"]["filename"] == "agreement-a.htm"
    assert result.data["source"]["selected_by"] == "url"


@pytest.mark.fast
@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["read", "search"])
async def test_url_filename_conflict_rejects_other_explicit_document_without_access(
    setup_tool, monkeypatch, action
):
    from edgar.ai.mcp.tools.document import edgar_document

    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000073/agreement-a.htm"
    other = setup_tool[1][3]
    accesses = []
    original_markdown = other.markdown
    original_text = other.text

    def track_markdown():
        accesses.append("markdown")
        return original_markdown()

    def track_text():
        accesses.append("text")
        return original_text()

    monkeypatch.setattr(other, "markdown", track_markdown)
    monkeypatch.setattr(other, "text", track_text)
    arguments = {"action": action, "url": url, "document": "agreement-b.htm"}
    if action == "search":
        arguments["query"] = "needle"

    result = await edgar_document(**arguments)

    assert result.success is False
    assert result.error_code == "DOCUMENT_MISMATCH"
    assert accesses == []


@pytest.mark.fast
@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["read", "search"])
async def test_url_filename_allows_matching_sequence_alias(setup_tool, action):
    from edgar.ai.mcp.tools.document import edgar_document

    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000073/agreement-a.htm"
    arguments = {"action": action, "url": url, "document": "5"}
    if action == "search":
        arguments["query"] = "needle"

    result = await edgar_document(**arguments)

    assert result.success is True, result.error
    if action == "read":
        assert result.data["document"]["filename"] == "agreement-a.htm"
    else:
        assert result.data["matches"]
        assert {match["locator"]["document"] for match in result.data["matches"]} == {
            "agreement-a.htm"
        }


@pytest.mark.fast
@pytest.mark.asyncio
async def test_url_listing_lists_all_documents_without_filename_filter(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000073/agreement-a.htm"
    result = await edgar_document(action="list", url=url)

    assert result.success is True, result.error
    assert len(result.data["documents"]) == 5


@pytest.mark.fast
@pytest.mark.asyncio
async def test_search_locator_offset_aligns_to_markdown_read_text(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    attachments = setup_tool[1]
    agreement = attachments[2]
    agreement._text = "plain text differs from markdown"
    agreement._markdown = "heading\nneedle in rendered markdown"
    result = await edgar_document(
        action="search", accession_number=ACCESSION, document=agreement.document, query="needle"
    )
    reread = await edgar_document(action="read", accession_number=ACCESSION, document=agreement.document)

    assert result.success is True, result.error
    match = result.data["matches"][0]
    assert "BDC filing" in result.data["evidence_scope_note"]
    assert match["locator"] == {
        "document": agreement.document,
        "char_offset": reread.data["text"].index("needle"),
    }
    assert match["match"].lower() == "needle"


@pytest.mark.fast
@pytest.mark.asyncio
async def test_search_pages_match_records_and_rejects_changed_fingerprint(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    attachments = setup_tool[1]
    first = await edgar_document(
        action="search", accession_number=ACCESSION, document="agreement-a.htm", query="needle", limit=1
    )
    cursor = first.data["page"]["next_cursor"]
    assert first.data["matches"][0]["locator"]["char_offset"] == 0

    # Simulate the cursor being resumed in another worker with a cold cache.
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(continuation, "text_cache", ResultCache(max_entries=16, max_bytes=2_000_000))
    monkeypatch.setattr(continuation, "results_cache", ResultCache(max_entries=16))
    attachments[2]._text = "changed evidence needle"
    attachments[2]._markdown = "changed evidence needle"
    continued = await edgar_document(
        action="search", accession_number=ACCESSION, document="agreement-a.htm", query="needle", cursor=cursor, limit=1
    )
    monkeypatch.undo()

    assert continued.success is False
    assert continued.error_code == "CURSOR_STALE"


@pytest.mark.fast
@pytest.mark.asyncio
async def test_search_paginates_serialized_match_records(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    first = await edgar_document(
        action="search", accession_number=ACCESSION, document="agreement-a.htm", query="needle", limit=1
    )
    assert len(first.data["matches"]) == 1
    assert first.data["page"]["next_cursor"]
    second = await edgar_document(
        action="search",
        accession_number=ACCESSION,
        document="agreement-a.htm",
        query="needle",
        cursor=first.data["page"]["next_cursor"],
        limit=1,
    )
    assert [m["match"].lower() for m in first.data["matches"] + second.data["matches"]] == ["needle", "needle"]


@pytest.mark.fast
@pytest.mark.asyncio
async def test_search_cursor_is_bound_to_query_and_document(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    first = await edgar_document(
        action="search", accession_number=ACCESSION, document="agreement-a.htm", query="needle", limit=1
    )
    cursor = first.data["page"]["next_cursor"]
    changed_query = await edgar_document(
        action="search", accession_number=ACCESSION, document="agreement-a.htm", query="one", cursor=cursor
    )
    changed_document = await edgar_document(
        action="search", accession_number=ACCESSION, document="agreement-b.htm", query="needle", cursor=cursor
    )

    assert changed_query.error_code == "CURSOR_MISMATCH"
    assert changed_document.error_code == "CURSOR_MISMATCH"


@pytest.mark.fast
@pytest.mark.asyncio
async def test_exact_filename_filter_wins_over_other_type_substring(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    setup_tool[0]._test_attachments.append(
        FakeAttachment("10", "distractor.htm", "EX-agreement-a.htm", "needle distractor")
    )
    result = await edgar_document(
        action="search", accession_number=ACCESSION, document="agreement-a.htm", query="needle"
    )

    assert result.success is True, result.error
    assert {m["locator"]["document"] for m in result.data["matches"]} == {"agreement-a.htm"}


@pytest.mark.fast
@pytest.mark.asyncio
async def test_search_skips_attachments_without_a_filename(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    setup_tool[0]._test_attachments.append(FakeAttachment("10", "", "EX-99.2", "needle empty identity"))
    result = await edgar_document(action="search", accession_number=ACCESSION, query="needle")

    assert result.success is True, result.error
    assert all(match["locator"]["document"] for match in result.data["matches"])


@pytest.mark.fast
@pytest.mark.asyncio
async def test_broad_regex_search_is_bounded_across_all_attachments_and_not_cached(
    monkeypatch, setup_tool
):
    from edgar.ai.mcp.tools import document as document_module
    from edgar.ai.mcp.tools.document import edgar_document

    monkeypatch.setattr(document_module, "MAX_SEARCH_MATCHES", 5)
    filing = setup_tool[0]
    filing.attachments.clear()
    filing.attachments.extend(
        [
            FakeAttachment("20", "cap-a.txt", "EX-99.3", "xxxx"),
            FakeAttachment("21", "cap-b.txt", "EX-99.4", "yyyy"),
        ]
    )
    grep_limits = []
    original_grep = filing.grep

    def bounded_grep(pattern, **kwargs):
        grep_limits.append(kwargs["max_matches"])
        return original_grep(pattern, **kwargs)

    monkeypatch.setattr(filing, "grep", bounded_grep)
    result = await edgar_document(
        action="search", accession_number=ACCESSION, query=r"(?s).", regex=True
    )

    assert result.success is False
    assert result.error_code == "QUERY_TOO_BROAD"
    assert grep_limits == [5, 1]
    assert continuation.results_cache.stats()["entries"] == 0
    assert any("narrow" in suggestion.lower() for suggestion in result.suggestions)


@pytest.mark.fast
@pytest.mark.asyncio
async def test_regex_timeout_returns_error_and_does_not_cache_partial_matches(
    setup_tool
):
    from edgar.ai.mcp.tools.document import edgar_document

    filing = setup_tool[0]
    filing.attachments.clear()
    filing.attachments.extend(
        [
            FakeAttachment("20", "partial.txt", "EX-99.3", "needle"),
            FakeAttachment("21", "catastrophic.txt", "EX-99.4", "a" * 50_000 + "!"),
        ]
    )
    result = await edgar_document(
        action="search",
        accession_number=ACCESSION,
        query=r"needle|(a+)+$",
        regex=True,
    )

    assert result.success is False
    assert result.error_code == "REGEX_TIMEOUT"
    assert result.data is None
    assert "timed out" in result.error.lower()
    assert any("simplif" in suggestion.lower() for suggestion in result.suggestions)
    assert continuation.results_cache.stats()["entries"] == 0


@pytest.mark.fast
@pytest.mark.asyncio
async def test_list_pages_and_binds_include_all(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    for sequence in range(20, 45):
        setup_tool[0]._test_attachments.append(
            FakeAttachment(str(sequence), f"appendix-{sequence}.txt", "EX-99.1", "appendix")
        )
    first = await edgar_document(action="list", accession_number=ACCESSION, limit=3)
    second = await edgar_document(
        action="list", accession_number=ACCESSION, limit=3, cursor=first.data["page"]["next_cursor"]
    )
    changed_filter = await edgar_document(
        action="list", accession_number=ACCESSION, include_all=True, limit=3,
        cursor=first.data["page"]["next_cursor"],
    )

    assert len(first.data["documents"]) == 3
    assert len(second.data["documents"]) == 3
    assert first.data["documents"][-1]["filename"] != second.data["documents"][0]["filename"]
    assert changed_filter.error_code == "CURSOR_MISMATCH"


@pytest.mark.fast
@pytest.mark.asyncio
async def test_around_reads_text_centered_on_locator(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    text = "x" * 10_000
    setup_tool[1][2]._text = text
    setup_tool[1][2]._markdown = text
    result = await edgar_document(
        action="read",
        accession_number=ACCESSION,
        around={"document": "agreement-a.htm", "char_offset": 7_000},
    )

    assert result.success is True, result.error
    assert len(result.data["text"]) <= 6_000
    assert result.data["page"]["offset"] == 4_000
    assert result.data["page"]["offset"] + len(result.data["text"]) == 10_000


@pytest.mark.fast
@pytest.mark.asyncio
async def test_around_rejects_cursor_and_conflicting_document_url(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    conflict = await edgar_document(
        action="read",
        url="https://www.sec.gov/Archives/edgar/data/320193/000032019325000073/agreement-a.htm",
        around={"document": "agreement-b.htm", "char_offset": 0},
    )
    both = await edgar_document(
        action="read",
        accession_number=ACCESSION,
        document="agreement-a.htm",
        around={"document": "agreement-a.htm", "char_offset": 0},
        cursor="cursor",
    )

    assert conflict.error_code == "DOCUMENT_MISMATCH"
    assert both.error_code == "AROUND_CURSOR_CONFLICT"


@pytest.mark.fast
@pytest.mark.asyncio
async def test_read_pages_are_bounded_lossless_and_non_overlapping(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    text = ("0123456789" * 1_300) + "tail"
    setup_tool[1][2]._text = text
    setup_tool[1][2]._markdown = text
    response = await edgar_document(action="read", accession_number=ACCESSION, document="agreement-a.htm")
    pages = [response.data["text"]]
    cursor = response.data["page"]["next_cursor"]
    assert len(pages[0]) <= 6_000
    while cursor:
        page = await edgar_document(
            action="read", accession_number=ACCESSION, document="agreement-a.htm", cursor=cursor
        )
        assert page.success is True, page.error
        assert len(page.data["text"]) <= 6_000
        pages.append(page.data["text"])
        cursor = page.data["page"]["next_cursor"]
    assert "".join(pages) == text


@pytest.mark.fast
@pytest.mark.asyncio
async def test_read_cursor_is_stale_when_document_text_changes(monkeypatch, setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    attachment = setup_tool[1][2]
    attachment._text = "original evidence " * 500
    attachment._markdown = attachment._text
    first = await edgar_document(
        action="read", accession_number=ACCESSION, document=attachment.document
    )
    cursor = first.data["page"]["next_cursor"]
    assert cursor is not None

    # A restarted worker has a cold text cache and re-renders the filing.
    monkeypatch.setattr(
        continuation, "text_cache", ResultCache(max_entries=16, max_bytes=2_000_000)
    )
    attachment._text = "changed evidence " * 500
    attachment._markdown = attachment._text
    continued = await edgar_document(
        action="read",
        accession_number=ACCESSION,
        document=attachment.document,
        cursor=cursor,
    )

    assert continued.success is False
    assert continued.error_code == "CURSOR_STALE"


@pytest.mark.fast
@pytest.mark.asyncio
async def test_unreadable_pdf_returns_identity_url_and_reason(setup_tool):
    from edgar.ai.mcp.tools.document import edgar_document

    result = await edgar_document(action="read", accession_number=ACCESSION, document="9")

    assert result.success is True, result.error
    assert result.data["document"]["filename"] == "scan.pdf"
    assert result.data["document"]["url"].endswith("scan.pdf")
    assert result.data["unreadable_reason"]
    assert "BDC filing" in result.data["evidence_scope_note"]


@pytest.mark.fast
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "doc_type"),
    [("scan.png", "GRAPHIC"), ("submission.paper", "TEXT"), ("", "EX-99.2")],
)
async def test_unreadable_image_paper_and_empty_attachment_keep_identity(setup_tool, filename, doc_type):
    from edgar.ai.mcp.tools.document import edgar_document

    setup_tool[0]._test_attachments.append(FakeAttachment("10", filename, doc_type, None))
    result = await edgar_document(action="read", accession_number=ACCESSION, document="10")

    assert result.success is True, result.error
    assert result.data["document"]["filename"] == filename
    assert "url" in result.data["document"]
    assert result.data["unreadable_reason"]


@pytest.mark.fast
@pytest.mark.asyncio
async def test_real_paper_attachment_is_listed_unreadable_and_never_searched(monkeypatch):
    from edgar.ai.mcp.tools.document import edgar_document
    from edgar.attachments import Attachment

    paper = Attachment(
        sequence_number="10",
        description="Paper submission",
        document="submission.paper",
        ixbrl=False,
        path=f"/Archives/edgar/data/320193/000032019325000073/submission.paper",
        document_type="TEXT",
        size=20,
    )
    paper.content = "Confidential paper attachment contents."
    assert paper.text() == "Confidential paper attachment contents."
    filing = make_filing([paper])
    monkeypatch.setattr(Filing, "attachments", property(lambda self: self._test_attachments))
    monkeypatch.setattr("edgar.find", lambda **kwargs: filing)

    listed = await edgar_document(action="list", accession_number=ACCESSION, include_all=True)
    read = await edgar_document(action="read", accession_number=ACCESSION, document="submission.paper")
    searched = await edgar_document(
        action="search", accession_number=ACCESSION, document="submission.paper", query="Confidential"
    )

    paper_record = listed.data["documents"][0]
    assert paper_record["readable"] is False
    assert read.success is True
    assert read.data["document"]["url"].endswith("submission.paper")
    assert "paper" in read.data["unreadable_reason"].lower()
    assert searched.success is True
    assert searched.data["matches"] == []


@pytest.mark.fast
@pytest.mark.asyncio
async def test_silence_checks_for_invalid_action_and_required_arguments():
    from edgar.ai.mcp.tools.document import edgar_document

    invalid_action = await edgar_document(action="download", accession_number=ACCESSION)
    missing_source = await edgar_document(action="list")
    missing_query = await edgar_document(action="search", accession_number=ACCESSION)

    assert invalid_action.error_code == "INVALID_ACTION"
    assert missing_source.error_code == "FILING_REQUIRED"
    assert missing_query.error_code == "QUERY_REQUIRED"
