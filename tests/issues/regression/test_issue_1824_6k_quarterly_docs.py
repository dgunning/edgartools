"""get_quarterly_financials() returns None for TSM, and the docs did not say why.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1824

TSMC files its quarterly results on Form 6-K as an HTML press release (EX-99)
with no XBRL, so ``get_quarterly_financials()`` has no statements to read and
returns ``None``, which is the 6.0 contract (docs/upgrade/6.0.md). The guide now
says so and points to ``EarningsRelease``. This runs the documented example as
written in docs/guides/financial-data.md.

Ground truth: TSMC 6-K 0001046179-26-000726 (filed 2026-10-15), exhibit
a3q26e_withguidancexfinal.htm, unit "NT$ million": 3Q26 net income 763,064
and 3Q25 net income 452,302.
"""
import pytest

from edgar import Company, find
from edgar.earnings import EarningsRelease
from tests.paths import REPO_ROOT


@pytest.mark.vcr
def test_documented_6k_quarterly_example():
    assert Company("TSM").get_quarterly_financials() is None

    filing = find("0001046179-26-000726")
    release = EarningsRelease.from_filing(filing)
    df = release.income_statement.dataframe

    net_income = df.loc["Net income"]
    assert net_income.iloc[0] == 763064
    assert net_income.iloc[1] == 452302


def test_guide_shows_the_example_this_test_runs():
    guide = (REPO_ROOT / "docs" / "guides" / "financial-data.md").read_text(encoding="utf-8")

    assert 'find("0001046179-26-000726")' in guide
    assert "EarningsRelease.from_filing(filing)" in guide
    assert "763,064" in guide
