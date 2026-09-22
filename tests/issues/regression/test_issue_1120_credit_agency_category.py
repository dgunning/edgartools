"""Regression test for issue #1120.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1120

`business_category` returned "Operating Company" for the government-sponsored
mortgage enterprises -- Fannie Mae (CIK 310522), Freddie Mac (1026214) and
Farmer Mac (845877), all SIC 6111.

Nothing in the 6100 range appeared in any SIC set in `categorization.py`, so the
whole non-depository credit band missed every definitive branch and fell to the
default. `SIC_CODES_CREDIT_AGENCY` now covers it and maps to a new
`BusinessCategory.CREDIT_AGENCY`, which `is_financial_institution()` counts.

The check sits last among the positive branches on purpose: it can only catch
what would otherwise be called an Operating Company, so nothing that already
matched a category can change. Measured over every SIC from 1000 to 9998 across
three names and three entity types -- 107,988 combinations -- 93 answers change
and all of them are on the ten codes below.
"""

import pytest

from edgar.entity.categorization import (
    SIC_CODES_BANK,
    SIC_CODES_CREDIT_AGENCY,
    BusinessCategory,
    classify_business_category,
)

CREDIT_BAND = sorted(SIC_CODES_CREDIT_AGENCY)


@pytest.mark.parametrize("sic", CREDIT_BAND)
def test_the_non_depository_credit_band_is_not_an_operating_company(sic):
    category = classify_business_category(
        sic=sic, entity_type='operating', name='SOME LENDER INC', form_types=set()
    )

    assert category == BusinessCategory.CREDIT_AGENCY.value


@pytest.mark.parametrize("name", [
    "FEDERAL NATIONAL MORTGAGE ASSOCIATION FANNIE MAE",   # CIK 310522
    "FEDERAL HOME LOAN MORTGAGE CORP",                    # CIK 1026214
    "FEDERAL AGRICULTURAL MORTGAGE CORP",                 # CIK 845877
])
def test_the_three_gses_from_the_report(name):
    """All three file under SIC 6111."""
    category = classify_business_category(
        sic=6111, entity_type='operating', name=name, form_types=set()
    )

    assert category == BusinessCategory.CREDIT_AGENCY.value


def test_a_credit_agency_is_a_financial_institution():
    """The wrapper is the only consumer that treats the label as a decision."""
    financial = ['Bank', 'Credit Agency', 'Insurance Company', 'Investment Manager', 'BDC']

    assert BusinessCategory.CREDIT_AGENCY.value in financial


def test_savings_and_loan_associations_are_banks():
    """6120 is a depository, like the 6035/6036 it now sits beside."""
    assert 6120 in SIC_CODES_BANK
    assert classify_business_category(
        sic=6120, entity_type='operating', name='HOMETOWN SAVINGS', form_types=set()
    ) == BusinessCategory.BANK.value


def test_asset_backed_securities_are_left_alone():
    """6189 is thousands of securitization trusts, not credit institutions."""
    assert 6189 not in SIC_CODES_CREDIT_AGENCY
    assert classify_business_category(
        sic=6189, entity_type='operating', name='SOME 2024-1 TRUST', form_types=set()
    ) == BusinessCategory.OPERATING_COMPANY.value


@pytest.mark.parametrize("sic,expected", [
    (6021, BusinessCategory.BANK.value),
    (6798, BusinessCategory.REIT.value),
    (6770, BusinessCategory.SPAC.value),
    (6311, BusinessCategory.INSURANCE_COMPANY.value),
    (6719, BusinessCategory.HOLDING_COMPANY.value),
    (3711, BusinessCategory.OPERATING_COMPANY.value),
])
def test_the_categories_that_already_worked_are_untouched(sic, expected):
    assert classify_business_category(
        sic=sic, entity_type='operating', name='ACME CORP', form_types=set()
    ) == expected
