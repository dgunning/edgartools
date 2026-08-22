"""
Tests for the section content-size guardrail (edgartools-9hwf).

The guardrail flags sections whose extracted content size is anomalous for their
item — too small (anchor landed on a heading) or too large (boundary overshoot) —
attaching a human-readable warning and reducing confidence, instead of returning
wrong content at 0.95 confidence (the GS/Citi silent-failure class).
"""
import json
from pathlib import Path

import pytest

from edgar.documents.section_size_bands import (
    SIZE_BANDS,
    band_for,
    cross_reference_warning,
    evaluate_size,
    is_cross_reference,
    is_undersize,
)

HTML_ROOT = Path(__file__).parent / "fixtures" / "html"
CORPUS_BANDS = Path(__file__).parent / "fixtures" / "parser_corpus" / "size_bands.json"


# ---------------------------------------------------------------------------
# Unit: the band evaluator (fast, no parsing)
# ---------------------------------------------------------------------------

def test_evaluate_size_in_band_returns_none():
    band = band_for("10-K", "1A")
    mid = (band["low"] + band["high"]) // 2
    assert evaluate_size("10-K", "1A", mid) is None


def test_evaluate_size_too_large_flags_overshoot():
    warning = evaluate_size("10-K", "1", 668_343)  # GS Business
    assert warning is not None
    assert "above the expected maximum" in warning
    assert "over-captured" in warning


def test_evaluate_size_too_small_flags_truncation():
    # Length alone only says "undersize"; which of the two undersize causes it is
    # (truncated extraction vs incorporation by reference) needs the text, and is
    # decided by is_cross_reference on the detector path.
    warning = evaluate_size("10-K", "8", 268)
    assert warning is not None
    assert "below the expected minimum" in warning
    assert "truncated" in warning


def test_library_bands_match_corpus():
    """Drift guard: the library's hardcoded SIZE_BANDS must match the enforced
    bands in the corpus (tests/fixtures/parser_corpus/size_bands.json). The two
    are maintained by hand-copying on corpus refresh; this catches a stale copy.

    The library keys a 10-Q band by Part ("I:1"), because that form's item
    numbers repeat and only Part I's Item 1 is enforced (edgartools-xhmd). The
    corpus file predates that and keys by bare item, collapsing both Item 1s
    into one bucket by keeping the larger — which is Part I's, so the *numbers*
    are the ones the library carries and the comparison is exact once the Part
    qualifier is stripped. Regenerating the corpus per-Part (edgartools-d64d)
    removes the need for this normalization.
    """
    def bare(key: str) -> str:
        return key.split(":")[-1]

    corpus = json.loads(CORPUS_BANDS.read_text())["bands"]
    for form, items in corpus.items():
        enforced = {bare(k): v for k, v in items.items() if v.get("enforce")}
        lib = {bare(k): v for k, v in SIZE_BANDS.get(form, {}).items()}
        assert set(lib) == set(enforced), (
            f"{form}: library bands {sorted(lib)} != enforced corpus bands "
            f"{sorted(enforced)} — rerun build_corpus.py and update SIZE_BANDS"
        )
        for item, band in enforced.items():
            assert lib[item]["low"] == band["low_flag"], f"{form} Item {item} low drifted"
            assert lib[item]["high"] == band["high_flag"], f"{form} Item {item} high drifted"


def test_evaluate_size_silence_paths():
    # Unenforced item → no band → never flagged.
    assert evaluate_size("10-K", "1B", 50) is None
    # Unknown form → no band.
    assert evaluate_size("S-1", "1", 10) is None
    # Zero/unknown length is not a size anomaly (handled as "missing" upstream).
    assert evaluate_size("10-K", "1", 0) is None
    # None inputs.
    assert evaluate_size(None, "1", 100) is None
    assert evaluate_size("10-K", None, 100) is None


# ---------------------------------------------------------------------------
# Unit: telling the two undersize causes apart (GH #927)
# ---------------------------------------------------------------------------

# Verbatim Item 8 bodies from the fixture corpus. Every filer whose Item 8 falls
# below the band is one of these — an incorporation-by-reference pointer, not a
# truncated extraction.
CROSS_REFERENCE_ITEM8 = {
    "nvda": "Item\xa08. Financial Statements and Supplementary Data\n\nThe information "
            "required by this Item is set forth in our Consolidated Financial Statements "
            "and Notes thereto included in this Annual Report on Form 10-K.",
    "nflx": "Item 8.Financial Statements and Supplementary Data\n\nThe consolidated "
            "financial statements and accompanying notes listed in Part IV, Item\xa015(a)(1) "
            "of this Annual Report on Form 10-K are included immediately following Part IV.",
    "ibm": "Item 8. Financial Statements and Supplementary Data:\n\nRefer to pages 46 "
           "through 121 of IBM's 2024 Annual Report to Stockholders, which are "
           "incorporated herein by reference.",
    "orcl": "Item 8.\tFinancial Statements and Supplementary Data\n\nThe response to this "
            "item is submitted as a separate section of this Annual Report. See Part IV, "
            "Item 15.",
    "cik915358": "FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA\n\nThe response to this item "
                 "is included in Item 15(a) of this Report.",
}


@pytest.mark.parametrize("filer", sorted(CROSS_REFERENCE_ITEM8))
def test_cross_reference_stubs_are_recognised(filer):
    assert is_cross_reference(CROSS_REFERENCE_ITEM8[filer]) is True


@pytest.mark.parametrize("text", [
    "Item 8. Financial Statements and Supplementary Data",   # anchor on the heading
    "PART II\n\nItem 8.",                                    # anchor on the PART header
    "Item 8. Financial Statements and Supplementary Data\n\n46",
    "The following discussion should be read together with our consolidated "
    "financial statements. Revenue increased 114% to $130,497 million.",
    # XOM's Item 1 shape (see test_xom_complete_item1_keeps_the_size_warning):
    # a real body that mentions a deferral. Each bound rejects one half —
    # a body too long to be a pointer, and a deferral sitting past the top.
    "Information about our business segments is contained in the Financial "
    "Section of this report. " + "x" * 1_600,
    "Our operations span exploration, production, refining and chemicals "
    "across six continents, described further below. " * 5
    + "Segment results are set forth in Part II, Item 8.",
    "",
    None,
])
def test_non_cross_reference_text_is_not_flagged(text):
    """A truncated extraction carries no deferral — it must keep the size warning."""
    assert is_cross_reference(text) is False


def test_is_undersize_only_below_the_floor():
    band = band_for("10-K", "8")
    assert is_undersize("10-K", "8", 207) is True
    assert is_undersize("10-K", "8", band["low"]) is False
    assert is_undersize("10-K", "8", band["high"] + 1) is False   # oversize is not undersize
    assert is_undersize("10-K", "1B", 50) is False                # unenforced item
    assert is_undersize("10-K", "8", 0) is False                  # unknown length


def test_cross_reference_warning_names_the_cause():
    warning = cross_reference_warning("10-K", "8", 207)
    assert "incorporation by reference" in warning
    assert "faithful" in warning
    assert "truncated" not in warning


def test_undersize_cross_reference_replaces_the_truncation_warning():
    """Detector path: an undersize section whose text is a pointer gets the
    cross-reference warning; an undersize section without one keeps the
    truncation warning. Both stay flagged and both keep reduced confidence."""
    from edgar.documents.document import Section
    from edgar.documents.extractors.hybrid_section_detector import HybridSectionDetector
    from edgar.documents.nodes import SectionNode
    from edgar.documents.section_size_bands import ANOMALOUS_CONFIDENCE

    det = HybridSectionDetector.__new__(HybridSectionDetector)  # bypass heavy __init__
    det.form = "10-K"

    def mk(text):
        section = Section(
            name="part_ii_item_8", title="x", node=SectionNode(section_name="x"),
            start_offset=0, end_offset=len(text),
            detection_method="toc", item="8",
        )
        section.text = lambda **kw: text  # noqa: ARG005 - stub the extraction
        return section

    sections = det._apply_size_guardrail({
        "pointer": mk(CROSS_REFERENCE_ITEM8["nvda"]),
        "truncated": mk("Item 8. Financial Statements and Supplementary Data"),
    })

    pointer = sections["pointer"]
    assert len(pointer.warnings) == 1
    assert "incorporation by reference" in pointer.warnings[0]
    assert pointer.confidence <= ANOMALOUS_CONFIDENCE

    truncated = sections["truncated"]
    assert len(truncated.warnings) == 1
    assert "truncated" in truncated.warnings[0]
    assert truncated.confidence <= ANOMALOUS_CONFIDENCE


def test_oversize_section_never_pays_for_the_text_test():
    """Silence/cost check: the cross-reference test is undersize-only, so an
    over-captured section is never re-extracted to run it."""
    from edgar.documents.document import Section
    from edgar.documents.extractors.hybrid_section_detector import HybridSectionDetector
    from edgar.documents.nodes import SectionNode

    det = HybridSectionDetector.__new__(HybridSectionDetector)
    det.form = "10-K"
    section = Section(
        name="part_ii_item_8", title="x", node=SectionNode(section_name="x"),
        start_offset=0, end_offset=5_000_000,
        detection_method="toc", item="8",
    )

    def boom(**kwargs):
        raise AssertionError("oversize section must not be re-extracted")

    section.text = boom
    out = det._apply_size_guardrail({"oversize": section})
    assert "over-captured" in out["oversize"].warnings[0]


def test_guardrail_only_applies_to_toc_sections():
    """Only TOC sections carry a text-length in end_offset; pattern sections
    store a document char-position there (a different yardstick). The guardrail
    must skip non-TOC sections to avoid mis-flagging them on the wrong scale."""
    from edgar.documents.document import Section
    from edgar.documents.extractors.hybrid_section_detector import HybridSectionDetector
    from edgar.documents.nodes import SectionNode

    det = HybridSectionDetector.__new__(HybridSectionDetector)  # bypass heavy __init__
    det.form = "10-K"

    def mk(method):
        return Section(
            name="part_ii_item_1", title="x", node=SectionNode(section_name="x"),
            start_offset=0, end_offset=5_000_000,  # absurd: would trip the band
            detection_method=method, item="1",
        )

    sections = {"toc": mk("toc"), "pattern": mk("pattern"), "heading": mk("heading")}
    out = det._apply_size_guardrail(sections)

    assert out["toc"].warnings, "TOC section should be flagged"
    assert not out["pattern"].warnings, "pattern section must not be flagged (wrong length scale)"
    assert not out["heading"].warnings, "heading section must not be flagged"


# ---------------------------------------------------------------------------
# Integration: real filings through the detection pipeline (offline)
# ---------------------------------------------------------------------------

def _sections(rel: str, form: str):
    from edgar.documents.config import ParserConfig
    from edgar.documents.parser import HTMLParser
    html = (HTML_ROOT / rel).read_text()
    return HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(html).sections


@pytest.mark.slow
def test_gs_business_correctly_bounded():
    """Ground truth (edgartools-sldz): GS 10-K once mapped Business to a 668KB
    over-captured section (item structure lived only in a link-less TOC). The
    body-header detector now bounds it correctly to ~150KB, well within the
    Item 1 band — so it is no longer flagged and keeps full TOC confidence."""
    sections = _sections("gs/10k/gs-10-k-2025-02-27.html", "10-K")
    item1 = [s for s in sections.values() if s.item == "1"]
    assert item1, "GS Item 1 not detected"
    # Exactly one canonical Business section, correctly keyed under Part I.
    assert "part_i_item_1" in sections
    s = item1[0]
    length = (s.end_offset - s.start_offset) if (s.end_offset and s.start_offset is not None) else len(s.text() or "")
    assert 50_000 < length < 321_384, f"GS Item 1 length {length} outside the healthy band"
    assert not s.warnings, f"GS Item 1 unexpectedly flagged: {s.warnings}"
    assert s.confidence >= 0.9
    # The Business section starts with the real heading, not adjacent content.
    assert s.text().lstrip().lower().startswith("item 1")


@pytest.mark.slow
@pytest.mark.parametrize("filer,path,form,key,length", [
    ("nvda", "nvda/10k/nvda-10-k-2025-02-26.html", "10-K", "part_ii_item_8", 207),
    ("nflx", "nflx/10k/nflx-10-k-2025-01-27.html", "10-K", "part_ii_item_8", 268),
    ("ibm", "ibm/10k/ibm-10-k-2025-02-25.html", "10-K", "part_ii_item_8", 250),
    ("orcl", "orcl/10k/orcl-10-k-2025-06-18.html", "10-K", "part_ii_item_8", 158),
    ("cik915358", "915358/10k/915358-10-k-2025-08-27.html", "10-K", "part_ii_item_8", 112),
    # The deferral pattern is not Item-8-specific: IBM also incorporates MD&A
    # by reference.
    ("ibm", "ibm/10k/ibm-10-k-2025-02-25.html", "10-K", "part_ii_item_7", 212),
    # Boeing's 10-Q Part II Item 1 (a 258-char pointer into Part I's notes) was
    # here too. It is no longer flagged, and deliberately: that item is not
    # size-enforced since edgartools-xhmd. It only ever reached this warning
    # because Part II's Legal Proceedings was being judged against Part I's
    # Financial Statements band, which flagged 18 of 25 corpus 10-Qs — mostly
    # correct extractions of a legitimately short item. Losing an accurate note
    # on the few that really are pointers is the price of not crying wolf on the
    # rest; see test_ten_q_part_ii_items_are_not_judged_by_part_i_bands below.
])
def test_undersized_pointer_section_is_flagged_as_a_cross_reference(filer, path, form, key, length):
    """Ground truth (GH #927): these filers answer an item with a pointer and file
    the content elsewhere. The extraction is correct, so the guardrail must
    say incorporation-by-reference — not that the anchor missed the body."""
    sections = _sections(path, form)
    assert key in sections, f"{filer} {key} not detected"
    section = sections[key]
    assert section.warnings, f"{filer} undersized {key} was not flagged"
    assert len(section.text()) == length, f"{filer} {key} length drifted from ground truth"
    assert "incorporation by reference" in section.warnings[0]
    assert "truncated" not in section.warnings[0]
    assert section.confidence <= 0.5


@pytest.mark.slow
def test_xom_complete_item1_keeps_the_size_warning():
    """Negative ground truth: XOM's Item 1 is a complete 7,208-char Business
    section that falls 10% under a band floor tuned to large-caps, and its
    narrative mentions a deferral 2,423 chars in ("contained in the Financial
    Section"). An unbounded pointer test recast it as an incorporation by
    reference — a false factual claim about a real body. It must keep the
    plain undersize warning."""
    sections = _sections("xom/10k/xom-10-k-2025-02-19.html", "10-K")
    assert "part_i_item_1" in sections, "XOM Item 1 not detected"
    section = sections["part_i_item_1"]
    text = section.text()
    assert len(text) == 7_208, "XOM Item 1 length drifted from ground truth"
    assert is_cross_reference(text) is False
    assert section.warnings, "XOM Item 1 should still be flagged undersize"
    assert "below the expected minimum" in section.warnings[0]
    assert "incorporation by reference" not in section.warnings[0]


@pytest.mark.slow
def test_healthy_filing_has_no_warnings():
    """Silence check: a healthy filing (NKE) produces no size warnings and keeps
    full TOC confidence."""
    sections = _sections("nke/10k/nke-10-k-2025-07-17.html", "10-K")
    warned = {n: s.warnings for n, s in sections.items() if s.warnings}
    assert not warned, f"healthy NKE filing produced unexpected warnings: {warned}"
    # Enforced content items retain high confidence.
    for s in sections.values():
        if s.item in ("1", "1A", "7"):
            assert s.confidence >= 0.9
