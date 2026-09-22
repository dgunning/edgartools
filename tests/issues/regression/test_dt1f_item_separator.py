"""An item header may separate its number from its title with more than a period.

Filers write the same header five ways — ``Item 1. Business``,
``Item 1: Business``, ``Item 1 - Business``, ``Item 1 — Business`` and bare
``Item 1 Business``. The 10-K section vocabulary accepted only the first and
the last, spelling its separator inline as ``\\.?\\s*`` in each of 23 patterns.

That is not a cosmetic gap, because of *where* the pattern extractor sits. The
hybrid detector tries TOC detection, then the cross-reference index, then
headings, and only then patterns; a filing that reaches the pattern extractor
has already exhausted every other strategy. And the failure is correlated
rather than per-item: a filer picks one separator and uses it for the whole
document, so a colon does not cost one item, it costs all of them at once.
Two filings in the parity corpus resolved a single section apiece —

    0000950153-99-001234   TenK.items == ['Item 8'],  legacy found 15
    0001376474-16-000635   TenK.items == ['Item 8'],  legacy found 20

— and every other item was reachable only through the ``ChunkedDocument``
fallback that 6.0 deletes, so on those filings the deletion would have taken
the content with it. Restoring the separator recovers 32 items across three
filings and loses none; 10-K corpus coverage moves +0.1% -> +2.8% against
legacy (edgartools-dt1f).

WHY THE FIRST TEST BELOW IS THE IMPORTANT ONE. The separator now lives in a
single constant, ``form_schema._ITEM_SEP``, which is what stops the three forms
drifting apart again — 10-Q and 20-F already accepted a dash that 10-K did not,
and nothing was checking. A new pattern written with an inline ``\\.?\\s*``
would reintroduce exactly this bug for one item, quietly, so the drift guard
matters more than any single spelling assertion.
"""
import re
from unittest.mock import MagicMock

import pytest

from edgar.company_reports import TenK
from edgar.documents.config import ParserConfig
from edgar.documents.extractors.pattern_section_extractor import SectionExtractor
from edgar.documents.form_schema import _ITEM_SEP, get_form_schema
from edgar.documents.parser import HTMLParser

# The forms whose vocabulary keys on "Item N" headers. 8-K is excluded on
# purpose: its numbers are dotted ("Item 5.02") and the period between 5 and 02
# is structural, not a separator, so _ITEM_SEP does not belong there.
ITEM_FORMS = ("10-K", "10-Q", "20-F")

SEPARATORS = ["1.", "1:", "1 -", "1 –", "1 —", "1", "1.-", "1. "]


def _item_patterns(form):
    """Every pattern in ``form``'s vocabulary that keys on an item number."""
    for key, patterns in get_form_schema(form).section_patterns.items():
        for pattern, label in patterns:
            if pattern.startswith("^(Item|ITEM)"):
                yield key, pattern, label


@pytest.mark.fast
class TestTheSeparatorIsDefinedOnce:
    """The drift guard. Every item pattern must take its separator from _ITEM_SEP."""

    @pytest.mark.parametrize("form", ITEM_FORMS)
    def test_no_pattern_spells_its_own_separator(self, form):
        offenders = [
            (key, pattern)
            for key, pattern, _label in _item_patterns(form)
            if _ITEM_SEP not in pattern
        ]
        assert not offenders, (
            f"{form} patterns spell the item separator inline instead of using "
            f"_ITEM_SEP, so they accept whatever that one author thought of: "
            f"{offenders}"
        )

    def test_the_separator_accepts_every_spelling_filers_use(self):
        for sep in SEPARATORS:
            assert re.fullmatch(_ITEM_SEP, sep[1:]), (
                f"_ITEM_SEP rejects {sep[1:]!r}, the separator in {sep!r}"
            )

    def test_the_separator_does_not_swallow_a_title(self):
        """It must stay a separator: a word after it is the title, not padding."""
        assert not re.fullmatch(_ITEM_SEP, ". Business")

    @pytest.mark.parametrize("form", ITEM_FORMS)
    def test_the_extractor_sees_the_same_patterns(self, form):
        """SECTION_PATTERNS is a projection of the schema, not a second copy."""
        assert SectionExtractor.SECTION_PATTERNS[form] == \
            get_form_schema(form).section_patterns


# Real header spellings, one per form, taken from filings rather than invented.
# The two tests above already prove the general case — every item pattern is
# built from _ITEM_SEP, and _ITEM_SEP takes every spelling — so this table is
# here to keep that proof honest end to end, not to enumerate the vocabulary.
REAL_HEADERS = [
    # (form, section key, header as the filer wrote it)
    ("10-K", "business", "Item 1:  Business"),                      # 0000950153-99-001234
    ("10-K", "risk_factors", "ITEM 1A: RISK FACTORS"),              # 0001376474-16-000635
    ("10-K", "mda", "ITEM 7: MANAGEMENT DISCUSSION AND ANALYSIS"),  # 0001376474-16-000635
    ("10-K", "business", "Item 1. Business"),                       # the modern majority
    ("10-K", "properties", "Item 2 - Properties"),
    ("10-K", "part_iii_item_10", "Item 10 — Directors and Executive Officers"),
    ("10-Q", "part_i_item_1", "Item 1: Financial Statements"),
    ("10-Q", "part_i_item_2", "Item 2. Management's Discussion and Analysis"),
    ("20-F", "item_5", "Item 5: Operating and Financial Review and Prospects"),
    ("20-F", "item_16a", "ITEM 16A - Audit Committee Financial Expert"),
]


@pytest.mark.fast
@pytest.mark.parametrize("form,key,header", REAL_HEADERS)
def test_real_headers_match_their_section_pattern(form, key, header):
    pattern = get_form_schema(form).section_patterns[key][0][0]
    assert re.match(pattern, header, re.IGNORECASE), \
        f"{form}/{key} does not recognise {header!r}"


# --- End to end, through the object a user actually holds --------------------

def _ten_k(html):
    filing = MagicMock()
    filing.form = "10-K"
    filing.html.return_value = html
    filing.accession_number = "0000000000-00-000000"
    filing.base_dir = None
    report = TenK.__new__(TenK)
    report._filing = filing
    return report


_ITEMS = [
    ("1", "BUSINESS"),
    ("1A", "RISK FACTORS"),
    ("2", "PROPERTIES"),
    ("3", "LEGAL PROCEEDINGS"),
    ("7", "MANAGEMENT DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION"),
    ("8", "FINANCIAL STATEMENTS"),
    ("10", "DIRECTORS AND EXECUTIVE OFFICERS AND CORPORATE GOVERNANCE"),
    ("11", "EXECUTIVE COMPENSATION"),
]


def _html(sep):
    """A 10-K body whose only usable headers are bold item paragraphs.

    Deliberately gives the detector nothing else to work with — no TOC, no
    cross-reference index, no semantic headings — so it falls to the pattern
    extractor, which is the path the real filings took.
    """
    return "<html><body>" + "".join(
        f'<p style="font-weight:bold">ITEM {num}{sep} {title}</p>'
        f'<p>{"body text " * 60}</p>'
        for num, title in _ITEMS
    ) + "</body></html>"


def _pattern_sections(sep):
    """Sections the PATTERN EXTRACTOR alone finds in a body punctuated with ``sep``.

    Deliberately not routed through ``TenK.items``: on synthetic HTML the bold
    paragraphs are promoted to heading nodes and the heading detector — which
    has always accepted a colon — answers first, so an end-to-end assertion here
    passes with or without this fix and guards nothing. The extractor is the
    component that changed, and on the real filings it is the component that was
    reached, every earlier strategy having declined. The end-to-end evidence
    lives on the real fixture at the bottom of this file, where it discriminates.

    The document is parsed with ``detect_sections=True`` so the node tree is the
    one the hybrid detector's own fallback strategies see; building an extractor
    over a ``detect_sections=False`` parse measures a different pipeline.
    """
    doc = HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(_html(sep))
    return SectionExtractor("10-K").extract(doc)


@pytest.mark.fast
class TestThePatternExtractorOnEachSeparator:

    @pytest.mark.parametrize("sep", [":", ".", " -", " —", ""])
    def test_every_item_is_found(self, sep):
        found = _pattern_sections(sep)
        items = sorted(s.item for s in found.values() if s.item)
        for num, _title in _ITEMS:
            assert num in items, (
                f"separator {sep!r} lost Item {num}; found {items}"
            )

    def test_a_colon_body_matches_a_period_body_exactly(self):
        assert set(_pattern_sections(":")) == set(_pattern_sections("."))

    def test_the_sections_carry_text_not_just_names(self):
        """The failure this guards is a list that names sections holding nothing."""
        for key, section in _pattern_sections(":").items():
            assert len(section.text()) > 100, f"{key} matched but is empty"


@pytest.mark.fast
class TestTenKItemsOnColonSeparatedHeaders:
    """The user-level view, on the same bodies."""

    @pytest.mark.parametrize("sep", [":", ".", " -", " —"])
    def test_every_item_is_listed(self, sep):
        items = _ten_k(_html(sep)).items
        for num, _title in _ITEMS:
            assert f"Item {num}" in items, (
                f"separator {sep!r} lost Item {num}; got {items}"
            )

    def test_the_items_are_retrievable_not_merely_listed(self):
        report = _ten_k(_html(":"))
        for num, _title in _ITEMS:
            text = report[f"Item {num}"]
            assert text and len(text) > 100, f"Item {num} listed but empty"


# --- Ground truth: the filing the defect was found on ------------------------

FIXTURE = "tests/fixtures/parity_gate/10-K/0000950153-99-001234.html"


@pytest.fixture(scope="module")
def report(pytestconfig):
    path = pytestconfig.rootpath / FIXTURE
    if not path.exists():  # pragma: no cover
        pytest.fail(f"tracked parity-gate fixture is missing: {FIXTURE}")
    return _ten_k(path.read_text(errors="ignore"))


@pytest.mark.fast
class TestTheFilingThatFoundIt:
    """Medicis Pharmaceutical's FY1999 10-K, headers written ``Item 1:  Business``.

    Tracked in ``parity_gate`` rather than left in the gitignored era corpus:
    the whole point is that CI can see this one.
    """

    def test_items_is_no_longer_a_single_item(self, report):
        """Before the fix this returned exactly ['Item 8'].

        Item 4 joined the list on 2026-08-22: this filing titles it "Submission
        of Matters to a Vote of Security Holders", the pre-2011 title, and the
        vocabulary only held the modern "Mine Safety Disclosures"
        (edgartools-dt1f.1 Defect A). The gap it left is why this assertion used
        to jump from Item 3 to Item 5.
        """
        items = report.items
        assert len(items) >= 12, f"expected the full item list, got {items}"
        assert items[:4] == ["Item 1", "Item 2", "Item 3", "Item 4"]

    def test_item_1_is_the_business_section(self, report):
        text = report["Item 1"]
        assert "Medicis" in text
        assert len(text) > 20_000

    def test_the_parts_resolve(self, report):
        """Part III items 10-13, the block most often lost to a failed pattern."""
        for num in ("10", "11", "12", "13"):
            assert f"Item {num}" in report.items
