"""
Regression test for beads issue edgartools-83gh: EightK API consistency.

Two defects, both forcing downstream consumers (edgar-storage material_events /
cyber_incidents) to write defensive fallbacks:

1. ``EightK.items`` under-reported present items. The new HTML parser could
   silently miss an item whose body is clearly in the document — e.g. Bitcoin
   Depot's 2026-04-08 8-K lists only Item 9.01 in the parsed sections but carries
   a full Item 1.05 (Material Cybersecurity Incident) body. ``.items`` trusted the
   partial parser result and returned early. Fixed by unioning the new-parser
   sections with the chunked parser (both read the primary document, so no
   exhibit-text false positives).

   The accompanying ``__getitem__`` accessor also returned the chunked parser's
   ``None`` for an unmatched key format (e.g. ``'1.05'`` when it indexes by
   ``'Item 1.05'``), short-circuiting the text-based fallback. Fixed so an item in
   ``.items`` is always retrievable via ``eightk['1.05']`` or ``eightk['Item 1.05']``.

2. ``EightK.date_of_report`` returned a mix of ``datetime.date`` and formatted
   strings. It now always returns a ``datetime.date`` (or ``None`` when absent).
"""
from datetime import date

import pytest

from edgar import Company, Filing
from edgar.company_reports import EightK


@pytest.mark.network
def test_items_includes_item_105_not_in_parser_sections():
    """Item 1.05 body is present but missed by the section parser — .items must still list it."""
    filing = Company('BTM').get_filings(form='8-K').filter(date='2026-04-08')[0]
    eightk = filing.obj()
    assert isinstance(eightk, EightK)

    items = eightk.items
    assert 'Item 1.05' in items, f"Item 1.05 (cybersecurity) missing from {items}"
    assert 'Item 9.01' in items, f"Item 9.01 missing from {items}"
    # Ordering is numeric, not lexical
    assert items == ['Item 1.05', 'Item 9.01']


@pytest.mark.network
def test_item_105_accessible_via_both_key_formats():
    """Consistency contract: every item in .items is retrievable via __getitem__."""
    filing = Company('BTM').get_filings(form='8-K').filter(date='2026-04-08')[0]
    eightk = filing.obj()

    for key in ('1.05', 'Item 1.05'):
        content = eightk[key]
        assert content, f"eightk[{key!r}] returned no content"
        assert 'Cybersecurity' in content, f"unexpected content for {key!r}: {content[:80]!r}"

    # Every reported item must be accessible (the documented consistency contract)
    for item in eightk.items:
        assert eightk[item], f"{item} is in .items but not accessible via eightk[{item!r}]"


@pytest.mark.network
def test_date_of_report_is_always_a_date():
    """date_of_report returns datetime.date, never a formatted string."""
    # Modern filing
    filing = Company('BTM').get_filings(form='8-K').filter(date='2026-04-08')[0]
    eightk = filing.obj()
    assert isinstance(eightk.date_of_report, date)
    assert eightk.date_of_report == date(2026, 4, 6)

    # Legacy 1995 filing — same type, no string formats
    legacy = Filing(form='8-K', filing_date='1995-01-24', company='AMERICAN EXPRESS CO',
                    cik=4962, accession_no='0000004962-95-000001')
    eightk_legacy = legacy.obj()
    assert isinstance(eightk_legacy.date_of_report, date)
    assert eightk_legacy.date_of_report == date(1995, 1, 23)


def test_parse_period_of_report_normalizes_mixed_types():
    """The helper accepts ISO strings, date/datetime objects, and human formats; None when absent."""
    from datetime import datetime

    from edgar.company_reports.current_report import _parse_period_of_report

    assert _parse_period_of_report('2024-12-20') == date(2024, 12, 20)
    assert _parse_period_of_report('December 20, 2024') == date(2024, 12, 20)
    assert _parse_period_of_report('Dec 20, 2024') == date(2024, 12, 20)
    assert _parse_period_of_report(date(2024, 12, 20)) == date(2024, 12, 20)
    assert _parse_period_of_report(datetime(2024, 12, 20, 9, 30)) == date(2024, 12, 20)
    # Silence check: missing / unparseable input yields None, not a misleading value
    assert _parse_period_of_report('') is None
    assert _parse_period_of_report(None) is None
    assert _parse_period_of_report('not a date') is None
