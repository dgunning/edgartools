"""Regression test for bead edgartools-8p5ci: get_concept() agrees with the getters.

``EntityFacts.get_revenue()`` and ``get_shareholders_equity()`` read their own
variant lists, while ``get_concept('revenue')`` and
``get_concept('stockholders_equity')`` read the synonym groups in
``edgar/standardization/synonym_groups.py``. After the getters learned the
IFRS, bank and utility totals, the groups had not, so the two paths disagreed:
TD's equity came back as its FY2019 figure, Novo Nordisk's as None, and Duke's
revenue as its contract-revenue slice. ``test_issue_637`` checks agreement for
TSM only. These cases check it offline for the filers that showed the gap.

Values as filed, read from SEC company facts:
- Toronto-Dominion Bank 6-K 0000947263-26-000019 (2026-01-31) and
  40-F 0001193125-19-307329 (FY2019)
- Novo Nordisk 20-F 0000353278-26-000012 (FY2025)
- Goldman Sachs 10-Q 0000886982-26-000532 (nine months to 2026-09-30)
- Duke Energy 10-K 0001326160-26-000014 (FY2025)
"""
from datetime import date

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact

pytestmark = pytest.mark.regression


def _fact(concept, value, end, filed, accession, form, fp, *, unit="USD", start=None):
    return FinancialFact(
        concept=concept, taxonomy=concept.split(":")[0], label=concept.split(":")[1],
        value=value, numeric_value=value, unit=unit,
        period_start=start, period_end=end,
        period_type="duration" if start else "instant",
        fiscal_year=end.year, fiscal_period=fp,
        filing_date=filed, form_type=form, accession=accession)


def _agree(ef, getter, concept, unit=None):
    via_getter = getattr(ef, getter)(unit=unit, annual=False)
    via_concept = ef.get_concept(concept, unit=unit)
    assert via_getter == via_concept, (
        f"{getter}() returned {via_getter!r} but get_concept({concept!r}) returned {via_concept!r}")
    return via_concept


def test_td_equity_is_the_current_total_not_fy2019():
    ef = EntityFacts(cik=947263, name="Toronto-Dominion Bank", facts=[
        _fact("ifrs-full:EquityAttributableToOwnersOfParent", 87_701_000_000, date(2019, 10, 31),
              date(2019, 12, 5), "0001193125-19-307329", "40-F", "FY", unit="CAD"),
        _fact("ifrs-full:Equity", 125_596_000_000, date(2026, 1, 31),
              date(2026, 2, 26), "0000947263-26-000019", "6-K", "Q1", unit="CAD"),
    ])
    # Before the fix: get_concept returned 87,701,000,000, the FY2019 figure.
    assert _agree(ef, "get_shareholders_equity", "stockholders_equity", unit="CAD") == 125_596_000_000


def test_novo_nordisk_equity_total():
    ef = EntityFacts(cik=353278, name="Novo Nordisk A/S", facts=[
        _fact("ifrs-full:Equity", 194_047_000_000, date(2025, 12, 31),
              date(2026, 2, 4), "0000353278-26-000012", "20-F", "FY", unit="DKK"),
    ])
    # Before the fix: get_concept returned None.
    assert _agree(ef, "get_shareholders_equity", "stockholders_equity", unit="DKK") == 194_047_000_000


def test_bank_net_revenue():
    ef = EntityFacts(cik=886982, name="Goldman Sachs Group Inc", facts=[
        _fact("us-gaap:RevenuesNetOfInterestExpense", 56_244_000_000, date(2026, 9, 30),
              date(2026, 11, 2), "0000886982-26-000532", "10-Q", "Q3", start=date(2026, 1, 1)),
    ])
    # Before the fix: get_concept returned None.
    assert _agree(ef, "get_revenue", "revenue") == 56_244_000_000


def test_utility_total_operating_revenue_ranks_before_contract_revenue():
    start, end, filed, acc = date(2025, 1, 1), date(2025, 12, 31), date(2026, 2, 26), "0001326160-26-000014"
    ef = EntityFacts(cik=1326160, name="Duke Energy Corp", facts=[
        _fact("us-gaap:RegulatedAndUnregulatedOperatingRevenue", 32_237_000_000, end, filed, acc,
              "10-K", "FY", start=start),
        _fact("us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax", 31_741_000_000, end, filed, acc,
              "10-K", "FY", start=start),
    ])
    # Before the fix: get_concept returned 31,741,000,000, contract revenue only.
    assert _agree(ef, "get_revenue", "revenue") == 32_237_000_000
