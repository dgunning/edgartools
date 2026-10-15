"""A filing with no XBRL used to hand back a hollow `Financials`, silently.

Bead: edgartools-07lk.10.1, the first finding of 07lk.10's silent-None sweep.

`Company(104599).get_financials()` returned a `Financials` object — truthy, so
the documented `if financials is not None:` guard passed — whose every accessor
then answered `None`, with no warning at any level. The only signal was a
`log.debug`, which is off for every normal user.

5.x warned there; since 6.0 `Financials.extract` raises `XBRLFilingWithNoXbrlData`.

WHERE THE ERROR GOES, AND WHY NOT ONE LEVEL DOWN. `XBRL.from_filing` is the
shared choke point and raising there would have caught every path in one edit.
It is the wrong place: `filing.xbrl()` answering `None` for a filing without
XBRL is a TRUE ABSENCE, and docs/upgrade/6.0.md commits in writing to it staying
quiet in 6.0 — "those are answers, not failures, and that distinction is the
point of the whole change". Asking for financial statements and getting an
object that has none is the failure. So `Financials.extract` raises and
`filing.xbrl()` does not, and the tests below pin BOTH halves — the second is
the one a future choke-point refactor would quietly break.

WHAT THESE TESTS PROTECT, in order of how quietly each could break:

  1. **`filing.xbrl()` stays silent.** Nothing about it is asserted anywhere
     else, so moving the warning down to `from_filing` would look like a tidy
     simplification and pass every other test in this file.
  2. **It actually raises.** `XBRLFilingWithNoXbrlData` was never raised
     ANYWHERE before 07lk.10.1, so the two `except` clauses written for it —
     in `Financials.extract` and in `Filing.xbrl` — were dead code that looked
     like handling. Re-adding one would restore the silent `None`, and it would
     read as conscientious error handling to whoever added it.
  3. **Filings WITH XBRL are untouched.**
"""
import warnings

import pytest

from edgar import Filing
from edgar.financials import Financials
from edgar.xbrl.xbrl import XBRLFilingWithNoXbrlData, no_xbrl_attachments

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
    """The smallest thing `no_xbrl_attachments` reads."""
    form = "10-K"
    accession_no = "0001193125-08-093063"


# --------------------------------------------------------------------------
# The error value itself — offline
# --------------------------------------------------------------------------

def test_error_is_built_not_raised():
    """The helper returns the error as a value; `Financials.extract` raises it."""
    assert isinstance(no_xbrl_attachments(_Filing()), XBRLFilingWithNoXbrlData)


def test_error_message_names_the_filing():
    """The copy a user debugs against identifies WHICH filing."""
    error = no_xbrl_attachments(_Filing())
    assert "0001193125-08-093063" in str(error)
    assert "10-K" in str(error)


def test_error_explains_that_this_is_the_filing_not_the_form():
    """A user seeing this on a 10-K must not conclude 10-Ks are unsupported."""
    assert "property of the filing" in str(no_xbrl_attachments(_Filing()))


# --------------------------------------------------------------------------
# The dead handlers — offline, via AST
# --------------------------------------------------------------------------

def _caught_exception_names(func) -> set:
    """Names in this function's `except` clauses, via AST rather than text.

    Grepping the source is what a first pass does and it is wrong here: both
    functions carry a comment explaining why they do NOT catch this error, so a
    text match reports the handler it is meant to prove absent.
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
    """Neither call site may catch XBRLFilingWithNoXbrlData again."""
    from edgar import _filings

    assert "XBRLFilingWithNoXbrlData" not in _caught_exception_names(_filings.Filing.xbrl)
    assert "XBRLFilingWithNoXbrlData" not in _caught_exception_names(Financials.extract)


def test_the_handler_probe_can_actually_see_a_handler():
    """Mutation probe: the guard above must fail when a handler IS present.

    Without this, `_caught_exception_names` returning an empty set for any
    reason would make the guard vacuously pass forever.
    """
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
def test_filing_xbrl_stays_silent():
    """`filing.xbrl()` answering None is a true absence: no raise, no warning.

    docs/upgrade/6.0.md commits to this. Moving the error down to
    `XBRL.from_filing` would break this and nothing else.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert Filing(**CIRCUIT_CITY_10K).xbrl() is None


@pytest.mark.network
def test_financials_extract_raises():
    """The ground truth: asking for statements that cannot exist says so."""
    with pytest.raises(XBRLFilingWithNoXbrlData, match="0001193125-08-093063"):
        Financials.extract(Filing(**CIRCUIT_CITY_10K))


@pytest.mark.network
def test_get_financials_raises():
    """The public entry point users actually call."""
    from edgar import Company

    with pytest.raises(XBRLFilingWithNoXbrlData):
        Company(104599).get_financials()


@pytest.mark.network
def test_filing_with_xbrl_is_untouched():
    """Apple's FY2023 10-K (0000320193-23-000106): revenue $383,285M."""
    filing = Filing(form="10-K", filing_date="2023-11-03", company="Apple Inc.",
                    cik=320193, accession_no="0000320193-23-000106")
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        financials = Financials.extract(filing)
    assert financials.get_revenue() == 383_285_000_000
