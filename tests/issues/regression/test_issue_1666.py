"""Regression: ``get_revenue()`` returned a bank's deposit service-charge line as
total revenue when the statement has no total row.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1666

The bank rule (edgartools-hmj0j: on a bank-layout statement with no total row,
read a non-dimensional us-gaap:Revenues fact or report None) ran only after the
contract-revenue search. Auburn National tags "Service charge on deposit
accounts" with us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax, so
that search answered first with $603K, a fee line inside noninterest income.
"""
from pathlib import Path

import pandas as pd
import pytest

from edgar.financials import Financials

AUBN = Path("tests/fixtures/xbrl/aubn/10k_2023")


def _stub(rows):
    df = pd.DataFrame(
        [{'concept': c, 'label': lbl, 'abstract': False, '2023-12-31': v} for c, lbl, v in rows])
    financials = Financials(object())
    financials._render_statement_frame = lambda statement_type: (None, df.copy())
    return financials


@pytest.mark.fast
def test_a_bank_contract_revenue_fee_line_is_not_total_revenue():
    financials = _stub([
        ('us-gaap_InterestIncomeExpenseNet', 'Net interest income', 26328000),
        ('us-gaap_RevenueFromContractWithCustomerIncludingAssessedTax', 'Service charge on deposit accounts', 603000),
        ('us-gaap_NoninterestIncome', 'Total noninterest income', -2981000),
    ])
    assert financials.get_revenue() is None


@pytest.mark.fast
def test_a_non_bank_whose_top_line_is_contract_revenue_is_unchanged():
    financials = _stub([
        ('us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax', 'Net sales', 383285000000),
        ('us-gaap_CostOfGoodsAndServicesSold', 'Cost of sales', 214137000000),
    ])
    assert financials.get_revenue() == 383285000000


@pytest.mark.fast
def test_auburn_reports_no_revenue_rather_than_its_service_charge_line():
    """Auburn National 10-K FY2023, 0001193125-24-067944 (fixture). The statement of
    earnings has no total revenue row; Service charge on deposit accounts is 603
    (2022: 598) $K, and the only us-gaap:Revenues facts are dimensioned
    (ParentCompanyMember 3,784 and 3,797), so there is no consolidated total."""
    from edgar.xbrl import XBRL

    auburn = Financials(XBRL.from_directory(AUBN))
    contract = auburn.xb.facts.query().by_concept(
        'us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax', exact=True).to_dataframe()
    assert sorted(contract['numeric_value']) == [598000.0, 603000.0]
    revenues = auburn.xb.facts.query().by_concept('us-gaap:Revenues', exact=True).to_dataframe()
    assert sorted(revenues['numeric_value']) == [3784000.0, 3797000.0]
    assert revenues['is_dimensioned'].astype(bool).all()

    assert auburn._is_bank_income_statement()
    assert auburn.get_revenue() is None
    assert auburn.get_revenue(1) is None
    assert auburn.get_financial_metrics()['revenue'] is None
