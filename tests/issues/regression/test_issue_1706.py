"""Company.md, XBRL.md and Statement.md taught calls that fail.

The reference pages ``edgar/entity/docs/Company.md``, ``edgar/xbrl/docs/Statement.md`` and
``edgar/xbrl/docs/XBRL.md`` ship in the package, are served by ``.docs`` and are copied
into the AI skill's ``api-reference/``. Their examples raised ``KeyError`` (label lookups
on a RangeIndex, ``'dimensions'``, ``'end'``), ``TypeError`` (subtracting text columns,
``count=``), ``AttributeError`` (``Statement.periods``, ``equity_statement``) or
returned nothing (``period_filter='2024'``, ``by_dimension('Segment')``,
``entity_info`` keys that do not exist), and ``Company("INVALID")`` raises rather than
returning a placeholder.

The corrected pages are executed here, every python block as written, against Apple's
FY2023 10-K fixture (accession 0000320193-23-000106), so they cannot drift again.
Blocks that draw a chart need matplotlib, which is not a dependency, and are left out;
``company`` is a stand-in that hands back the fixture's filing.

Ground truth (Apple FY2023 consolidated statements, USD): net sales 383,285 million for
the year ended 2023-09-30 against 394,328 million a year earlier (-2.80%); iPhone net
sales 200,583 million; total assets 352,583 million.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1706
"""
import re
import textwrap
import types

import pandas as pd
import pytest

from edgar import Company
from edgar.exceptions import CompanyNotFoundError
from edgar.xbrl import XBRL
from tests.paths import FIXTURES_DIR, REPO_ROOT

AAPL_FY2023 = FIXTURES_DIR / "xbrl" / "aapl" / "10k_2023"
STATEMENT_MD = "edgar/xbrl/docs/Statement.md"
XBRL_MD = "edgar/xbrl/docs/XBRL.md"
COMPANY_MD = "edgar/entity/docs/Company.md"


def python_blocks(page):
    text = (REPO_ROOT / page).read_text(encoding="utf-8")
    return [textwrap.dedent(b) for b in re.findall(r"```python\n(.*?)```", text, re.DOTALL)]


@pytest.fixture(autouse=True)
def in_tmp_dir(tmp_path, monkeypatch):
    """The pages export CSV files to the working directory."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture(scope="module")
def xbrl():
    return XBRL.from_directory(AAPL_FY2023)


def namespace(xbrl):
    """What the pages assume is already defined."""
    filing = types.SimpleNamespace(xbrl=lambda: xbrl, filing_date="2023-11-03")
    filings = types.SimpleNamespace(latest=lambda: filing, head=lambda n: [filing] * min(n, 2))
    company = types.SimpleNamespace(get_filings=lambda **kwargs: filings)
    return {
        "pd": pd, "xbrl": xbrl, "filing": filing, "company": company,
        "income": xbrl.statements.income_statement(),
        "balance": xbrl.statements.balance_sheet(),
        "cashflow": xbrl.statements.cash_flow_statement(),
        "statement": xbrl.statements.income_statement(),
    }


def run_page(page, xbrl):
    """Run every python block on `page` in one namespace, the way a reader pastes them."""
    ns = namespace(xbrl)
    ran = 0
    for number, block in enumerate(python_blocks(page)):
        if "matplotlib" in block:
            continue
        try:
            exec(compile(block, f"{page}#block{number}", "exec"), ns)  # noqa: S102 - our own docs
        except Exception as error:
            pytest.fail(f"{page} python block {number} raised {type(error).__name__}: {error}\n{block}")
        ran += 1
    return ns, ran


@pytest.mark.fast
def test_statement_page_runs(xbrl):
    ns, ran = run_page(STATEMENT_MD, xbrl)
    assert ran >= 35
    amounts = ns["amounts"](ns["income"])
    assert amounts.columns.tolist() == ["2023-09-30 (FY)", "2022-09-24 (FY)", "2021-09-25 (FY)"]
    assert amounts.loc["Net sales", "2023-09-30 (FY)"] == 383_285_000_000.0
    assert amounts.loc["Net sales", "2022-09-24 (FY)"] == 394_328_000_000.0
    growth = ((amounts.iloc[:, 0] - amounts.iloc[:, 1]) / amounts.iloc[:, 1] * 100).round(2)
    assert growth["Net sales"] == -2.8


@pytest.mark.fast
def test_period_filter_takes_a_period_key_not_a_year(xbrl):
    income = xbrl.statements.income_statement()
    kept = income.to_dataframe(period_filter="duration_2022-09-25_2023-09-30")
    assert [c for c in kept.columns if c[:4].isdigit()] == ["2023-09-30 (FY)"]
    assert income.to_dataframe(period_filter="2023").shape == (0, 0)
    assert [c for c in xbrl.statements.balance_sheet().to_dataframe(period_filter="instant_2023-09-30").columns
            if c[:4].isdigit()] == ["2023-09-30"]


@pytest.mark.fast
def test_xbrl_page_runs(xbrl):
    ns, ran = run_page(XBRL_MD, xbrl)
    assert ran >= 35
    # Method 2 on the page: the filer's own revenue concept, undimensioned, newest first
    assert ns["latest_revenue"] == 383_285_000_000.0
    assert ns["metrics"]["Revenue"] == 383_285_000_000.0
    assert ns["metrics"]["Total Assets"] == 352_583_000_000.0
    # by_dimension on the product axis, FY2023
    assert ns["segment_totals"]["aapl:IPhoneMember"] == 200_583_000_000.0
    assert ns["entity_info"].get("ticker") == "AAPL"
    assert ns["entity_info"].get("fiscal_year") == "2023"
    assert len(ns["recent_facts"]) == 918


@pytest.mark.fast
def test_the_calls_the_pages_stopped_using_still_fail(xbrl):
    """Pins why the pages changed, so the old examples are not reinstated."""
    statements = xbrl.statements
    assert not hasattr(statements, "equity_statement")
    assert not hasattr(statements.income_statement(), "periods")
    df = statements.income_statement().to_dataframe()
    assert "Revenue" not in df.index
    with pytest.raises(KeyError):
        df.loc["Revenue"]
    assert xbrl.entity_info.get("trading_symbol") is None
    assert len(xbrl.facts.query().by_concept("Revenue").by_dimension("Segment", "ProductSegment").to_dataframe()) == 0
    with pytest.raises(KeyError):
        xbrl.facts.query().by_custom(lambda fact: fact["end"] >= "2022-01-01").to_dataframe()


@pytest.mark.vcr
def test_issue_1706_company_not_found_examples():
    blocks = [b for b in python_blocks(COMPANY_MD) if "Company(9999999999)" in b]
    assert len(blocks) == 1
    with pytest.raises(CompanyNotFoundError):
        Company("INVALID")
    ns = {"Company": Company}
    exec(compile(blocks[0], COMPANY_MD, "exec"), ns)  # noqa: S102 - our own docs
    assert ns["company"].not_found is True


@pytest.mark.vcr
def test_issue_1706_get_filings_takes_head_not_count():
    company = Company("AAPL")
    with pytest.raises(TypeError):
        company.get_filings(form="10-Q", count=4)
    assert len(company.get_filings(form="10-Q").head(4)) == 4
