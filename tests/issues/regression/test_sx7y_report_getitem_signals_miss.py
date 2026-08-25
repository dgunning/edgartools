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

The three were independent mistakes with one cause: the base class's
`report_lookup_miss` call is invisible at the override site, so every
reimplementation of the miss path dropped it. That is why this asserts against
the real class rather than grepping the source for the call.
"""
import warnings
from contextlib import contextmanager

import pytest

from edgar import Filing
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
