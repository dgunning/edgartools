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

Lines starting with ``#>`` are shown output: each must appear in the rendered
result of the block.

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


def _numbers(df: pd.DataFrame) -> set[float]:
    values = pd.to_numeric(df.select_dtypes(exclude="bool").stack(), errors="coerce").dropna()
    return set(values.astype(float))


# Apple 10-K for FY2025, accession 0000320193-25-000079 (data.sec.gov companyconcept,
# RevenueFromContractWithCustomerExcludingAssessedTax, 2024-09-29 to 2025-09-27).
AAPL_FY2025_REVENUE = 416_161_000_000
# Microsoft 10-K for FY2026, accession 0001193125-26-323660 (same concept,
# 2025-07-01 to 2026-06-30).
MSFT_FY2026_REVENUE = 331_839_000_000
TESLA_CIK = 1318605


def check_aapl_income_statement(result, ns):
    assert AAPL_FY2025_REVENUE in _numbers(result.to_dataframe())


def check_identity(result, ns):
    assert ns["_identities"] == ["your.name@example.com"]


def check_quick_start(result, ns):
    from edgar.ownership import Form4
    assert isinstance(result, Form4)
    assert int(result.issuer.cik) == 320193


def check_msft_financials(result, ns):
    assert MSFT_FY2026_REVENUE in _numbers(result.to_dataframe())


def check_tsla_form4(result, ns):
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert int(ns["form4"].issuer.cik) == TESLA_CIK


def check_thirteenf(result, ns):
    from edgar.thirteenf import ThirteenF
    assert isinstance(ns["thirteenf"], ThirteenF)
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert "Value" in result.columns


def check_eightk(result, ns):
    from edgar.company_reports import EightK
    assert isinstance(ns["eightk"], EightK)
    assert result, "the latest 8-K reported no items"
    assert all(re.search(r"\d+\.\d{2}", str(item)) for item in result), result


def check_facts_revenue(result, ns):
    assert isinstance(result, pd.DataFrame)
    assert AAPL_FY2025_REVENUE in _numbers(result)


# Key: a fragment unique to one README block. Value: the check for its result.
CHECKS = {
    "# Apple's latest income statement": check_aapl_income_statement,
    'set_identity("your.name@example.com")': check_identity,
    "# The latest insider Form 4 as a structured object": check_quick_start,
    'Company("MSFT").get_financials()': check_msft_financials,
    'Company("TSLA").get_filings(form="4")': check_tsla_form4,
    'get_filings(form="13F-HR")': check_thirteenf,
    'get_filings(form="8-K")': check_eightk,
    'by_concept("Revenue")': check_facts_revenue,
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
    exec(compile(ast.Module(body=body, type_ignores=[]), "<README>", "exec"), ns)
    return eval(compile(ast.Expression(last.value), "<README>", "eval"), ns) if last else None


def rendered(value) -> str:
    from edgar.richtools import repr_rich
    try:
        return repr_rich(value, strip_ansi=True)
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
            text = rendered(result)
            missing = [s for s in shown if s not in text]
            assert not missing, f"README.md:{line} shows output not in the result: {missing}"
