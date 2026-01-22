"""
Regression test for edgartools-rqxi: Fix definition linkbase table creation bug.

The bug: In `_process_dimensional_relationships()`, the `all` arc processing
had from/to elements swapped. The `all` arc connects:
  - from: LineItems element
  - to: Hypercube (table) element

But the code was treating `from_element` as the table and `to_element` as
line items, so the lookup in `hypercube_axes` dict always failed.

Fix: Swap the interpretation so hypercube_id = to_element.
"""

import pytest


@pytest.mark.network
def test_boeing_10k_tables_created():
    """
    Boeing 10-K should have tables created from definition linkbase.

    Before fix: 0 tables despite 67 axes and 127 domains
    After fix: 65 tables correctly created
    """
    from edgar import Company

    ba = Company("BA")
    filing = ba.get_filings(form="10-K").latest()
    xbrl = filing.xbrl()

    # Tables should be created
    assert len(xbrl.tables) > 0, "Tables should be created from definition linkbase"

    # Axes and domains should exist
    assert len(xbrl.axes) > 0, "Axes should be parsed"
    assert len(xbrl.domains) > 0, "Domains should be parsed"


@pytest.mark.network
def test_income_statement_has_product_service_axis():
    """
    Boeing Income Statement should have ProductOrServiceAxis via StatementTable.

    The definition linkbase declares:
      all: StatementLineItems -> StatementTable
      hypercube-dimension: StatementTable -> ProductOrServiceAxis

    This is critical because Boeing reports CostOfGoodsAndServicesSold
    ONLY through ProductOrServiceAxis dimensions.
    """
    from edgar import Company

    ba = Company("BA")
    filing = ba.get_filings(form="10-K").latest()
    xbrl = filing.xbrl()

    # Find the income statement role
    income_roles = [
        role for role in xbrl.tables.keys()
        if 'Operations' in role or 'Income' in role
    ]

    assert len(income_roles) > 0, "Should have income statement role with tables"

    # Check that ProductOrServiceAxis is declared
    income_role = income_roles[0]
    tables = xbrl.tables[income_role]

    has_product_service_axis = any(
        'ProductOrServiceAxis' in axis
        for table in tables
        for axis in table.axes
    )

    assert has_product_service_axis, (
        "Income statement should have ProductOrServiceAxis declared "
        "in its hypercube definition"
    )


@pytest.mark.network
def test_table_structure_correct():
    """
    Verify table structure has correct element IDs and axes.
    """
    from edgar import Company

    ba = Company("BA")
    filing = ba.get_filings(form="10-K").latest()
    xbrl = filing.xbrl()

    # Get any table
    first_role = list(xbrl.tables.keys())[0]
    first_table = xbrl.tables[first_role][0]

    # Table should have a hypercube element ID (contains "Table")
    assert 'Table' in first_table.element_id or 'table' in first_table.element_id.lower(), (
        f"Table element_id should be a hypercube, got: {first_table.element_id}"
    )

    # Table should have axes
    assert len(first_table.axes) > 0, "Table should have at least one axis"

    # Table should have line items
    assert len(first_table.line_items) > 0, "Table should have line items"

    # Line items should contain "LineItems"
    has_line_items = any('LineItems' in li or 'lineitems' in li.lower()
                         for li in first_table.line_items)
    assert has_line_items, f"Line items should contain 'LineItems': {first_table.line_items}"
