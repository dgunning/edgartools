"""
Regression test for edgartools-6k96: XBRLS.from_filings([list], filter_amendments=True) crash.

The signature accepts ``Union[Filings, List[Filing]]`` and defaults
``filter_amendments=True``, but the implementation called ``filings.filter()``
unconditionally — which raised ``AttributeError`` when a plain list was passed.

The fix branches on whether the input has a ``.filter`` method, falling back to
a form-suffix filter for lists.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from edgar.xbrl.stitching import XBRLS


def _mock_filing(form: str, filing_date: str = "2024-01-01"):
    """Build a Filing-like mock that XBRLS.from_filings will consume."""
    f = MagicMock()
    f.form = form
    f.filing_date = filing_date
    return f


def test_from_filings_list_with_default_filter_amendments_does_not_crash(monkeypatch):
    """A plain list with the default filter_amendments=True must not crash."""
    # Stub XBRL.from_filing so we don't need real network/SGML access.
    fake_xbrl_calls = []

    def fake_from_filing(filing):
        fake_xbrl_calls.append(filing.form)
        return MagicMock()

    monkeypatch.setattr("edgar.xbrl.xbrl.XBRL.from_filing", fake_from_filing)

    filings = [
        _mock_filing("10-K", "2024-02-01"),
        _mock_filing("10-K/A", "2024-03-01"),  # amendment, must be dropped
        _mock_filing("10-K", "2023-02-01"),
    ]

    xbrls = XBRLS.from_filings(filings)  # default filter_amendments=True

    assert xbrls is not None
    # Amendment was filtered out
    assert "10-K/A" not in fake_xbrl_calls
    # Both non-amendments survived
    assert fake_xbrl_calls.count("10-K") == 2


def test_from_filings_list_with_filter_amendments_false_keeps_amendments(monkeypatch):
    """filter_amendments=False is the existing workaround — keep working."""
    fake_xbrl_calls = []

    def fake_from_filing(filing):
        fake_xbrl_calls.append(filing.form)
        return MagicMock()

    monkeypatch.setattr("edgar.xbrl.xbrl.XBRL.from_filing", fake_from_filing)

    filings = [
        _mock_filing("10-K", "2024-02-01"),
        _mock_filing("10-K/A", "2024-03-01"),
    ]

    XBRLS.from_filings(filings, filter_amendments=False)

    # Both kept
    assert sorted(fake_xbrl_calls) == ["10-K", "10-K/A"]


def test_from_filings_list_drops_amendments_for_all_form_types(monkeypatch):
    """Form-suffix /A check should work for any base form, not just 10-K."""
    fake_xbrl_calls = []

    def fake_from_filing(filing):
        fake_xbrl_calls.append(filing.form)
        return MagicMock()

    monkeypatch.setattr("edgar.xbrl.xbrl.XBRL.from_filing", fake_from_filing)

    filings = [
        _mock_filing("10-Q", "2024-05-01"),
        _mock_filing("10-Q/A", "2024-06-01"),
        _mock_filing("8-K", "2024-07-01"),
        _mock_filing("8-K/A", "2024-08-01"),
    ]

    XBRLS.from_filings(filings)  # default

    assert "/A" not in " ".join(fake_xbrl_calls)
    assert sorted(fake_xbrl_calls) == ["10-Q", "8-K"]


def test_from_filings_filings_object_path_unchanged(monkeypatch):
    """A Filings-like object with .filter() must still take that path."""
    filter_calls = []

    class FakeFilings:
        def __init__(self, filings):
            self._filings = filings

        def filter(self, **kwargs):
            filter_calls.append(kwargs)
            return [f for f in self._filings if not (f.form or "").endswith("/A")]

    fake_xbrl_calls = []

    def fake_from_filing(filing):
        fake_xbrl_calls.append(filing.form)
        return MagicMock()

    monkeypatch.setattr("edgar.xbrl.xbrl.XBRL.from_filing", fake_from_filing)

    fobj = FakeFilings([_mock_filing("10-K"), _mock_filing("10-K/A")])
    XBRLS.from_filings(fobj)

    # The Filings.filter path was used (preserves prior behavior)
    assert filter_calls == [{"amendments": False}]
    assert fake_xbrl_calls == ["10-K"]
