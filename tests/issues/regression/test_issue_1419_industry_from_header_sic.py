"""
Regression test for GitHub issue #1419: filing.xbrl() never set the filer's industry

``XBRL.from_filing()`` sets ``xbrl.standardization.industry`` from the SIC in the
filing header, so that ``ReverseIndex.lookup()`` can apply any Fama-French 48
``industry_overrides`` in ``gaap_mappings.json`` for that industry. The hook never
ran, for two reasons:

1. It read ``header.filers[0].company_data.assigned_sic``. ``Filer`` has no
   ``company_data`` attribute (the field is ``company_information``), and the
   ``AttributeError`` was swallowed by ``except Exception: pass``.
2. The full-text SEC header gives the SIC as a display string,
   ``NATIONAL COMMERCIAL BANKS [6021]``, which ``set_industry_from_sic()`` cannot
   parse. Only the daily-feed (``.nc``) header's ``ASSIGNED-SIC`` is a bare code.

So ``industry`` was ``None`` after every ``filing.xbrl()``. The issue reports it on
JPMorgan Chase's FY2025 10-K (0001628280-26-008131), SIC 6021, which resolves to
``Banks``.

The SIC table the hook feeds (``sic_industry._FF48_SIC_RANGES``) had two faults of
its own, which only mattered once the hook ran:

3. Twelve SIC codes sat in two ranges, and ``sic_to_fama_french()`` returns the
   first match, despite a comment calling the list sorted for binary search.
   3570-3579 (computer and office equipment, Apple's 3571) went to Mach instead of
   Comps, 3622 (industrial controls) to ElcEq instead of Chips, and 3647 (vehicular
   lighting) to ElcEq instead of Autos. Ken French's Siccodes48.txt puts each of
   them in the second industry only.
4. SIC 6798 (real estate investment trusts) went to Fin, French's Trading group
   of brokers, holding companies and blank-check shells. REITs report real-estate
   statements, so they are RlEst now.

The fixtures are committed and parse offline. The SIC values were read from each
file's header:

  0000943374-24-000509  1895 Bancorp of Wisconsin 8-K, full-text header
                        "SAVINGS INSTITUTIONS, NOT FEDERALLY CHARTERED [6036]"  -> Banks
  0001493152-25-001317  Acorn Energy 8-K, daily-feed header, ASSIGNED-SIC 8711 -> BusSv
  0000320193-24-000123  Apple FY2024 10-K, full-text header
                        "ELECTRONIC COMPUTERS [3571]"                          -> Comps (was Mach)

What switching the hook on did to the override data is covered in
test_issue_1419_industry_overrides.py.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1419
"""

from pathlib import Path

import pytest

from edgar import Filing
from edgar.xbrl.standardization.sic_industry import _FF48_SIC_RANGES, sic_to_fama_french

DATA = Path(__file__).parents[3] / "data"


@pytest.mark.parametrize(
    "fixture, header_sic, industry",
    [
        ("sgml/0000943374-24-000509.txt", "SAVINGS INSTITUTIONS, NOT FEDERALLY CHARTERED [6036]", "Banks"),
        ("localstorage/filings/20250108/0001493152-25-001317.nc", "8711", "BusSv"),
        ("sgml/0000320193-24-000123.txt", "ELECTRONIC COMPUTERS [3571]", "Comps"),
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


@pytest.mark.parametrize(
    "sic, industry",
    [
        # Each of these sat in two ranges and went to the first (was Mach, ElcEq, ElcEq).
        (3570, "Comps"),
        (3571, "Comps"),  # Apple
        (3579, "Comps"),
        (3622, "Chips"),
        (3647, "Autos"),
        # Their neighbours keep their industry.
        (3569, "Mach"),
        (3580, "Mach"),
        (3621, "ElcEq"),
        (3623, "ElcEq"),
        (3646, "ElcEq"),
        (3648, "ElcEq"),
    ],
)
def test_sic_codes_that_sat_in_two_ranges_get_one_industry(sic, industry):
    assert sic_to_fama_french(sic) == industry


def test_reits_are_real_estate():
    assert sic_to_fama_french(6798) == "RlEst"  # was Fin
    assert sic_to_fama_french(6799) == "Fin"  # investors, NEC: still French's Trading


def test_every_sic_code_maps_to_at_most_one_industry():
    """sic_to_fama_french() returns the first range that matches, so an overlap is silent."""
    industries_by_code = {}
    for start, end, industry in _FF48_SIC_RANGES:
        assert start <= end, (start, end, industry)
        for code in range(start, end + 1):
            industries_by_code.setdefault(code, []).append(industry)

    overlaps = {code: found for code, found in industries_by_code.items() if len(found) > 1}

    assert overlaps == {}
