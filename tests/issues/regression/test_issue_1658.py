"""EntityFacts.time_series() matched a bare concept name by substring.

``time_series("Assets")`` passed ``exact=":" in concept`` to ``FactQuery.by_concept``,
so a name without a taxonomy prefix kept every fact whose concept or label CONTAINED
the text: AssetsCurrent, AmortizationOfIntangibleAssets, DeferredTaxAssetsNet... The
result has no concept column, so the mixing was invisible. On the Snowflake fixture
below, 18 of the 20 rows returned for ``Assets`` came from other concepts.

The fix resolves the name the way ``get_fact()`` does (exact key, then lowercased
label); only text that names no concept falls back to the substring search, and that
fallback now warns and names the concepts it mixed.

Ground truth: Snowflake 10-Q 0001640147-25-000110 (filed 2025-05-30), total assets of
$8,157,407,000 at 2025-04-30, read from the filing's XBRL. The tracked fixture
``tests/fixtures/entity/snow_facts.json`` is Snowflake's SEC company facts, so this
runs offline.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1658
"""

import json
import warnings
from datetime import date
from pathlib import Path

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import DataQuality, FinancialFact
from edgar.entity.parser import EntityFactsParser

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "entity" / "snow_facts.json"

SNOW_ASSETS_2025_04_30 = 8_157_407_000  # 10-Q 0001640147-25-000110


def _fact(concept, label, value, period_start, period_end):
    return FinancialFact(
        concept=concept, taxonomy='us-gaap', label=label,
        value=value, numeric_value=value, unit='USD', scale=1,
        period_start=period_start, period_end=period_end,
        period_type='duration' if period_start else 'instant',
        fiscal_year=2025, fiscal_period='Q2',
        filing_date=date(2025, 8, 1), accession='0000000000-25-000001',
        form_type='10-Q', data_quality=DataQuality.HIGH,
    )


@pytest.fixture
def mixed():
    return EntityFacts(cik=1, name='Test Corp', facts=[
        _fact('us-gaap:Assets', 'Assets', 100.0, None, date(2025, 6, 30)),
        _fact('us-gaap:AssetsCurrent', 'Assets, Current', 40.0, None, date(2025, 6, 30)),
        _fact('us-gaap:AmortizationOfIntangibleAssets', 'Amortization of Intangible Assets',
              7.0, date(2025, 1, 1), date(2025, 6, 30)),
        _fact('us-gaap:NetIncomeLoss', 'Net Income (Loss)', 9.0, date(2025, 4, 1), date(2025, 6, 30)),
    ])


@pytest.mark.fast
def test_bare_name_selects_only_that_concept(mixed):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        ts = mixed.time_series("Assets")
    assert ts['numeric_value'].tolist() == [100.0]
    assert ts['period_start'].isna().all(), "Assets is an instant; no row may carry a start date"


@pytest.mark.fast
def test_bare_and_prefixed_names_agree(mixed):
    bare = mixed.time_series("Assets").reset_index(drop=True)
    prefixed = mixed.time_series("us-gaap:Assets").reset_index(drop=True)
    assert bare.equals(prefixed)


@pytest.mark.fast
def test_lowercased_label_resolves_exactly(mixed):
    ts = mixed.time_series("assets, current")
    assert ts['numeric_value'].tolist() == [40.0]


@pytest.mark.fast
def test_text_naming_no_concept_falls_back_and_says_so(mixed):
    """'Net Income' is no concept name or label; discovery still works, but loudly."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ts = mixed.time_series("Net Income")
    assert ts['numeric_value'].tolist() == [9.0]
    messages = [str(w.message) for w in caught]
    assert any("substring" in m and "us-gaap:NetIncomeLoss" in m for m in messages), messages


@pytest.mark.fast
def test_unknown_prefixed_name_is_empty_without_fuzzy_fallback(mixed):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        ts = mixed.time_series("us-gaap:Asset")
    assert ts.empty


@pytest.mark.fast
def test_snowflake_assets_series_holds_only_total_assets():
    facts = EntityFactsParser.parse_company_facts(json.loads(FIXTURE.read_text("utf-8")))
    ts = facts.time_series("Assets", periods=50)
    qualified = facts.time_series("us-gaap:Assets", periods=50)

    assert ts.reset_index(drop=True).equals(qualified.reset_index(drop=True))
    assert ts['period_start'].isna().all()
    row = ts[ts['period_end'] == date(2025, 4, 30)]
    assert row['numeric_value'].tolist() == [SNOW_ASSETS_2025_04_30]
