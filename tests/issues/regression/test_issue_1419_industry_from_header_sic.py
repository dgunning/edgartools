"""
Regression test for GitHub issue #1419: filing.xbrl() never set the filer's industry

``XBRL.from_filing()`` sets ``xbrl.standardization.industry`` from the SIC in the
filing header, so that the Fama-French 48 ``industry_overrides`` in
``gaap_mappings.json`` apply to banks, insurers and the other industries they
cover. The hook never ran, for two reasons:

1. It read ``header.filers[0].company_data.assigned_sic``. ``Filer`` has no
   ``company_data`` attribute (the field is ``company_information``), and the
   ``AttributeError`` was swallowed by ``except Exception: pass``.
2. The full-text SEC header gives the SIC as a display string,
   ``NATIONAL COMMERCIAL BANKS [6021]``, which ``set_industry_from_sic()`` cannot
   parse. Only the daily-feed (``.nc``) header's ``ASSIGNED-SIC`` is a bare code.

So ``industry`` was ``None`` after every ``filing.xbrl()``. The issue reports it on
JPMorgan Chase's FY2025 10-K (0001628280-26-008131), SIC 6021, which resolves to
``Banks``.

The two fixtures are already committed and parse offline, one per header dialect.
The SIC values were read from each file's header:

  0000943374-24-000509  1895 Bancorp of Wisconsin 8-K, full-text header
                        "SAVINGS INSTITUTIONS, NOT FEDERALLY CHARTERED [6036]"  -> Banks
  0001493152-25-001317  Acorn Energy 8-K, daily-feed header, ASSIGNED-SIC 8711 -> BusSv

GitHub Issue: https://github.com/dgunning/edgartools/issues/1419
"""

from pathlib import Path

import pytest

from edgar import Filing

DATA = Path(__file__).parents[3] / "data"


@pytest.mark.parametrize(
    "fixture, header_sic, industry",
    [
        ("sgml/0000943374-24-000509.txt", "SAVINGS INSTITUTIONS, NOT FEDERALLY CHARTERED [6036]", "Banks"),
        ("localstorage/filings/20250108/0001493152-25-001317.nc", "8711", "BusSv"),
    ],
)
def test_filing_xbrl_sets_industry_from_header_sic(fixture, header_sic, industry):
    path = DATA / fixture
    assert path.exists(), f"committed SGML fixture is missing: {path}"
    filing = Filing.from_sgml(str(path))
    assert filing.header.filers[0].company_information.sic == header_sic

    xbrl = filing.xbrl()

    assert xbrl is not None
    assert xbrl.standardization.industry == industry


@pytest.mark.parametrize(
    "header_sic, code",
    [
        ("NATIONAL COMMERCIAL BANKS [6021]", "6021"),
        ("6021", "6021"),
        ("[]", None),  # the full-text header of a filer with no SIC assigned
        ("", None),
        (None, None),
    ],
)
def test_sic_code_from_header(header_sic, code):
    from edgar.xbrl.xbrl import _sic_code_from_header

    assert _sic_code_from_header(header_sic) == code
