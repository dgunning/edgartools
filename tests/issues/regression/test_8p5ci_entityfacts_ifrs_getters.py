"""Regression test for bead edgartools-8p5ci: EntityFacts getters and IFRS tags.

``EntityFacts.get_shareholders_equity()`` and ``get_operating_income()`` listed
no ifrs-full concept, so IFRS filers got None: Shell, SAP, Novartis and BHP
among them. A filer that moved from US-GAAP to IFRS got its last US-GAAP figure
instead, years stale (Toyota: FY2020 equity of 20.06T yen against 35.92T for
FY2025). ``get_net_income()`` reached ifrs-full ProfitLoss, which includes
non-controlling interests, before any owners-of-parent tag. ``get_total_assets()``
fell back to AssetsCurrent.

The values below are as filed, read from SEC company facts:
- Shell plc 20-F 0001628280-26-017024 (FY2025)
- BHP Group 20-F 0001193125-25-185641 (FY to 2025-06-30)
- Toyota Motor 20-F 0001193125-25-142326 (FY to 2025-03-31) and
  20-F 0001193125-20-177015 (FY to 2020-03-31, its last US-GAAP year)
- AT&T 10-K 0000732717-26-000120 (FY2025)
- Duke Energy 10-K 0001326160-26-000014 (FY2025)
"""
from datetime import date

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact

pytestmark = pytest.mark.regression


def _fact(concept, value, end, filed, accession, *, unit="USD", start=None, form="20-F", fy=None):
    return FinancialFact(
        concept=concept, taxonomy=concept.split(":")[0], label=concept.split(":")[1],
        value=value, numeric_value=value, unit=unit,
        period_start=start, period_end=end,
        period_type="duration" if start else "instant",
        fiscal_year=fy or end.year, fiscal_period="FY",
        filing_date=filed, form_type=form, accession=accession)


SHELL = "0001628280-26-017024"
BHP = "0001193125-25-185641"
TM_2025 = "0001193125-25-142326"
TM_2020 = "0001193125-20-177015"
ATT = "0000732717-26-000120"
DUKE = "0001326160-26-000014"


def test_ifrs_equity_is_the_owners_total_not_none():
    end, filed = date(2025, 12, 31), date(2026, 3, 12)
    ef = EntityFacts(cik=1306965, name="Shell plc", facts=[
        _fact("ifrs-full:Equity", 175_319_000_000, end, filed, SHELL),
        _fact("ifrs-full:EquityAttributableToOwnersOfParent", 174_392_000_000, end, filed, SHELL),
    ])
    # Before the fix: None.
    assert ef.get_shareholders_equity() == 174_392_000_000


def test_ifrs_net_income_is_attributable_to_owners():
    start, end, filed = date(2024, 7, 1), date(2025, 6, 30), date(2025, 8, 22)
    ef = EntityFacts(cik=811809, name="BHP Group", facts=[
        _fact("ifrs-full:ProfitLoss", 11_143_000_000, end, filed, BHP, start=start),
        _fact("ifrs-full:ProfitLossAttributableToOwnersOfParent", 9_019_000_000, end, filed, BHP, start=start),
        _fact("ifrs-full:ProfitLossFromOperatingActivities", 19_464_000_000, end, filed, BHP, start=start),
    ])
    # Before the fix: 11,143,000,000, profit including non-controlling interests.
    assert ef.get_net_income() == 9_019_000_000
    assert ef.get_net_income_detailed().value == 9_019_000_000
    # Before the fix: None.
    assert ef.get_operating_income() == 19_464_000_000


def test_filer_that_moved_to_ifrs_gets_its_current_year():
    ef = EntityFacts(cik=1094517, name="Toyota Motor Corp", facts=[
        _fact("us-gaap:StockholdersEquity", 20_060_618_000_000, date(2020, 3, 31),
              date(2020, 6, 24), TM_2020, unit="JPY"),
        _fact("us-gaap:OperatingIncomeLoss", 2_442_869_000_000, date(2020, 3, 31),
              date(2020, 6, 24), TM_2020, unit="JPY", start=date(2019, 4, 1)),
        _fact("ifrs-full:Equity", 36_878_913_000_000, date(2025, 3, 31),
              date(2025, 6, 18), TM_2025, unit="JPY"),
        _fact("ifrs-full:EquityAttributableToOwnersOfParent", 35_924_826_000_000, date(2025, 3, 31),
              date(2025, 6, 18), TM_2025, unit="JPY"),
        _fact("ifrs-full:ProfitLossFromOperatingActivities", 4_795_586_000_000, date(2025, 3, 31),
              date(2025, 6, 18), TM_2025, unit="JPY", start=date(2024, 4, 1)),
    ])
    # Before the fix: the FY2020 US-GAAP figures, 20.06T and 2.44T.
    assert ef.get_shareholders_equity(unit="JPY") == 35_924_826_000_000
    assert ef.get_operating_income(unit="JPY") == 4_795_586_000_000


def test_equity_including_nci_answers_when_no_parent_total_is_filed():
    ef = EntityFacts(cik=732717, name="AT&T Inc.", facts=[
        _fact("us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
              126_491_000_000, date(2025, 12, 31), date(2026, 2, 9), ATT, form="10-K"),
    ])
    # Before the fix: None. AT&T files no us-gaap:StockholdersEquity.
    assert ef.get_shareholders_equity() == 126_491_000_000


def test_utility_revenue_is_total_operating_revenue_not_the_contract_slice():
    start, end, filed = date(2025, 1, 1), date(2025, 12, 31), date(2026, 2, 26)
    ef = EntityFacts(cik=1326160, name="Duke Energy Corp", facts=[
        _fact("us-gaap:RegulatedAndUnregulatedOperatingRevenue", 32_237_000_000, end, filed, DUKE,
              start=start, form="10-K"),
        _fact("us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax", 31_741_000_000, end, filed, DUKE,
              start=start, form="10-K"),
    ])
    # Before the fix: None; neither concept was listed.
    assert ef.get_revenue() == 32_237_000_000


def test_prefixed_variant_matches_only_its_own_taxonomy():
    """ifrs-full:ProfitLossFromOperatingActivities is not a us-gaap concept."""
    ef = EntityFacts(cik=1, name="Example", facts=[
        _fact("us-gaap:ProfitLossFromOperatingActivities", 5_000_000, date(2025, 12, 31),
              date(2026, 2, 1), "0000000000-26-000001", start=date(2025, 1, 1), form="10-K"),
    ])
    assert ef.get_operating_income() is None


def test_current_assets_are_not_total_assets():
    ef = EntityFacts(cik=1, name="Example", facts=[
        _fact("us-gaap:AssetsCurrent", 7_000_000, date(2025, 12, 31),
              date(2026, 2, 1), "0000000000-26-000001", form="10-K"),
    ])
    # Before the fix: 7,000,000.
    assert ef.get_total_assets() is None
