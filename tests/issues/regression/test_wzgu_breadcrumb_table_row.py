"""A page-header breadcrumb laid out as a one-row table is stripped from a section's start.

Bead: edgartools-wzgu (follow-up). Found by the network test
tests/issues/regression/test_issue_rv86_incorporated_mda.py after 5.59.0.

ExxonMobil's 10-K puts "Table of Contents" and "Financial Table of Contents" in
one table row at the top of each page. ``_strip_leading_nav`` removes that
breadcrumb when a re-attributed anchor lands on it, matching one label per line.
Before the table-rendering fix those cells arrived on separate lines; once tables
rendered cell by cell they arrived as one line, "Table of Contents  Financial
Table of Contents", which matched nothing, so XOM's Item 7 opened on the
breadcrumb again. Offline.
"""
import pytest

from edgar.documents.extractors.toc_section_extractor import SECSectionExtractor

pytestmark = pytest.mark.fast

BODY = "MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION\n\nForward-looking statements"


def _strip(text):
    extractor = SECSectionExtractor.__new__(SECSectionExtractor)
    return extractor._strip_leading_nav(text)


@pytest.mark.parametrize("header", [
    "Table of Contents  Financial Table of Contents",        # XOM's one-row table
    "Table of Contents  Financial Table of Contents  58",    # with a page number cell
    "Table of Contents\nFinancial Table of Contents",        # the old line-per-cell form
    "Table of Contents\n58",                                  # label then page number
])
def test_breadcrumb_is_stripped(header):
    assert _strip(f"{header}\n\n{BODY}") == BODY


@pytest.mark.parametrize("first_line", [
    "2024  2023",                          # a row of bare numbers is data, not navigation
    "2024",                                # a standalone number with no breadcrumb is kept
    "Table of Contents  Revenue by segment",  # a label sharing a row with real text
])
def test_content_that_only_resembles_a_breadcrumb_is_kept(first_line):
    text = f"{first_line}\n\n{BODY}"
    assert _strip(text) == text
