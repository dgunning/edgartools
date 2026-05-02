"""Regression test for Issue #795.

When calling time_series() with a fully-qualified concept like 'us-gaap:NetIncomeLoss',
only facts matching that exact concept should be returned. Previously, fuzzy matching
would also include semantically different concepts (e.g.,
NetIncomeLossAvailableToCommonStockholdersBasic), producing duplicate rows for the
same reporting period.

The fix uses exact=":" in concept so that:
- Fully-qualified names (containing ':') get exact matching
- Unqualified names (bare labels) retain fuzzy/label matching for discovery
"""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import DataQuality, FinancialFact


def _make_fact(concept, period_start, period_end, value,
               fiscal_period='Q2', fiscal_year=2025):
    return FinancialFact(
        concept=concept,
        taxonomy='us-gaap',
        label='Net Income Loss',
        value=value,
        numeric_value=value,
        unit='USD',
        scale=1,
        period_start=period_start,
        period_end=period_end,
        period_type='duration',
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        filing_date=date(2025, 8, 1),
        accession='0000000000-25-000001',
        form_type='10-Q',
        data_quality=DataQuality.HIGH,
    )


@pytest.mark.fast
def test_time_series_qualified_concept_uses_exact_matching():
    """time_series('us-gaap:NetIncomeLoss') must only return facts for us-gaap:NetIncomeLoss.

    It must NOT include us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic
    or other similar-but-distinct concepts. The ':' in the concept name signals
    an exact-match intent.
    """
    facts_list = [
        _make_fact('us-gaap:NetIncomeLoss',
                   date(2025, 1, 1), date(2025, 3, 31),
                   -1_000_000.0, fiscal_period='Q1', fiscal_year=2025),
        _make_fact('us-gaap:NetIncomeLoss',
                   date(2025, 4, 1), date(2025, 6, 30),
                   -2_000_000.0, fiscal_period='Q2', fiscal_year=2025),
        # Contaminating fact: same period but different concept
        _make_fact('us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic',
                   date(2025, 4, 1), date(2025, 6, 30),
                   -1_800_000.0, fiscal_period='Q2', fiscal_year=2025),
    ]
    ef = EntityFacts(cik=1234567890, entity_name='Test Corp', facts_list=facts_list)

    result = ef.time_series('us-gaap:NetIncomeLoss', periods=10)

    assert not result.empty
    assert len(result) == 2, (
        f"Expected 2 rows for us-gaap:NetIncomeLoss, got {len(result)}. "
        "Fuzzy matching may be contaminating with similar concepts."
    )


@pytest.mark.fast
def test_time_series_unqualified_concept_still_allows_discovery():
    """time_series('Revenue') (no ':') should not error and should return DataFrame."""
    facts_list = [
        _make_fact('us-gaap:Revenues',
                   date(2025, 1, 1), date(2025, 3, 31),
                   5_000_000.0, fiscal_period='Q1', fiscal_year=2025),
    ]
    ef = EntityFacts(cik=1234567890, entity_name='Test Corp', facts_list=facts_list)
    result = ef.time_series('Revenue', periods=10)
    assert isinstance(result, pd.DataFrame)
