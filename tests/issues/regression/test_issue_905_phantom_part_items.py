"""Regression test for GitHub Issue #905.

Freddie Mac's Q1 2026 10-Q (CIK 0001026214, accession 0001026214-26-000027)
scatters MD&A into a phantom ``part_i_item_6`` (165K chars) while the real
Part I items return mislabeled scraps. A 10-Q Part I has Items 1-4 only, and
Part II Items 1-6 — but nothing in the pipeline knew that, so the phantom keys
were presented at full 0.95 confidence with no warnings.

Fix (flag-and-return, Verification Constitution #2): the 10-Q ``FormSchema``
now carries per-part item ranges (``part_item_ranges``), and
``HybridSectionDetector._apply_part_validity`` flags any section whose
(part, item) cannot exist on the form — warning appended, confidence reduced
to ``ANOMALOUS_CONFIDENCE`` — so callers can tell the Part's boundaries were
mis-anchored. The content itself is kept: the underlying running-header
mis-anchoring is a separate, harder problem, and silently dropping the section
would lose the only copy of the MD&A text.

GitHub Issue: https://github.com/dgunning/edgartools/issues/905
"""
import pytest

from edgar.documents import HTMLParser
from edgar.documents.config import ParserConfig
from edgar.documents.document import Section
from edgar.documents.extractors.hybrid_section_detector import HybridSectionDetector
from edgar.documents.form_schema import get_form_schema
from edgar.documents.nodes import SectionNode
from tests._offline_filings import offline_filing

pytestmark = pytest.mark.regression


# --- Schema: per-part item validity -------------------------------------------

@pytest.mark.fast
def test_10q_part_item_ranges():
    schema = get_form_schema("10-Q")
    # Part I: Items 1-4 only.
    assert schema.item_valid_in_part("I", "1") is True
    assert schema.item_valid_in_part("I", "4") is True
    assert schema.item_valid_in_part("I", "5") is False
    assert schema.item_valid_in_part("I", "6") is False
    # Part II: Items 1-6 (1A included via its number).
    assert schema.item_valid_in_part("II", "1A") is True
    assert schema.item_valid_in_part("II", "6") is True
    assert schema.item_valid_in_part("II", "7") is False


@pytest.mark.fast
def test_part_item_ranges_unknown_never_flags():
    """None (never flag) for forms without ranges, missing args, unknown parts."""
    assert get_form_schema("10-K").item_valid_in_part("I", "5") is None
    schema = get_form_schema("10-Q")
    assert schema.item_valid_in_part(None, "5") is None
    assert schema.item_valid_in_part("I", None) is None
    assert schema.item_valid_in_part("III", "1") is None


# --- Pipeline: _apply_part_validity -------------------------------------------

def _make_detector(form):
    doc = HTMLParser(ParserConfig(form=form)).parse(
        "<html><body><p>placeholder</p></body></html>"
    )
    return HybridSectionDetector(doc, form=form)


def _section(name, part, item, length=1000, confidence=0.95):
    return Section(
        name=name, title=name, node=SectionNode(section_name=name),
        start_offset=0, end_offset=length, confidence=confidence,
        detection_method="toc", part=part, item=item,
    )


@pytest.mark.fast
def test_phantom_part_i_items_flagged_on_10q():
    sections = {
        "part_i_item_2": _section("part_i_item_2", "I", "2"),
        "part_i_item_5": _section("part_i_item_5", "I", "5"),
        "part_i_item_6": _section("part_i_item_6", "I", "6", length=165_000),
        "part_ii_item_6": _section("part_ii_item_6", "II", "6"),
    }
    result = _make_detector("10-Q")._apply_part_validity(sections)

    for phantom in ("part_i_item_5", "part_i_item_6"):
        section = result[phantom]
        assert any("has no Item" in w for w in section.warnings), (phantom, section.warnings)
        assert section.confidence == 0.5

    # Schema-valid keys are untouched.
    for valid in ("part_i_item_2", "part_ii_item_6"):
        assert result[valid].warnings == []
        assert result[valid].confidence == 0.95


@pytest.mark.fast
def test_part_validity_noop_without_ranges():
    """10-K declares no per-part ranges here (its validity is enforced at key
    construction, GH #836) — the stage must not touch its sections."""
    sections = {"part_i_item_5": _section("part_i_item_5", "I", "5")}
    result = _make_detector("10-K")._apply_part_validity(sections)
    assert result["part_i_item_5"].warnings == []
    assert result["part_i_item_5"].confidence == 0.95


@pytest.mark.fast
def test_part_validity_skips_partless_sections():
    sections = {"signatures": _section("signatures", None, None)}
    result = _make_detector("10-Q")._apply_part_validity(sections)
    assert result["signatures"].warnings == []


# --- End-to-end: Freddie Mac 10-Q under VCR ------------------------------------

@pytest.mark.fast
@pytest.mark.vcr
def test_fmcc_phantom_items_are_prevented():
    """FMCC 10-Q: the phantom part_i_item_5/6 no longer exist at all.

    When #905 was fixed, the phantoms could only be *flagged*: the generic
    TOC scan read the bare row-number cells of FMCC's MD&A "List of Tables"
    index as item numbers, and every Part I item anchored on a "Table N"
    caption. The numbered-index header guard (GH #918, second defect —
    tests/issues/regression/test_issue_918_numbered_index_rows.py) removes
    the phantoms at the source, and the surviving Part I items anchor on
    their real content — part_i_item_2 is the actual MD&A, not 1.2K chars of
    table prose. The schema-validity stage this file pins in its unit tests
    still guards any future mis-anchored map.
    """
    tenq = offline_filing("0001026214-26-000027").obj()
    sections = tenq.document.sections

    for phantom in ("part_i_item_5", "part_i_item_6"):
        assert phantom not in sections, f"{phantom} resurfaced: {sorted(sections.keys())}"

    # The surviving Part I items carry their real content at full confidence.
    mda = sections["part_i_item_2"]
    assert mda.confidence == 0.95
    mda_text = mda.text()
    assert len(mda_text) == 51_860
    assert mda_text.lstrip().startswith("Management's Discussion and Analysis")
    assert not mda_text.lstrip().startswith("Table")

    item3 = sections["part_i_item_3"]
    assert not any("has no Item" in w for w in item3.warnings)
    assert item3.text().lstrip().startswith("Market Risk")

    # Part II is unchanged: Legal Proceedings still opens on its own heading.
    assert (sections["part_ii_item_1"].text() or "").lstrip().startswith("LEGAL PROCEEDINGS")
