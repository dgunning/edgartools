"""
Calculation parser for XBRL documents.

This module handles parsing of XBRL calculation linkbases and building
calculation trees with weights for validation.

Calculation edges are PER RELATIONSHIP. A concept may roll up into two different
totals under the same role, with a different weight — often a different sign —
under each, so `CalculationTree.all_nodes` (one node per concept) cannot hold
them. `CalculationTree.all_arcs` holds one entry per filed edge beside it.

Relationships are accumulated across every `parse_calculation_content` call and
every `calculationLink` element, then the trees are rebuilt from the accumulated
set. One role may legally be split across several extended links, or files.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from edgar.xbrl.core import extract_element_id
from edgar.xbrl.models import (
    CalculationArc,
    CalculationNode,
    CalculationTree,
    ElementCatalog,
    Fact,
    XBRLProcessingError,
)

from .base import BaseParser

XLINK = "{http://www.w3.org/1999/xlink}"
LINKBASE = "{http://www.xbrl.org/2003/linkbase}"


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

        # Every relationship seen so far, grouped by the role that declared it.
        # The trees are rebuilt from this after each parse.
        self._relationships_by_role: Dict[str, List[Dict[str, Any]]] = {}
        self._seen_arcs: set = set()

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
            root = self._safe_parse_xml(content)

            for link in root.findall(f'.//{LINKBASE}calculationLink'):
                role = link.get(f'{XLINK}role')
                if not role:
                    continue

                self._record_role(role)
                self._collect_relationships(link, role)

            # Rebuild from everything seen so far, not just this link element:
            # one role may be split across several extended links or files.
            self._rebuild_calculation_trees()

        except Exception as e:
            raise XBRLProcessingError(f"Error parsing calculation content: {str(e)}") from e

    def _record_role(self, role: str) -> None:
        """Store the human-readable identity of an extended link role."""
        role_id = role.split('/')[-1] if '/' in role else role

        self.calculation_roles[role] = {
            'roleUri': role,
            'definition': role_id.replace('_', ' '),
            'roleId': role_id
        }

    def _collect_relationships(self, link, role: str) -> None:
        """Extract every calculation arc in one extended link into the store."""
        relationships = self._relationships_by_role.setdefault(role, [])

        # Resolve every xlink:label once. Searching the link per arc is
        # quadratic, and an extended link can carry hundreds of each.
        labels = {}
        for element in link.iter():
            label = element.get(f'{XLINK}label')
            if label is not None:
                labels.setdefault(label, element)

        for arc in link.findall(f'.//{LINKBASE}calculationArc'):
            from_ref = arc.get(f'{XLINK}from')
            to_ref = arc.get(f'{XLINK}to')
            if not from_ref or not to_ref:
                continue

            from_loc = labels.get(from_ref)
            to_loc = labels.get(to_ref)
            if from_loc is None or to_loc is None:
                continue

            from_href = from_loc.get(f'{XLINK}href')
            to_href = to_loc.get(f'{XLINK}href')
            if not from_href or not to_href:
                continue

            from_element = extract_element_id(from_href)
            to_element = extract_element_id(to_href)

            # Re-reading the same linkbase must not duplicate an edge
            key = (role, from_element, to_element)
            if key in self._seen_arcs:
                continue
            self._seen_arcs.add(key)

            relationships.append({
                'from_element': from_element,
                'to_element': to_element,
                'order': self._parse_order_attribute(arc),
                'weight': self._parse_weight_attribute(arc),
            })

    def _parse_weight_attribute(self, arc) -> float:
        """Parse the weight attribute, defaulting to 1.0 when absent or unusable."""
        try:
            return float(arc.get('weight', '1.0'))
        except (TypeError, ValueError):
            return 1.0

    def _rebuild_calculation_trees(self) -> None:
        """Rebuild every role's tree from all the relationships seen so far."""
        self.calculation_trees.clear()

        for role, relationships in self._relationships_by_role.items():
            if relationships:
                self._build_calculation_tree(role, relationships)

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
        # Issue #601: Sort to ensure deterministic ordering across Python processes
        # (set iteration order depends on hash randomization which varies per process)
        root_elements = sorted(set(from_map.keys()) - set(to_map.keys()))

        if not root_elements:
            return  # No root elements found

        # Create calculation tree. all_arcs carries every filed relationship;
        # all_nodes carries one node per concept, so a concept with two parents
        # is one node and two arcs.
        tree = CalculationTree(
            role_uri=role,
            definition=self.calculation_roles[role]['definition'],
            root_element_id=root_elements[0],  # Use first sorted element
            all_nodes={},
            all_arcs=[
                CalculationArc(
                    parent_id=rel['from_element'],
                    child_id=rel['to_element'],
                    weight=rel['weight'],
                    order=rel['order'],
                )
                for rel in relationships
            ],
        )

        # Build tree recursively
        for root_id in root_elements:
            self._build_calculation_subtree(root_id, None, from_map, tree.all_nodes)

        # Add tree to collection
        self.calculation_trees[role] = tree

    def _build_calculation_subtree(self, element_id: str, parent_id: Optional[str],
                               from_map: Dict[str, List[Dict[str, Any]]],
                               all_nodes: Dict[str, CalculationNode],
                               ancestors: tuple = ()) -> None:
        """
        Recursively build a calculation subtree.

        Args:
            element_id: Current element ID
            parent_id: Parent element ID
            from_map: Map of relationships by source element
            all_nodes: Dictionary to store all nodes
            ancestors: Element IDs on the path from the root, to stop a cycle.
                Merging relationships across extended links makes a directed
                cycle reachable where building each link separately could not
                produce one. A cycle is not valid XBRL, but it must fail as a
                missing edge rather than as a stack overflow. Tracking the path
                rather than a global visited set keeps a diamond working: a
                concept legitimately reached twice is still built twice.
        """
        if element_id in ancestors:
            return

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
                    child_id, element_id, from_map, all_nodes,
                    ancestors + (element_id,)
                )

                # Update weight and order after child is built
                if child_id in all_nodes:
                    all_nodes[child_id].weight = weight
                    all_nodes[child_id].order = rel['order']
