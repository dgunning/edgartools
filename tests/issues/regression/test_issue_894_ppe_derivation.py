"""Regression test for GitHub Issue #894.

GE's standardized EntityFacts balance sheet
(``Company('GE').get_facts().balance_sheet()``) silently omitted Property, Plant
& Equipment entirely for FY2021 onward. Root cause: GE stopped reporting
``us-gaap:PropertyPlantAndEquipmentNet`` after FY2020 and now presents the net
line only under a company-specific extension tag
(``ge:PropertyPlantAndEquipmentAndOperatingLeaseRightOfUseAssetAfterAccumulated...``)
that the SEC companyfacts API — this path's data source — does not expose. The
balance-sheet PP&E node maps solely to ``PropertyPlantAndEquipmentNet``, so with
no such fact the row was built empty and then dropped by the empty-row filter,
vanishing with no error.

The XBRL path (``get_financials().balance_sheet()``) was unaffected because it
renders the filing's own presentation linkbase, which includes the custom tag.

Fix: ``EnhancedStatementBuilder`` now reconstructs standard 'Net' balance-sheet
lines from component concepts the filer still reports, matched to each displayed
period by ``period_end`` (the balance date) rather than fiscal tags — GE's
``PropertyPlantAndEquipmentGross`` and ``AccumulatedDepreciation...`` survive
only as prior-year-end comparatives in later 10-Qs, tagged Q1-Q3 of the
*following* fiscal year, never FY. See ``DERIVED_BALANCE_CONCEPTS`` and
``_inject_derived_balance_facts``. The derived value is the pure, cross-company
comparable net (Gross - AccumulatedDepreciation); GE additionally folds an
operating-lease ROU asset into its extension line, but that asset renders on its
own standardized row (``OperatingLeaseRightOfUseAsset``).
"""
from datetime import date

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact

pytestmark = pytest.mark.regression


def _instant(concept, value, period_end, filing_date, fiscal_year, fiscal_period,
             statement_type=None, label=None):
    """An instant (balance-sheet) fact."""
    return FinancialFact(
        concept=concept,
        taxonomy=concept.split(':', 1)[0] if ':' in concept else 'us-gaap',
        label=label if label is not None else concept.split(':', 1)[-1],
        value=value,
        numeric_value=float(value),
        unit='USD',
        period_type='instant',
        period_start=None,
        period_end=period_end,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        accession=f'0001234-{str(fiscal_year)[2:]}-000001',
        filing_date=filing_date,
        form_type='10-K' if fiscal_period == 'FY' else '10-Q',
        statement_type=statement_type,
    )


# A trimmed GE-shaped balance sheet: an FY2024 annual period with the usual
# classified balance-sheet items, plus PP&E Gross / AccumulatedDepreciation that
# — exactly like GE — are unclassified and reach companyfacts only as prior-
# year-end comparatives inside the FY2025 Q1 10-Q (fiscal_period='Q1'), never FY.
def _ge_like_facts():
    fye = date(2024, 12, 31)
    filed = date(2025, 2, 3)
    facts = [
        # Classified FY2024 balance-sheet anchors so the annual period is selected.
        _instant('us-gaap:Assets', 130_000_000_000, fye, filed, 2024, 'FY', 'BalanceSheet'),
        _instant('us-gaap:AssetsCurrent', 40_000_000_000, fye, filed, 2024, 'FY', 'BalanceSheet'),
        _instant('us-gaap:Goodwill', 15_000_000_000, fye, filed, 2024, 'FY', 'BalanceSheet'),
        _instant('us-gaap:CashAndCashEquivalentsAtCarryingValue', 13_000_000_000, fye, filed, 2024, 'FY', 'BalanceSheet'),
        _instant('us-gaap:LiabilitiesAndStockholdersEquity', 130_000_000_000, fye, filed, 2024, 'FY', 'BalanceSheet'),
        _instant('us-gaap:StockholdersEquity', 20_000_000_000, fye, filed, 2024, 'FY', 'BalanceSheet'),
        # NO us-gaap:PropertyPlantAndEquipmentNet at all (GE dropped it).
        # PP&E components: unclassified, and tagged as the *next* year's Q1
        # comparative (period_end still the FY2024 balance date).
        _instant('us-gaap:PropertyPlantAndEquipmentGross', 15_894_000_000, fye,
                 date(2025, 4, 22), 2025, 'Q1', None),
        _instant('us-gaap:AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment',
                 9_673_000_000, fye, date(2025, 4, 22), 2025, 'Q1', None),
    ]
    return facts


# --- Core: the missing line is reconstructed (the GH #894 symptom) -----------

@pytest.mark.fast
def test_ppe_derived_when_net_tag_dropped():
    """PP&E net is reconstructed as Gross - AccumulatedDepreciation for a period
    that has no PropertyPlantAndEquipmentNet fact."""
    ef = EntityFacts(cik=40545, name='GENERAL ELECTRIC CO', facts=_ge_like_facts())
    df = ef.balance_sheet(periods=1, annual=True, as_dataframe=True)

    ppe = df[df['label'].astype(str).str.contains('property, plant', case=False, na=False)]
    assert len(ppe) == 1, "PP&E row must be present, not silently dropped"

    period_col = [c for c in df.columns if str(c).startswith('FY')][0]
    # Ground truth: 15.894B gross - 9.673B accumulated depreciation = 6.221B.
    assert ppe.iloc[0][period_col] == pytest.approx(6_221_000_000)


# --- No regression: a real Net fact is never overridden by a derivation ------

@pytest.mark.fast
def test_reported_net_is_not_overridden():
    """When the filer reports PropertyPlantAndEquipmentNet directly, that value is
    used verbatim — the derivation must not fire or override it."""
    fye = date(2024, 12, 31)
    filed = date(2025, 2, 3)
    facts = _ge_like_facts()
    # Add a real Net fact whose value deliberately differs from Gross - AccumDepr.
    facts.append(_instant('us-gaap:PropertyPlantAndEquipmentNet', 5_000_000_000,
                          fye, filed, 2024, 'FY', 'BalanceSheet',
                          label='Property, Plant and Equipment, Net'))

    ef = EntityFacts(cik=40545, name='GENERAL ELECTRIC CO', facts=facts)
    df = ef.balance_sheet(periods=1, annual=True, as_dataframe=True)

    ppe = df[df['label'].astype(str).str.contains('property, plant', case=False, na=False)]
    assert len(ppe) == 1
    period_col = [c for c in df.columns if str(c).startswith('FY')][0]
    assert ppe.iloc[0][period_col] == pytest.approx(5_000_000_000), \
        "Reported net (5.0B) must win over derived (6.221B)"


# --- Silence: derivation requires every component ----------------------------

@pytest.mark.fast
def test_no_derivation_when_component_missing():
    """With Gross present but AccumulatedDepreciation absent, no partial (gross-as-
    net) value is fabricated — the row stays absent rather than misleading."""
    facts = [f for f in _ge_like_facts()
             if 'AccumulatedDepreciation' not in f.concept]

    ef = EntityFacts(cik=40545, name='GENERAL ELECTRIC CO', facts=facts)
    df = ef.balance_sheet(periods=1, annual=True, as_dataframe=True)

    ppe = df[df['label'].astype(str).str.contains('property, plant', case=False, na=False)]
    assert len(ppe) == 0, "Must not show gross mislabelled as net when depreciation is missing"


# --- Ground truth against the live GE filing (network) -----------------------

@pytest.mark.network
def test_ge_ppe_ground_truth_live():
    """End-to-end against real GE companyfacts: PP&E appears on the standardized
    balance sheet with the derived net, and the operating-lease ROU asset renders
    as its own row (the two together equal GE's blended as-presented line)."""
    from edgar import Company

    facts = Company('GE').get_facts()
    df = facts.balance_sheet(periods=4, annual=True, as_dataframe=True)

    ppe = df[df['label'].astype(str).str.contains('property, plant', case=False, na=False)]
    assert len(ppe) == 1, "GH #894: PP&E must not be missing from GE's balance sheet"

    fy_cols = [c for c in df.columns if str(c).startswith('FY')]
    # At least the most recent period must carry a positive derived value.
    latest = ppe.iloc[0][fy_cols[0]]
    assert latest is not None and latest > 0

    # The operating-lease ROU asset stays a separate standardized line.
    rou = df[df['label'].astype(str).str.contains('right-of-use', case=False, na=False)]
    assert len(rou) >= 1
