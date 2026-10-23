"""The ownership skill's "Screen Large Transactions" pattern matched only net purchases.

Its ``when`` text said "Find significant insider activity", but the predicate
``net_change > 10000 and net_value > 100000`` is False for every net sale, because
``net_change`` and ``net_value`` are negative for sales. Over 30 Apple Form 4 filings it
printed nothing although six were large sales.

The pattern now tests ``abs()`` and says it finds purchases and sales. The code is
executed here as written in ``edgar/ai/skills/ownership/skill.yaml``.

Ground truth: Apple Form 4 0001140361-26-038674 (filed 2026-10-05), Timothy D. Cook:
four open-market sales (code S) of 23,143 + 39,492 + 88,239 + 40,879 = 191,753 shares,
$63,845,841.04 at the filer's weighted-average prices.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1716
"""
import pytest
import yaml

from edgar import Filing
from tests.paths import REPO_ROOT

SKILL = REPO_ROOT / "edgar/ai/skills/ownership/skill.yaml"
COOK_FORM4 = "0001140361-26-038674"


def pattern():
    patterns = yaml.safe_load(SKILL.read_text(encoding="utf-8"))["patterns"]
    return next(p for p in patterns if p["name"] == "Screen Large Transactions")


class FakeCompany:
    def __init__(self, filings):
        self.filings = filings

    def get_filings(self, form):
        return self.filings


@pytest.mark.vcr
def test_issue_1716_large_net_sale_is_printed(capsys):
    filing = Filing(form="4", filing_date="2026-10-05", company="Apple Inc.", cik=320193,
                    accession_no=COOK_FORM4)
    summary = filing.obj().get_ownership_summary()
    assert summary.insider_name == "Timothy D Cook"
    assert summary.net_change == -191_753
    assert summary.net_value == pytest.approx(-63_845_841.04)

    code = pattern()["code"]
    exec(compile(code, "skill.yaml", "exec"), {"company": FakeCompany([filing])})  # noqa: S102
    assert capsys.readouterr().out == "Timothy D Cook: -191,753 shares (-63,845,841 USD)\n"

    # The old predicate printed nothing for this filing
    assert not (summary.net_change > 10000 and summary.net_value > 100000)


@pytest.mark.fast
def test_pattern_says_it_covers_sales_and_how_net_is_counted():
    p = pattern()
    assert "purchases or sales" in p["when"]
    assert "abs(summary.net_change) > 10000" in p["code"]
    assert "minus open-market sales (code S)" in p["note"]
