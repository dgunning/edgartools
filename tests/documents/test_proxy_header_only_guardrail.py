"""Header-only sliver guardrail for title-based TOC sections (edgartools-x341).

On hierarchical / divider proxy TOCs a vocabulary term can match a divider tab
or summary cross-reference whose section boundary lands at the very next entry,
so the section's whole body is just its heading phrase ("Executive Compensation",
"BOARD OF DIRECTORS") while the real content is absorbed by an adjacent section.
``HybridSectionDetector._drop_header_only_sections`` removes those mislabeled
slivers — but only for title-based forms (DEF 14A / 424B / S-1) and only when the
body carries no sentence (a real short section, e.g. a one-line proposal
recommendation, is kept).

Verified offline against the method directly so the invariants are deterministic
and need no network. The broader behaviour (8/32 diverse proxies stop emitting
slivers, lifting the clean rate 69% -> 91%+) is captured in the field notes.
"""
import pytest

from edgar.documents import parse_html
from edgar.documents.document import Section
from edgar.documents.extractors.hybrid_section_detector import HybridSectionDetector


def _detector(form):
    # A trivial parsed document is enough — _drop_header_only_sections only reads
    # self.form and the supplied Section objects, not document content.
    doc = parse_html("<html><body><p>x</p></body></html>")
    return HybridSectionDetector(doc, form)


def _toc_section(name, body, *, method="toc"):
    """A TOC section whose lazily-extracted text is ``body`` and whose length
    proxy (end_offset, start_offset==0) matches — mirroring how the TOC detector
    stores extracted text length in end_offset."""
    s = Section(name=name, title=name, node=None)
    s.detection_method = method
    s.start_offset = 0
    s.end_offset = len(body)
    s._text_extractor = lambda n, **kw: body
    return s


# Real slivers observed across the 32-filer proxy corpus (all header-only, ≤48 chars).
HEADER_ONLY = [
    ("executive_compensation", "Executive Compensation"),          # WMT/NKE
    ("corporate_governance", "BOARD OF DIRECTORS"),                # XOM
    ("audit_matters", "Audit matters"),                           # VZ
    ("director_compensation", "COMPENSATION OF DIRECTORS"),        # BA
    ("executive_compensation", "Table of Contents\n\n    Executive Compensation"),  # PFE
]


@pytest.mark.parametrize("name,body", HEADER_ONLY)
def test_header_only_sliver_dropped_for_title_based_form(name, body):
    det = _detector("DEF 14A")
    # DEF 14A schema is title_based=False until the x341 flip; force the
    # title-based branch the way the flip will, without depending on the flip.
    det.form = "S-1"  # a shipped title_based form
    sections = {name: _toc_section(name, body)}
    survivors = det._drop_header_only_sections(sections)
    assert name not in survivors, f"header-only sliver {body!r} should be dropped"


def test_real_short_section_with_sentence_is_kept():
    """A terse but real section (a proposal recommendation) has a sentence and
    must survive — this is the VZ voting_proposals=120 case."""
    det = _detector("S-1")
    body = ("Item 1: Election of Directors\n\nThe Board of Directors recommends "
            "that you vote FOR the election of the Board's nominees.")
    survivors = det._drop_header_only_sections({"voting_proposals": _toc_section("voting_proposals", body)})
    assert "voting_proposals" in survivors


def test_long_section_kept_even_without_sentence_punctuation():
    """A heading + table section is long; length alone keeps it."""
    det = _detector("S-1")
    body = "EXECUTIVE COMPENSATION\n\n" + "Name Title Salary Bonus Total\n" * 20
    survivors = det._drop_header_only_sections({"executive_compensation": _toc_section("executive_compensation", body)})
    assert "executive_compensation" in survivors


def test_non_title_based_form_untouched():
    """10-K (Item-based) keeps its output even if a section is header-only —
    the guardrail is scoped to title-based forms only."""
    det = _detector("10-K")
    survivors = det._drop_header_only_sections({"item_1": _toc_section("item_1", "BUSINESS")})
    assert "item_1" in survivors


def test_heading_and_pattern_sections_untouched():
    """Only toc sections are considered (heading/pattern measure length
    differently); a header-only heading section is left alone."""
    det = _detector("S-1")
    sections = {
        "a": _toc_section("a", "Audit matters", method="heading"),
        "b": _toc_section("b", "Audit matters", method="pattern"),
    }
    survivors = det._drop_header_only_sections(sections)
    assert set(survivors) == {"a", "b"}
