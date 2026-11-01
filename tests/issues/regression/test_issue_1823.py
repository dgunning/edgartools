"""Regression test for GitHub Issue #1823.

Mastercard's EntityFacts income statement had no net income row. The only row
whose label began "Net Income (Loss) Attributable to" was the noncontrolling
interest's ($21M for FY2025), so code that picked net income by label got that
figure with no error.

Mastercard's 10-K tags the income statement's net income as us-gaap:ProfitLoss,
net income including the noncontrolling interest, and never as NetIncomeLoss.
The learned mappings place ProfitLoss on the cash flow statement, which does not
feed the income statement, so its facts were dropped. The income statement now
takes ProfitLoss for a period that has no reported NetIncomeLoss, and shows it
with the other profit lines.

Measured over 50 companies before and after (annual and quarterly): five gain a
ProfitLoss row (MA, CAT, F, AMT, SPG), and no other row, value or column changes.
Ford keeps its NetIncomeLoss row for the years that have one, and ProfitLoss
fills only FY2025.

The fixture is SEC companyfacts for CIK 1141391, downloaded 2026-11-01.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1823
"""
import json
from datetime import date
from pathlib import Path

import pytest

from edgar.entity.enhanced_statement import _with_profit_loss_fallback
from edgar.entity.models import FinancialFact
from edgar.entity.parser import EntityFactsParser

pytestmark = pytest.mark.regression

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "entity" / "ma_facts.json"


@pytest.fixture(scope="module")
def ma_income():
    facts = EntityFactsParser.parse_company_facts(json.loads(FIXTURE.read_text("utf-8")))
    return facts.income_statement(periods=3, annual=True, as_dataframe=True)


def test_net_income_row_is_the_10k_profit_loss(ma_income):
    """Mastercard's FY2025 10-K (accession 0001141391-26-000013) reports
    ProfitLoss of 14,968,000,000 for 2025-01-01..2025-12-31, and FY2024's
    12,874,000,000."""
    row = ma_income.loc["ProfitLoss"]
    assert row["FY 2025"] == 14_968_000_000
    assert row["FY 2024"] == 12_874_000_000


def test_net_income_sits_with_the_profit_lines(ma_income):
    concepts = list(ma_income.index)
    assert concepts.index("IncomeTaxExpenseBenefit") < concepts.index("ProfitLoss")
    assert concepts.index("ProfitLoss") < concepts.index("NetIncomeLossAttributableToNoncontrollingInterest")
    assert ma_income.loc["NetIncomeLossAttributableToNoncontrollingInterest", "FY 2025"] == 21_000_000


def _fact(concept, value, statement_type, fiscal_period="FY", form="10-K"):
    return FinancialFact(
        concept=f"us-gaap:{concept}",
        taxonomy="us-gaap",
        label=concept,
        value=value,
        numeric_value=float(value),
        unit="USD",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        period_type="duration",
        fiscal_year=2025,
        fiscal_period=fiscal_period,
        form_type=form,
        statement_type=statement_type,
    )


def test_profit_loss_is_not_added_beside_a_reported_net_income():
    net_income = _fact("NetIncomeLoss", 100, "IncomeStatement")
    profit_loss = _fact("ProfitLoss", 105, "CashFlowStatement")
    stmt_facts = [_fact("Revenues", 1000, "IncomeStatement"), net_income]
    assert _with_profit_loss_fallback(stmt_facts, stmt_facts + [profit_loss]) == stmt_facts


def test_a_proxy_statements_net_income_does_not_block_the_fallback():
    """Mastercard's only NetIncomeLoss facts for recent years come from its DEF 14A
    pay-versus-performance table, which carries no fiscal period."""
    proxy_net_income = _fact("NetIncomeLoss", 105, "IncomeStatement", fiscal_period="", form="DEF 14A")
    profit_loss = _fact("ProfitLoss", 105, "CashFlowStatement")
    stmt_facts = [_fact("Revenues", 1000, "IncomeStatement"), proxy_net_income]
    assert _with_profit_loss_fallback(stmt_facts, stmt_facts + [profit_loss]) == stmt_facts + [profit_loss]
