"""
README-as-test: every fenced ``python`` block in README.md runs, and its result
is checked (bead edgartools-07lk.19.11).

The README's ``financials.income_statement`` example broke at least four times in
user reports (#266, #288, #619, #1424) before anyone here noticed. This file makes
README drift a test failure.

Blocks run in order in one namespace, the way a reader pastes them: the Quick
Start's ``from edgar import *`` is what the later Use Case blocks rely on. Each
block's last line is evaluated and handed to the check in ``CHECKS`` whose key
appears in the block. A block with no check, or with two, fails the fast lane,
so a new README example cannot ship without an assertion.

Lines starting with ``#>`` are shown output: each must appear in the result of
the block as rendered 200 columns wide, compared with runs of whitespace
collapsed, so column padding and terminal width do not count as drift.

The network lane runs live, without a cassette. The examples call ``.latest()``
and the current quarter's index, so a recording would stop matching the URLs
the code asks for as soon as the quarter turns. The value assertions are pinned
to periods that stay in the comparative columns for at least two more annual
filings.
"""
import ast
import re
from pathlib import Path

import pandas as pd
import pytest

README = Path(__file__).resolve().parents[2] / "README.md"

FENCE = re.compile(r"^```python[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)


def readme_python_blocks() -> list[tuple[int, str]]:
    """(line number, source) for each fenced python block in README.md."""
    text = README.read_text(encoding="utf-8")
    return [(text.count("\n", 0, m.start()) + 1, m.group(1)) for m in FENCE.finditer(text)]


# Ground truth, read from data.sec.gov (companyconcept / submissions / EFTS), not
# through this library. Each names the filing it came from.
#
# NVIDIA 10-K FY2026, 0001045810-26-000021: us-gaap:Revenues 2025-01-27..2026-01-25.
NVDA_FY2026_REVENUE = 215_938_000_000
# NVIDIA 10-Q, 0001045810-25-000116: us-gaap:Revenues 2025-01-27..2025-04-27 (fiscal Q1 2026).
NVDA_Q1_FY2026_REVENUE = 44_062_000_000
# Microsoft 10-K FY2026, 0001193125-26-323660: Revenue 2025-07-01..2026-06-30.
MSFT_FY2026_REVENUE = 331_839_000_000
# FY2025 10-Ks: JPMorgan 0001628280-26-008131 (us-gaap:Revenues), Pfizer
# 0000078003-26-000026 (us-gaap:Revenues), Exxon 0000034088-26-000045 (us-gaap:Revenues).
FY2025_REVENUE_BILLIONS = {"JPM": 182.4, "PFE": 62.6, "XOM": 332.2}  # 182,447 / 62,579 / 332,238 M
# EFTS: forms=8-K&items=1.05&startdt=2025-01-01&enddt=2025-12-31 -> total 19 (relation eq).
ITEM_105_8KS_IN_2025 = 19
# NVIDIA 8-K 2026-08-26, 0001045810-26-000073, items "2.02,9.01" in the submissions JSON.
NVDA_EARNINGS_8K_ITEMS = ["Item 2.02", "Item 9.01"]
APPLE_CIK, NVIDIA_CIK, TESLA_CIK, BERKSHIRE_CIK = 320193, 1045810, 1318605, 1067983


def _revenue_row(statement) -> pd.Series:
    df = statement.to_dataframe()
    return df.loc[df.label == "Total Revenue"].iloc[0]


def check_identity(result, ns):
    assert ns["_identities"] == ["your.name@example.com"]


def check_nvda_five_years(result, ns):
    row = _revenue_row(result)
    assert row["FY 2026"] == NVDA_FY2026_REVENUE
    assert len([c for c in row.index if c.startswith("FY ")]) == 5


def check_search(result, ns):
    from edgar import Filing
    assert result.total == ITEM_105_8KS_IN_2025
    assert all(r.form.startswith("8-K") for r in result)
    tariff_hits = ns["results"]
    assert len(tariff_hits) > 0
    # start_date alone: EFTS ignores a one-sided range unless both bounds are
    # sent, so this also guards edgartools-329yu
    assert all(str(r.filed) >= "2025-01-01" for r in tariff_hits), (
        "the date range was not applied"
    )
    assert all(r.form.startswith("10-K") for r in tariff_hits)
    hit = ns["hit"]
    assert re.fullmatch(r"\d{10}-\d{2}-\d{6}", hit.accession_number)
    assert hit.form.startswith("10-K") and hit.filed >= "2025-01-01" and hit.company
    assert isinstance(hit.get_filing(), Filing)
    assert hit.get_filing().accession_no == hit.accession_number


def check_msft_ten_years(result, ns):
    row = _revenue_row(result)
    assert MSFT_FY2026_REVENUE in set(row.values)
    assert len([c for c in row.index if c.startswith("FY ")]) == 10


def check_metric_across_companies(result, ns):
    assert result.loc["FY 2025"].to_dict() == FY2025_REVENUE_BILLIONS


def check_quarterly_and_ttm(result, ns):
    row = _revenue_row(result)
    quarters = [c for c in row.index if c.startswith("Q")]
    assert len(quarters) == 8
    if "Q1 2026" in quarters:  # rolls out of an 8-quarter window in 2027
        assert row["Q1 2026"] == NVDA_Q1_FY2026_REVENUE
    if {"Q1 2026", "Q2 2026", "Q3 2026", "Q4 2026"} <= set(quarters):
        # Q4 has no 10-Q: it is the fiscal year less the first three quarters
        first_three = row["Q1 2026"] + row["Q2 2026"] + row["Q3 2026"]
        assert row["Q4 2026"] == NVDA_FY2026_REVENUE - first_three
    ttm = ns["nvda"].get_ttm_revenue()
    assert ttm.value == sum(row[q] for q in quarters[:4]), "TTM is not the last four quarters"


def check_sections(result, ns):
    assert ns["filing"].form == "10-K"
    assert int(ns["filing"].cik) == NVIDIA_CIK
    assert len(ns["filing"].markdown()) > 100_000
    assert len(ns["tenk"].risk_factors) > 10_000
    assert result.startswith("Item 1C") and "Cybersecurity" in result[:200]


def check_find(result, ns):
    assert result.accession_no == "0000320193-25-000079"
    assert result.form == "10-K"
    assert int(result.cik) == APPLE_CIK


def check_thirteenf(result, ns):
    from edgar.thirteenf import ThirteenF
    assert isinstance(ns["thirteenf"], ThirteenF)
    assert int(ns["thirteenf"].filing.cik) == BERKSHIRE_CIK
    assert isinstance(result, pd.DataFrame) and not result.empty
    # the README names these columns; the share count is SharesPrnAmount, not Shares
    assert {"Issuer", "Cusip", "Ticker", "SharesPrnAmount", "Value"} <= set(result.columns)


def check_tsla_form4(result, ns):
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert int(ns["form4"].issuer.cik) == TESLA_CIK


def check_fund_portfolio(result, ns):
    assert isinstance(result, pd.DataFrame)
    assert len(result) > 400  # VOO holds the S&P 500
    assert "NVDA" in set(result["ticker"])


def check_eightk_earnings(result, ns):
    from edgar.company_reports import EightK
    assert isinstance(ns["eightk"], EightK)
    assert ns["eightk"].items == NVDA_EARNINGS_8K_ITEMS
    assert result is not None, "the earnings exhibit was not parsed"
    assert result.income_statement is not None


# Key: a fragment unique to one README block. Value: the check for its result.
CHECKS = {
    'set_identity("your.name@example.com")': check_identity,
    'Company("NVDA").income_statement(periods=5)': check_nvda_five_years,
    'items="1.05"': check_search,
    'income_statement(periods=10)': check_msft_ten_years,
    '["JPM", "PFE", "XOM"]': check_metric_across_companies,
    'period="quarterly"': check_quarterly_and_ttm,
    'latest("10-K")': check_sections,
    'find("0000320193-25-000079")': check_find,
    'form="13F-HR"': check_thirteenf,
    'Company("TSLA").get_filings(form="4")': check_tsla_form4,
    'Fund("VOO")': check_fund_portfolio,
    'find("0001045810-26-000073")': check_eightk_earnings,
}


def check_for(source: str):
    return [check for key, check in CHECKS.items() if key in source]


@pytest.mark.fast
def test_every_readme_python_block_has_one_check():
    blocks = readme_python_blocks()
    assert blocks, f"no ```python blocks found in {README}"
    problems = []
    for line, source in blocks:
        ast.parse(source)  # a README example that is not valid Python fails here
        n = len(check_for(source))
        if n != 1:
            problems.append(f"README.md:{line} matches {n} checks in CHECKS")
    assert not problems, "\n".join(problems)
    used = {key for key in CHECKS for _, source in blocks if key in source}
    assert used == set(CHECKS), f"CHECKS keys no README block contains: {set(CHECKS) - used}"


def run_block(source: str, ns: dict):
    """Exec the block and return the value of its final expression, like a REPL."""
    tree = ast.parse(source)
    last = tree.body[-1] if tree.body and isinstance(tree.body[-1], ast.Expr) else None
    body = tree.body[:-1] if last else tree.body
    exec(compile(ast.Module(body=body, type_ignores=[]), "<README>", "exec"), ns)  # noqa: S102 - our own README, not user input
    return eval(compile(ast.Expression(last.value), "<README>", "eval"), ns) if last else None  # noqa: S307 - our own README


def rendered(value) -> str:
    from edgar.richtools import repr_rich
    try:
        return repr_rich(value, strip_ansi=True, width=200)
    except Exception:
        return str(value)


@pytest.mark.network
def test_readme_python_blocks_run_and_their_results_check_out(monkeypatch):
    import edgar
    identities = []
    # The Quick Start sets a placeholder identity; record it instead of sending it to SEC.
    monkeypatch.setattr(edgar, "set_identity", identities.append)
    ns = {"__name__": "__readme__", "_identities": identities}
    for line, source in readme_python_blocks():
        try:
            result = run_block(source, ns)
        except Exception as exc:
            raise AssertionError(f"README.md:{line} raised {type(exc).__name__}: {exc}\n{source}") from exc
        (check,) = check_for(source)
        try:
            check(result, ns)
        except AssertionError as exc:
            raise AssertionError(f"README.md:{line} result failed {check.__name__}: {exc}\n{source}") from exc
        shown = [m.group(1).strip() for m in re.finditer(r"^\s*#>(.*)$", source, re.MULTILINE)]
        if shown:
            text = " ".join(rendered(result).split())
            missing = [s for s in shown if " ".join(s.split()) not in text]
            assert not missing, f"README.md:{line} shows output not in the result: {missing}"
