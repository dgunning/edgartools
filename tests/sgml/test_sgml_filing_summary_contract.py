"""What `FilingSummary.parse` owes its callers, with no network.

`edgar/sgml/filing_summary.py` moved its XML parse from BeautifulSoup to lxml
under edgartools-07lk.11.3. `tests/test_filing_summary.py` is classified `network`
by `tests/conftest.py`, so the regressions that move could introduce silently —
an attribute read that returns nothing, a `<File>` whose name comes back empty,
a container skipped because an lxml element with no children is falsy — would
only be caught by the sequential network suite. These belong on every commit.

The two `BeautifulSoup` calls still in that module parse R-file *HTML* with
`html.parser`, not XML, and are deliberately untouched: they are `edgar.documents`
work, not `xmltools` work.

Ground truth is Apple's FY2024 10-K FilingSummary, checked in at
`data/sgml/AAPL-FilingSummary.xml`.
"""
from pathlib import Path

import pytest

from edgar.sgml.filing_summary import FilingSummary

AAPL = Path('data/sgml/AAPL-FilingSummary.xml')


@pytest.fixture(scope="module")
def aapl_summary():
    return FilingSummary.parse(AAPL.read_text())


def test_the_document_level_counts_are_read(aapl_summary):
    assert aapl_summary.report_format == "html"
    assert aapl_summary.context_count == "193"
    assert aapl_summary.element_count == "382"
    assert aapl_summary.entity_count == "1"
    assert aapl_summary.segment_count == "73"
    assert aapl_summary.footnotes_reported is False
    assert aapl_summary.has_presentation_linkbase is True


def test_every_report_is_found_with_its_attribute_and_its_children(aapl_summary):
    """`instance` is an ATTRIBUTE of <Report>; everything else is a child element.

    Both reads changed backend here, and an attribute read that quietly returns
    None would leave a report that still looks structurally fine.
    """
    reports = list(aapl_summary.reports)
    assert len(reports) == 74

    cover = reports[0]
    assert cover.instance == "aapl-20240928.htm"
    assert cover.html_file_name == "R1.htm"
    assert cover.short_name == "Cover Page"
    assert cover.menu_category == "Cover"
    assert cover.report_type == "Sheet"
    assert cover.position == "1"
    assert cover.is_default is False


def test_input_and_supplemental_files_keep_their_names_and_flags(aapl_summary):
    """`<File>` carries its name as TEXT and the rest as attributes.

    lxml's own `.text` would be right for these leaves and wrong the moment one
    is not, which is why the module reads them through `element_text`.
    """
    inputs = {f.file_name: f for f in aapl_summary.input_files}
    assert len(inputs) == 6

    primary = inputs["aapl-20240928.htm"]
    assert primary.doc_type == "10-K"
    assert primary.is_definitely_fs is True
    assert primary.is_usgaap is True
    assert primary.original == "aapl-20240928.htm"

    # A schema file carries the name and nothing else — the absent attributes must
    # read as absent, not as the previous file's values.
    schema = inputs["aapl-20240928.xsd"]
    assert schema.doc_type is None
    assert schema.is_definitely_fs is False
    assert schema.original is None

    assert [f.file_name for f in aapl_summary.supplemental_files] == [
        "aapl-20240928_g1.jpg", "aapl-20240928_g2.jpg"]


def test_reports_are_indexed_by_short_name_and_menu_category(aapl_summary):
    assert aapl_summary._short_name_map["Cover Page"].html_file_name == "R1.htm"
    assert {k: len(v) for k, v in aapl_summary._category_map.items()} == {
        "Cover": 2, "Statements": 6, "Notes": 16, "Policies": 1,
        "Tables": 12, "Details": 36,
        # One report — the "All Reports" index — carries no <MenuCategory>, so its
        # key is None. That it stays None rather than becoming "" is the point:
        # absent and empty are different facts (see the child_text contract).
        None: 1,
    }
    assert sum(len(v) for v in aapl_summary._category_map.values()) == 74


def test_parse_rejects_a_document_that_is_not_a_filing_summary():
    """The root check has to survive the move off bs4.

    `soup.find('FilingSummary')` searched the whole document and returned None
    when it was absent, which then failed several lines later with an
    `AttributeError` on None. The lxml parse starts at the root, so the guard is
    now a name comparison — and it says what it got.
    """
    with pytest.raises(ValueError, match="FilingSummary"):
        FilingSummary.parse("<?xml version='1.0'?><MetaLinks><foo/></MetaLinks>")


def test_a_summary_with_no_input_files_parses_rather_than_failing():
    """The truthiness trap. `<InputFiles/>` has no children, which lxml considers
    false — but so would a guard written as `if input_files_tag:` for a container
    that is merely empty, and the same guard is what decides whether the section
    is read at all."""
    summary = FilingSummary.parse(
        "<?xml version='1.0'?><FilingSummary>"
        "<ReportFormat>html</ReportFormat>"
        "<MyReports><Report instance='x.htm'><ShortName>Only</ShortName>"
        "<MenuCategory>Cover</MenuCategory></Report></MyReports>"
        "<InputFiles/></FilingSummary>")

    assert summary.input_files == []
    assert summary.supplemental_files == []
    assert [r.short_name for r in summary.reports] == ["Only"]
