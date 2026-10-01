"""BDCEntity.is_active went stale for a BDC the newest SEC report dropped (edgartools-huul).

Since #1146 the register unions the last three yearly reports, so a registrant
the 2026 report dropped (Ares Capital among 22) keeps its 2025 row, whose
last_filing_date is 2025-05-29. That row leaves the 18-month window around
2026-11-29 and is_active flipped to False, though ARCC files every quarter.
For such a row, is_active now asks the company's own filings.

The clock is frozen at 2026-12-01, past the flip.
"""
from datetime import date

import httpx
import pandas as pd
import pytest

from edgar.bdc import reference
from edgar.bdc.reference import BDCEntity, get_bdc_list

ARCC = 1287750
MAIN = 1396440


class _Dec2026(date):
    @classmethod
    def today(cls):
        return cls(2026, 12, 1)


@pytest.fixture
def december_2026(monkeypatch):
    # Held directly: by teardown a test may have monkeypatched the module attribute
    lookup = reference._latest_filing_date
    monkeypatch.setattr(reference, "date", _Dec2026)
    lookup.cache_clear()
    yield
    lookup.cache_clear()


def _entity(in_latest_report, last_filing_date=date(2025, 5, 29)):
    return BDCEntity(file_number="814-00663", cik=ARCC, name="ARES CAPITAL CORP",
                     last_filing_date=last_filing_date, last_filing_type="10-Q",
                     in_latest_report=in_latest_report)


def _own_latest_filing(monkeypatch, result):
    calls = []

    def fake(cik):
        calls.append(cik)
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(reference, "_latest_filing_date", fake)
    return calls


@pytest.mark.fast
def test_a_dropped_bdc_that_still_files_stays_active(december_2026, monkeypatch):
    calls = _own_latest_filing(monkeypatch, date(2026, 10, 29))
    assert _entity(in_latest_report=False).is_active is True
    assert calls == [ARCC]


@pytest.mark.fast
def test_a_dropped_bdc_that_stopped_filing_is_inactive(december_2026, monkeypatch):
    _own_latest_filing(monkeypatch, date(2025, 3, 31))
    assert _entity(in_latest_report=False).is_active is False


@pytest.mark.fast
def test_a_dropped_bdc_with_no_filings_is_inactive(december_2026, monkeypatch):
    _own_latest_filing(monkeypatch, None)
    assert _entity(in_latest_report=False).is_active is False


@pytest.mark.fast
def test_the_newest_report_is_trusted_without_a_request(december_2026, monkeypatch):
    """A row in the newest report is the SEC's own current answer, so no lookup."""
    calls = _own_latest_filing(monkeypatch, date(2026, 10, 29))
    assert _entity(in_latest_report=True).is_active is False
    assert calls == []


@pytest.mark.fast
def test_a_row_inside_the_window_needs_no_request(december_2026, monkeypatch):
    calls = _own_latest_filing(monkeypatch, None)
    assert _entity(in_latest_report=False, last_filing_date=date(2026, 5, 8)).is_active is True
    assert calls == []


@pytest.mark.fast
def test_an_unreachable_sec_falls_back_to_the_report_row(december_2026, monkeypatch, caplog):
    _own_latest_filing(monkeypatch, httpx.ConnectError("connection refused"))
    assert _entity(in_latest_report=False).is_active is False
    assert "Could not check ARES CAPITAL CORP's own filings" in caplog.text


@pytest.mark.fast
def test_any_other_failure_is_not_read_as_inactive(december_2026, monkeypatch):
    _own_latest_filing(monkeypatch, KeyError("filings"))
    with pytest.raises(KeyError):
        _ = _entity(in_latest_report=False).is_active


@pytest.mark.fast
def test_latest_filing_date_is_the_newest_in_the_submissions(monkeypatch):
    from edgar.entity import submissions
    monkeypatch.setattr(submissions, "download_entity_submissions_from_sec", lambda cik: {
        "filings": {"recent": {"filingDate": ["2026-09-15", "2026-07-29", "2026-04-29"]}}})
    reference._latest_filing_date.cache_clear()
    try:
        assert reference._latest_filing_date(ARCC) == date(2026, 9, 15)
    finally:
        reference._latest_filing_date.cache_clear()


def _report(rows):
    return pd.DataFrame([
        {'file_number': '814-00001', 'cik': cik, 'registrant_name': name, 'city': 'NEW YORK', 'state': 'NY',
         'zip_code': '10019', 'last_filing_date': pd.Timestamp(filed), 'last_filing_type': '10-Q'}
        for cik, name, filed in rows
    ])


@pytest.mark.fast
def test_the_register_marks_rows_the_newest_report_dropped(monkeypatch):
    reports = {
        2026: _report([(MAIN, 'MAIN STREET CAPITAL CORP', '2026-05-08')]),
        2025: _report([(MAIN, 'MAIN STREET CAPITAL CORP', '2025-05-09'), (ARCC, 'ARES CAPITAL CORP', '2025-05-29')]),
        2024: _report([(MAIN, 'MAIN STREET CAPITAL CORP', '2024-05-10')]),
    }
    monkeypatch.setattr(reference, 'fetch_bdc_report', lambda year=None: reports[year or 2026])
    monkeypatch.setattr(reference, 'get_latest_bdc_report_year', lambda: 2026)

    bdcs = get_bdc_list()
    assert bdcs.get_by_cik(MAIN).in_latest_report is True
    assert bdcs.get_by_cik(ARCC).in_latest_report is False
    # An explicit older year is a snapshot of then
    assert get_bdc_list(year=2025).get_by_cik(MAIN).in_latest_report is False
    assert get_bdc_list(year=2026).get_by_cik(MAIN).in_latest_report is True


@pytest.mark.network
def test_arcc_is_still_active_after_its_report_row_expires(december_2026):
    """Live: ARCC is in the register only through the 2025 report, and its own
    filings (10-Q for 2026-06-30 filed 2026-07-29) keep it active on 2026-12-01."""
    bdcs = get_bdc_list()
    arcc, main = bdcs.get_by_cik(ARCC), bdcs.get_by_cik(MAIN)

    assert arcc.in_latest_report is False
    assert arcc.last_filing_date == date(2025, 5, 29)
    assert reference._latest_filing_date(ARCC) >= date(2026, 7, 29)
    assert arcc.is_active is True
    assert main.in_latest_report is True
    assert main.is_active is True
