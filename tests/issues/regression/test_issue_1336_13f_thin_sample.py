"""A thin implied-price sample must not force a 13F's values into thousands.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1336

``resolve_value_unit`` read "half or more of the priceable rows imply a price
under $1" as values in thousands, with no minimum sample and ``ambiguous=False``.
MFN Partners' Q4 2025 13F-HR/A holds two rows: a warrant at $0.80 and ordinary
shares at $10.25. The fraction landed on exactly 0.5, the filing was multiplied
by 1,000 to $24.92 billion, and the 5.58.0 ambiguity warning stayed silent. The
filing's own schema (X0202, dollars) and cover total (24,920,000) were ignored.

Fix: a fraction inside a dead band (0.35-0.65) is no evidence, so metadata
decides; a decisive fraction from fewer than 10 rows still decides but is
flagged ambiguous. The issue proposed letting metadata decide every small
sample. Measured over the SEC 13F data sets (Dec 2025 - Aug 2026), that would
silently mis-scale 99 of 151 small filings that genuinely report thousands;
the dead band gets MFN right and leaves 20 errors, 17 of them now warned.

The original XML is preserved under tests/fixtures/13f/mfn-0000904454-26-000248;
see its README for provenance. Offline.
"""
import warnings
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from edgar import ThirteenF
from edgar.thirteenf import Ambiguous13FValueUnitWarning
from edgar.thirteenf.units import resolve_value_unit

pytestmark = pytest.mark.fast

DATA = Path(__file__).resolve().parents[2] / "fixtures" / "13f" / "mfn-0000904454-26-000248"


@pytest.fixture
def mfn_filing(monkeypatch):
    """The original SEC XML; only attachment I/O and optional tickers are stubbed."""
    import importlib
    parser = importlib.import_module("edgar.thirteenf.parsers.infotable_xml")
    monkeypatch.setattr(parser, "cusip_ticker_mapping",
                        lambda **kwargs: pd.DataFrame({"Ticker": pd.Series(dtype=str)}))
    monkeypatch.setattr(ThirteenF, "_get_infotable_from_attachment",
                        lambda self: ((DATA / "holdings.xml").read_text(), "xml"))
    monkeypatch.setattr(ThirteenF, "_cache_provider", None)
    return SimpleNamespace(
        form="13F-HR/A", accession_no="0000904454-26-000248",
        filing_date="2026-05-01", xml=lambda: (DATA / "primary.xml").read_text(),
    )


def test_mfn_amendment_is_valued_in_dollars(mfn_filing):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Ambiguous13FValueUnitWarning)
        report = ThirteenF(mfn_filing)
        resolution = report.value_unit_resolution
        total = report.infotable.Value.sum()

    # The cover page states tableValueTotal 24,920,000 for 2 entries.
    assert total == 24_920_000
    assert report.raw_infotable.Value.sum() == 24_920_000
    assert resolution.unit == "dollars"
    assert resolution.multiplier == 1
    assert resolution.source == "schema"
    assert resolution.schema_version == "X0202"
    assert resolution.priceable_rows == 2
    assert resolution.fraction_sub_dollar == 0.5


def test_mfn_amendment_records_the_ambiguity_without_a_conversion_warning(mfn_filing):
    """The resolution is flagged ambiguous; no 1000x is applied, so nothing warns.

    Ambiguous13FValueUnitWarning is raised only when an ambiguous resolution
    multiplies values by 1,000. MFN now keeps its dollars, so the ambiguity is
    visible on value_unit_resolution rather than as a warning.
    """
    report = ThirteenF(mfn_filing)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert report.value_unit_resolution.ambiguous is True
        _ = report.infotable
    assert not [w for w in caught if w.category is Ambiguous13FValueUnitWarning]


def test_a_thin_sample_that_falls_back_to_thousands_now_warns(mfn_filing):
    """Before, a thin sample reached thousands with ambiguous=False and no warning.

    The same two rows under an X0201 (thousands) schema now reach thousands
    through the metadata fallback, flagged ambiguous, so the conversion warns.
    """
    report = ThirteenF(mfn_filing)
    report.__dict__.update(_schema_version="X0201")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        resolution = report.value_unit_resolution
        _ = report.infotable
    assert (resolution.unit, resolution.source, resolution.ambiguous) == ("thousands", "schema", True)
    assert [w.category for w in caught] == [Ambiguous13FValueUnitWarning]


def _frame(prices, shares=1_000.0):
    return pd.DataFrame([dict(Value=p * shares, SharesPrnAmount=shares, Type="Shares", PutCall="")
                         for p in prices])


@pytest.mark.parametrize("schema", [None, "X0202"])
def test_two_rows_with_one_warrant_do_not_decide_the_unit(schema):
    r = resolve_value_unit(_frame([0.80, 10.25]), schema_version=schema,
                           report_period_dt=datetime(2025, 12, 31))
    assert (r.unit, r.ambiguous, r.multiplier) == ("dollars", True, 1)


def test_x0201_thin_sample_falls_back_to_thousands_by_schema():
    """Falling through to metadata is not "always dollars": X0201 means thousands."""
    r = resolve_value_unit(_frame([0.80, 10.25]), schema_version="X0201",
                           report_period_dt=datetime(2021, 12, 31))
    assert (r.unit, r.source, r.ambiguous) == ("thousands", "schema", True)


@pytest.mark.parametrize("rows,sub_dollar", [
    (23, 23),   # Baupost's shape: every implied price under $1
    (86, 83),   # Duquesne's shape: 0.965 sub-dollar
    (10, 7),    # the minimum sample, clearly on the thousands side (0.70)
])
def test_large_decisive_samples_still_resolve_to_thousands_silently(rows, sub_dollar):
    prices = [0.25] * sub_dollar + [40.0] * (rows - sub_dollar)
    r = resolve_value_unit(_frame(prices), schema_version="X0202")
    assert (r.unit, r.source, r.ambiguous, r.multiplier) == ("thousands", "implied_prices", False, 1000)


def test_a_split_sample_is_not_evidence_even_when_large():
    """0.5 of twenty rows is still a coin flip: the metadata decides."""
    prices = [0.25] * 10 + [40.0] * 10
    r = resolve_value_unit(_frame(prices), schema_version="X0202")
    assert (r.unit, r.source, r.ambiguous) == ("dollars", "schema", True)


@pytest.mark.parametrize("rows", [2, 3, 9])
def test_a_thin_unanimous_sample_still_scales_but_is_flagged(rows):
    """Small filings that genuinely report thousands keep being scaled (edgartools-mun2).

    Measured over the SEC 13F data sets for Dec 2025 - Aug 2026: of 151 small
    filings with a sub-dollar fraction of at least 0.35, 99 report thousands. So
    a thin sample outside the dead band still decides by price, but is flagged
    ambiguous so the 1000x conversion warns rather than passing silently.
    """
    r = resolve_value_unit(_frame([0.13] * rows), schema_version="X0202")
    assert (r.unit, r.source, r.ambiguous, r.multiplier) == ("thousands", "implied_prices", True, 1000)
    assert r.priceable_rows == rows
