"""Regression: a position whose identifier ends in its coupon is kept and typed.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1504

``_parse_investment_identifier`` types any identifier ending in a bracketed
percent as ``Unknown``, a rule written for category roll-ups such as Hercules'
"Debt Investments Software (52.80%)", and ``from_xbrl`` drops ``Unknown`` rows.
PhenixFIN ends a real loan with its coupon:

    Affiliated Investments - Advocates for Disabled Vets, LLC (dba Reps for Vets)
    - Services: Consumer - Senior Secured Delayed Draw Term Loan (14.00%)

so the loan left the portfolio with no warning. The two cases differ in what
they state: the loan states a principal amount, and none of the 52 roll-ups in
Hercules' 10-Q for 2024-09-30 does (they state cost, so cost cannot separate them).
"""
from decimal import Decimal

import pytest

from edgar.bdc.investments import PortfolioInvestment, PortfolioInvestments

PFX_LOAN = ('Affiliated Investments - Advocates for Disabled Vets, LLC (dba Reps for Vets) - '
            'Services: Consumer - Senior Secured Delayed Draw Term Loan (14.00%)')


@pytest.mark.fast
def test_a_coupon_suffixed_row_with_principal_is_typed():
    from edgar.bdc.investments import _type_coupon_suffixed

    row = PortfolioInvestment(identifier=PFX_LOAN, company_name=PFX_LOAN, investment_type='Unknown',
                              fair_value=Decimal('221625'), cost=Decimal('225132'),
                              principal_amount=Decimal('225000'))
    typed = _type_coupon_suffixed(row)
    assert typed.investment_type == 'Senior Secured Delayed Draw Term Loan'
    assert typed.company_name == 'Advocates for Disabled Vets, LLC (dba Reps for Vets)'
    assert typed.identifier == PFX_LOAN


@pytest.mark.fast
def test_a_roll_up_without_principal_stays_unknown():
    from edgar.bdc.investments import _type_coupon_suffixed

    row = PortfolioInvestment(identifier='Debt Investments Software (52.80%)',
                              company_name='Debt Investments Software (52.80%)', investment_type='Unknown',
                              fair_value=Decimal('1050563000'), cost=Decimal('1091349000'))
    assert _type_coupon_suffixed(row) is row


@pytest.mark.network
@pytest.mark.vcr
def test_phenixfin_keeps_its_delayed_draw_loan():
    """Ground truth: PhenixFIN 10-Q for 2026-06-30, accession 0001213900-26-085667."""
    from edgar import find

    portfolio = PortfolioInvestments.from_xbrl(find('0001213900-26-085667').xbrl())
    loan = [i for i in portfolio if i.identifier == PFX_LOAN]
    assert [(i.fair_value, i.cost, i.principal_amount, i.investment_type) for i in loan] == [
        (Decimal('221625'), Decimal('225132'), Decimal('225000'), 'Senior Secured Delayed Draw Term Loan')]


@pytest.mark.network
@pytest.mark.vcr
def test_hercules_roll_ups_stay_excluded():
    """Hercules' 10-Q for 2024-09-30, accession 0001280784-24-000026, files 52 roll-ups ending in a percent."""
    from edgar import find

    xbrl = find('0001280784-24-000026').xbrl()
    portfolio = PortfolioInvestments.from_xbrl(xbrl)
    untyped = PortfolioInvestments.from_xbrl(xbrl, include_untyped=True)
    software = [i for i in untyped if i.identifier == 'Debt Investments Software (53.06%)']
    assert [(i.investment_type, i.fair_value, i.principal_amount) for i in software] == [
        ('Unknown', Decimal('982622000'), None)]
    assert [i.identifier for i in portfolio if i.identifier.endswith('%)')] == []
    assert len(portfolio) == 331
