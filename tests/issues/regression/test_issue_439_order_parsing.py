"""
Regression test for Issue #439: `order` and `balance_type` values not properly parsed in calculation trees

This test ensures that order values from XBRL calculation and presentation linkbases
are correctly parsed and applied to calculation and presentation nodes.

The issue was that CalculationNode.order and PresentationNode.order were showing 0.0
instead of the actual order values specified in the XBRL linkbase files.

Fixed by properly setting the order attribute on child nodes when building the trees.
"""

import pytest
from edgar import find


class TestIssue439OrderParsing:
    """Test cases for order value parsing in XBRL trees."""

    @pytest.fixture(scope="class")
    def aapl_xbrl(self):
        """Get AAPL 10-K XBRL data for testing."""
        filing = find('000032019324000123')  # AAPL 10-K filed 2024-11-01
        return filing.xbrl()

    def test_calculation_nodes_have_correct_order_values(self, aapl_xbrl):
        """Test that calculation nodes have correct order values from linkbase."""
        calc_trees = aapl_xbrl.calculation_trees

        # Count nodes with non-zero order values
        nodes_with_non_zero_order = 0
        total_nodes = 0

        for role, tree in calc_trees.items():
            for element_id, node in tree.all_nodes.items():
                total_nodes += 1
                if node.order != 0.0:
                    nodes_with_non_zero_order += 1

        # Verify that a significant portion of nodes have non-zero order values
        # (Root nodes will have order 0.0, but child nodes should have proper order values)
        assert total_nodes > 0, "Should have calculation nodes"
        assert nodes_with_non_zero_order > 0, "Should have nodes with non-zero order values"

        # Expect at least 70% of nodes to have order values
        order_percentage = nodes_with_non_zero_order / total_nodes
        assert order_percentage > 0.7, f"Expected >70% nodes with order values, got {order_percentage:.1%}"

    def test_specific_calculation_nodes_have_expected_order(self, aapl_xbrl):
        """Test that specific calculation nodes have expected order values."""
        calc_trees = aapl_xbrl.calculation_trees

        # These nodes were verified to have order 2.0 in the debug logs
        expected_nodes = [
            'us-gaap_CostOfGoodsAndServicesSold',
            'us-gaap_NonoperatingIncomeExpense',
            'us-gaap_SellingGeneralAndAdministrativeExpense',
        ]

        found_nodes = {}
        for role, tree in calc_trees.items():
            for element_id, node in tree.all_nodes.items():
                if element_id in expected_nodes:
                    found_nodes[element_id] = node.order

        # Verify we found the expected nodes
        assert len(found_nodes) >= 2, f"Should find at least 2 expected nodes, found: {found_nodes}"

        # Verify they have non-zero order values
        for element_id, order in found_nodes.items():
            assert order > 0.0, f"Node {element_id} should have order > 0.0, got {order}"

    def test_presentation_nodes_have_correct_order_values(self, aapl_xbrl):
        """Test that presentation nodes have correct order values from linkbase."""
        pres_trees = aapl_xbrl.presentation_trees

        # Count nodes with non-zero order values
        nodes_with_non_zero_order = 0
        total_nodes = 0

        for role, tree in pres_trees.items():
            for element_id, node in tree.all_nodes.items():
                total_nodes += 1
                if node.order != 0.0:
                    nodes_with_non_zero_order += 1

        # Verify that a significant portion of nodes have non-zero order values
        assert total_nodes > 0, "Should have presentation nodes"
        assert nodes_with_non_zero_order > 0, "Should have nodes with non-zero order values"

        # Expect at least 80% of nodes to have order values (presentation typically has more ordered nodes)
        order_percentage = nodes_with_non_zero_order / total_nodes
        assert order_percentage > 0.8, f"Expected >80% nodes with order values, got {order_percentage:.1%}"

    def test_specific_presentation_nodes_have_expected_order(self, aapl_xbrl):
        """Test that specific presentation nodes have expected order values."""
        pres_trees = aapl_xbrl.presentation_trees

        # These nodes were verified to have order 2.0 and 3.0 in the debug logs
        expected_nodes = [
            'aapl_A0.000Notesdue2025Member',
            'aapl_A0.875NotesDue2025Member',
        ]

        found_nodes = {}
        for role, tree in pres_trees.items():
            for element_id, node in tree.all_nodes.items():
                if element_id in expected_nodes:
                    found_nodes[element_id] = node.order

        # Verify we found the expected nodes
        assert len(found_nodes) >= 1, f"Should find at least 1 expected node, found: {found_nodes}"

        # Verify they have non-zero order values
        for element_id, order in found_nodes.items():
            assert order > 0.0, f"Node {element_id} should have order > 0.0, got {order}"

    def test_child_nodes_have_higher_order_than_zero(self, aapl_xbrl):
        """Test that child nodes (non-root) generally have order > 0."""
        calc_trees = aapl_xbrl.calculation_trees

        child_nodes = 0
        child_nodes_with_order = 0

        for role, tree in calc_trees.items():
            for element_id, node in tree.all_nodes.items():
                if node.parent is not None:  # This is a child node
                    child_nodes += 1
                    if node.order > 0.0:
                        child_nodes_with_order += 1

        assert child_nodes > 0, "Should have child nodes"

        # Most child nodes should have order > 0 (only exceptional cases should be 0)
        order_percentage = child_nodes_with_order / child_nodes
        assert order_percentage > 0.9, f"Expected >90% child nodes with order > 0, got {order_percentage:.1%}"

    def test_order_values_are_numeric(self, aapl_xbrl):
        """Test that order values are proper numeric types."""
        calc_trees = aapl_xbrl.calculation_trees
        pres_trees = aapl_xbrl.presentation_trees

        # Check calculation nodes
        for role, tree in calc_trees.items():
            for element_id, node in tree.all_nodes.items():
                assert isinstance(node.order, (int, float)), f"Order should be numeric, got {type(node.order)} for {element_id}"
                assert node.order >= 0.0, f"Order should be >= 0, got {node.order} for {element_id}"

        # Check presentation nodes
        for role, tree in pres_trees.items():
            for element_id, node in tree.all_nodes.items():
                assert isinstance(node.order, (int, float)), f"Order should be numeric, got {type(node.order)} for {element_id}"
                assert node.order >= 0.0, f"Order should be >= 0, got {node.order} for {element_id}"