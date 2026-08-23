"""FilingHomepage.get_filers() actually returns filers (edgartools-jrmw).

It returned ``[]`` for every filing from 2024-05-28 until this fix.
``attachments.py`` searched ``find_all("div", id="filerDiv")`` while SEC emits
``<div class="filerDiv">`` -- id versus class -- so the selector matched nothing
and the method returned before reaching any of its body. ``git log -S`` shows
the line was wrong when it was introduced, so this is not SEC markup drift.

WHY THIS MATTERED MORE THAN AN EMPTY LIST. Roughly 35 lines sit below that
selector -- the companyName parse, the CIK split, the identInfo <br>-to-newline
replacement, the mailer address cleanup -- and none of them had ever executed on
real input. ``FilingHomepage.__rich__`` also renders the filer panel from this
list, so the homepage display was silently missing it.

The bug was found while building fixtures for the bs4->lxml port of this file
(edgartools-07lk.11.5). Porting first would have been worse than useless: a
characterization baseline taken then would have recorded ``[]`` as correct and
pinned the bug, and the never-executed block would have been translated with no
working output to check the translation against.

ASSERTIONS ARE GROUND TRUTH, not shape checks. Each value below was read off the
filing's own index page. A test that only asserted ``len(filers) > 0`` would
pass on a selector that matched the wrong div.
"""
import pathlib

import pytest
from bs4 import BeautifulSoup

from edgar.attachments import Attachments, FilingHomepage

pytestmark = pytest.mark.fast

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures" / "homepages"


def _homepage(stem: str) -> FilingHomepage:
    path = FIXTURES / f"{stem}.html"
    assert path.exists(), f"missing fixture {path}"
    soup = BeautifulSoup(path.read_text(), "html.parser")
    return FilingHomepage(f"file://{path}", soup, Attachments.load(soup))


def test_the_fixture_corpus_is_present():
    """These are the only coverage this code path has; a glob miss must be loud."""
    assert len({p.stem for p in FIXTURES.glob("*.html")}) >= 5


@pytest.mark.parametrize("stem", [
    "aapl-10k-2024", "eightk-2005", "form4-reporting-owner",
    "s4-multifiler", "thirteenf-2023",
])
def test_every_filing_reports_at_least_one_filer(stem):
    """The bug, stated directly: this was [] on all five."""
    assert _homepage(stem).get_filers()


def test_an_ordinary_filing_reports_its_filer():
    filer, = _homepage("aapl-10k-2024").get_filers()

    assert filer.company_name == "Apple Inc."
    assert filer.cik == "0000320193"
    assert "EIN.: 942404110" in filer.identification
    assert "State of Incorp.: CA" in filer.identification


def test_identification_keeps_the_line_breaks_the_filer_wrote():
    """The <br>-to-newline replacement, which had never run on real input.

    Asserted as separate lines rather than as a substring of the whole blob: the
    failure mode of a bad <br> translation is not missing text, it is text glued
    together across the break -- the word-boundary family that has bitten this
    codebase repeatedly. A substring check on 'Type: 10-K' passes either way.
    """
    filer, = _homepage("aapl-10k-2024").get_filers()
    lines = filer.identification.split("\n")

    assert len(lines) >= 3, filer.identification
    assert lines[0].startswith("EIN.:")
    assert any(line.startswith("Type: 10-K") for line in lines), lines
    assert any(line.startswith("SIC: 3571") for line in lines), lines
    # Nothing glued: no line should carry two fields that belong on separate ones.
    assert not any("Fiscal Year End" in line and "Type:" in line for line in lines)


def test_a_form4_reports_both_the_issuer_and_the_reporting_owner():
    """Two filerDivs, and the reason the count matters."""
    filers = _homepage("form4-reporting-owner").get_filers()

    assert len(filers) == 2
    issuer, owner = filers
    assert issuer.company_name == "UFP TECHNOLOGIES INC"
    assert issuer.cik == "0000914156"
    assert owner.company_name == "Hassett Joseph"
    assert owner.cik == "0001641388"


def test_the_role_suffix_is_stripped_whether_sec_links_it_or_not():
    """The half-fix that was already in the code.

    SEC renders an ordinary filer's role as plain text -- "Apple Inc. (Filer)" --
    but a Form 4's roles as links: "UFP TECHNOLOGIES INC (<a>Issuer</a>)". Both
    reach .text identically, so the old ``.replace("(Filer)", "")`` stripped one
    spelling and left the others, making company_name inconsistent by form type.
    Fixed here rather than later because this method has never returned data, so
    there is no caller yet to break -- once one exists, the wart is permanent.
    """
    names = [f.company_name for stem in
             ("aapl-10k-2024", "eightk-2005", "form4-reporting-owner",
              "s4-multifiler", "thirteenf-2023")
             for f in _homepage(stem).get_filers()]

    assert names, "no filers parsed at all"
    for name in names:
        assert not name.endswith(")"), f"{name!r} kept its role suffix"


def test_a_company_name_containing_parentheses_would_survive():
    """The risk the role-stripping regex takes on.

    Anchored to the end AND limited to known role words, so a real name like
    'Acme (Holdings) Inc.' is untouched. Guarded directly because no fixture
    happens to have such a name, and a looser regex would pass every other test
    in this file.
    """
    from edgar.attachments import _FILER_ROLE_SUFFIX

    assert _FILER_ROLE_SUFFIX.sub("", "Acme (Holdings) Inc.") == "Acme (Holdings) Inc."
    assert _FILER_ROLE_SUFFIX.sub("", "Acme Inc. (Filer)") == "Acme Inc."
    assert _FILER_ROLE_SUFFIX.sub("", "Acme (Holdings) Inc. (Issuer)") == "Acme (Holdings) Inc."


def test_addresses_are_parsed_and_indented_continuations_collapsed():
    filer, = _homepage("thirteenf-2023").get_filers()

    assert len(filer.addresses) == 2
    mailing, business = filer.addresses
    assert mailing.startswith("Mailing Address")
    assert business.startswith("Business Address")
    assert "650 MADISON AVENUE, 15TH FLOOR" in mailing
    # The re.sub(r'\n\s+', '\n', ...) cleanup: no line starts with whitespace.
    assert not any(line[:1].isspace() for line in mailing.split("\n") if line)


def test_the_homepage_renders_with_real_filer_data():
    """__rich__ builds the filer panel from get_filers() and indexes
    ``addresses[1]``. That index never ran before this fix, so rendering is
    exercised here rather than assumed."""
    import io

    from rich.console import Console

    # StringIO rather than os.devnull: nothing to close, and `pathlib.os` is an
    # import artifact that 3.13's pathlib package no longer exposes.
    console = Console(file=io.StringIO(), width=200)
    for stem in ("aapl-10k-2024", "form4-reporting-owner", "thirteenf-2023"):
        console.print(_homepage(stem))
