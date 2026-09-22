"""One item header is not an item structure (edgartools-dt1f, Defect 1).

``SectionExtractor._find_section_headers`` layers five strategies: semantic
HeadingNodes first, then bold paragraphs, table cells, and plain paragraphs as
fallbacks. The fallbacks were gated on *presence* — if any header collected so
far mentioned an item, they were assumed unnecessary and did not run.

That question is not the one the gate needed answered. On a 2010 20-F
(``0001144204-10-017467``, EDGARizer-generated: 12,880 ``<font>`` tags and zero
``<p>``) header detection promoted 86 nodes, of which three named an item — one
of those a prose cross-reference, "Please refer to Item 6.E, Directors, Senior
Management and Employees". Those three were enough to suppress the strategies
that find that filing's fifteen real item headers, so ``doc.sections`` returned
four items where the legacy ChunkedDocument found twenty-six.

The gate now asks for coverage: has the form's item *structure* been found, not
merely one item. Three items out of the thirty-one a 20-F defines has not.

WHY THE FIXTURE HERE IS SYNTHETIC. The filing above lives in
``tests/fixtures/text_boundary_corpus``, which is gitignored (91 MB), so a test
that read it would silently skip in CI — the failure mode
``tests/test_section_parity_ratchet.py`` documents at length. The document built
below reproduces the shape rather than the filing: a handful of promoted heading
nodes that name no item, one titled item heading that does, and the real item
headers rendered where header detection will not reach them. It fails the same
way (2 sections, not 11) against the pre-fix gate.

End-to-end coverage of the real filing lives in the parity ratchet, which
measures it wherever the era corpus is present.
"""
import pytest

from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.extractors.pattern_section_extractor import SectionExtractor
from edgar.documents.nodes import HeadingNode

# Ten of the nineteen items a 20-F defines, with their real titles.
ITEMS = [
    ("1", "IDENTITY OF DIRECTORS, SENIOR MANAGEMENT AND ADVISERS"),
    ("2", "OFFER STATISTICS AND EXPECTED TIMETABLE"),
    ("3", "KEY INFORMATION"),
    ("4", "INFORMATION ON THE COMPANY"),
    ("5", "OPERATING AND FINANCIAL REVIEW AND PROSPECTS"),
    ("6", "DIRECTORS, SENIOR MANAGEMENT AND EMPLOYEES"),
    ("7", "MAJOR SHAREHOLDERS AND RELATED PARTY TRANSACTIONS"),
    ("8", "FINANCIAL INFORMATION"),
    ("9", "THE OFFER AND LISTING"),
    ("10", "ADDITIONAL INFORMATION"),
]

# Bold, large, uppercase — everything header detection scores on, and not one of
# them an item. This is what the real filing's 86 promoted headings look like.
PROMOTED_NON_ITEMS = [
    "(Mark One)",
    "ANNUAL REPORT PURSUANT TO SECTION 13",
    "A-POWER ENERGY GENERATION SYSTEMS, LTD.",
    "Commission File Number 001-1234",
    "Date March 31, 2010",
    "Business Overview Competition",
    "Certain Arrangements With Management",
    "Consulting Services By Chardan",
]


def _twenty_f_html() -> str:
    """A 20-F whose item headers sit where header detection will not promote them.

    The items go in table cells, split across two of them — the layout the
    filer-agent HTML in this class uses. Header detection leaves them as table
    content, so Strategy 1 collects the eight non-item headings and the single
    "ITEM 19. EXHIBITS" heading, and nothing else.
    """
    body = [
        f'<div><b><font size="5">{text}</font></b></div>'
        for text in PROMOTED_NON_ITEMS
    ]
    for num, title in ITEMS:
        body.append(
            f'<table><tr>'
            f'<td><font style="font-weight:bold">ITEM {num}.</font></td>'
            f'<td><font style="font-weight:bold">{title}</font></td>'
            f'</tr></table>'
        )
        body.append(f'<div><font>Body text for item {num}. {"padding " * 80}</font></div>')
    # The one item header that *is* promoted, and that used to be sufficient on
    # its own to prove the item structure had been found.
    body.append('<div><b><font size="5">ITEM 19. EXHIBITS</font></b></div>')
    body.append(f'<div><font>Exhibit index. {"padding " * 80}</font></div>')
    return "<html><body>" + "\n".join(body) + "</body></html>"


@pytest.fixture(scope="module")
def document():
    return HTMLParser(ParserConfig(form='20-F')).parse(_twenty_f_html())


class TestTheFixtureHasTheShapeTheBugNeeds:
    """If these stop holding, the test below stops testing the defect."""

    def test_header_detection_promotes_almost_no_items(self, document):
        headings = document.root.find(lambda n: isinstance(n, HeadingNode))
        item_headings = [
            h for h in headings
            if (h.text() or '').strip().upper().startswith('ITEM ')
        ]
        assert len(headings) > 5, "no headings promoted — the gate is never reached"
        assert len(item_headings) == 1, (
            f"expected exactly one promoted item heading, got "
            f"{[h.text() for h in item_headings]}. The defect needs a heading set "
            f"that is non-empty but names almost no items."
        )


class TestSparseItemHeadingsDoNotSuppressTheFallbacks:

    def test_all_item_sections_are_found(self, document):
        """The regression: 2 sections before the fix, 11 after."""
        found = set(document.sections)
        expected = {f'item_{num}' for num, _ in ITEMS} | {'item_19'}
        assert found >= expected, (
            f"missing {sorted(expected - found)}. One promoted item heading "
            f"suppressed the strategies that find the rest."
        )

    def test_the_sections_carry_their_body_text(self, document):
        """Found is not the same as usable — a section must reach its content."""
        mda = document.sections['item_5']
        assert 'Body text for item 5' in mda.text()


class TestTheCoverageGate:
    """``_item_structure_found`` — the predicate the fallbacks are gated on."""

    @staticmethod
    def _headers(*texts):
        return [(None, text, i) for i, text in enumerate(texts)]

    def test_a_handful_of_items_is_not_a_structure(self):
        extractor = SectionExtractor('20-F')
        headers = self._headers("ITEM 17. FINANCIAL STATEMENTS",
                                "ITEM 18. FINANCIAL STATEMENTS",
                                "ITEM 19. EXHIBITS")
        assert not extractor._item_structure_found(headers)

    def test_most_of_the_form_is_a_structure(self):
        extractor = SectionExtractor('20-F')
        headers = self._headers(*[f"ITEM {n}. TITLE HERE" for n in range(1, 20)])
        assert extractor._item_structure_found(headers)

    def test_a_prose_cross_reference_is_not_an_item_header(self):
        """The real filing's third "item heading" was a sentence.

        The gate used to search for "Item N" anywhere in the text, so a body
        paragraph pointing at another section counted as evidence that section
        had been found.
        """
        extractor = SectionExtractor('20-F')
        prose = ("Please refer to Item 6.E, “Directors, Senior Management "
                 "and Employees — Share Ownership”")
        assert extractor._item_numbers_in(self._headers(prose)) == set()

    def test_an_empty_header_set_is_never_a_structure(self):
        extractor = SectionExtractor('20-F')
        assert not extractor._item_structure_found([])

    def test_8k_keeps_the_presence_test(self):
        """An 8-K reports only the items it has, so coverage has no denominator.

        A two-item 8-K is complete. Measuring it against the thirty-three items
        the form allows would put every 8-K permanently below any floor and run
        the fallbacks on all of them — the same reason the parity benchmark
        gives 8-K no coverage rate.
        """
        extractor = SectionExtractor('8-K')
        assert extractor._canonical_item_count() == 0
        assert extractor._item_structure_found(
            self._headers("Item 8.01 Other Events", "Item 9.01 Financial Statements")
        )

    def test_a_bare_item_number_is_not_a_complete_header(self):
        """20-F filers emit "Item 3." as a heading and the titled form in the body."""
        extractor = SectionExtractor('20-F')
        assert not extractor._is_complete_item_header("Item 3.")
        assert extractor._is_complete_item_header("Item 3. Key Information")
