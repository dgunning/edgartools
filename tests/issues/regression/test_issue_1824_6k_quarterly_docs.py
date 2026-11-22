"""Read a particular historical 6-K through the documented EarningsRelease API.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1824

Ground truth: TSMC 6-K 0001046179-26-000726 (filed 2026-10-15), exhibit
a3q26e_withguidancexfinal.htm, unit "NT$ million": 3Q26 net income 763,064
and 3Q25 net income 452,302.
"""
import pytest

from edgar import find
from edgar.earnings import EarningsRelease
from tests.paths import REPO_ROOT


@pytest.mark.vcr
def test_documented_6k_quarterly_example():
    filing = find("0001046179-26-000726")
    release = EarningsRelease.from_filing(filing)
    assert release.income_statement.currency == "TWD"
    df = release.income_statement.dataframe

    net_income = df.loc["Net income"]
    assert net_income.iloc[0] == 763064
    assert net_income.iloc[1] == 452302


def test_guide_shows_the_example_this_test_runs():
    guide = (REPO_ROOT / "docs" / "guides" / "financial-data.md").read_text(encoding="utf-8")

    assert 'find("0001046179-26-000726")' in guide
    assert "EarningsRelease.from_filing(filing)" in guide
    assert "763,064" in guide
