"""``get_financial_metrics()['debt_to_assets']`` had no stated definition.

The value is total liabilities (``us-gaap:Liabilities``) divided by total assets. The
docstring and the extraction guide said nothing about the numerator, while
``FormC.debt_to_asset_ratio`` uses the same name for borrowings over assets, as a
percentage. The number is unchanged; the docstring and guide now define it.

Ground truth: Apple FY2023 10-K, accession 0000320193-23-000106 (filed 2023-11-03),
balance sheet at 2023-09-30, USD millions: total assets 352,583; total liabilities
290,437 (so 290,437 / 352,583 = 0.8237); commercial paper 5,985, current term debt
9,822 and non-current term debt 95,281, which are 0.3151 of assets.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1729
"""
from pathlib import Path

import pytest

from edgar.financials import Financials
from edgar.xbrl import XBRL

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl" / "aapl" / "10k_2023"
GUIDE = Path(__file__).resolve().parents[3] / "docs" / "guides" / "extract-statements.md"


@pytest.fixture(scope="module")
def metrics():
    return Financials(XBRL.from_directory(FIXTURE)).get_financial_metrics()


@pytest.mark.fast
def test_debt_to_assets_is_liabilities_over_assets(metrics):
    assert metrics["total_assets"] == 352_583_000_000
    assert metrics["total_liabilities"] == 290_437_000_000
    assert metrics["debt_to_assets"] == pytest.approx(290_437 / 352_583)
    borrowings = (5_985 + 9_822 + 95_281) * 1_000_000
    assert borrowings / metrics["total_assets"] == pytest.approx(0.3151, abs=1e-4)
    assert metrics["debt_to_assets"] != pytest.approx(borrowings / metrics["total_assets"], abs=0.1)


@pytest.mark.fast
def test_docstring_defines_the_ratio():
    doc = " ".join(Financials.get_financial_metrics.__doc__.split())
    assert "``debt_to_assets``: ``total_liabilities / total_assets``" in doc
    assert "us-gaap:Liabilities" in doc
    assert "not only borrowings" in doc


@pytest.mark.fast
def test_guide_defines_the_ratio():
    guide = " ".join(GUIDE.read_text(encoding="utf-8").split())
    assert "`debt_to_assets` is **total liabilities divided by total assets**" in guide
    assert "290,437 / 352,583 = 0.82" in guide
