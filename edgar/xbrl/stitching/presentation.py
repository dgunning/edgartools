"""
XBRL Presentation Tree - Virtual presentation tree for multi-period statements

This module creates a virtual presentation tree that preserves hierarchical
relationships while applying semantic ordering within sibling groups.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class PresentationNode:
    """Represents a node in the virtual presentation tree"""

    concept: str
    label: str
    level: int
    metadata: Dict[str, Any]
    semantic_order: float = 999.0
    original_index: int = 999

    def __post_init__(self):
        self.children: List[PresentationNode] = []
        self.parent: Optional[PresentationNode] = None

    def add_child(self, child: 'PresentationNode'):
        """Add a child node and set parent relationship"""
        child.parent = self
        self.children.append(child)

    def sort_children(self):
        """Sort children using semantic ordering while preserving hierarchy"""
        # Sort direct children by semantic order, then by original index as tiebreaker
        self.children.sort(key=lambda x: (x.semantic_order, x.original_index))

        # Recursively sort grandchildren
        for child in self.children:
            child.sort_children()

    def flatten_to_list(self) -> List['PresentationNode']:
        """Flatten tree to ordered list while preserving hierarchy"""
        result = [self]
        for child in self.children:
            result.extend(child.flatten_to_list())
        return result


class VirtualPresentationTree:
    """Builds and manages virtual presentation tree for stitched statements"""

    def __init__(self, ordering_manager=None):
        self.ordering_manager = ordering_manager
        self.root_nodes: List[PresentationNode] = []
        self.all_nodes: Dict[str, PresentationNode] = {}

    def build_tree(self, concept_metadata: Dict, concept_ordering: Dict, 
                   original_statement_order: List[str] = None) -> List[PresentationNode]:
        """
        Build presentation tree from concept metadata and ordering.

        Args:
            concept_metadata: Metadata for each concept including level
            concept_ordering: Semantic ordering positions
            original_statement_order: Original order of concepts for context

        Returns:
            Flattened list of nodes in correct presentation order
        """
        # Step 1: Create nodes for all concepts
        self._create_nodes(concept_metadata, concept_ordering, original_statement_order)

        # Step 2: Build parent-child relationships based on levels and context
        self._build_hierarchy(original_statement_order or [])

        # Step 3: Apply semantic ordering within sibling groups
        self._apply_semantic_ordering()

        # Step 4: Flatten tree to linear list
        return self._flatten_tree()

    def _create_nodes(self, concept_metadata: Dict, concept_ordering: Dict,
                     original_statement_order: List[str] = None):
        """Create nodes for all concepts"""
        self.all_nodes = {}

        for i, (concept, metadata) in enumerate(concept_metadata.items()):
            label = metadata.get('latest_label', concept)
            level = metadata.get('level', 0)
            semantic_order = concept_ordering.get(concept, concept_ordering.get(label, 999.0))

            # Track original index for maintaining some original order context
            original_index = i
            if original_statement_order:
                try:
                    original_index = original_statement_order.index(concept)
                except ValueError:
                    try:
                        original_index = original_statement_order.index(label)
                    except ValueError:
                        original_index = i + 1000  # Place unknown concepts later

            node = PresentationNode(
                concept=concept,
                label=label,
                level=level,
                metadata=metadata,
                semantic_order=semantic_order,
                original_index=original_index
            )

            self.all_nodes[concept] = node

    def _build_hierarchy(self, original_order: List[str]):
        """Build parent-child relationships based on level progression and context"""

        # Sort nodes by their original order to maintain context for hierarchy detection
        nodes_in_order = []

        # First, try to use original order if available
        if original_order:
            # Map concepts in original order
            concept_to_node = {node.concept: node for node in self.all_nodes.values()}
            label_to_node = {node.label: node for node in self.all_nodes.values()}

            for item in original_order:
                if item in concept_to_node:
                    nodes_in_order.append(concept_to_node[item])
                elif item in label_to_node:
                    nodes_in_order.append(label_to_node[item])

            # Add any remaining nodes not in original order
            remaining_nodes = [node for node in self.all_nodes.values() 
                             if node not in nodes_in_order]
            remaining_nodes.sort(key=lambda x: x.original_index)
            nodes_in_order.extend(remaining_nodes)
        else:
            # Fall back to sorting by original index
            nodes_in_order = sorted(self.all_nodes.values(), 
                                  key=lambda x: x.original_index)

        # Build hierarchy using a parent stack approach
        parent_stack = []  # Stack of potential parents at each level

        for node in nodes_in_order:
            current_level = node.level

            # Pop parents that are at the same level or deeper
            # We're looking for a parent at a level less than current
            while parent_stack and parent_stack[-1].level >= current_level:
                parent_stack.pop()

            if parent_stack:
                # Check if potential parent and child belong to compatible sections
                parent = parent_stack[-1]

                # Prevent cross-section hierarchies for critical sections like per_share
                should_be_child = self._should_be_hierarchical_child(parent, node)

                if should_be_child:
                    # Valid parent-child relationship
                    parent.add_child(node)
                else:
                    # Different sections - make this a root node instead
                    self.root_nodes.append(node)
            else:
                # No parent - this is a root node
                self.root_nodes.append(node)

            # This node could be a parent for subsequent nodes
            parent_stack.append(node)

    def _apply_semantic_ordering(self):
        """Apply semantic ordering within sibling groups"""

        # Sort root nodes by semantic order first, then original index
        self.root_nodes.sort(key=lambda x: (x.semantic_order, x.original_index))

        # Sort children within each parent recursively
        for root in self.root_nodes:
            root.sort_children()

    def _flatten_tree(self) -> List[PresentationNode]:
        """Flatten tree to linear list preserving hierarchy"""
        result = []

        for root in self.root_nodes:
            result.extend(root.flatten_to_list())

        return result

    def _should_be_hierarchical_child(self, parent: PresentationNode, child: PresentationNode) -> bool:
        """
        Determine if child should be hierarchically under parent based on semantic ordering.

        Prevents cross-section hierarchies that would break template section groupings.
        """
        # Get semantic ordering positions
        parent_order = parent.semantic_order
        child_order = child.semantic_order

        # If both have very specific semantic orders from templates (not defaults),
        # check if they're in similar ranges (same section)
        if parent_order < 900 and child_order < 900:
            # Both are template-positioned, check if they're in similar sections
            # Allow parent-child within 200 points (roughly same section)
            section_gap = abs(parent_order - child_order)
            if section_gap > 200:
                return False

        # Special case: Per-share items (900+) should never be children of early items
        if child_order >= 900 and parent_order < 800:
            return False

        # Special case: Non-operating items (500-599) should not be children of operating items
        if 500 <= child_order < 600 and parent_order < 500:
            return False

        # Special case: Revenue items should not be parents of per-share items
        if parent_order < 100 and child_order >= 900:
            return False

        # Check for semantic incompatibility based on labels
        child_label = child.label.lower()
        parent_label = parent.label.lower()

        # Per-share items should not be children of non-per-share items
        if any(term in child_label for term in ['earnings per share', 'shares outstanding']):
            if not any(term in parent_label for term in ['earnings', 'shares', 'per share']):
                return False

        # Interest expense items should not be children of non-interest items  
        if 'interest expense' in child_label:
            if 'interest' not in parent_label and 'nonoperating' not in parent_label:
                return False

        # Otherwise, allow hierarchical relationship
        return True

    def debug_tree(self) -> str:
        """Generate a debug representation of the tree"""
        lines = []

        def _add_node_lines(node: PresentationNode, depth: int = 0):
            indent = "  " * depth
            lines.append(f"{indent}├─ {node.label} (level={node.level}, "
                        f"semantic={node.semantic_order:.1f}, orig={node.original_index})")

            for child in node.children:
                _add_node_lines(child, depth + 1)

        lines.append("Virtual Presentation Tree:")
        for root in self.root_nodes:
            _add_node_lines(root)

        return "\n".join(lines)
