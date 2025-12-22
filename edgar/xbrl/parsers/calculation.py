"""
Calculation parser for XBRL documents.

This module handles parsing of XBRL calculation linkbases and building
calculation trees with weights for validation.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from edgar.xbrl.core import NAMESPACES, extract_element_id
from edgar.xbrl.models import CalculationNode, CalculationTree, ElementCatalog, Fact, XBRLProcessingError

from .base import BaseParser


class CalculationParser(BaseParser):
    """Parser for XBRL calculation linkbases."""

    def __init__(self, calculation_roles: Dict[str, Dict[str, Any]],
                 calculation_trees: Dict[str, CalculationTree],
                 element_catalog: Dict[str, ElementCatalog],
                 facts: Dict[str, Fact]):
        """
        Initialize calculation parser with data structure references.

        Args:
            calculation_roles: Reference to calculation roles dictionary
            calculation_trees: Reference to calculation trees dictionary
            element_catalog: Reference to element catalog dictionary
            facts: Reference to facts dictionary
        """
        super().__init__()

        # Store references to data structures
        self.calculation_roles = calculation_roles
        self.calculation_trees = calculation_trees
        self.element_catalog = element_catalog
        self.facts = facts

    def parse_calculation(self, file_path: Union[str, Path]) -> None:
        """Parse calculation linkbase file and build calculation trees."""
        try:
            content = Path(file_path).read_text()
            self.parse_calculation_content(content)
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing calculation file {file_path}: {str(e)}") from e

    def parse_calculation_content(self, content: str) -> None:
        """Parse calculation linkbase content and build calculation trees."""
        try:
            # Use safe XML parsing method
            root = self._safe_parse_xml(content)

            # Extract calculation links
            calculation_links = root.findall('.//{http://www.xbrl.org/2003/linkbase}calculationLink')

            for link in calculation_links:
                role = link.get('{http://www.w3.org/1999/xlink}role')
                if not role:
                    continue

                # Store role information
                role_id = role.split('/')[-1] if '/' in role else role
                role_def = role_id.replace('_', ' ')

                self.calculation_roles[role] = {
                    'roleUri': role,
                    'definition': role_def,
                    'roleId': role_id
                }

                # Extract arcs
                arcs = link.findall('.//{http://www.xbrl.org/2003/linkbase}calculationArc')

                # Create relationships list
                relationships = []

                for arc in arcs:
                    from_ref = arc.get('{http://www.w3.org/1999/xlink}from')
                    to_ref = arc.get('{http://www.w3.org/1999/xlink}to')
                    order = self._parse_order_attribute(arc)
                    weight = float(arc.get('weight', '1.0'))

                    if not from_ref or not to_ref:
                        continue

                    # Find locators for from/to references
                    from_loc = link.find(f'.//*[@{{{NAMESPACES["xlink"]}}}label="{from_ref}"]')
                    to_loc = link.find(f'.//*[@{{{NAMESPACES["xlink"]}}}label="{to_ref}"]')

                    if from_loc is None or to_loc is None:
                        continue

                    from_href = from_loc.get('{http://www.w3.org/1999/xlink}href')
                    to_href = to_loc.get('{http://www.w3.org/1999/xlink}href')

                    if not from_href or not to_href:
                        continue

                    # Extract element IDs
                    from_element = extract_element_id(from_href)
                    to_element = extract_element_id(to_href)

                    # Add relationship
                    relationships.append({
                        'from_element': from_element,
                        'to_element': to_element,
                        'order': order,
                        'weight': weight
                    })

                # Build calculation tree for this role
                if relationships:
                    self._build_calculation_tree(role, relationships)

        except Exception as e:
            raise XBRLProcessingError(f"Error parsing calculation content: {str(e)}") from e

    def _build_calculation_tree(self, role: str, relationships: List[Dict[str, Any]]) -> None:
        """
        Build a calculation tree from relationships.

        Args:
            role: Extended link role URI
            relationships: List of relationships (from_element, to_element, order, weight)
        """
        # Group relationships by source element
        from_map = {}
        to_map = {}

        for rel in relationships:
            from_element = rel['from_element']
            to_element = rel['to_element']

            if from_element not in from_map:
                from_map[from_element] = []
            from_map[from_element].append(rel)

            if to_element not in to_map:
                to_map[to_element] = []
            to_map[to_element].append(rel)

        # Find root elements (appear as 'from' but not as 'to')
        root_elements = set(from_map.keys()) - set(to_map.keys())

        if not root_elements:
            return  # No root elements found

        # Create calculation tree
        tree = CalculationTree(
            role_uri=role,
            definition=self.calculation_roles[role]['definition'],
            root_element_id=next(iter(root_elements)),
            all_nodes={}
        )

        # Build tree recursively
        for root_id in root_elements:
            self._build_calculation_subtree(root_id, None, from_map, tree.all_nodes)

        # Add tree to collection
        self.calculation_trees[role] = tree

    def _build_calculation_subtree(self, element_id: str, parent_id: Optional[str],
                               from_map: Dict[str, List[Dict[str, Any]]],
                               all_nodes: Dict[str, CalculationNode]) -> None:
        """
        Recursively build a calculation subtree.

        Args:
            element_id: Current element ID
            parent_id: Parent element ID
            from_map: Map of relationships by source element
            all_nodes: Dictionary to store all nodes
        """
        # Create node
        node = CalculationNode(
            element_id=element_id,
            parent=parent_id,
            children=[]
        )

        # Add element information if available
        elem_info = None
        if element_id in self.element_catalog:
            elem_info = self.element_catalog[element_id]
        else:
            # Try alternative element ID formats (colon vs underscore)
            alt_element_id = element_id.replace(':', '_') if ':' in element_id else element_id.replace('_', ':')
            if alt_element_id in self.element_catalog:
                elem_info = self.element_catalog[alt_element_id]

        if elem_info:
            node.balance_type = elem_info.balance
            node.period_type = elem_info.period_type

        # Add to collection
        all_nodes[element_id] = node

        # Process children
        if element_id in from_map:
            # Sort children by order
            children = sorted(from_map[element_id], key=lambda r: r['order'])

            for rel in children:
                child_id = rel['to_element']

                # Add child to parent's children list
                node.children.append(child_id)

                # Set weight
                weight = rel['weight']

                # Recursively build child subtree
                self._build_calculation_subtree(
                    child_id, element_id, from_map, all_nodes
                )

                # Update weight and order after child is built
                if child_id in all_nodes:
                    all_nodes[child_id].weight = weight
                    all_nodes[child_id].order = rel['order']
