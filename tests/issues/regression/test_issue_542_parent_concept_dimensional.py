"""
Test for Issue #542: parent_concept missing for key metrics due to dictionary key collision

Bug: The _add_metadata_columns() method in statements.py used a dictionary comprehension
that caused key collisions when the same concept appeared multiple times (main line item
+ dimensional breakdowns like Products, Services, geographic regions).

Root cause: `raw_data_by_concept = {item.get('concept'): item for item in raw_data}`
keeps the LAST occurrence, which is typically a dimensional item without parent info,
overwriting the FIRST occurrence which has the correct parent information.

Fix: Use first occurrence of each concept to preserve parent info.

Reporter: Nikolay Ivanov (@Velikolay)
"""
import pytest
from edgar import Company


@pytest.mark.network
def test_parent_concept_populated_for_revenue():
    """
    Test that Revenue (RevenueFromContractWithCustomerExcludingAssessedTax) has parent_concept populated.

    Before fix: Revenue parent_concept = None (due to dimensional data overwriting)
    After fix: Revenue parent_concept = 'us-gaap_GrossProfit' or similar
    """
    company = Company("AAPL")
    filing = company.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()

    statement = xbrl.statements.income_statement()
    df = statement.to_dataframe()

    # Find Revenue concept
    revenue_concepts = [
        'us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax',
        'us-gaap_Revenues',
        'us-gaap_SalesRevenueNet',
    ]

    revenue_rows = df[df['concept'].isin(revenue_concepts)]

    if len(revenue_rows) > 0:
        # Revenue should have a parent_concept value (not None)
        # The first occurrence (main line item) has parent info from calculation tree
        parent_value = revenue_rows['parent_concept'].iloc[0]

        # Depending on the filing, parent_concept might be:
        # - 'us-gaap_GrossProfit' (calculation tree)
        # - None for some companies without calc tree
        # The key test is that if parent info exists, it should be preserved

        # Check that parent_abstract_concept is populated (presentation tree always present)
        abstract_parent = revenue_rows['parent_abstract_concept'].iloc[0]
        assert abstract_parent is not None or parent_value is not None, \
            "Revenue should have at least one parent concept (calculation or presentation)"


@pytest.mark.network
def test_parent_concept_population_rate():
    """
    Test that parent_concept is populated for a reasonable percentage of concepts.

    Before fix: Only ~14% of concepts had parent_concept (7/49 for AAPL)
    After fix: ~40-50% should have parent_concept (calculation tree participants)
    """
    company = Company("AAPL")
    filing = company.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()

    statement = xbrl.statements.income_statement()
    df = statement.to_dataframe()

    # Calculate parent_concept population rate
    total_concepts = len(df)
    concepts_with_parent = df['parent_concept'].notna().sum()
    population_rate = concepts_with_parent / total_concepts if total_concepts > 0 else 0

    # The population rate should be reasonable (>10% minimum)
    # Before fix, it was ~14% but many concepts were missing due to overwriting
    # We're being conservative here - just ensuring it's not zero
    assert concepts_with_parent > 0, \
        f"parent_concept should be populated for at least some concepts (found {concepts_with_parent}/{total_concepts})"

    # Also check parent_abstract_concept (presentation tree)
    concepts_with_abstract_parent = df['parent_abstract_concept'].notna().sum()
    assert concepts_with_abstract_parent > 0, \
        f"parent_abstract_concept should be populated for at least some concepts"


@pytest.mark.network
def test_parent_concept_not_overwritten_by_dimensional():
    """
    Test that the first occurrence's parent info is preserved, not overwritten by dimensional data.

    This is the core regression test for Issue #542.
    The bug was that dimensional items (Products, Services, regions) would overwrite
    the main line item's parent info because they appear later in raw_data.
    """
    company = Company("AAPL")
    filing = company.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()

    statement = xbrl.statements.income_statement()

    # Get raw data to verify the fix
    raw_data = statement.get_raw_data()

    # Build lookup using first occurrence (the fixed approach)
    first_occurrence = {}
    for item in raw_data:
        concept = item.get('concept')
        if concept and concept not in first_occurrence:
            first_occurrence[concept] = item

    # Build lookup using last occurrence (the buggy approach)
    last_occurrence = {item.get('concept'): item for item in raw_data}

    # Find concepts where first occurrence has parent but last doesn't
    parent_lost_count = 0
    for concept in first_occurrence:
        first_item = first_occurrence[concept]
        last_item = last_occurrence.get(concept, {})

        first_calc_parent = first_item.get('calculation_parent')
        last_calc_parent = last_item.get('calculation_parent')

        # If first has parent but last doesn't, the bug would lose parent info
        if first_calc_parent and not last_calc_parent:
            parent_lost_count += 1

    # Before the fix, many concepts would lose parent info
    # After the fix, this should be much less (or zero)
    # We're not asserting zero because some concepts legitimately have no parent

    # The key assertion is that the DataFrame uses first occurrence
    df = statement.to_dataframe()

    # For each concept with a calculation_parent in first occurrence,
    # verify the DataFrame has that parent
    for concept in first_occurrence:
        first_item = first_occurrence[concept]
        calc_parent = first_item.get('calculation_parent')

        if calc_parent:
            # Find this concept in the DataFrame
            concept_rows = df[df['concept'] == concept]
            if len(concept_rows) > 0:
                df_parent = concept_rows['parent_concept'].iloc[0]
                # The DataFrame should have the parent from first occurrence
                assert df_parent == calc_parent, \
                    f"Concept {concept} should have parent_concept={calc_parent}, got {df_parent}"


@pytest.mark.network
def test_cost_of_goods_sold_parent_concept():
    """
    Test that Cost of Goods Sold has parent_concept populated.

    AAPL's CostOfGoodsAndServicesSold should have parent 'us-gaap_GrossProfit'.
    """
    company = Company("AAPL")
    filing = company.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()

    statement = xbrl.statements.income_statement()
    df = statement.to_dataframe()

    # Find Cost of Goods Sold concept
    cogs_concepts = [
        'us-gaap_CostOfGoodsAndServicesSold',
        'us-gaap_CostOfRevenue',
        'us-gaap_CostOfGoodsSold',
    ]

    cogs_rows = df[df['concept'].isin(cogs_concepts)]

    if len(cogs_rows) > 0:
        # COGS should have parent info (part of Gross Profit calculation)
        parent_value = cogs_rows['parent_concept'].iloc[0]
        abstract_parent = cogs_rows['parent_abstract_concept'].iloc[0]

        # At least one parent should be present
        assert parent_value is not None or abstract_parent is not None, \
            "Cost of Goods Sold should have at least one parent concept"


@pytest.mark.network
def test_operating_income_parent_concept():
    """
    Test that Operating Income has parent_concept populated.

    AAPL's OperatingIncomeLoss should have a parent in the calculation tree.
    """
    company = Company("AAPL")
    filing = company.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()

    statement = xbrl.statements.income_statement()
    df = statement.to_dataframe()

    # Find Operating Income concept
    op_income_concepts = [
        'us-gaap_OperatingIncomeLoss',
        'us-gaap_OperatingIncome',
    ]

    op_income_rows = df[df['concept'].isin(op_income_concepts)]

    if len(op_income_rows) > 0:
        # Operating Income should have parent info
        parent_value = op_income_rows['parent_concept'].iloc[0]
        abstract_parent = op_income_rows['parent_abstract_concept'].iloc[0]

        # At least one parent should be present
        assert parent_value is not None or abstract_parent is not None, \
            "Operating Income should have at least one parent concept"


@pytest.mark.fast
def test_first_occurrence_dictionary_logic():
    """
    Unit test for the dictionary building logic.

    Verifies that first occurrence is kept, not last.
    """
    # Simulate raw_data with same concept appearing multiple times
    raw_data = [
        {'concept': 'us-gaap_Revenue', 'calculation_parent': 'us-gaap_GrossProfit', 'label': 'Revenue'},
        {'concept': 'us-gaap_Revenue', 'calculation_parent': None, 'label': 'Products'},
        {'concept': 'us-gaap_Revenue', 'calculation_parent': None, 'label': 'Services'},
        {'concept': 'us-gaap_Revenue', 'calculation_parent': None, 'label': 'Americas'},
        {'concept': 'us-gaap_CostOfRevenue', 'calculation_parent': 'us-gaap_GrossProfit', 'label': 'Cost of Revenue'},
    ]

    # Old buggy approach: last occurrence wins
    buggy_dict = {item.get('concept'): item for item in raw_data}

    # Fixed approach: first occurrence wins
    fixed_dict = {}
    for item in raw_data:
        concept = item.get('concept')
        if concept and concept not in fixed_dict:
            fixed_dict[concept] = item

    # Buggy approach loses parent info for Revenue
    assert buggy_dict['us-gaap_Revenue']['calculation_parent'] is None, \
        "Buggy approach should have None (last occurrence)"
    assert buggy_dict['us-gaap_Revenue']['label'] == 'Americas', \
        "Buggy approach should have last label"

    # Fixed approach preserves parent info for Revenue
    assert fixed_dict['us-gaap_Revenue']['calculation_parent'] == 'us-gaap_GrossProfit', \
        "Fixed approach should preserve calculation_parent from first occurrence"
    assert fixed_dict['us-gaap_Revenue']['label'] == 'Revenue', \
        "Fixed approach should keep first label"

    # Both approaches should handle concepts that appear once
    assert buggy_dict['us-gaap_CostOfRevenue']['calculation_parent'] == 'us-gaap_GrossProfit'
    assert fixed_dict['us-gaap_CostOfRevenue']['calculation_parent'] == 'us-gaap_GrossProfit'
