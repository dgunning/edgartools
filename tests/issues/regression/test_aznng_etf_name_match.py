"""business_category matches "ETF" only at the start or end of a word.

Bead: edgartools-aznng

classify_business_category tested ``'ETF' in name_upper``, so any name with
those three letters inside a word became an ETF. On 6.0.0
``Company('NFLX').business_category`` returned 'ETF'. The same substring test
sat in four places: the ETF-in-name step, the investment-company split (twice)
and the SIC 6211 broker check.

The name now has to contain ETF at the start or end of a word, which keeps the
real fund names a whole-word match would lose ("ETFS Asian Gold Trust",
"ETFis Series Trust I", "Innovator ETFs Trust"). Over all 563,611 names in the
SEC company list, 391 contain the letters ETF; the old and new rule disagree on
60, every one of them a mid-word match (NETFLIX, JETFLEET, STRETFORD,
MARKETFIELD, ROCKETFUEL), and every change moves the name out of ETF.

Ground truth from SEC submissions (data.sec.gov/submissions):

* Netflix, Inc.: CIK 1065280, SIC 7841, entity type operating.
* ETFS Asian Gold Trust: CIK 1496337, SIC 6221.
* ETFis Series Trust I: CIK 1559109, entity type investment.
"""

import pytest

from edgar.entity.categorization import BusinessCategory, classify_business_category

ETF = BusinessCategory.ETF.value


@pytest.mark.parametrize(
    "sic, name",
    [
        ('7841', 'NETFLIX INC'),
        ('3571', 'NETFRAME SYSTEMS INC'),
        ('7359', 'JETFLEET AIRCRAFT II LP'),
        ('7372', 'MARKETFIRST SOFTWARE INC'),
        ('7370', 'GetFugu, Inc.'),
    ],
)
def test_etf_inside_a_word_is_not_an_etf(sic, name):
    category = classify_business_category(sic, 'operating', name, {'10-K', '10-Q'})

    assert category == BusinessCategory.OPERATING_COMPANY.value


def test_netflix_is_an_operating_company():
    assert classify_business_category('7841', 'operating', 'NETFLIX INC', {'10-K', '10-Q'}) == 'Operating Company'


@pytest.mark.parametrize(
    "sic, entity_type, name",
    [
        (None, 'other', 'ISHARES BITCOIN ETF'),           # whole word
        (6221, 'operating', 'ETFS Asian Gold Trust'),     # word starts with ETF
        (None, 'investment', 'ETFis Series Trust I'),     # word starts with ETF
        (None, 'investment', 'Innovator ETFs Trust'),     # word ends with ETFs
    ],
)
def test_etf_at_a_word_edge_is_still_an_etf(sic, entity_type, name):
    assert classify_business_category(sic, entity_type, name, set()) == ETF


def test_investment_company_with_fund_and_mid_word_etf_is_a_mutual_fund():
    # Before the fix, the substring hit in "MARKETFIELD" stopped the FUND rule
    # and the name fell through to the ETF default.
    category = classify_business_category(None, 'investment', 'MARKETFIELD FUND', {'N-CSR'})

    assert category == BusinessCategory.MUTUAL_FUND.value


def test_broker_dealer_with_mid_word_etf_is_an_investment_manager():
    # SIC 6211 skipped the investment-manager branch for any name containing ETF.
    category = classify_business_category(6211, 'operating', 'MARKETFORCE SECURITIES LLC', set())

    assert category == BusinessCategory.INVESTMENT_MANAGER.value


@pytest.mark.network
def test_netflix_business_category_live():
    from edgar import Company

    company = Company(1065280)

    assert company.sic == '7841'
    assert company.business_category == 'Operating Company'
