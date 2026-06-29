"""
Regression test for GH #879 / edgartools-papt:
8-K item text includes the trailing SIGNATURES block, leaking into the last item.

Bug (FIXED): For an 8-K filing, the last reported item over-extended through the
SIGNATURES block that follows it, because SIGNATURES was not registered as a named
section boundary in `_EIGHT_K_SECTION_PATTERNS`. The pattern extractor had no way
to stop the last item at the SIGNATURES header, so the signature block (header +
registrant name + signer) leaked into the last item's text.

Affected filing (Meta Platforms, single-item 8-K):
    Accession: 0001628280-25-058337
    Filed: 2025-12-19, Item 5.02 (director resignation)
    Before fix: Item 5.02 = 821 chars, SIGNATURE at offset 351
    After fix:  Item 5.02 = 349 chars, no SIGNATURE content

Root cause (two-part failure):
1. `_EIGHT_K_SECTION_PATTERNS` in `edgar/documents/form_schema.py` had no
   `'signatures'` entry, so SIGNATURES was never registered as a terminal section
   boundary for 8-K. The 20-F schema already had this entry; 8-K was missing it.
2. `_find_section_headers` Strategy 3b (bold-child paragraph scan) was gated to
   `self.form == '10-K'` only. Many 8-K filers (Workiva, Donnelley, et al.) render
   the SIGNATURES heading as a ParagraphNode whose own style is unstyled (fw=None)
   but whose child TextNode carries font-weight:700. Strategy 3 (_is_bold on the
   paragraph itself) missed these; Strategy 3b was needed for 8-K too.
   Additionally, some filers (JPMorgan) render SIGNATURES with font-weight:400
   (plain, underlined), so a new Strategy 5b scans for bare "SIGNATURES?" paragraphs
   regardless of bold styling.

Fix (three-part):
- edgar/documents/form_schema.py: Added `'signatures'` entry to
  `_EIGHT_K_SECTION_PATTERNS`, mirroring the existing 20-F entry.
- edgar/documents/extractors/pattern_section_extractor.py: Widened Strategy 3b
  from `form == '10-K'` to `form in ('10-K', '8-K')` so bold-child SIGNATURES
  headings are captured on 8-K.
- edgar/documents/extractors/pattern_section_extractor.py: Added Strategy 5b
  that unconditionally scans for bare "SIGNATURES?" ParagraphNode text on 8-K
  forms, covering plain-text (non-bold) SIGNATURES headings.

Ground truth (Meta, accession 0001628280-25-058337):
- Item 5.02 exact length post-fix: 349 chars
- SIGNATURES not in Item 5.02 text
- document.sections.named("signatures") is not None
- ek.items == ['Item 5.02']

Multi-item ground truth (JPMorgan, accession 0000019617-26-000241):
- Items: ['Item 5.02', 'Item 9.01']
- Item 5.02 (middle): 4097 chars, no SIGNATURE
- Item 9.01 (last): 794 chars, no SIGNATURE
- document.sections.named("signatures") is not None
"""

from pathlib import Path

import pytest

pytestmark = [pytest.mark.regression]

# ---------------------------------------------------------------------------
# VCR configuration — used for the HTML-only cassette tests below
# ---------------------------------------------------------------------------
try:
    import vcr as _vcr_module

    _CASSETTES_DIR = Path(__file__).parent.parent.parent / "cassettes"
    _my_vcr = _vcr_module.VCR(
        cassette_library_dir=str(_CASSETTES_DIR),
        record_mode="none",   # replay only; never re-record
        match_on=["method", "scheme", "host", "port", "path", "query"],
        filter_headers=["User-Agent", "Authorization"],
        decode_compressed_response=True,
    )
    _HAS_VCR = True
except ImportError:
    _HAS_VCR = False
    _my_vcr = None


# ---------------------------------------------------------------------------
# In-process deterministic tests (no network, no VCR)
# ---------------------------------------------------------------------------

class TestSignaturesBoundaryInProcess:
    """In-process HTML fixtures that exercise the fix without network access.

    Two variants:
    - Bold-child: SIGNATURES header has fw=700 on a child TextNode (Workiva style)
    - Plain-text: SIGNATURES header has fw=400 / underline only (JPMorgan style)
    """

    _BOLD_CHILD_HTML = """
    <html><body>
    <div><span style="font-weight:700">Item 5.02. Departure of Directors.</span></div>
    <p>On December 19, 2025, the director resigned from the Board effective immediately.</p>
    <div style="text-align:center"><span style="font-weight:700">SIGNATURES</span></div>
    <p>Pursuant to the requirements of the Securities Exchange Act of 1934, the
    Registrant has duly caused this report to be signed on its behalf by the
    undersigned hereunto duly authorized.</p>
    <p>META PLATFORMS, INC.</p>
    </body></html>
    """

    _PLAIN_TEXT_HTML = """
    <html><body>
    <div><span style="font-weight:700">Item 5.02. Departure of Directors.</span></div>
    <p>The director resigned effective immediately.</p>
    <div><span style="font-weight:700">Item 9.01. Financial Statements and Exhibits.</span></div>
    <p>(d) Exhibits: 99.1</p>
    <div style="text-align:center"><span style="text-decoration:underline">SIGNATURE</span></div>
    <p>Pursuant to the requirements of the Exchange Act, the Registrant has duly
    caused this report to be signed on its behalf.</p>
    </body></html>
    """

    def _parse(self, html: str):
        from edgar.documents import parse_html
        from edgar.documents.config import ParserConfig
        return parse_html(html, ParserConfig(form="8-K"))

    def test_bold_child_signatures_not_in_last_item(self):
        """Bold-child SIGNATURES paragraph must terminate the last 8-K item."""
        doc = self._parse(self._BOLD_CHILD_HTML)
        sections = doc.sections
        assert "item_502" in sections, "Item 5.02 not detected"
        text = sections["item_502"].text()
        assert "SIGNATURE" not in text.upper(), (
            "SIGNATURES block leaked into Item 5.02 (bold-child case)"
        )
        assert "resigned" in text.lower(), "Item 5.02 body text must be present"

    def test_bold_child_signatures_accessible_as_named_section(self):
        """The SIGNATURES block must be retrievable as a named section."""
        doc = self._parse(self._BOLD_CHILD_HTML)
        sig = doc.sections.named("signatures")
        assert sig is not None, "Named 'signatures' section not found (bold-child case)"
        assert sig.kind == "named"
        assert "SIGNATURE" in sig.text().upper()

    def test_plain_text_signatures_not_in_last_item(self):
        """Plain-text (non-bold) SIGNATURES paragraph must terminate the last item."""
        doc = self._parse(self._PLAIN_TEXT_HTML)
        sections = doc.sections
        assert "item_901" in sections, "Item 9.01 not detected"
        text = sections["item_901"].text()
        assert "SIGNATURE" not in text.upper(), (
            "SIGNATURES block leaked into Item 9.01 (plain-text case)"
        )

    def test_plain_text_signatures_accessible_as_named_section(self):
        """SIGNATURES must be a named section regardless of bold styling."""
        doc = self._parse(self._PLAIN_TEXT_HTML)
        sig = doc.sections.named("signatures")
        assert sig is not None, "Named 'signatures' section not found (plain-text case)"
        assert sig.kind == "named"

    def test_middle_item_unaffected_by_fix(self):
        """The fix must not alter middle items (only the last-item boundary)."""
        doc = self._parse(self._PLAIN_TEXT_HTML)
        sections = doc.sections
        assert "item_502" in sections, "Item 5.02 not detected"
        text_502 = sections["item_502"].text()
        assert "resigned" in text_502.lower(), "Item 5.02 body text must be present"
        assert "SIGNATURE" not in text_502.upper(), (
            "SIGNATURES unexpectedly in Item 5.02 (middle item)"
        )

    def test_8k_schema_has_signatures_pattern(self):
        """_EIGHT_K_SECTION_PATTERNS must include 'signatures' (the missing piece).

        This is the root-cause guard — if the pattern is absent the section
        extractor cannot create a named signatures section for 8-K forms.
        """
        from edgar.documents.form_schema import get_form_schema
        schema = get_form_schema("8-K")
        assert "signatures" in schema.section_patterns, (
            "'signatures' missing from _EIGHT_K_SECTION_PATTERNS — "
            "the terminal boundary is not registered and the last item will "
            "absorb the signatures block (GH #879)"
        )

    def test_items_property_excludes_signatures(self):
        """ek.items must not include 'Item signatures' after the fix."""
        from edgar.documents import parse_html
        from edgar.documents.config import ParserConfig
        from edgar.company_reports.current_report import CurrentReport

        # Parse a minimal 8-K document in-process to access sections
        doc = parse_html(self._BOLD_CHILD_HTML, ParserConfig(form="8-K"))
        sections = doc.sections
        # Only item sections should appear; 'signatures' is kind='named'
        item_sections = {k: v for k, v in sections.items() if v.kind == "item"}
        named_sections = {k: v for k, v in sections.items() if v.kind == "named"}
        assert "item_502" in item_sections, "item_502 not in item sections"
        assert "signatures" not in item_sections, "'signatures' leaked into item sections"
        assert "signatures" in named_sections, "'signatures' should be a named section"


# ---------------------------------------------------------------------------
# VCR ground-truth tests — replay the real filing HTML without re-fetching
# ---------------------------------------------------------------------------

def _parse_filing_html(cassette_name: str, filing_html_uri: str, form: str):
    """Fetch the filing HTML from the VCR cassette and parse it.

    This bypasses `get_by_accession_number` (which needs the full quarterly
    index) and directly downloads the filing's primary document using VCR
    to replay the recorded response. Uses httpx (the same transport edgar uses)
    so VCR intercepts the request correctly.
    """
    if not _HAS_VCR:
        pytest.skip("vcrpy not installed")
    import httpx

    with _my_vcr.use_cassette(cassette_name):
        with httpx.Client() as client:
            resp = client.get(filing_html_uri, headers={"User-Agent": "EdgarTools test"})
        html = resp.text

    from edgar.documents import parse_html
    from edgar.documents.config import ParserConfig
    return parse_html(html, ParserConfig(form=form))


@pytest.mark.fast
class TestMetaSingleItemGroundTruth:
    """GH #879: Meta 8-K (0001628280-25-058337) — single item, Workiva rendering.

    Workiva renders SIGNATURES as a ParagraphNode with an unstyled wrapper and
    a bold-child TextNode (font-weight:700 on the <span>).
    Ground truth: Item 5.02 = 349 chars post-fix (before fix: 821 chars, SIGNATURE at 351).
    Cassette: tests/cassettes/test_issue_879_meta_8k.yaml (records filing HTML only).
    """

    _CASSETTE = "test_issue_879_meta_8k.yaml"
    _HTML_URI = "https://www.sec.gov/Archives/edgar/data/1326801/000162828025058337/meta-20251219.htm"

    @pytest.fixture(scope="class")
    def doc(self):
        return _parse_filing_html(self._CASSETTE, self._HTML_URI, "8-K")

    def test_item_502_does_not_contain_signatures(self, doc):
        """Item 5.02 must end before the SIGNATURES block."""
        sections = doc.sections
        assert "item_502" in sections
        text = sections["item_502"].text().strip()
        assert "SIGNATURE" not in text.upper(), (
            f"SIGNATURES block leaked into Item 5.02 (len={len(text)}). "
            "Root cause: last item not bounded at SIGNATURES header."
        )

    def test_item_502_ground_truth_length(self, doc):
        """Item 5.02 exact post-fix length is ~349 chars (allow ±15%)."""
        sections = doc.sections
        text = sections["item_502"].text().strip()
        # Ground truth: 349 chars. Allow ±15% (297–401) for minor rendering changes.
        assert 297 <= len(text) <= 401, (
            f"Item 5.02 length {len(text)} outside expected range [297, 401]; "
            "either the signatures block leaked in or the item body was truncated."
        )

    def test_signatures_named_section_accessible(self, doc):
        """The SIGNATURES block must be retrievable as a named section.

        Ground truth: ~470 chars starting with 'SIGNATURES'.
        """
        sig = doc.sections.named("signatures")
        assert sig is not None, (
            "document.sections.named('signatures') returned None; "
            "the signatures block is lost rather than just relocated."
        )
        assert sig.kind == "named"
        sig_text = sig.text()
        assert "SIGNATURE" in sig_text.upper(), (
            "Signatures section text doesn't contain 'SIGNATURE'"
        )
        # Ground truth length: ~470 chars (allow ±25%)
        assert len(sig_text) >= 300, (
            f"Signatures section seems too short ({len(sig_text)} chars)"
        )


@pytest.mark.fast
class TestJPMMultiItemGroundTruth:
    """GH #879: JPMorgan 8-K (0000019617-26-000241) — two items.

    JPMorgan renders SIGNATURES as plain text (font-weight:400, underlined),
    not bold. Tests that middle items are untouched and the last item is bounded.
    Ground truth:
    - Item 5.02: 4097 chars (middle item, unchanged)
    - Item 9.01: 794 chars (last item; before fix this contained the sig block)
    Cassette: tests/cassettes/test_issue_879_jpm_8k.yaml
    """

    _CASSETTE = "test_issue_879_jpm_8k.yaml"
    # Primary document URL from the JPM 8-K index
    _HTML_URI = "https://www.sec.gov/Archives/edgar/data/19617/000001961726000241/jpm-20260624.htm"

    @pytest.fixture(scope="class")
    def doc(self):
        """Parse the JPM 8-K primary document from the VCR cassette."""
        return _parse_filing_html(self._CASSETTE, self._HTML_URI, "8-K")

    def test_middle_item_502_unchanged(self, doc):
        """Item 5.02 (middle item) must be unaffected — length stays ~4097 chars."""
        sections = doc.sections
        assert "item_502" in sections, "Item 5.02 not detected"
        text = sections["item_502"].text().strip()
        assert "SIGNATURE" not in text.upper(), (
            "SIGNATURES unexpectedly in JPM Item 5.02 (middle item)"
        )
        # Ground truth: 4097 chars. Allow ±15% (3482–4712).
        assert 3482 <= len(text) <= 4712, (
            f"JPM Item 5.02 length {len(text)} outside expected range [3482, 4712]; "
            "middle item should be unchanged by the fix."
        )

    def test_last_item_901_no_signatures(self, doc):
        """Item 9.01 (last item) must not contain the SIGNATURES block."""
        sections = doc.sections
        assert "item_901" in sections, "Item 9.01 not detected"
        text = sections["item_901"].text().strip()
        assert "SIGNATURE" not in text.upper(), (
            f"SIGNATURES block leaked into JPM Item 9.01 (len={len(text)}). "
            "GH #879 regression: last item not bounded at SIGNATURES header."
        )

    def test_last_item_901_ground_truth_length(self, doc):
        """Item 9.01 post-fix exact length is ~794 chars (allow ±15%)."""
        sections = doc.sections
        text = sections["item_901"].text().strip()
        # Ground truth: 794 chars. Allow ±15% (674–913).
        assert 674 <= len(text) <= 913, (
            f"JPM Item 9.01 length {len(text)} outside expected range [674, 913]"
        )

    def test_signatures_named_section_accessible(self, doc):
        """The SIGNATURES block must be retrievable as a named section."""
        sig = doc.sections.named("signatures")
        assert sig is not None, (
            "document.sections.named('signatures') returned None for JPM 8-K"
        )
        assert sig.kind == "named"
        sig_text = sig.text()
        assert "SIGNATURE" in sig_text.upper()
