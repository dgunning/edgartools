"""Regression test for gross profit calculated from mismatched fiscal years.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1979
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
