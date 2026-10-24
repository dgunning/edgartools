"""Regression: shelf_registration must not depend on header file-number order or a truncated fast path.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1707

``FilingHeader.file_numbers`` returned ``list(set(...))``, so the number the 424B cover parser took
(``[0]``) changed with Python's per-process hash seed. For BofA Finance LLC 424B2
0001918704-25-005439 the header lists ``333-268718-01`` and ``333-268718``; with the suffixed number
first, ``Prospectus424B.lifecycle`` accepted a recent-only family that did not contain the S-3
0001193125-22-301119 and ``shelf_registration`` was None.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from edgar.sgml.sgml_header import FilingHeader


def _filer(number):
    return SimpleNamespace(filing_information=SimpleNamespace(file_number=number))


def test_file_numbers_keep_header_order_and_dedupe():
    header = FilingHeader.__new__(FilingHeader)
    header.filers = [_filer("333-268718-01"), _filer("333-268718"), _filer("333-268718-01")]
    header.reporting_owners = []
    header.subject_companies = []
    assert header.file_numbers == ["333-268718-01", "333-268718"]


def test_file_numbers_order_does_not_depend_on_hash_seed():
    """Old list(set(...)) order changed with PYTHONHASHSEED; run several fresh interpreters."""
    import subprocess
    import sys
    code = (
        "from types import SimpleNamespace as N\n"
        "from edgar.sgml.sgml_header import FilingHeader\n"
        "f=lambda n: N(filing_information=N(file_number=n))\n"
        "h=FilingHeader.__new__(FilingHeader)\n"
        "h.filers=[f('333-268718-01'), f('333-268718')]\n"
        "h.reporting_owners=[]; h.subject_companies=[]\n"
        "print(h.file_numbers)\n"
    )
    outs = {
        subprocess.run([sys.executable, "-c", code], env={"PYTHONHASHSEED": str(seed), "PATH": ""},
                       capture_output=True, text=True, check=True).stdout
        for seed in range(12)
    }
    assert outs == {"['333-268718-01', '333-268718']\n"}


def _f(form):
    return SimpleNamespace(form=form)


def test_lifecycle_loads_full_history_when_recent_family_has_no_shelf():
    from edgar.offerings.prospectus.document import Prospectus424B

    recent = MagicMock()
    recent.empty = False
    recent.__iter__ = lambda self: iter([_f("424B2"), _f("424B2")])
    full = MagicMock()
    full.empty = False
    full.__iter__ = lambda self: iter([_f("S-3"), _f("424B2")])
    company = MagicMock()
    company.get_filings.side_effect = lambda **kw: full if kw["trigger_full_load"] else recent

    obj = Prospectus424B.__new__(Prospectus424B)
    obj._filing = SimpleNamespace(cik=1682472, accession_no="x")
    obj._filing.header = SimpleNamespace(file_numbers=["333-268718-01"])
    obj._cover_page = SimpleNamespace(registration_number="333-268718-01")
    with patch("edgar.entity.Company", return_value=company):
        lc = obj.lifecycle
    assert lc is not None and lc.filings is full
    assert [c.kwargs["trigger_full_load"] for c in company.get_filings.call_args_list] == [False, True]


class _Family:
    def __init__(self, forms):
        self._items = [_f(f) for f in forms]
        self.empty = not forms

    def __iter__(self):
        return iter(self._items)


@pytest.mark.parametrize("numbers", [
    ["333-269296", "333-269296-03"],  # Goldman Sachs 424B2 0000950170-24-004291: only the suffixed number has the S-3
    ["333-275587", "333-275587-01"],  # Morgan Stanley 424B2 0001839882-24-001121: same shape
])
def test_lifecycle_tries_every_header_file_number_until_one_has_the_shelf(numbers):
    from edgar.offerings.prospectus.document import Prospectus424B

    base, suffixed = numbers
    families = {base: _Family(["424B2"]), suffixed: _Family(["S-3", "424B2"])}
    company = MagicMock()
    company.get_filings.side_effect = lambda file_number, **kw: families[file_number]
    obj = Prospectus424B.__new__(Prospectus424B)
    obj._filing = SimpleNamespace(cik=1, accession_no="x", header=SimpleNamespace(file_numbers=numbers))
    obj._cover_page = SimpleNamespace(registration_number=base)
    with patch("edgar.entity.Company", return_value=company):
        lc = obj.lifecycle
    assert lc.filings is families[suffixed]


def test_registration_related_filings_reload_full_history_when_current_filing_missing():
    from edgar.offerings.prospectus.registration_s3 import RegistrationS3

    me = SimpleNamespace(form="S-3", accession_no="acc-me")
    recent = MagicMock()
    recent.empty = False
    recent.__iter__ = lambda self: iter([SimpleNamespace(form="424B2", accession_no="other")])
    full = MagicMock()
    full.empty = False
    full.__iter__ = lambda self: iter([me])
    company = MagicMock()
    company.get_filings.side_effect = lambda **kw: full if kw["trigger_full_load"] else recent
    obj = RegistrationS3.__new__(RegistrationS3)
    obj._filing = SimpleNamespace(cik=1, accession_no="acc-me")
    obj._cover_page = SimpleNamespace(registration_number="333-1")
    with patch("edgar.entity.Company", return_value=company):
        assert obj.related_filings is full


@pytest.mark.network
@pytest.mark.vcr
def test_bofa_424b2_finds_s3_shelf_for_suffixed_registration_number():
    from edgar import find
    obj = find("0001918704-25-005439").obj()
    obj._cover_page.registration_number = "333-268718-01"  # the order that used to lose the shelf
    assert obj.shelf_registration.accession_no == "0001193125-22-301119"
