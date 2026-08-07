"""Regression test for GitHub issue #889 (ticker / Class-ID prefix collision).

`Fund(ticker)` failed to resolve the share class for *any* ETF ticker starting
with "C" that has genuine series/class registration (e.g. CNEQ, CIBR, CQQQ,
COPX, CARZ, CALF, CGW, CATH, CUT). The `Fund` object still constructed, but
`.company`, `.series`, and `.share_class` raised `AttributeError` instead of
returning the resolved objects — because `Fund.__init__` never assigned
`self._company`/`self._series`/`self._class`.

Root cause: inside `_build_hierarchy_from_mf_tickers()` (and the identical
slow-path fallback in `get_fund_object()`), `identifier.startswith('C')` was used
as a proxy for "this identifier is a Class ID". Real Class IDs look like
`C000248577`, but a *ticker* like `CNEQ` also starts with "C", so the code
searched for `class_id == "CNEQ"` (never true) instead of taking the
ticker-match branch. The fix replaces the naive prefix check with a proper
Class-ID shape check, `re.match(r'^C\\d+$', identifier)`, mirroring the check
`get_fund_object` already uses one level up.
"""
import pandas as pd
import pytest

from edgar.funds.data import _build_hierarchy_from_mf_tickers
from edgar.funds.core import FundClass


# One CIK (Alger ETF Trust) with two share classes: a C-ticker (CNEQ) and a
# non-C sibling (AWEG) in a different series. Mirrors the real registration.
_MF_TICKERS = pd.DataFrame(
    [
        {"cik": 1807486, "seriesId": "S000084280", "classId": "C000248577", "ticker": "CNEQ"},
        {"cik": 1807486, "seriesId": "S000080000", "classId": "C000240821", "ticker": "AWEG"},
    ]
)


@pytest.fixture
def mock_mf_tickers(monkeypatch):
    """Patch the cached mf_tickers source and disable name enrichment."""
    monkeypatch.setattr(
        "edgar.reference.tickers.get_mutual_fund_tickers", lambda: _MF_TICKERS
    )

    def _no_ref_data():
        raise RuntimeError("reference data unavailable in test")

    monkeypatch.setattr(
        "edgar.funds.reference.get_fund_reference_data", _no_ref_data
    )


@pytest.mark.fast
def test_c_ticker_resolves_to_class(mock_mf_tickers):
    """The bug: a C-prefixed *ticker* must match on ticker, not be mistaken for a Class ID."""
    result = _build_hierarchy_from_mf_tickers(
        cik="1807486", identifier_type="Class", identifier="CNEQ"
    )
    assert isinstance(result, FundClass)
    assert result.class_id == "C000248577"
    assert result.ticker == "CNEQ"
    assert result.series.series_id == "S000084280"
    assert result.series.fund_company.cik == 1807486


@pytest.mark.fast
def test_c_ticker_case_insensitive(mock_mf_tickers):
    result = _build_hierarchy_from_mf_tickers(
        cik="1807486", identifier_type="Class", identifier="cneq"
    )
    assert isinstance(result, FundClass)
    assert result.class_id == "C000248577"


@pytest.mark.fast
def test_real_class_id_still_resolves(mock_mf_tickers):
    """A genuine Class ID must still match on class_id (the shape check preserves this)."""
    result = _build_hierarchy_from_mf_tickers(
        cik="1807486", identifier_type="Class", identifier="C000248577"
    )
    assert isinstance(result, FundClass)
    assert result.class_id == "C000248577"
    assert result.ticker == "CNEQ"


@pytest.mark.fast
def test_non_c_ticker_still_resolves(mock_mf_tickers):
    """Sibling ticker not starting with C must keep working (never regressed)."""
    result = _build_hierarchy_from_mf_tickers(
        cik="1807486", identifier_type="Class", identifier="AWEG"
    )
    assert isinstance(result, FundClass)
    assert result.class_id == "C000240821"
    assert result.ticker == "AWEG"


# --------------------------------------------------------------------------- #
# End-to-end reproduction (network) — the exact scenario from the issue.
# --------------------------------------------------------------------------- #

@pytest.mark.network
def test_fund_c_ticker_end_to_end():
    import edgar
    from edgar.funds import Fund

    edgar.set_identity("research@example.com")

    fund = Fund("CNEQ")  # must not raise, and must resolve the full hierarchy

    # Properties must honor their Optional[...] contract, not raise AttributeError.
    assert fund.company is not None
    assert fund.company.name == "Alger ETF Trust"
    assert fund.series is not None
    assert fund.series.series_id == "S000084280"
    assert fund.share_class is not None
    assert fund.share_class.class_id == "C000248577"
    assert fund.share_class.ticker == "CNEQ"
