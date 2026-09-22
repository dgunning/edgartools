"""`FortyF["No Such Section"]` announces the miss instead of answering None.

Bead: edgartools-sx7y

`CompanyReport.__getitem__` ends with `report_lookup_miss(...)` before returning
None, so asking for an item a filing does not have warns today and raises
`SectionNotFoundError` under `EDGARTOOLS_STRICT_ERRORS` -- which is what 6.0
ships. Three subclasses overrode `__getitem__`, reimplemented the miss path and
dropped that call: TwentyF, CurrentReport and FortyF. All three returned a
silent None in both error modes.

TwentyF and CurrentReport are pinned OFFLINE against the committed fixture
corpus in `test_3dp_groupb_fixture_corpus.py`, so they gate every pull request.
There is no 40-F in that corpus, so FortyF is pinned here against a real filing
and marked `network` -- deliberately, rather than letting it ride in the `fast`
lane, because `test-strict-errors` runs that lane and exists to check 6.0 error
behaviour "without a second pass over the SEC endpoint".

Those behavioural tests pin the five report types that exist today. A SIXTH
would slip straight through them, which is the failure this bug already
demonstrated three times, so `test_every_getitem_override_announces_a_miss`
below guards the shape rather than the behaviour: it walks the CompanyReport
subclasses and refuses any override of `__getitem__` that never reaches
`report_lookup_miss`.

The three were independent mistakes with one cause: the base class's
`report_lookup_miss` call is invisible at the override site, so every
reimplementation of the miss path dropped it. That is why this asserts against
the real class rather than grepping the source for the call.
"""
import ast
import importlib
import inspect
import pkgutil
import textwrap
import warnings
from contextlib import contextmanager

import pytest

import edgar.company_reports
from edgar import Filing
from edgar.company_reports._base import CompanyReport, report_lookup_miss
from edgar.exceptions import SectionNotFoundError

# Avino Silver & Gold's 2023 40-F. "Nonexistent Section" is absent by
# construction rather than by drift -- no AIF carries a section by that name.
FORTY_F = dict(form='40-F', filing_date='2024-03-27',
               company='AVINO SILVER & GOLD MINES LTD', cik=1011509,
               accession_no='0001477932-24-001577')
MISSING = "Nonexistent Section"


@pytest.fixture
def strict(monkeypatch):
    monkeypatch.setenv("EDGARTOOLS_STRICT_ERRORS", "1")


@pytest.fixture
def lenient(monkeypatch):
    monkeypatch.delenv("EDGARTOOLS_STRICT_ERRORS", raising=False)


@contextmanager
def _no_warnings():
    """Record warnings without making their ABSENCE the failure.

    `pytest.warns` asserts that something was warned and has no negative form,
    and `filterwarnings("error")` would fail on the first unrelated warning the
    parser emits.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        yield caught


@pytest.mark.network
def test_a_missing_forty_f_section_warns_today(lenient):
    """The user is told what 6.0 will do, rather than getting a bare None."""
    report = Filing(**FORTY_F).obj()

    with pytest.warns(FutureWarning, match="raises SectionNotFoundError in edgartools 6.0"):
        assert report[MISSING] is None


@pytest.mark.network
def test_a_missing_forty_f_section_raises_under_strict(strict):
    """Under the 6.0 error behaviour the same lookup raises."""
    report = Filing(**FORTY_F).obj()

    with pytest.raises(SectionNotFoundError, match=MISSING):
        report[MISSING]


@pytest.mark.network
def test_get_stays_silent_in_both_modes(monkeypatch):
    """`.get()` is the migration target, so it must neither warn nor raise.

    The mechanism is a ContextVar set by `CompanyReport.get()` and read inside
    `report_lookup_miss`; an override that calls the helper inherits the
    silence. Asserted in both modes because a subclass that also overrode
    `.get()` would break it in only one.
    """
    for strict_mode in (False, True):
        if strict_mode:
            monkeypatch.setenv("EDGARTOOLS_STRICT_ERRORS", "1")
        else:
            monkeypatch.delenv("EDGARTOOLS_STRICT_ERRORS", raising=False)

        report = Filing(**FORTY_F).obj()
        with _no_warnings() as caught:
            assert report.get(MISSING, "DEFAULT") == "DEFAULT"

        assert not [w for w in caught if issubclass(w.category, FutureWarning)], (
            f".get() warned with strict={strict_mode}; it promises a default, "
            f"so it stays quiet in both modes"
        )


def _all_report_subclasses():
    """Every CompanyReport subclass, importing the package so none hides.

    `__subclasses__()` only sees classes that have been imported, and report
    types are lazily imported by `obj()` dispatch. Importing every module in
    `edgar.company_reports` first means a new report type is discovered whether
    or not anything has touched it yet.
    """
    for mod in pkgutil.iter_modules(edgar.company_reports.__path__):
        importlib.import_module(f"edgar.company_reports.{mod.name}")

    seen = []

    def walk(cls):
        for sub in cls.__subclasses__():
            if sub not in seen:
                seen.append(sub)
                walk(sub)

    walk(CompanyReport)
    return seen


def _reaches_the_miss(method) -> bool:
    """True if this __getitem__ calls report_lookup_miss, or defers to the base."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(method)))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # report_lookup_miss(...)
        if isinstance(func, ast.Name) and func.id == "report_lookup_miss":
            return True
        # super().__getitem__(...) -- the base announces on our behalf
        if (isinstance(func, ast.Attribute) and func.attr == "__getitem__"
                and isinstance(func.value, ast.Call)
                and isinstance(func.value.func, ast.Name)
                and func.value.func.id == "super"):
            return True
    return False


def test_every_getitem_override_announces_a_miss():
    """A report type that overrides __getitem__ must still announce a miss.

    `CompanyReport.__getitem__` calls `report_lookup_miss` before returning
    None, so `report[item]` on an absent item warns today and raises under
    EDGARTOOLS_STRICT_ERRORS. That call is invisible at the override site, and
    three subclasses reimplemented the miss path without it -- independently,
    which is what makes this worth guarding rather than remembering.

    This is a STRUCTURAL check and deliberately a weak one: it proves the call
    is present in the source, not that every miss path reaches it. FortyF needs
    TWO call sites and this test would pass with one. The behavioural tests
    above and in test_3dp_groupb_fixture_corpus.py are what prove reachability
    for the types that exist; this exists to catch the SIXTH type, which those
    tests would never mention.

    If this fails on a class you just wrote: call `report_lookup_miss(self,
    key)` immediately before each `return None` that means "this filing has no
    such item" -- and NOT before one that means the caller passed nonsense,
    which is a different failure (see FortyF's empty-key branch).
    """
    offenders = [
        cls.__name__
        for cls in _all_report_subclasses()
        if "__getitem__" in cls.__dict__ and not _reaches_the_miss(cls.__getitem__)
    ]

    assert not offenders, (
        f"Overrides __getitem__ without ever reaching report_lookup_miss: "
        f"{', '.join(offenders)}. A lookup for an absent item answers None in "
        f"silence there -- no FutureWarning today, and no SectionNotFoundError "
        f"under EDGARTOOLS_STRICT_ERRORS, so report[item] will not raise in 6.0 "
        f"for that form. See edgartools-sx7y."
    )


def test_the_guard_can_actually_fail():
    """The guard above must reject a class that forgets, or it guards nothing.

    A structural test that only ever sees correct code proves nothing about
    what it would do with incorrect code -- so this hands it exactly the shape
    the three real subclasses had.
    """
    class ForgetfulReport(CompanyReport):
        def __getitem__(self, item_or_part: str):
            section = self.document.sections.get(item_or_part)
            if section:
                return section.text()
            return None            # no report_lookup_miss -- the sx7y bug

    class CorrectReport(CompanyReport):
        def __getitem__(self, item_or_part: str):
            section = self.document.sections.get(item_or_part)
            if section:
                return section.text()
            report_lookup_miss(self, item_or_part)
            return None

    class DeferringReport(CompanyReport):
        def __getitem__(self, item_or_part: str):
            return super().__getitem__(item_or_part)

    assert not _reaches_the_miss(ForgetfulReport.__getitem__)
    assert _reaches_the_miss(CorrectReport.__getitem__)
    assert _reaches_the_miss(DeferringReport.__getitem__), (
        "deferring to the base is a legitimate way to announce a miss"
    )
