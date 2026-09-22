"""get_revenue() (and other standardized concept getters) could return a
years-stale value when a company migrated its XBRL tag over time.

``EntityFacts._get_standardized_concept_value`` tries each concept variant in
a fixed priority order (``RevenueFromContractWithCustomerExcludingAssessedTax``
before ``Revenues`` for revenue) and returns as soon as ANY variant has ANY
matching fact - it never compares across variants for recency.

NVIDIA hits this exactly: it tagged revenue as
``RevenueFromContractWithCustomerExcludingAssessedTax`` through FY2022, then
switched to plain ``Revenues`` from FY2023 onward. The old tag is tried first
and has real (but 5-year-stale) data, so ``get_revenue()`` returned NVDA's
FY2022 revenue ($26,914,000,000) instead of its current FY2026 revenue
($215,938,000,000) - both real values, just for the wrong year, because tag
priority order won out over actual recency.

Fix: gather a candidate fact from every concept variant instead of stopping
at the first match, then prefer the most recent one (ties broken toward
non-dimensioned/consolidated facts) - falling back to an older candidate only
if unit normalization fails for it.

Ground truth: NVIDIA's own FY2026 10-K (fiscal year ended 2026-01-25) reports
Total Revenue of $215,938,000,000.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1149
"""

from datetime import date

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact


def _fact(concept, value, period_end, filing_date, fiscal_year):
    return FinancialFact(
        concept=concept,
        taxonomy="us-gaap",
        label=concept,
        value=value,
        numeric_value=float(value),
        unit="USD",
        period_end=period_end,
        period_type="duration",
        fiscal_year=fiscal_year,
        fiscal_period="FY",
        filing_date=filing_date,
        form_type="10-K",
    )


def _nvda_facts():
    return [
        # Discontinued after FY2022 - only stale data under this tag.
        _fact(
            "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            26_914_000_000, date(2022, 1, 30), date(2022, 3, 18), 2022,
        ),
        _fact(
            "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            16_675_000_000, date(2021, 1, 31), date(2022, 3, 18), 2021,
        ),
        # Current tag, with the real FY2026 figure.
        _fact(
            "us-gaap:Revenues",
            215_938_000_000, date(2026, 1, 25), date(2026, 2, 25), 2026,
        ),
        _fact(
            "us-gaap:Revenues",
            130_497_000_000, date(2025, 1, 26), date(2026, 2, 25), 2025,
        ),
    ]


def test_get_revenue_prefers_current_tag_over_stale_priority_tag():
    """get_revenue() must return the current FY2026 figure, not the stale
    FY2022 value under a higher-priority but discontinued tag."""
    facts = EntityFacts(cik=1045810, name="NVIDIA CORP", facts=_nvda_facts())

    assert facts.get_revenue() == 215_938_000_000.0, (
        "get_revenue() returned a stale value from a discontinued XBRL tag "
        "instead of the most recent value across all tag variants"
    )


def test_get_revenue_still_finds_data_when_only_the_old_tag_exists():
    """A company that never migrated tags (only the older one has data)
    must still resolve normally."""
    facts = EntityFacts(
        cik=999,
        name="OLD TAG ONLY CO",
        facts=[
            _fact(
                "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                5_000_000, date(2024, 12, 31), date(2025, 2, 1), 2024,
            ),
        ],
    )

    assert facts.get_revenue() == 5_000_000.0
