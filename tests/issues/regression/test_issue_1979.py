"""Regression test for gross profit calculated from mismatched fiscal years.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1979

The component fallbacks also picked each part with get_fact(), which returns the
newest fact of any duration, and stopped at the first concept variant with any
fact. annual=True was ignored: Procter & Gamble's "annual" gross profit was one
quarter, and stale variants could win. Both parts now come from one period, the
anchor's latest, full-year when annual is set.
"""

import pytest

from edgar.entity.parser import EntityFactsParser

pytestmark = pytest.mark.fast


def annual_fact(year, value):
    return {
        "start": f"{year}-01-01",
        "end": f"{year}-12-31",
        "filed": f"{year + 1}-02-15",
        "accn": f"0000000001-{(year + 1) % 100:02d}-000001",
        "fy": year,
        "fp": "FY",
        "form": "10-K",
        "val": value,
    }


@pytest.mark.parametrize(
    ("getter", "concept", "value"),
    [("get_gross_profit", "Revenues", 120), ("get_revenue", "GrossProfit", 50)],
)
def test_component_fallback_rejects_mixed_periods(getter, concept, value):
    facts = EntityFactsParser.parse_company_facts({
        "cik": 1,
        "entityName": "Synthetic Example",
        "facts": {
            "us-gaap": {
                concept: {"units": {"USD": [annual_fact(2025, value)]}},
                "CostOfRevenue": {"units": {"USD": [annual_fact(2024, 70)]}},
            }
        },
    })

    assert facts is not None
    assert getattr(facts, getter)() is None


def test_gross_profit_fallback_preserves_matching_period():
    # Apple FY2025 10-K, accession 0000320193-25-000079.
    # Supply net sales and costs only to exercise the fallback.
    period = {
        "start": "2024-09-29",
        "end": "2025-09-27",
        "filed": "2025-10-31",
        "accn": "0000320193-25-000079",
        "fy": 2025,
        "fp": "FY",
        "form": "10-K",
    }
    facts = EntityFactsParser.parse_company_facts({
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": [dict(period, val=416_161_000_000)]},
                },
                "CostOfGoodsAndServicesSold": {
                    "units": {"USD": [dict(period, val=220_960_000_000)]},
                },
            }
        },
    })

    assert facts is not None
    assert facts.get_gross_profit() == 195_201_000_000


def fact(start, end, fy, fp, value, accn, form, filed):
    return {"start": start, "end": end, "fy": fy, "fp": fp, "val": value,
            "accn": accn, "form": form, "filed": filed}


def parse(concepts):
    return EntityFactsParser.parse_company_facts({
        "cik": 1, "entityName": "Synthetic Example",
        "facts": {"us-gaap": {c: {"units": {"USD": rows}} for c, rows in concepts.items()}},
    })


# Procter & Gamble, as SEC's companyfacts lists them: the FY2026 10-K
# (0000080424-26-000103: net sales $87,032M, cost of products sold $43,362M) and
# the later Q1 FY2027 10-Q (0000080424-26-000256: $23,276M and $11,678M).
PG_10K = dict(accn="0000080424-26-000103", form="10-K", filed="2026-08-04")
PG_10Q = dict(accn="0000080424-26-000256", form="10-Q", filed="2026-10-22")
PG = {
    "Revenues": [fact("2025-07-01", "2026-06-30", 2026, "FY", 87_032_000_000, **PG_10K),
                 fact("2026-07-01", "2026-09-30", 2027, "Q1", 23_276_000_000, **PG_10Q)],
    "CostOfGoodsAndServicesSold": [fact("2025-07-01", "2026-06-30", 2026, "FY", 43_362_000_000, **PG_10K),
                                   fact("2026-07-01", "2026-09-30", 2027, "Q1", 11_678_000_000, **PG_10Q)],
}


def test_annual_gross_profit_is_the_fiscal_year_not_the_newer_quarter():
    facts = parse(PG)
    assert facts.get_gross_profit() == 43_670_000_000             # FY2026, as the 10-K's lines give it
    assert facts.get_gross_profit(annual=False) == 11_598_000_000  # Q1 FY2027
    assert facts.get_gross_profit(period="2026-FY") == 43_670_000_000


def test_a_stale_variant_does_not_win_by_priority():
    # Revenues ranks first but was last tagged for 2017; the current year is under
    # RevenueFromContractWithCustomerExcludingAssessedTax
    facts = parse({
        "Revenues": [fact("2017-01-01", "2017-12-31", 2017, "FY", 500, "a", "10-K", "2018-02-15")],
        "RevenueFromContractWithCustomerExcludingAssessedTax": [
            fact("2025-01-01", "2025-12-31", 2025, "FY", 900, "b", "10-K", "2026-02-15")],
        "CostOfRevenue": [fact("2017-01-01", "2017-12-31", 2017, "FY", 300, "a", "10-K", "2018-02-15"),
                          fact("2025-01-01", "2025-12-31", 2025, "FY", 600, "b", "10-K", "2026-02-15")],
    })
    assert facts.get_gross_profit() == 300


def test_quarter_and_year_to_date_are_never_mixed():
    # A 10-Q tags revenue for the quarter and the nine months; cost only for the nine months
    q3 = dict(accn="c", form="10-Q", filed="2025-11-01")
    facts = parse({
        "Revenues": [fact("2025-07-01", "2025-09-30", 2025, "Q3", 100, **q3),
                     fact("2025-01-01", "2025-09-30", 2025, "Q3", 280, **q3)],
        "CostOfRevenue": [fact("2025-01-01", "2025-09-30", 2025, "Q3", 160, **q3)],
    })
    # The latest period is the quarter, which has no cost: no answer, not 100 - 160
    assert facts.get_gross_profit(annual=False) is None
    facts = parse({
        "Revenues": [fact("2025-07-01", "2025-09-30", 2025, "Q3", 100, **q3),
                     fact("2025-01-01", "2025-09-30", 2025, "Q3", 280, **q3)],
        "CostOfRevenue": [fact("2025-07-01", "2025-09-30", 2025, "Q3", 55, **q3),
                          fact("2025-01-01", "2025-09-30", 2025, "Q3", 160, **q3)],
    })
    assert facts.get_gross_profit(annual=False) == 45


def test_an_older_year_is_not_answered_when_the_latest_lacks_cost():
    # Starbucks last tagged CostOfGoodsAndServicesSold for FY2019
    facts = parse({
        "Revenues": [fact("2018-10-01", "2019-09-29", 2019, "FY", 26_500, "d", "10-K", "2019-11-15"),
                     fact("2025-09-29", "2026-09-27", 2026, "FY", 37_910, "e", "10-K", "2026-11-14")],
        "CostOfGoodsAndServicesSold": [fact("2018-10-01", "2019-09-29", 2019, "FY", 8_500, "d", "10-K", "2019-11-15")],
    })
    assert facts.get_gross_profit() is None
    assert facts.get_gross_profit(period="2019-FY") == 18_000


def test_revenue_fallback_uses_the_same_period_rule():
    facts = parse({
        "GrossProfit": [fact("2025-01-01", "2025-12-31", 2025, "FY", 400, "f", "10-K", "2026-02-15"),
                        fact("2026-01-01", "2026-03-31", 2026, "Q1", 90, "g", "10-Q", "2026-05-01")],
        "CostOfRevenue": [fact("2025-01-01", "2025-12-31", 2025, "FY", 600, "f", "10-K", "2026-02-15"),
                          fact("2026-01-01", "2026-03-31", 2026, "Q1", 160, "g", "10-Q", "2026-05-01")],
    })
    assert facts.get_revenue() == 1000
    assert facts.get_revenue(annual=False) == 250
