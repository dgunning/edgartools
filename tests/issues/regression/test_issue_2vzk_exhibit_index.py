"""The exhibit index survives into rendered markdown and text (edgartools-2vzk).

Found by the markdown-parity harness (``edgartools-zqjn``), which measured the
new renderer losing numeric content that the legacy one kept. Almost all of it
was this: SEC exhibit indexes vanishing from ``Document.to_markdown()``.

TWO DEFECTS, ONE SYMPTOM. Both are asserted here because either alone leaves the
exhibit index unusable.

1. *Every row classified as a header.* ``_is_header_row`` treats a date anywhere
   in a row as evidence of a period column ("Three Months Ended June 30, 2025").
   Exhibit descriptions are full of incidental dates — "...dated as of June 25,
   2019, between AbbVie Inc. and ..." — so every row matched, ``TableNode.rows``
   came back nearly empty, and the markdown renderer combined 30-odd "header"
   rows into a single line. The table disappeared.

2. *Fabricated whitespace inside exhibit numbers.* ABBV splits each number across
   two anchors — ``<a>10.1</a><a>0</a>`` with nothing between them — and
   ``_extract_text`` inserted a space between any two adjacent text fragments.
   ``10.10`` came out as ``10.1 0``, which is worse than missing: the figure is
   present but wrong, so neither a reader nor a search finds it.

WHY IT MATTERS. The exhibit index is the route from a 10-K to its material
contracts, and "incorporated by reference" rows are the only place some
agreements are named at all. Dropping it silently from markdown means every RAG
pipeline built on that output is blind to a filing's exhibits.

Ground truth is read off the filing itself: ABBV's FY2024 10-K exhibit index runs
2.1 through 32.1, and the values asserted here were confirmed by hand against the
rendered document, not copied from parser output.
"""
import re
from pathlib import Path

import pytest

from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser

pytestmark = pytest.mark.fast

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "html" / "abbv" / "10k"


@pytest.fixture(scope="module")
def abbv_document():
    fixtures = sorted(FIXTURE_DIR.glob("*.html"))
    assert fixtures, f"committed ABBV 10-K fixture is missing from {FIXTURE_DIR}"
    html = fixtures[0].read_text(errors="ignore")
    return HTMLParser(ParserConfig(form="10-K")).parse(html)


class TestTheExhibitIndexReachesTheOutput:

    def test_exhibit_numbers_render_in_markdown(self, abbv_document):
        """The whole point: you can find an exhibit by its number."""
        markdown = abbv_document.to_markdown()
        missing = [n for n in ("2.1", "4.8", "10.10", "10.11", "10.19", "32.1")
                   if n not in markdown]
        assert not missing, (
            f"exhibit numbers absent from rendered markdown: {missing}. The "
            "exhibit index is how a 10-K points at its material contracts."
        )

    def test_exhibit_descriptions_render_in_markdown(self, abbv_document):
        markdown = abbv_document.to_markdown()
        assert "Exhibit Description" in markdown
        assert "Transaction Agreement" in markdown
        assert "incorporated by reference" in markdown.lower()

    def test_exhibit_numbers_render_in_text(self, abbv_document):
        """``text()`` lost the exhibit-NUMBER column while keeping descriptions.

        Asserted separately from markdown because the two renderers failed
        differently — markdown dropped the table, text kept it but dropped a
        column — and a fix for one need not fix the other.
        """
        text = abbv_document.text()
        assert "10.10" in text
        assert "10.11" in text
        assert "Exhibit Description" in text


class TestTheExhibitTableIsStructuredNotSquashed:

    def test_exhibit_tables_have_data_rows(self, abbv_document):
        """Header/data split, the mechanism behind defect 1.

        Before the fix the first exhibit table reported 30+ header rows and 2
        data rows. Asserting the shape rather than only the rendered string
        means a renderer that papered over the misclassification would not make
        this pass.
        """
        exhibit_tables = [t for t in abbv_document.tables
                          if "Exhibit Description" in (t.text() or "")]
        assert exhibit_tables, "no exhibit table found in the parsed document"

        for table in exhibit_tables:
            headers = table.headers or []
            rows = table.rows or []
            assert len(rows) > len(headers), (
                f"exhibit table has {len(headers)} header rows and {len(rows)} "
                "data rows — its data rows are being classified as headers"
            )


class TestNumbersAreNotSplitByFabricatedWhitespace:

    def test_no_space_is_inserted_inside_an_exhibit_number(self, abbv_document):
        """Defect 2, asserted as the corruption rather than the absence.

        ``10.1 0`` would satisfy a naive "is 10.1 present" check, so the
        assertion has to name the broken form.
        """
        markdown = abbv_document.to_markdown()
        split = re.findall(r"\b\d{1,2}\.\d\s+\d\b", markdown)
        assert not split, (
            f"whitespace fabricated inside numbers: {sorted(set(split))[:10]}. "
            "Adjacent inline elements must not be separated by a space."
        )

    def test_block_boundaries_still_separate_words(self, abbv_document):
        """The converse, so the fix cannot be 'never insert whitespace'.

        Word-gluing is the opposite failure and the reason the original
        fragment-joining code existed. The header cell is built from two
        separate block elements and must not collapse to 'ExhibitNumber'.
        """
        markdown = abbv_document.to_markdown()
        assert "ExhibitNumber" not in markdown
        assert "ExhibitDescription" not in markdown
        assert re.search(r"Exhibit\s+Number", markdown), (
            "the two-block header cell lost its separator entirely"
        )
