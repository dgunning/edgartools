"""
Regression test for Issue #646: Dimensional COGS lost during stitching.

DIS (Disney) reports CostOfGoodsAndServicesSold with ONLY dimensional facts
(Service and Product on ProductOrServiceAxis) and NO non-dimensional total.
Before the fix, _generate_line_items picked just one dimensional fact via min(),
losing the other member. The stitched income statement showed ~$52,677M instead
of the correct ~$58,766M total (Service + Product).
"""
import pytest
from edgar import Company


@pytest.mark.network
def test_dis_cost_of_goods_includes_all_dimensional_members():
    """
    DIS CostOfGoodsAndServicesSold should sum Service + Product dimensional
    members when no non-dimensional total exists.
    """
    company = Company("DIS")
    financials = company.get_financials()
    income = financials.income_statement()
    assert income is not None, "Income statement not found for DIS"

    df = income.to_dataframe()

    # Find COGS parent row (non-dimensional, with label "Cost of Product and Service Sold")
    cogs_rows = df[
        (df['concept'] == 'us-gaap_CostOfGoodsAndServicesSold') &
        (df['label'] == 'Cost of Product and Service Sold')
    ]
    assert not cogs_rows.empty, "CostOfGoodsAndServicesSold parent row not found in DIS income statement"

    # Get the most recent period value
    value_cols = [c for c in df.columns if c not in (
        'concept', 'label', 'standard_concept', 'level', 'abstract', 'dimension',
        'is_breakdown', 'dimension_axis', 'dimension_member', 'dimension_member_label',
        'dimension_label', 'balance', 'weight', 'preferred_sign',
        'parent_concept', 'parent_abstract_concept', 'is_abstract', 'is_total', 'units'
    )]
    assert len(value_cols) > 0, "No period columns found"

    cogs_value = cogs_rows.iloc[0][value_cols[0]]
    assert cogs_value == cogs_value, "COGS parent value is NaN — dimensional total not computed"

    # FY2024: Service (~$52,677M) + Product (~$6,089M) = ~$58,766M
    # Value may be negative due to preferred_sign application, so use abs()
    assert abs(cogs_value) > 55_000_000_000, (
        f"COGS value {cogs_value:,.0f} appears to be a single dimensional member, "
        f"not the sum. Expected > $55B (Service + Product combined)."
    )
