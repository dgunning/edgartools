"""Deriving a Reports collection dropped the filing summary, so the reports it handed
back had correct metadata and unreadable content.

bead edgartools-5ysl, GH #1191.

``Report.content`` fetches its R-file through ``reports._filing_summary._filing_sgml``.
Three of the four methods that return a NEW Reports built it with the bare constructor
and lost that back-reference, so ``filter()``, ``next()`` and ``previous()`` returned
collections whose reports listed the right filenames and raised
``AttributeError: 'NoneType' object has no attribute '_filing_sgml'`` on ``.content``.

The ledger here is synthetic and the SGML is a stub. The defect is entirely about which
state survives constructing a derived collection, so a real filing would add a download
without adding evidence -- and it lets these run in the lane that gates pull requests.
The behaviour was reproduced against the filing named in the report first: AAPL 10-K
0000320193-24-000123, where the root collection and ``get_by_category()`` read R3.htm as
79,891 characters while the multi-row ``filter()`` and ``next()`` raised.
"""

import pyarrow as pa
import pytest

from edgar.sgml.filing_summary import Reports

# Comfortably above the 50-row page size, and large enough that a SINGLE category
# (half the ledger) also spans more than one page -- otherwise the paging assertions on
# a filtered collection skip instead of running, which proves nothing.
N_REPORTS = 120
PAGE_SIZE = 50


class _StubSgml:
    """Stands in for FilingSGML. Only get_content() is reached from Report.content."""

    def get_content(self, html_file_name):
        return f"<html>content of {html_file_name}</html>"


class _StubFilingSummary:
    def __init__(self):
        self._filing_sgml = _StubSgml()


def _reports(n=N_REPORTS, attached=True):
    records = [{
        "instance": "aapl-20240928_htm.xml",
        "IsDefault": i == 0,
        "HasEmbeddedReports": False,
        "HtmlFileName": f"R{i + 1}.htm",
        "LongName": f"{i + 1:04d} - Report {i + 1}",
        "ReportType": "Sheet",
        "Role": f"http://example.com/role/Report{i + 1}",
        "ParentRole": None,
        "ShortName": f"Report {i + 1}",
        # Two categories, both above and below the page boundary, so a filter on
        # either one spans pages the way the reported filter() did.
        "MenuCategory": "Statements" if i % 2 == 0 else "Notes",
        "Position": str(i + 1),
    } for i in range(n)]
    return Reports(pa.Table.from_pylist(records),
                   filing_summary=_StubFilingSummary() if attached else None,
                   title="Reports")


def _first(reports):
    return next(iter(reports))


def test_multi_row_filter_keeps_the_filing_summary():
    """The reported case. Only the MULTI-row branch was affected: a one-row filter()
    returns a Report still attached to the original collection, which is why this was
    invisible to anyone filtering down to a single report."""
    reports = _reports()
    filtered = reports.filter("MenuCategory", "Statements")

    assert len(filtered) == N_REPORTS // 2, "expected the multi-row branch, not a Report"
    assert filtered._filing_summary is not None
    assert _first(filtered).content == "<html>content of R1.htm</html>"


def test_next_page_keeps_the_filing_summary():
    reports = _reports()
    page = reports.next()

    assert page is not None and len(page) == PAGE_SIZE, "expected a full second page"
    assert page._filing_summary is not None
    assert _first(page).content == "<html>content of R51.htm</html>"


def test_previous_page_keeps_the_filing_summary():
    """previous() was NOT in the bug report -- it was found by grepping for every
    Reports() construction, as the bead asked. It had the identical defect."""
    reports = _reports()
    reports.next()                    # advance this object's stateful pager
    page = reports.previous()

    assert page is not None
    assert page._filing_summary is not None
    assert _first(page).content == "<html>content of R1.htm</html>"


def test_get_by_category_still_works():
    """The healthy control: this one always passed the filing summary through, and
    routing it via the shared helper must not change what it returns."""
    reports = _reports()
    statements = reports.get_by_category("Statements")

    assert len(statements) == N_REPORTS // 2
    assert statements.title == "Statements", "the explicit title must still win"
    assert _first(statements).content == "<html>content of R1.htm</html>"


def test_a_derived_collection_can_be_derived_again():
    """Paging a filtered collection, or filtering a page. The back-reference has to
    survive more than one hop, which a per-call-site fix gets right only if every site
    is fixed -- three of four were not."""
    reports = _reports()
    filtered = reports.filter("MenuCategory", ["Statements", "Notes"])
    page = filtered.next()

    assert page is not None
    assert page._filing_summary is not None
    assert _first(page).content.startswith("<html>content of ")


def test_the_title_survives_paging():
    """A page of the Statements collection is still Statements. Paging renamed it to the
    default 'Reports', because the derived collection was built from scratch."""
    statements = _reports().get_by_category("Statements")
    assert len(statements) > PAGE_SIZE, "the ledger must be big enough for this to page"
    page = statements.next()

    assert page is not None
    assert page.title == "Statements"


def test_an_unattached_collection_still_reports_no_content_rather_than_lying():
    """The silence check. A Reports genuinely built without a filing summary -- which is
    what FilingSummary.from_xml does before back-wiring itself -- must not now pretend to
    have content. It has none, and .content raises rather than inventing a value."""
    detached = _reports(attached=False)

    assert detached._filing_summary is None
    with pytest.raises(AttributeError):
        _first(detached).content
