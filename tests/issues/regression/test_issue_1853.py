"""PortfolioInvestments.to_dataframe() keeps a filed zero as 0.0, not NaN.

Golub Capital BDC, Inc. (GBDC), 10-Q for March 31, 2025, accession
0001476765-25-000040. The holding "PPW Aero Buyer, Inc., One stop 3" files
us-gaap:InvestmentOwnedBalancePrincipalAmount (fact f-534) and
us-gaap:InvestmentOwnedAtFairValue (fact f-537) as the literal text "0"
(context c-70, decimals -3, no xsi:nil). A genuinely absent amount stays missing.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1853
"""
from decimal import Decimal

import pandas as pd
import pytest

from edgar.bdc.investments import PortfolioInvestment, PortfolioInvestments


@pytest.mark.fast
def test_filed_zero_amounts_are_zero_not_missing():
    zero = PortfolioInvestment(
        identifier='PPW Aero Buyer, Inc., One stop 3', company_name='PPW Aero Buyer, Inc.',
        investment_type='One stop 3', fair_value=Decimal('0'), principal_amount=Decimal('0'),
        cost=Decimal('0'))
    absent = PortfolioInvestment(
        identifier='Other, Loan', company_name='Other', investment_type='Loan',
        fair_value=Decimal('34629000'))
    df = PortfolioInvestments([zero, absent]).to_dataframe()

    for column in ('fair_value', 'principal_amount', 'cost'):
        assert df[column].iloc[0] == 0.0
        assert not pd.isna(df[column].iloc[0])
    assert df['fair_value'].iloc[1] == 34629000.0
    assert pd.isna(df['principal_amount'].iloc[1])
    assert pd.isna(df['cost'].iloc[1])
