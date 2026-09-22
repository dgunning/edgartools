"""Regression test for GitHub Issue #928.

``CrossReferenceIndex.has_index()`` never returned on some 10-Ks. Detection ran
two probes: a cheap heading regex, then a single pattern nesting six lazy
quantifiers under ``DOTALL`` matched against the *entire* filing HTML::

    r'<td[^>]*>.*?(?:Item\\s+)?1A\\..*?</td>'
    r'.*?<td[^>]*>.*?Risk\\s+Factors.*?</td>'
    r'.*?<td[^>]*>.*?\\d+(?:(?:&#8211;|-)\\d+)?.*?</td>'

Where the heading matched but the table shape did not, the engine backtracked
catastrophically. On ODP Corp's FY2025 10-K (CIK 800240, accession
0000950170-25-027569, 5.6MB) the call did not finish within 45 seconds. A
successful match returned instantly, so only the *non-matching* case was
affected — which is why it survived until a filing hit it.

The blast radius came from where it is reached: ``TenK.__getitem__`` ->
``_cross_reference_index`` -> ``has_index()``, so any ``filing['Item 7']`` on an
affected 10-K hung. ``re`` holds the GIL throughout, so one such filing froze
every other thread in the process, presenting as a whole-process hang rather
than one slow filing.

Fix: detection is anchored to the index table ``_find_index_table()`` already
locates, and the single mega-pattern is replaced by a linear row-by-row scan
reusing the row/cell shapes ``parse()`` relies on. Bounding the search window
alone was *not* sufficient — on dense markup the old pattern exceeded 10s at
3.6K chars, so any fixed window remained exploitable.

GitHub Issue: https://github.com/dgunning/edgartools/issues/928
"""
import re
import time

import pytest

from edgar import Company
from edgar.documents.cross_reference_index import (
    CrossReferenceIndex,
    detect_cross_reference_index,
)

pytestmark = pytest.mark.regression

# The filing from the report.
REPRO_CIK = 800240
REPRO_ACCESSION = "0000950170-25-027569"

# Generous next to the observed post-fix times (tens of milliseconds on filings
# up to 16MB) and far below the pre-fix behaviour, which did not terminate.
BUDGET_SECONDS = 10.0

# A row that matches the *first* leg of the old pattern and nothing after it —
# the shape that made it backtrack.
_DECOY_ROW = (
    '<tr><td style="x">Item 1A.</td>'
    '<td style="y">Other Heading</td>'
    '<td style="z">text</td></tr>'
)
_HEADING = "<p>FORM 10-K CROSS-REFERENCE INDEX</p>"


def _document(rows: str) -> str:
    return f"<html><body>{_HEADING}<table>{rows}</table></body></html>"


# --- The hang ------------------------------------------------------------------

@pytest.mark.fast
def test_dense_decoy_rows_do_not_hang():
    """Heading present, table shape absent, many partial-prefix rows.

    The old pattern exceeded 10s on 3.6K chars of this markup; this document is
    ~1.8MB of it.
    """
    html = _document(_DECOY_ROW * 20_000)
    assert len(html) > 1_000_000

    start = time.monotonic()
    detected = CrossReferenceIndex(html).has_index()
    elapsed = time.monotonic() - start

    assert detected is False
    assert elapsed < BUDGET_SECONDS, f"has_index() took {elapsed:.1f}s"


@pytest.mark.fast
def test_heading_without_a_table_is_not_an_index():
    """A filing that names the index but has no table must answer False, fast."""
    html = f"<html><body>{_HEADING}<p>{'filler ' * 50_000}</p></body></html>"

    start = time.monotonic()
    detected = CrossReferenceIndex(html).has_index()
    elapsed = time.monotonic() - start

    assert detected is False
    assert elapsed < BUDGET_SECONDS


@pytest.mark.fast
def test_no_heading_short_circuits():
    assert detect_cross_reference_index("<html><body><p>Item 1A. Risk Factors</p></body></html>") is False


# --- Detection still works -----------------------------------------------------

@pytest.mark.fast
def test_real_index_row_still_detected_among_decoys():
    """The fix must not trade the hang for a missed detection."""
    html = _document(
        _DECOY_ROW * 5_000
        + '<tr><td>1A.</td><td>Risk Factors</td><td>26-33</td></tr>'
    )
    assert CrossReferenceIndex(html).has_index() is True


@pytest.mark.fast
def test_item_prefixed_row_detected():
    """Both bare ('1A.') and prefixed ('Item 1A.') numbering — see issue #251."""
    html = _document('<tr><td>Item 1A.</td><td>Risk Factors</td><td>26</td></tr>')
    assert CrossReferenceIndex(html).has_index() is True


@pytest.mark.fast
def test_row_without_pages_is_not_an_index_row():
    """An Item 1A / Risk Factors pair with no page reference is a TOC row, not an index."""
    html = _document('<tr><td>Item 1A.</td><td>Risk Factors</td><td>Not applicable</td></tr>')
    assert CrossReferenceIndex(html).has_index() is False


# --- The reported filing, end to end -------------------------------------------

@pytest.mark.network
def test_repro_filing_detects_quickly():
    filing = {f.accession_no: f for f in Company(REPRO_CIK).get_filings(form="10-K")}[REPRO_ACCESSION]
    html = filing.html()
    assert len(html) > 5_000_000, "expected the multi-MB document from the report"

    # The heading is present — this filing reaches the second probe, which is the
    # only path that hung.
    assert re.search(r'FORM\s+10-K\s+CROSS[- ]?REFERENCE\s+INDEX', html, re.IGNORECASE)

    start = time.monotonic()
    detected = CrossReferenceIndex(html).has_index()
    elapsed = time.monotonic() - start

    assert detected is False
    assert elapsed < BUDGET_SECONDS, f"has_index() took {elapsed:.1f}s"


@pytest.mark.network
def test_repro_filing_item_lookup_returns():
    """``filing['Item 7']`` is the call users reported hanging."""
    filing = {f.accession_no: f for f in Company(REPRO_CIK).get_filings(form="10-K")}[REPRO_ACCESSION]

    start = time.monotonic()
    item_7 = filing.obj()["Item 7"]
    elapsed = time.monotonic() - start

    assert item_7, "Item 7 should resolve"
    assert elapsed < 60.0, f"filing['Item 7'] took {elapsed:.1f}s"


@pytest.mark.network
@pytest.mark.parametrize("ticker", ["GE", "C"])
def test_genuine_cross_reference_filers_still_detected(ticker):
    """GE (issue #215) and Citigroup (issue #251) must keep detecting and parsing."""
    html = Company(ticker).get_filings(form="10-K").latest().html()

    index = CrossReferenceIndex(html)
    assert index.has_index() is True

    entries = index.parse()
    assert "1A" in entries, f"expected Item 1A among {sorted(entries)}"
    assert entries["1A"].pages, "Item 1A should carry page ranges"
