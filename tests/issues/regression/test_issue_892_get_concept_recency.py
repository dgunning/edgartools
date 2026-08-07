"""Regression test for GitHub Issue #892.

``EntityFacts.get_concept("capex")`` silently returned years-stale values for
companies that switched GAAP capex tags. NVIDIA and Amazon moved capex from
``PaymentsToAcquirePropertyPlantAndEquipment`` to
``PaymentsToAcquireProductiveAssets``, but still have old facts sitting under the
former. ``get_concept`` iterated the synonym group in priority order and returned
on the *first* synonym holding any fact, so it handed back the most-recent fact
*under the stale tag* (NVDA: 2020, ~4.7x understated; AMZN: 2017, ~6x
understated) and never consulted the recent tag — which is present in the group
but ranked last.

Fix: when no explicit period is requested, ``get_concept`` now selects the most
recent fact *across all synonyms* (by filing_date then period_end, ties broken by
priority), mirroring the intra-tag recency ordering ``get_fact`` already uses.
The returned metadata now also carries the resolved ``period``/``period_end``/
``filing_date`` so a stale pick is visible. When a period *is* specified, the
priority ordering remains authoritative (first match wins, unchanged).

Note: the magnitude ``get_concept`` returns for a flow concept like capex still
reflects ``get_fact``'s existing period selection (it does not distinguish a
single quarter from a fiscal-YTD/cumulative value) — a separate, pre-existing
concern tracked apart from this tag-staleness fix.
"""
from datetime import date

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact

pytestmark = pytest.mark.regression


def _capex_fact(concept, value, period_end, filing_date, fiscal_year, fiscal_period):
    return FinancialFact(
        concept=concept,
        taxonomy='us-gaap',
        label='Capex',
        value=value,
        numeric_value=float(value),
        unit='USD',
        period_type='duration',
        period_start=date(period_end.year, 1, 1),
        period_end=period_end,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        accession=f'0001234-{str(fiscal_year)[2:]}-000001',
        filing_date=filing_date,
        form_type='10-Q',
    )


# --- Offline: the cross-synonym recency core of the fix (deterministic) ------

@pytest.mark.fast
def test_recent_low_priority_synonym_beats_stale_high_priority():
    """The NVDA/AMZN scenario: a stale fact under the top-priority tag must not
    win over a recent fact under a lower-priority synonym."""
    facts = [
        # Top-priority tag, but stale (company stopped filing under it in 2020).
        _capex_fact('PaymentsToAcquirePropertyPlantAndEquipment',
                    372_000_000, date(2020, 7, 26), date(2020, 8, 20), 2021, 'Q2'),
        # Last-priority tag, but current.
        _capex_fact('PaymentsToAcquireProductiveAssets',
                    1_757_000_000, date(2026, 4, 26), date(2026, 5, 20), 2027, 'Q1'),
    ]
    ef = EntityFacts(cik=123456, name='Test Co', facts=facts)

    result = ef.get_concept('capex', return_metadata=True)
    assert result['value'] == 1_757_000_000, "returned the stale value, not the recent one"
    assert result['tag_used'].endswith('PaymentsToAcquireProductiveAssets')
    # Staleness is now visible in the metadata (was 'period': None before).
    assert result['period_end'] == date(2026, 4, 26)
    assert result['filing_date'] == date(2026, 5, 20)
    # Plain (non-metadata) call returns the same recent value.
    assert ef.get_concept('capex') == 1_757_000_000


@pytest.mark.fast
def test_single_recent_priority_tag_is_unchanged():
    """A company that uses the top-priority tag with current data (MSFT/GOOG
    style) still resolves to it — no regression from the recency change."""
    facts = [
        _capex_fact('PaymentsToAcquirePropertyPlantAndEquipment',
                    35_674_000_000, date(2026, 3, 31), date(2026, 4, 30), 2026, 'Q1'),
    ]
    ef = EntityFacts(cik=123456, name='Test Co', facts=facts)
    result = ef.get_concept('capex', return_metadata=True)
    assert result['value'] == 35_674_000_000
    assert result['tag_used'].endswith('PaymentsToAcquirePropertyPlantAndEquipment')


@pytest.mark.fast
def test_explicit_period_keeps_priority_order():
    """With an explicit period, the priority ordering stays authoritative: the
    top-priority tag wins even though a lower-priority tag has the same period."""
    facts = [
        _capex_fact('PaymentsToAcquirePropertyPlantAndEquipment',
                    100, date(2026, 3, 31), date(2026, 4, 30), 2026, 'Q1'),
        _capex_fact('PaymentsToAcquireProductiveAssets',
                    200, date(2026, 3, 31), date(2026, 4, 30), 2026, 'Q1'),
    ]
    ef = EntityFacts(cik=123456, name='Test Co', facts=facts)
    value = ef.get_concept('capex', period='2026-Q1')
    assert value == 100, "explicit period should keep first-match-by-priority"


# --- End-to-end: the reported companies under VCR ---------------------------

@pytest.mark.network
@pytest.mark.vcr
def test_nvda_capex_resolves_to_recent_tag():
    """NVDA get_concept('capex') returns the current ProductiveAssets value
    ($1.757B, period ending 2026-04-26), not the stale 2020 PP&E value ($372M)."""
    from edgar import Company

    result = Company("NVDA").get_facts().get_concept("capex", return_metadata=True)
    assert result['tag_used'].endswith('PaymentsToAcquireProductiveAssets')
    assert result['value'] == 1_757_000_000
    assert result['value'] != 372_000_000  # the stale 2020 value
    assert result['period_end'].year >= 2025


@pytest.mark.network
@pytest.mark.vcr
def test_amzn_capex_resolves_to_recent_tag():
    """AMZN get_concept('capex') no longer returns the stale 2017 PP&E value
    ($7.417B); it resolves to the recent ProductiveAssets tag."""
    from edgar import Company

    result = Company("AMZN").get_facts().get_concept("capex", return_metadata=True)
    assert result['tag_used'].endswith('PaymentsToAcquireProductiveAssets')
    assert result['value'] != 7_417_000_000  # the stale 2017 value
    assert result['period_end'].year >= 2025
