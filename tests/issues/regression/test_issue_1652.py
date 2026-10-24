"""
Regression test for GitHub Issue #1652: ``CurrencyConverter`` returned no closing
rates, because a NaN ``period_end`` skipped the ``period_instant`` fallback.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1652

A closing rate (``ifrs-full:ClosingForeignExchangeRate``) is an instant fact.
Since PR #942 declared the ``FactQuery.to_dataframe()`` column set, an instant
fact's ``period_end`` cell is NaN rather than absent. The converter read the date
with ``row.get('period_end') or row.get('period_instant')``; NaN is truthy, so
the ``or`` returned NaN, no year was found, and the row was skipped without a
warning. Every closing rate in the filing went the same way.

Ground truth: Novo Nordisk's FY2025 20-F, accession 0000353278-26-000012, note
4.4 "Exchange rates applied for hedged currencies", row "Year-end exchange rate
applied (DKK per 100)", USD column: 635 (2025), 714 (2024), 674 (2023). The XBRL
facts carry the same values with unit ``dkkPerUSD`` and member ``currency:USD``.
"""

import pandas as pd
import pytest

from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.currency import CurrencyConverter

pytestmark = [pytest.mark.regression]

# The instance document alone carries the facts, contexts and units the
# converter reads, so the cassette holds one 8.4 MB response, not the submission.
NVO_FOLDER = "https://www.sec.gov/Archives/edgar/data/353278/000035327826000012/"
NVO_INSTANCE = "nvo-20251231_htm.xml"
NVO_CASSETTE = "currency_nvo_20f_0000353278-26-000012.yaml"


@pytest.fixture(scope="module")
def nvo_xbrl(vcr, tmp_path_factory):
    folder = tmp_path_factory.mktemp("nvo")
    with vcr.use_cassette(NVO_CASSETTE):
        text = download_file(NVO_FOLDER + NVO_INSTANCE)
    (folder / NVO_INSTANCE).write_text(text, encoding="utf-8")
    return XBRL.from_directory(folder)


def test_novo_closing_rates_are_read_from_period_instant(nvo_xbrl):
    converter = CurrencyConverter(nvo_xbrl)

    assert converter.home_currency == "DKK"
    assert converter.get_rate(2025, "closing") == 635.0
    assert converter.get_rate(2024, "closing") == 714.0
    assert converter.get_rate(2023, "closing") == 674.0
    # 635 DKK per 100 USD at the 2025 year end
    assert converter.to_usd(635, 2025, rate_type="closing") == pytest.approx(100.0)
    # The average rates, which always worked, are unchanged.
    assert converter.get_rate(2025, "average") == 662.0
    assert converter.extraction_warnings == []


# ---------------------------------------------------------------------------
# Offline: the frame shape that broke it, built by hand
# ---------------------------------------------------------------------------

class _Query:
    def __init__(self, frames):
        self._frames = frames
        self._concept = None

    def by_concept(self, concept, exact=False):
        self._concept = concept
        return self

    def to_dataframe(self):
        return self._frames.get(self._concept, pd.DataFrame())


class _Facts:
    def __init__(self, frames):
        self._frames = frames

    def to_dataframe(self):
        return pd.DataFrame({"unit_ref": ["dkk"]})

    def query(self):
        return _Query(self._frames)


class _StubXBRL:
    units = {"dkk": {"type": "simple", "measure": "iso4217:DKK"}}
    contexts: dict = {}

    def __init__(self, frames):
        self.facts = _Facts(frames)


def _closing_frame(period_instant):
    # The declared column set: an instant fact has period_end = NaN.
    return pd.DataFrame({
        "concept": ["ifrs-full:ClosingForeignExchangeRate"],
        "unit_ref": ["dkkPerUSD"],
        "context_ref": ["c-1"],
        "period_end": [float("nan")],
        "period_instant": [period_instant],
        "numeric_value": [635.0],
    })


def test_nan_period_end_falls_back_to_period_instant():
    converter = CurrencyConverter(_StubXBRL({
        "ifrs-full:ClosingForeignExchangeRate": _closing_frame("2025-12-31"),
    }))
    assert converter.get_rate(2025, "closing") == 635.0
    assert converter.extraction_warnings == []


def test_a_rate_with_no_date_is_reported_not_dropped_silently():
    converter = CurrencyConverter(_StubXBRL({
        "ifrs-full:ClosingForeignExchangeRate": _closing_frame(float("nan")),
    }))
    assert converter.exchange_rates == {}
    assert converter.extraction_warnings == [
        "1 closing exchange rate fact(s) had no period date and were not used"
    ]
