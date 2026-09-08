"""Regression test for issue #1146.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1146

`get_bdc_list()` read a single year's BDC report, the one
`get_latest_bdc_report_year()` picked by walking back until a CSV answered
HTTP 200. A yearly CSV is a snapshot taken while that year is still running,
not a complete register: the 2026 report dropped 15 registrants the 2025 one
carried, Ares Capital -- the largest publicly traded BDC -- among them. So
`is_bdc_cik(1287750)` answered False and `find_bdc("ARCC")` returned nothing.

**The fix direction recorded on the bead would not have worked.** It proposed
preferring the newer year only when its row count does not regress. The 2026
report has *more* rows than 2025 (212 against 196) because it added 31
registrants while dropping those 15, so a row-count guard still picks 2026 and
still loses Ares. Presence in any recent report is the signal that survives, so
`_combined_bdc_report` unions the last three years and keeps the most recent
row per CIK.

Per the standing rule that BDC tests must not hardcode a volatile issuer, the
live check below asserts the year-selection property and anchors on MAIN, which
is present across report years; Ares appears only in the offline fixtures, where
its absence is the thing being simulated.
"""

import pandas as pd
import pytest

from edgar.bdc import reference
from edgar.bdc.reference import get_active_bdc_ciks, get_bdc_list, is_bdc_cik

ARCC = 1287750
MAIN = 1396440


def _report(rows):
    return pd.DataFrame([
        {'file_number': f'814-{cik:05d}'[:9], 'cik': cik, 'registrant_name': name,
         'city': 'NEW YORK', 'state': 'NY', 'zip_code': '10019',
         'last_filing_date': pd.Timestamp('2025-05-29'), 'last_filing_type': '10-K'}
        for cik, name in rows
    ])


@pytest.fixture
def snapshot_reports(monkeypatch):
    """The shape of the reported failure: the newest year is bigger and still
    drops a registrant."""
    reports = {
        2026: _report([(MAIN, 'MAIN STREET CAPITAL CORP')]
                      + [(9_000_000 + n, f'NEW BDC {n}') for n in range(30)]),
        2025: _report([(MAIN, 'MAIN STREET CAPITAL CORP'),
                       (ARCC, 'ARES CAPITAL CORP'),
                       (1143513, 'GLADSTONE CAPITAL CORP')]),
        2024: _report([(MAIN, 'MAIN STREET CAPITAL CORP'),
                       (ARCC, 'ARES CAPITAL CORP'),
                       (1512931, 'MONROE CAPITAL Corp')]),
    }

    def fake_fetch(year=None):
        if year is None:
            year = 2026
        if year not in reports:
            raise ValueError(f"no BDC report for {year}")
        return reports[year]

    monkeypatch.setattr(reference, 'fetch_bdc_report', fake_fetch)
    monkeypatch.setattr(reference, 'get_latest_bdc_report_year', lambda: 2026)
    get_active_bdc_ciks.cache_clear()
    yield reports
    get_active_bdc_ciks.cache_clear()


def test_the_newest_report_is_larger_and_still_loses_a_registrant(snapshot_reports):
    """Guards the premise: a row-count check cannot detect this."""
    assert len(snapshot_reports[2026]) > len(snapshot_reports[2025])
    assert ARCC not in set(snapshot_reports[2026]['cik'])


def test_a_registrant_missing_from_the_newest_report_is_still_a_bdc(snapshot_reports):
    combined = reference._combined_bdc_report()
    ciks = set(combined['cik'])

    assert ARCC in ciks
    assert MAIN in ciks
    assert 1143513 in ciks    # dropped in 2026, present in 2025
    assert 1512931 in ciks    # present only in 2024


def test_the_combined_register_has_no_duplicate_registrants(snapshot_reports):
    combined = reference._combined_bdc_report()

    assert len(combined) == len(set(combined['cik']))
    assert len(combined) == 34   # 31 from 2026, 2 more from 2025, 1 more from 2024


def test_an_explicit_year_still_returns_that_year_exactly(snapshot_reports):
    """The union is what you get when you ask for "the BDCs", not for a year."""
    assert len(get_bdc_list(year=2026)) == 31
    assert len(get_bdc_list(year=2025)) == 3
    assert len(get_bdc_list()) == 34


def test_the_public_lookups_follow(snapshot_reports):
    assert is_bdc_cik(ARCC) is True
    assert is_bdc_cik(MAIN) is True
    assert ARCC in get_active_bdc_ciks(min_year=2023)


def test_one_unavailable_year_does_not_empty_the_register(monkeypatch):
    """Only the newest year exists -- the older probes must not be fatal."""
    only_2026 = _report([(MAIN, 'MAIN STREET CAPITAL CORP')])

    def fake_fetch(year=None):
        if year in (None, 2026):
            return only_2026
        raise ValueError("404")

    monkeypatch.setattr(reference, 'fetch_bdc_report', fake_fetch)
    monkeypatch.setattr(reference, 'get_latest_bdc_report_year', lambda: 2026)

    combined = reference._combined_bdc_report()
    assert set(combined['cik']) == {MAIN}


@pytest.mark.network
def test_live_register_does_not_lose_registrants_the_prior_year_listed():
    """The property, against the SEC's own data."""
    latest = reference.get_latest_bdc_report_year()
    previous = set(reference.fetch_bdc_report(latest - 1)['cik'].dropna().astype(int))
    combined = {bdc.cik for bdc in get_bdc_list()}

    missing = previous - combined
    assert not missing, f"registrants listed in {latest - 1} are absent from the register: {sorted(missing)[:10]}"
    assert MAIN in combined
