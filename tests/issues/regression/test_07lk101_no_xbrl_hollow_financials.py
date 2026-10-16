"""A filing with no XBRL used to hand back a hollow `Financials`, silently.

Bead: edgartools-07lk.10.1, the first finding of 07lk.10's silent-None sweep.

`Company(104599).get_financials()` returned a `Financials` object — truthy, so
the documented `if financials is not None:` guard passed — whose every accessor
then answered `None`. 5.x warned that 6.0 would raise `XBRLFilingWithNoXbrlData`.

6.0 returns `None` instead, for every form. No XBRL is a property of the filing
(filings from before SEC's 2009-2011 phase-in have none, and a 6-K or 8-K need
not carry statements), which is the same reason `filing.xbrl()` answers `None`.
What was broken was the hollow object that looked like data, and `None` makes
the documented guard correct.

WHAT THESE TESTS PROTECT:

  1. **No hollow object.** `Financials.extract`, `report.financials` and
     `get_financials()` answer `None`, never a `Financials` wrapping `xb=None`.
  2. **No raise.** `XBRLFilingWithNoXbrlData` stays defined but nothing raises
     it; the AST guard below keeps a dead `except` for it from coming back.
  3. **Filings WITH XBRL are untouched.**
"""
import warnings

import pytest

from edgar import Filing
from edgar.financials import Financials
from edgar.xbrl.xbrl import XBRL

# Circuit City stopped filing in 2009, so its LATEST 10-K predates SEC's
# 2009-2011 XBRL phase-in. That makes it reachable through get_financials()
# with no historical-filing gymnastics — the exact shape a user hits.
CIRCUIT_CITY_10K = dict(
    form="10-K",
    filing_date="2008-04-28",
    company="CIRCUIT CITY STORES INC",
    cik=104599,
    accession_no="0001193125-08-093063",
)


class _Filing:
    form = "10-K"
    accession_no = "0001193125-08-093063"


@pytest.fixture
def no_xbrl(monkeypatch):
    monkeypatch.setattr(XBRL, "from_filing", classmethod(lambda cls, filing: None))


# --------------------------------------------------------------------------
# Offline
# --------------------------------------------------------------------------

def test_extract_answers_none_not_a_hollow_object(no_xbrl):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert Financials.extract(_Filing()) is None


def test_six_k_financials_is_none_without_xbrl(no_xbrl):
    """ASML's 6-K 0001628280-26-065813 is one: most 6-Ks carry no XBRL."""
    from edgar.company_reports import SixK

    report = object.__new__(SixK)
    report._filing = _Filing()
    report._filing.form = "6-K"
    assert report.financials is None


def test_get_quarterly_financials_is_none_when_the_6k_has_no_xbrl(no_xbrl):
    from edgar.entity import core

    class _Filings:
        def latest(self):
            filing = _Filing()
            filing.form = "6-K"
            return filing

    class _ForeignFiler:
        latest_tenq = None

        def get_filings(self, **kwargs):
            assert kwargs["form"] == "6-K"
            return _Filings()

    assert core.Company.get_quarterly_financials(_ForeignFiler()) is None


# --------------------------------------------------------------------------
# The dead handlers — offline, via AST
# --------------------------------------------------------------------------

def _caught_exception_names(func) -> set:
    """Names in this function's `except` clauses, via AST rather than text.

    Grepping the source is what a first pass does and it is wrong here: a
    comment explaining why a function does NOT catch this error would match.
    """
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is not None:
            for sub in ast.walk(node.type):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
                elif isinstance(sub, ast.Attribute):
                    names.add(sub.attr)
    return names


def test_the_dead_handlers_stay_dead():
    """Nothing raises XBRLFilingWithNoXbrlData, so nothing may catch it."""
    from edgar import _filings

    assert "XBRLFilingWithNoXbrlData" not in _caught_exception_names(_filings.Filing.xbrl)
    assert "XBRLFilingWithNoXbrlData" not in _caught_exception_names(Financials.extract)


def test_the_handler_probe_can_actually_see_a_handler():
    """Mutation probe: the guard above must fail when a handler IS present."""
    from edgar.xbrl.xbrl import XBRLFilingWithNoXbrlData

    def _with_handler():
        try:
            pass
        except XBRLFilingWithNoXbrlData:
            return None

    assert "XBRLFilingWithNoXbrlData" in _caught_exception_names(_with_handler)


# --------------------------------------------------------------------------
# Behaviour against the real filing
# --------------------------------------------------------------------------

@pytest.mark.network
def test_filing_xbrl_is_none():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert Filing(**CIRCUIT_CITY_10K).xbrl() is None


@pytest.mark.network
def test_financials_extract_is_none():
    """The ground truth: a 2008 10-K has no statements to read."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        assert Financials.extract(Filing(**CIRCUIT_CITY_10K)) is None


@pytest.mark.network
def test_get_financials_is_none():
    """The public entry point users actually call, and the guard it documents."""
    from edgar import Company

    assert Company(104599).get_financials() is None


@pytest.mark.network
def test_filing_with_xbrl_is_untouched():
    """Apple's FY2023 10-K (0000320193-23-000106): revenue $383,285M."""
    filing = Filing(form="10-K", filing_date="2023-11-03", company="Apple Inc.",
                    cik=320193, accession_no="0000320193-23-000106")
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        financials = Financials.extract(filing)
    assert financials.get_revenue() == 383_285_000_000
