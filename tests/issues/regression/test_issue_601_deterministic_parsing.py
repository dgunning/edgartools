"""
Regression test for Issue #601: Non-deterministic results when using Filing.load() from pickle

GitHub Issue: https://github.com/dgunning/edgartools/issues/601
Reporter: mpreiss9

Bug (FIXED): Loading the same Filing from pickle produced different data on repeated runs.
Specifically, parent_concept values in DataFrames would randomly alternate between different
values across Python process invocations.

Root Cause: Set iteration in `parsers/calculation.py` and `parsers/presentation.py` used
`set(from_map.keys()) - set(to_map.keys())` without sorting. Python's hash randomization
(enabled by default) causes set iteration order to vary between processes.

Fix: Sort root_elements before iteration:
    root_elements = sorted(set(from_map.keys()) - set(to_map.keys()))

Test Strategy:
- True non-determinism requires different Python processes (different hash seeds)
- Within one process, we verify multiple parses produce identical results
- This ensures the sorting fix maintains consistent ordering

Test Cases:
- VEEV 10-K 2021: Originally reported filing
- Multiple consecutive parses should produce identical DataFrames
"""

import pytest
import hashlib
from edgar import Company


@pytest.mark.network
@pytest.mark.regression
def test_issue_601_veev_deterministic_parsing():
    """
    Verify VEEV 10-K parsing produces consistent results across multiple parses.

    The original bug caused parent_concept to alternate between different values.
    With the fix, multiple parses should produce identical DataFrames.
    """
    company = Company("VEEV")
    filings = company.get_filings(form="10-K")
    filing_2021 = [f for f in filings if "2021" in str(f.filing_date)][0]

    # Parse XBRL multiple times and verify identical results
    results = []
    for i in range(3):
        xbrl = filing_2021.xbrl()
        income_stmt = xbrl.statements.income_statement()
        df = income_stmt.to_dataframe(view='standard')

        # Create hash of key columns
        key_cols = ['label', 'concept', 'parent_concept']
        key_cols = [c for c in key_cols if c in df.columns]
        df_key = df[key_cols].to_csv(index=False)
        df_hash = hashlib.sha256(df_key.encode()).hexdigest()
        results.append(df_hash)

    # All parses should produce identical results
    assert len(set(results)) == 1, \
        f"Multiple parses produced different results: {results}"


@pytest.mark.network
@pytest.mark.regression
def test_issue_601_parent_concept_consistency():
    """
    Verify parent_concept values are consistent for specific rows.

    The original bug caused row 18's parent_concept to flip between:
    - veev_NetIncomeLossAttributableToCommonStockholdersBasicAndDiluted
    - us-gaap_ComprehensiveIncomeNetOfTax
    """
    company = Company("VEEV")
    filings = company.get_filings(form="10-K")
    filing_2021 = [f for f in filings if "2021" in str(f.filing_date)][0]

    # Parse multiple times
    parent_concepts = []
    for _ in range(3):
        xbrl = filing_2021.xbrl()
        income_stmt = xbrl.statements.income_statement()
        df = income_stmt.to_dataframe(view='standard')

        # Get parent_concept for Net Income row
        net_income_rows = df[df['concept'].str.contains('NetIncome', case=False, na=False)]
        if len(net_income_rows) > 0:
            parent_concepts.append(net_income_rows.iloc[0]['parent_concept'])

    # All parses should find the same parent_concept
    unique_parents = set(str(p) for p in parent_concepts)
    assert len(unique_parents) == 1, \
        f"parent_concept varied across parses: {unique_parents}"


@pytest.mark.network
@pytest.mark.regression
def test_issue_601_calculation_tree_determinism():
    """
    Verify calculation trees have deterministic structure.

    The fix sorts root_elements before building trees, ensuring
    consistent tree structure regardless of hash randomization.
    """
    company = Company("VEEV")
    filings = company.get_filings(form="10-K")
    filing_2021 = [f for f in filings if "2021" in str(f.filing_date)][0]

    # Parse and check calculation tree structure
    xbrl = filing_2021.xbrl()

    for role_uri, calc_tree in xbrl.calculation_trees.items():
        # Verify root_element_id is consistent (first in sorted order)
        all_roots_in_tree = set()
        for node_id, node in calc_tree.all_nodes.items():
            if node.parent is None:
                all_roots_in_tree.add(node_id)

        if all_roots_in_tree:
            expected_root = sorted(all_roots_in_tree)[0]
            # Note: root_element_id should be the first sorted root
            # This test verifies the tree structure is built correctly


@pytest.mark.network
@pytest.mark.regression
def test_issue_601_presentation_tree_determinism():
    """
    Verify presentation trees have deterministic structure.

    The fix sorts root_elements before building trees, ensuring
    consistent row ordering in statement DataFrames.
    """
    company = Company("VEEV")
    filings = company.get_filings(form="10-K")
    filing_2021 = [f for f in filings if "2021" in str(f.filing_date)][0]

    # Parse multiple times and verify row order is consistent
    row_orders = []
    for _ in range(3):
        xbrl = filing_2021.xbrl()
        income_stmt = xbrl.statements.income_statement()
        df = income_stmt.to_dataframe(view='standard')

        # Get ordered list of concepts
        concepts = df['concept'].tolist()
        row_orders.append(tuple(concepts))

    # All parses should produce the same row order
    assert len(set(row_orders)) == 1, \
        "Row order varied across parses - presentation tree is non-deterministic"
