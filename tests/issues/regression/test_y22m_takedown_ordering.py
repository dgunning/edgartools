"""Regression test for edgartools-y22m.

ShelfLifecycle.takedowns must be chronological (ascending filing_date)
regardless of the order _related arrives in, because avg_days_between_takedowns,
days_since_last_takedown, and the takedown-based expiry bound all assume it.

Repro from the bead: Atento F-3 file 333-220065 has 424B4s on 2017-11-13 and
2017-11-06; a newest-first _related yielded avg_days == -7.0 and read the oldest
takedown as "most recent".
"""
from __future__ import annotations

from datetime import date

from edgar.offerings.prospectus import ShelfLifecycle


class _FakeFiling:
    def __init__(self, form, filing_date, accession_no):
        self.form = form
        self.filing_date = filing_date
        self.accession_no = accession_no

    def related_filings(self):
        return None


class _FakeFilings:
    def __init__(self, items):
        self._items = items
        self.empty = not items

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, i):
        return self._items[i]


def _atento_lifecycle_newest_first():
    # _related deliberately in descending (newest-first) order.
    related = [
        _FakeFiling("424B4", "2017-11-13", "acc-late"),
        _FakeFiling("424B4", "2017-11-06", "acc-early"),
        _FakeFiling("F-3", "2017-08-18", "acc-base"),
    ]
    return ShelfLifecycle(related[0], _FakeFilings(related))


def test_takedowns_returned_chronologically():
    lc = _atento_lifecycle_newest_first()
    dates = [f.filing_date for f in lc.takedowns]
    assert dates == ["2017-11-06", "2017-11-13"]  # ascending, not _related order


def test_avg_days_between_takedowns_is_positive():
    lc = _atento_lifecycle_newest_first()
    assert lc.avg_days_between_takedowns == 7.0  # was -7.0 before the fix


def test_days_since_last_takedown_uses_most_recent():
    lc = _atento_lifecycle_newest_first()
    # Must measure from the newest takedown (2017-11-13), not the oldest.
    expected = (date.today() - date(2017, 11, 13)).days
    assert lc.days_since_last_takedown == expected
