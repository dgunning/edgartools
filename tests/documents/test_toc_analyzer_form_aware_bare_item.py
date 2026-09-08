r"""
Tests for form-aware bare-item-number filtering in TOCAnalyzer.

Bug: `TOCAnalyzer._extract_preceding_item_label` walked preceding `<td>`
siblings of a TOC link looking for an item label. A bare-number cell
(typically the page-number column in a TOC table) was matched by:

    re.match(r'^([1-9]|1[0-5])([A-Z]?)\.?\s*$', prev_text, re.IGNORECASE)

The cap (1–15) was tuned for 10-K's item range and is too loose for
10-Q (Part I: 1–4; Part II: 1, 1A, 2–6 — max = 6). A page-number
`<td>8</td>` on a 10-Q TOC therefore produced a phantom `Item 8`
label, propagated downstream to `TenQ.sections['part_i_item_8']` and
`TenQ.items` (sample: PPG Industries 10-Q `0000079879-26-000170`,
filed 2026-04-29, period 2026-03-31, where the 96 KB
"Notes to Condensed Consolidated Financial Statements" body was
hoisted out of Part I, Item 1 into a non-existent Item 8).

Fix: `TOCAnalyzer.__init__` now accepts a `form` parameter. The
bare-item match accepts any 1–2 digit number with optional letter
suffix, then filters by `_MAX_BARE_ITEM_BY_FORM[form]` (default 15).

Side benefit: 10-K cap raises from 15 → 16, picking up the rarely-used
`Item 16. Form 10-K Summary` heading that the old hardcoded regex
silently rejected.

Plumbing: `form` is passed `HybridSectionDetector → TOCSectionDetector
→ SECSectionExtractor → TOCAnalyzer`. Direct callers of
`SECSectionExtractor` in `edgar/documents/document.py` now also
forward `metadata.form`.
"""
from __future__ import annotations

import pytest

from edgar.documents.form_schema import get_form_schema
from edgar.documents.utils.toc_analyzer import TOCAnalyzer


class TestMaxBareItemByForm:
    """Verify the per-form max-bare-item caps match SEC form structure.

    The caps moved from module constants into the per-form schema
    (edgartools-fhno); these assert the schema values.
    """

    def test_ten_q_max_is_6(self):
        # 10-Q: Part I items 1-4, Part II items 1, 1A, 2-6. Max = 6.
        assert get_form_schema("10-Q").max_bare_item == 6
        assert get_form_schema("10-Q/A").max_bare_item == 6

    def test_default_is_15(self):
        # Preserves prior behaviour for callers that don't pass `form`
        # and for forms not in the override table.
        assert get_form_schema(None).max_bare_item == 15

    def test_ten_k_and_twenty_f_use_default(self):
        # 10-K and 20-F deliberately stay at the legacy default of 15.
        # Raising their caps would trade the 10-Q false-positive class
        # for new ones on those forms (page-16 cells on 10-K, page-17+
        # cells on 20-F). Real higher-numbered items are still detected
        # via the explicit `Item N` regex, which doesn't depend on this
        # cap.
        assert get_form_schema("10-K").max_bare_item == 15
        assert get_form_schema("10-K/A").max_bare_item == 15
        assert get_form_schema("20-F").max_bare_item == 15
        assert get_form_schema("20-F/A").max_bare_item == 15


class TestTOCAnalyzerFormParameter:
    """Verify `TOCAnalyzer` accepts and stores `form`."""

    def test_default_form_is_none(self):
        a = TOCAnalyzer()
        assert a.form is None

    def test_form_kwarg(self):
        for form in ("10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A"):
            a = TOCAnalyzer(form=form)
            assert a.form == form


# ---------------------------------------------------------------------------
# Behavioural test: synthetic TOC-table preceding-sibling extraction
# ---------------------------------------------------------------------------

from lxml import html as lxml_html


def _make_link_with_preceding_td(page_cell_text: str):
    """Build a tiny `<tr>` shaped like PPG's TOC row that triggered the bug.

    Returns the `<a>` element so it can be passed to
    `_extract_preceding_item_label`. The row looks like:

        <tr><td>Notes to Condensed ...</td><td>{page_cell_text}</td></tr>

    The page cell sits BETWEEN the title cell (containing the link) and
    the next cell. `_extract_preceding_item_label` walks preceding td
    siblings of the title's containing td and reads each one.
    """
    html_src = f"""
    <html><body><table><tr>
        <td>{page_cell_text}</td>
        <td><a href="#anchor">Notes to Condensed Consolidated Financial Statements</a></td>
    </tr></table></body></html>
    """
    tree = lxml_html.fromstring(html_src)
    return tree.xpath('//a')[0]


class TestBareItemFilteringIsFormAware:
    """The page-number cell `8` should NOT become 'Item 8' on a 10-Q."""

    def test_ten_q_rejects_page_number_8(self):
        analyzer = TOCAnalyzer(form="10-Q")
        link = _make_link_with_preceding_td("8")
        # 10-Q max is 6, so '8' is a page number, not an item.
        label = analyzer._extract_preceding_item_label(link)
        assert label == "", f"expected empty (no item label); got {label!r}"

    def test_ten_q_accepts_valid_item_6(self):
        analyzer = TOCAnalyzer(form="10-Q")
        link = _make_link_with_preceding_td("6")
        label = analyzer._extract_preceding_item_label(link)
        assert label == "Item 6", f"expected 'Item 6'; got {label!r}"

    def test_ten_k_accepts_item_8(self):
        analyzer = TOCAnalyzer(form="10-K")
        link = _make_link_with_preceding_td("8")
        label = analyzer._extract_preceding_item_label(link)
        assert label == "Item 8"

    def test_ten_k_rejects_page_number_16(self):
        # 10-K stays at the legacy default of 15. A bare-cell "16"
        # could legitimately be Item 16 (Form 10-K Summary) but is far
        # more often a page number, so we leave the cap alone to avoid
        # trading the 10-Q false-positive class for a 10-K one. Real
        # Item 16 is still detected via the explicit `Item N` regex.
        analyzer = TOCAnalyzer(form="10-K")
        link = _make_link_with_preceding_td("16")
        label = analyzer._extract_preceding_item_label(link)
        assert label == "", (
            f"10-K bare '16' should be treated as page number (legacy cap=15); got {label!r}"
        )

    def test_twenty_f_rejects_page_number_17(self):
        # Same reasoning as 10-K: 20-F stays at the legacy default of
        # 15 to avoid mis-interpreting page numbers as items.
        analyzer = TOCAnalyzer(form="20-F")
        link = _make_link_with_preceding_td("17")
        label = analyzer._extract_preceding_item_label(link)
        assert label == "", (
            f"20-F bare '17' should be treated as page number (legacy cap=15); got {label!r}"
        )

    def test_no_form_preserves_default_cap_15(self):
        # Without a form arg, the analyzer falls back to legacy behaviour:
        # accepts 1-15. So '8' still becomes 'Item 8' (existing behaviour
        # for backward compatibility with direct TOCAnalyzer users).
        analyzer = TOCAnalyzer()
        link = _make_link_with_preceding_td("8")
        assert analyzer._extract_preceding_item_label(link) == "Item 8"

        # And '16' is rejected because legacy cap is 15.
        link16 = _make_link_with_preceding_td("16")
        assert analyzer._extract_preceding_item_label(link16) == ""

    def test_letter_suffix_preserved(self):
        # '1A' is a real Part II item on 10-Q. Letter suffix kept,
        # uppercased.
        analyzer = TOCAnalyzer(form="10-Q")
        link = _make_link_with_preceding_td("1a")
        assert analyzer._extract_preceding_item_label(link) == "Item 1A"

    @pytest.mark.parametrize("padded", ["08", "01", "02", "06", "09"])
    @pytest.mark.parametrize("form", ["10-K", "10-Q", "20-F", None])
    def test_zero_padded_numbers_rejected(self, padded, form):
        # Zero-padded numbers like `08` are page-number formats, not
        # item identifiers. The original regex required a [1-9]
        # leading digit; the rewritten form-aware regex must preserve
        # that constraint or it accepts `08`, `01`, etc. as items.
        analyzer = TOCAnalyzer(form=form)
        link = _make_link_with_preceding_td(padded)
        label = analyzer._extract_preceding_item_label(link)
        assert label == "", (
            f"zero-padded `{padded}` should not be an item on form={form!r}; got {label!r}"
        )


class TestPagesNumbersStillFilteredOnLargeForms:
    """All forms still reject obvious page numbers like 20, 50, 108."""

    @pytest.mark.parametrize("page_text", ["20", "50", "108", "23"])
    @pytest.mark.parametrize("form", ["10-K", "10-Q", "20-F"])
    def test_above_max_rejected(self, page_text, form):
        analyzer = TOCAnalyzer(form=form)
        link = _make_link_with_preceding_td(page_text)
        # All these values exceed the cap for every form:
        # 10-Q max=6, 10-K and 20-F at default 15.
        assert analyzer._extract_preceding_item_label(link) == "", (
            f"page number {page_text} should not be accepted as an item on {form}"
        )


class TestNormalizeSectionNameIsFormAware:
    """`_normalize_section_name` had a 10-K-shaped text-fallback table
    that mapped any link containing 'financial statements' to 'Item 8'.

    On a 10-Q this produced the PPG regression: a TOC link reading
    "Notes to Condensed Consolidated Financial Statements" was
    normalised to "Item 8", a section the 10-Q form doesn't have.
    The form-aware guard skips the 10-K-specific table for other forms.
    """

    def test_ten_k_financial_statements_still_maps_to_item_8(self):
        analyzer = TOCAnalyzer(form="10-K")
        # Standard 10-K Item 8 wording
        assert analyzer._normalize_section_name(
            "Financial Statements", anchor_id="", preceding_item=""
        ) == "Item 8"

    def test_ten_q_financial_statements_not_normalised_to_item_8(self):
        analyzer = TOCAnalyzer(form="10-Q")
        text = "Notes to Condensed Consolidated Financial Statements"
        result = analyzer._normalize_section_name(text, anchor_id="", preceding_item="")
        assert result != "Item 8", (
            f"10-Q link must not be mapped to non-existent Item 8; got {result!r}"
        )
        # Returned as empty string so `_build_section_mapping` skips
        # the row (rather than emitting a phantom `part_i_notes_to_...`
        # section that downstream code mis-classifies as a Part header).
        assert result == ""

    @pytest.mark.parametrize("ten_k_phrase,expected_item", [
        ("Business", "Item 1"),
        ("Risk Factors", "Item 1A"),
        ("Properties", "Item 2"),
        ("Legal Proceedings", "Item 3"),
        ("Management's Discussion and Analysis", "Item 7"),
        ("Financial Statements", "Item 8"),
        ("Exhibits", "Item 15"),
    ])
    def test_ten_k_text_fallback_preserved(self, ten_k_phrase, expected_item):
        # Regression: the 10-K text-fallback mappings must keep working.
        analyzer = TOCAnalyzer(form="10-K")
        assert analyzer._normalize_section_name(
            ten_k_phrase, anchor_id="", preceding_item=""
        ) == expected_item

    @pytest.mark.parametrize("phrase", [
        "Business",
        "Properties",
        "Legal Proceedings",
        "Financial Statements",
        "Notes to Condensed Consolidated Financial Statements",
        "Exhibits",
    ])
    def test_ten_q_text_fallback_returns_empty_for_misapplied_mappings(self, phrase):
        # For 10-Q, the 10-K-shaped mappings that produce wrong items
        # are NOT applied (Business / Properties / Legal Proceedings /
        # Financial Statements / Exhibits map to different items in
        # the 10-Q form structure). Returning empty string signals
        # "skip this row" to `_build_section_mapping`, which prevents
        # phantom `part_X_notes_to_...` keys that `SECSectionExtractor`
        # would otherwise mis-classify as Part headers.
        analyzer = TOCAnalyzer(form="10-Q")
        assert analyzer._normalize_section_name(
            phrase, anchor_id="", preceding_item=""
        ) == ""

    def test_ten_q_keeps_risk_factors_to_item_1a(self):
        # The 'risk factors' → 'Item 1A' mapping is shared between 10-K
        # and 10-Q (Part II Item 1A on 10-Q). Without this mapping,
        # 10-Q TOC rows with opaque anchors and no preceding item cell
        # would emit `part_ii_risk_factors` keys that
        # `Document.get_section('item_1a', part='II')` can't resolve.
        analyzer = TOCAnalyzer(form="10-Q")
        assert analyzer._normalize_section_name(
            "Risk Factors", anchor_id="", preceding_item=""
        ) == "Item 1A"

    def test_ten_q_risk_factors_order(self):
        analyzer = TOCAnalyzer(form="10-Q")
        section_type, order = analyzer._get_section_type_and_order("Risk Factors")
        assert section_type == "item"
        assert order == 1001  # same slot as Item 1A on 10-K

    def test_ten_q_unrecognised_rows_skipped_in_section_mapping(self):
        """Regression: an unrecognised 10-Q TOC row (e.g., "Notes to ...
        Financial Statements" link with only a page cell before it)
        must NOT produce a `part_i_notes_to_...` phantom key.
        `_normalize_section_name` returns "" for these so
        `_build_section_mapping` skips them entirely.
        """
        from edgar.documents.utils.toc_analyzer import TOCSection

        analyzer = TOCAnalyzer(form="10-Q")
        # Simulate what `_analyze_generic_toc` would build for a
        # PPG-shape row that fell through to the text fallback.
        normalized = analyzer._normalize_section_name(
            "Notes to Condensed Consolidated Financial Statements",
            anchor_id="",
            preceding_item="",
        )
        assert normalized == "", (
            f"unrecognised 10-Q row must return empty to be skipped; got {normalized!r}"
        )

        section = TOCSection(
            name="raw_link_text",
            anchor_id="some_anchor",
            normalized_name=normalized,
            section_type="item",
            order=99999,
            part="Part I",
        )
        mapping = analyzer._build_section_mapping([section])
        assert mapping == {}, (
            f"empty normalized_name must be skipped in mapping; got {mapping}"
        )

    def test_no_form_preserves_ten_k_fallback(self):
        # Backward compat: a TOCAnalyzer with no form set continues to
        # use the 10-K-shaped fallback (matches pre-fix behaviour for
        # callers that don't pass `form`).
        analyzer = TOCAnalyzer()
        assert analyzer._normalize_section_name(
            "Financial Statements", anchor_id="", preceding_item=""
        ) == "Item 8"

    def test_higher_priority_paths_unaffected(self):
        # The preceding_item path takes precedence over text fallback
        # for ALL forms — explicit item context wins.
        for form in ("10-K", "10-Q", "20-F", None):
            analyzer = TOCAnalyzer(form=form)
            assert analyzer._normalize_section_name(
                "Notes to Financial Statements",
                anchor_id="",
                preceding_item="Item 1.",
            ) == "Item 1", f"preceding_item must override text on form={form!r}"

        # Anchor ID also takes precedence.
        for form in ("10-K", "10-Q", "20-F", None):
            analyzer = TOCAnalyzer(form=form)
            assert analyzer._normalize_section_name(
                "Notes to Financial Statements",
                anchor_id="item_1_financial",
                preceding_item="",
            ) == "Item 1", f"anchor_id must override text on form={form!r}"


class TestGetSectionTypeAndOrderIsFormAware:
    """`_get_section_type_and_order` had a parallel 10-K-shaped text
    fallback (Issue 1 from round-2 review). Without form-awareness, a
    10-Q TOC link reading "Notes to Condensed Consolidated Financial
    Statements" was assigned order=8000 (the Item 8 slot) even after
    `_normalize_section_name` started returning the verbatim text.
    The order/name mismatch is a correctness landmine inside
    `_build_section_mapping`.
    """

    def test_ten_k_financial_statements_still_orders_as_item_8(self):
        analyzer = TOCAnalyzer(form="10-K")
        section_type, order = analyzer._get_section_type_and_order("Financial Statements")
        assert section_type == "item"
        assert order == 8000

    def test_ten_q_unmatched_text_falls_to_other_not_item_8(self):
        analyzer = TOCAnalyzer(form="10-Q")
        section_type, order = analyzer._get_section_type_and_order(
            "Notes to Condensed Consolidated Financial Statements"
        )
        assert section_type == "other", (
            f"10-Q text fallback must not assign Item 8 ordering; "
            f"got ({section_type}, {order})"
        )
        assert order == 99999

    def test_ten_q_explicit_item_still_classified(self):
        # The explicit "Item 1" regex above the fallback table is unchanged.
        analyzer = TOCAnalyzer(form="10-Q")
        section_type, order = analyzer._get_section_type_and_order("Item 1")
        assert section_type == "item"
        assert order == 1000

    def test_no_form_preserves_ten_k_ordering(self):
        # Backward compat: callers without form get the legacy behaviour.
        analyzer = TOCAnalyzer()
        assert analyzer._get_section_type_and_order("Financial Statements") == (
            "item", 8000
        )


class TestAnalyzeTocForSectionsForwardsForm:
    """`analyze_toc_for_sections` is the public convenience function. It
    used to construct `TOCAnalyzer()` with no form, silently bypassing
    the form-aware bounds on the bare-item heuristic (Issue 2 from
    round-2 review)."""

    def test_form_kwarg_threads_to_analyzer(self, monkeypatch):
        # Spy on TOCAnalyzer.__init__ to assert the form is forwarded.
        from edgar.documents.utils import toc_analyzer as ta

        captured = {}
        orig_init = ta.TOCAnalyzer.__init__

        def spy_init(self, form=None):
            captured["form"] = form
            orig_init(self, form=form)

        monkeypatch.setattr(ta.TOCAnalyzer, "__init__", spy_init)
        ta.analyze_toc_for_sections("<html></html>", form="10-Q")
        assert captured["form"] == "10-Q"

    def test_default_form_is_none(self, monkeypatch):
        from edgar.documents.utils import toc_analyzer as ta

        captured = {}
        orig_init = ta.TOCAnalyzer.__init__

        def spy_init(self, form=None):
            captured["form"] = form
            orig_init(self, form=form)

        monkeypatch.setattr(ta.TOCAnalyzer, "__init__", spy_init)
        ta.analyze_toc_for_sections("<html></html>")
        assert captured["form"] is None


class TestPlumbingThroughCallChain:
    """Verify that form is forwarded `HybridSectionDetector → TOCAnalyzer`.

    Uses the real HTMLParser so the test exercises the production
    Document-construction path rather than a stub.
    """

    def _build_doc(self, form: str = "10-Q"):
        from edgar.documents import HTMLParser, ParserConfig
        # Minimal HTML; we're not testing detection, only attribute plumbing.
        return HTMLParser(ParserConfig(form=form)).parse(
            "<html><body><p>placeholder</p></body></html>"
        )

    def test_hybrid_detector_passes_form_to_toc_detector(self):
        from edgar.documents.extractors.hybrid_section_detector import (
            HybridSectionDetector,
        )

        doc = self._build_doc("10-Q")
        detector = HybridSectionDetector(doc, form="10-Q")
        assert detector.toc_detector.form == "10-Q"
        assert detector.toc_detector.extractor.form == "10-Q"
        assert detector.toc_detector.extractor.toc_analyzer.form == "10-Q"

    def test_form_propagates_for_ten_k(self):
        from edgar.documents.extractors.hybrid_section_detector import (
            HybridSectionDetector,
        )

        doc = self._build_doc("10-K")
        detector = HybridSectionDetector(doc, form="10-K")
        assert detector.toc_detector.extractor.toc_analyzer.form == "10-K"

    def test_document_get_sec_section_threads_form_to_analyzer(self):
        """`Document.get_sec_section` instantiates SECSectionExtractor lazily
        and now forwards `metadata.form`. Verify the analyzer ends up
        form-aware."""
        doc = self._build_doc("10-Q")
        # Trigger lazy construction by reading a section. It'll return None
        # for our minimal HTML but the side effect is what we care about.
        doc.get_sec_section("Item 1")
        assert doc._section_extractor.toc_analyzer.form == "10-Q"
