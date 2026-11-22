"""
Regression test for GitHub Issue #888:
Fund.get_filings(series_only=True) silently returned the whole umbrella trust's
filings instead of filtering to the fund's own series.

Root cause: the series-aware path used EFTS full-text search on the series ID,
which returns nothing (SEC full-text search does not index NPORT series IDs), so
the method fell through to the unfiltered trust delegation and returned a sibling
series' data (e.g. VCLT / S000026864 got a filing whose report.series_id was
S000026865).

Fix: _get_series_filings() resolves the series via SEC browse-edgar (series ID as
the CIK parameter), which returns exactly that series' filings; and series_only
now returns an empty Filings rather than the unfiltered trust when the series
cannot be resolved.

GitHub Issue: https://github.com/dgunning/edgartools/issues/888
"""
import pytest

from edgar import Fund
from edgar._filings import Filings
from edgar.funds.core import _series_filter_kwargs

# --- Offline: entity-style kwargs are mapped onto the Filings.filter interface
# (regression for the review finding that raw kwargs crashed with TypeError) ---

def test_series_filter_kwargs_defaults_amendments_true():
    # Filings.filter drops amendments by default when a form is given; the
    # entity path includes them, so the series path must too.
    assert _series_filter_kwargs({'form': 'NPORT-P'}) == {'form': 'NPORT-P', 'amendments': True}


def test_series_filter_kwargs_translates_year_and_quarter():
    assert _series_filter_kwargs({'form': 'NPORT-P', 'year': 2024})['filing_date'] == '2024-01-01:2024-12-31'
    assert _series_filter_kwargs({'year': 2024, 'quarter': 2})['filing_date'] == '2024-04-01:2024-06-30'


def test_series_filter_kwargs_drops_unsupported_without_crashing():
    # year/quarter/is_xbrl/file_number are valid on Entity.get_filings but not
    # on Filings.filter; they must be dropped, not forwarded (which raised
    # TypeError before the fix).
    mapped = _series_filter_kwargs({'form': 'NPORT-P', 'is_xbrl': True, 'file_number': '811-1', 'sort_by': 'x'})
    assert mapped == {'form': 'NPORT-P', 'amendments': True}


def test_series_filter_kwargs_respects_explicit_amendments():
    assert _series_filter_kwargs({'form': 'NPORT-P', 'amendments': False})['amendments'] is False


# --- Against SEC's own pages, offline ----------------------------------------
#
# browse-edgar pages for two ETF series in umbrella trusts, saved verbatim on
# 2026-11-22 under tests/fixtures/funds/browse_edgar_series_forms/:
#   VCLT  S000026864  VANGUARD SCOTTSDALE FUNDS (CIK 1021882)
#   PFF   S000013499  iSHARES TRUST (CIK 1100663; 9,099 N-PORT/NPORT-P filings
#                     trust-wide on that date, against 28 for this series)
# The Fund is built with its series already named, so no ticker lookup is
# involved, and the trust is a stub that fails if it is asked: reaching it from
# a series_only question is the original harm.
#
# Ground truth, read without edgartools: each series' newest NPORT-P below is
# the first row of its own listing, and its SEC header lists exactly one
# series, the one asked for.

SERIES = {
    "VCLT": ("S000026864", "0001021882-26-000851", 28),  # period 2026-08-31, filed 2026-10-29
    "PFF": ("S000013499", "0000940400-26-034998", 28),   # period 2026-06-30, filed 2026-08-27
}
TRUST_FILINGS = object()


class _Trust:
    """The umbrella trust: answers the default path, refuses series_only."""

    def __init__(self):
        self.asked = []

    def get_filings(self, **kwargs):
        self.asked.append(kwargs)
        return TRUST_FILINGS


def _fund(series_id):
    fund = Fund.__new__(Fund)
    fund._target_series_id = series_id
    fund._entity = fund._company = _Trust()
    fund._series = fund._class = None
    return fund


@pytest.fixture
def sec_pages(monkeypatch):
    from tests._browse_edgar_pages import serve_recorded_pages

    requested = []
    monkeypatch.setattr("edgar.funds.data.download_text", serve_recorded_pages(requested))
    return requested


def test_the_recorded_pages_are_present():
    """Absent is not passing."""
    from tests._browse_edgar_pages import FORM_PAGES

    for series_id, _, _ in SERIES.values():
        for form in ("N-PORT", "NPORT-P"):
            for start in (0, 100):
                assert (FORM_PAGES / f"{series_id}-{form}-start{start}.html").is_file()
    assert (FORM_PAGES / "S000026864-SC_13D-start0.html").is_file()


@pytest.mark.parametrize("ticker", list(SERIES))
def test_series_only_filters_to_fund_series(ticker, sec_pages):
    """Every filing comes from the series' own listing, never the trust's."""
    series_id, latest, count = SERIES[ticker]
    fund = _fund(series_id)

    series_only = fund.get_filings(form=["N-PORT", "NPORT-P"], series_only=True)

    assert fund._entity.asked == []
    assert len(series_only) == count
    assert set(series_only.data.column("form").to_pylist()) == {"NPORT-P"}
    assert series_only.latest(1).accession_no == latest
    assert sec_pages and all(f"CIK={series_id}&" in url for url in sec_pages)


def test_series_only_does_not_return_unfiltered_trust_when_no_matches(sec_pages):
    """When series_only is requested but no filings match, the result is an empty
    Filings, never the unfiltered trust (the original harm)."""
    fund = _fund(SERIES["VCLT"][0])

    result = fund.get_filings(form="SC 13D", series_only=True)

    assert isinstance(result, Filings)
    assert len(result) == 0
    assert fund._entity.asked == []


def test_default_get_filings_unchanged():
    """Without series_only, get_filings still asks the whole trust."""
    fund = _fund(SERIES["VCLT"][0])

    assert fund.get_filings(form=["N-PORT", "NPORT-P"]) is TRUST_FILINGS
    assert fund._entity.asked == [{"form": ["N-PORT", "NPORT-P"]}]
