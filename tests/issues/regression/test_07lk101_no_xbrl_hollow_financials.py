"""A filing with no XBRL used to hand back a hollow `Financials`, silently.

Bead: edgartools-07lk.10.1, the first finding of 07lk.10's silent-None sweep.

`Company(104599).get_financials()` returned a `Financials` object — truthy, so
the documented `if financials is not None:` guard passed — whose every accessor
then answered `None`, with no warning at any level. The only signal was a
`log.debug`, which is off for every normal user.

WHERE THE WARNING GOES, AND WHY NOT ONE LEVEL DOWN. `XBRL.from_filing` is the
shared choke point and warning there would have caught every path in one edit.
It is the wrong place: `filing.xbrl()` answering `None` for a filing without
XBRL is a TRUE ABSENCE, and docs/upgrade/6.0.md commits in writing to it staying
quiet in 6.0 — "those are answers, not failures, and that distinction is the
point of the whole change". Asking for financial statements and silently getting
an object that has none is the failure. So `Financials.extract` warns and
`filing.xbrl()` does not, and the tests below pin BOTH halves — the second is
the one a future choke-point refactor would quietly break.

WHAT THESE TESTS PROTECT, in order of how quietly each could break:

  1. **`filing.xbrl()` stays silent.** Nothing about it is asserted anywhere
     else, so moving the warning down to `from_filing` would look like a tidy
     simplification and pass every other test in this file.
  2. **Strict mode actually raises.** `XBRLFilingWithNoXbrlData` was never
     raised ANYWHERE before this change, so the two `except` clauses written
     for it — in `Financials.extract` and in `Filing.xbrl` — were dead code
     that looked like handling. Re-adding one would restore the silent `None`
     under strict while every lenient test still passed, and it would read as
     conscientious error handling to whoever added it.
  3. **The warning dedups.** Its text must not carry the accession number.
     Python's filter compares rendered text, so a per-filing message turns a
     sweep over a company's history into one warning per pre-2009 filing, which
     reads as a broken library. This is the trap `_no_xml_to_parse` already hit.
  4. **Filings WITH XBRL stay silent.** A guard that warned on the healthy path
     would be worse than the bug: it would train users to filter the warning.
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


@pytest.fixture
def strict(monkeypatch):
    monkeypatch.setenv("EDGARTOOLS_STRICT_ERRORS", "1")


@pytest.fixture
def lenient(monkeypatch):
    monkeypatch.delenv("EDGARTOOLS_STRICT_ERRORS", raising=False)


class _Filing:
    """The smallest thing `no_xbrl_attachments` reads."""
    form = "10-K"
    accession_no = "0001193125-08-093063"


# --------------------------------------------------------------------------
# The error value itself — offline
# --------------------------------------------------------------------------

def test_error_is_built_not_raised():
    """The helper returns the error as a value, so warn_will_raise can decide."""
    assert isinstance(no_xbrl_attachments(_Filing()), XBRLFilingWithNoXbrlData)


def test_error_message_names_the_filing():
    """The copy a user debugs against identifies WHICH filing."""
    error = no_xbrl_attachments(_Filing())
    assert "0001193125-08-093063" in str(error)
    assert "10-K" in str(error)


def test_warning_summary_is_dedup_stable():
    """The warning text must NOT vary per filing.

    Python suppresses a repeat only on an exact text match, so an accession
    number here turns a corpus loop into one warning per filing.
    """
    error = no_xbrl_attachments(_Filing())
    assert error.warning_summary is not None
    assert "0001193125-08-093063" not in error.warning_summary
    # Still has to say what happened, not merely that something did.
    assert "no XBRL" in error.warning_summary


def test_warning_summary_explains_that_this_is_the_filing_not_the_form():
    """A user seeing this on a 10-K must not conclude 10-Ks are unsupported."""
    assert "property of the filing" in no_xbrl_attachments(_Filing()).warning_summary


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
def test_filing_xbrl_stays_silent(lenient):
    """`filing.xbrl()` answering None is a true absence and must NOT warn.

    docs/upgrade/6.0.md commits to this staying quiet in 6.0. Moving the
    warning down to `XBRL.from_filing` would break this and nothing else.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = Filing(**CIRCUIT_CITY_10K).xbrl()
    assert result is None
    assert not [w for w in caught if issubclass(w.category, FutureWarning)]


@pytest.mark.network
def test_filing_xbrl_stays_silent_under_strict(strict):
    """Not even strict mode makes `filing.xbrl()` raise — it is not a failure."""
    assert Filing(**CIRCUIT_CITY_10K).xbrl() is None


@pytest.mark.network
def test_financials_extract_warns(lenient):
    """The ground truth: asking for statements that cannot exist says so."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        Financials.extract(Filing(**CIRCUIT_CITY_10K))
    messages = [str(w.message) for w in caught if issubclass(w.category, FutureWarning)]
    assert messages, "a filing with no XBRL must not go quiet"
    # The warning names what to catch, so the reader does not have to go find out.
    assert "XBRLFilingWithNoXbrlData" in messages[0]


@pytest.mark.network
def test_financials_still_returns_the_hollow_object_in_5x(lenient):
    """5.x behaviour is UNCHANGED apart from the warning.

    Removing the hollow object is the breaking half and lands in 6.0. Staging
    the warning without the flip is the whole point of edgartools-07lk.23.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        financials = Financials.extract(Filing(**CIRCUIT_CITY_10K))
    assert financials is not None
    assert financials.income_statement() is None
    assert financials.balance_sheet() is None
    assert financials.cash_flow_statement() is None


@pytest.mark.network
def test_strict_mode_raises_through_financials_extract(strict):
    """Under strict the error reaches the caller — the 6.0 behaviour."""
    with pytest.raises(XBRLFilingWithNoXbrlData):
        Financials.extract(Filing(**CIRCUIT_CITY_10K))


@pytest.mark.network
def test_strict_mode_raises_through_get_financials(strict):
    """The whole point: the public entry point users actually call."""
    from edgar import Company

    with pytest.raises(XBRLFilingWithNoXbrlData):
        Company(104599).get_financials()


@pytest.mark.network
def test_repeated_calls_warn_once(lenient):
    """A sweep over many pre-2009 filings must not emit one warning per filing."""
    filing = Filing(**CIRCUIT_CITY_10K)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("default")  # Python's real default filter
        for _ in range(5):
            Financials.extract(filing)
    assert len([w for w in caught if issubclass(w.category, FutureWarning)]) == 1


@pytest.mark.network
def test_filing_with_xbrl_is_untouched_and_silent(lenient):
    """The healthy path must not warn — a warning here would train users to filter it."""
    from edgar import Company

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        financials = Company("AAPL").get_financials()
        income = financials.income_statement()
    assert income is not None
    assert not [w for w in caught if issubclass(w.category, FutureWarning)]
