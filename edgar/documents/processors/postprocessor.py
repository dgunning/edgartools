"""
Document postprocessor for final processing after parsing.
"""

from typing import List, Set
from edgar.documents.config import ParserConfig
from edgar.documents.document import Document
from edgar.documents.nodes import Node, TextNode, ParagraphNode, HeadingNode
from edgar.documents.types import NodeType


class DocumentPostprocessor:
    """
    Postprocesses parsed documents to improve quality.
    
    Handles:
    - Adjacent node merging
    - Empty node removal
    - Heading level normalization
    - Section detection enhancement
    - Metadata enrichment
    """
    
    def __init__(self, config: ParserConfig):
        """Initialize postprocessor with configuration."""
        self.config = config
    
    def process(self, document: Document) -> Document:
        """
        Postprocess document.
        
        Args:
            document: Parsed document
            
        Returns:
            Processed document
        """
        # Remove empty nodes
        self._remove_empty_nodes(document.root)
        
        # Merge adjacent text nodes if configured
        if self.config.merge_adjacent_nodes:
            self._merge_adjacent_nodes(document.root)
        
        # Normalize heading levels
        self._normalize_heading_levels(document.root)
        
        # Enhance section detection if configured
        if self.config.detect_sections:
            self._enhance_sections(document)
        
        # Add document statistics
        self._add_statistics(document)
        
        # Validate document structure
        self._validate_structure(document)
        
        return document
    
    def _remove_empty_nodes(self, node: Node):
        """Remove empty nodes from tree."""
        # Process children first (bottom-up)
        children_to_remove = []
        
        for child in node.children:
            self._remove_empty_nodes(child)
            
            # Check if child is empty
            if self._is_empty_node(child):
                children_to_remove.append(child)
        
        # Remove empty children
        for child in children_to_remove:
            node.remove_child(child)
    
    def _is_empty_node(self, node: Node) -> bool:
        """Check if node is empty and can be removed."""
        # Never remove table nodes
        if node.type == NodeType.TABLE:
            return False
        
        # Never remove nodes with metadata
        if node.metadata:
            return False
        
        # Check text nodes
        if isinstance(node, TextNode):
            return not node.text().strip()
        
        # Check other nodes with text content
        if hasattr(node, 'content') and isinstance(node.content, str):
            return not node.content.strip()
        
        # Check container nodes
        if not node.children:
            # Empty container with no children
            return True
        
        return False
    
    def _merge_adjacent_nodes(self, node: Node):
        """Merge adjacent text nodes with similar properties."""
        if not node.children:
            return
        
        # Process children first
        for child in node.children:
            self._merge_adjacent_nodes(child)
        
        # Merge adjacent text nodes
        merged_children = []
        i = 0
        
        while i < len(node.children):
            current = node.children[i]
            
            # Look for mergeable nodes
            if self._can_merge(current):
                # Collect all adjacent mergeable nodes
                merge_group = [current]
                j = i + 1
                
                while j < len(node.children) and self._can_merge_with(current, node.children[j]):
                    merge_group.append(node.children[j])
                    j += 1
                
                # Merge if we have multiple nodes
                if len(merge_group) > 1:
                    merged = self._merge_nodes(merge_group)
                    merged_children.append(merged)
                    i = j
                else:
                    merged_children.append(current)
                    i += 1
            else:
                merged_children.append(current)
                i += 1
        
        # Update children
        node.children = merged_children
        
        # Update parent references
        for child in node.children:
            child.parent = node
    
    def _can_merge(self, node: Node) -> bool:
        """Check if node can be merged."""
        # Only merge TextNodes, not ParagraphNodes
        return isinstance(node, TextNode) and not node.metadata
    
    def _can_merge_with(self, node1: Node, node2: Node) -> bool:
        """Check if two nodes can be merged."""
        # Must be same type
        if type(node1) != type(node2):
            return False
        
        # Must have compatible styles
        if not self._compatible_styles(node1.style, node2.style):
            return False
        
        # Must not have metadata
        if node1.metadata or node2.metadata:
            return False
        
        return True
    
    def _compatible_styles(self, style1, style2) -> bool:
        """Check if two styles are compatible for merging."""
        # For now, just check key properties
        return (
            style1.font_size == style2.font_size and
            style1.font_weight == style2.font_weight and
            style1.text_align == style2.text_align
        )
    
    def _merge_nodes(self, nodes: List[Node]) -> Node:
        """Merge multiple nodes into one."""
        if not nodes:
            return None
        
        # Use first node as base
        merged = nodes[0]
        
        # Merge content
        if isinstance(merged, TextNode):
            texts = [n.text() for n in nodes]
            merged.content = '\n'.join(texts)
        elif isinstance(merged, ParagraphNode):
            # Merge all children
            for node in nodes[1:]:
                merged.children.extend(node.children)
        
        return merged
    
    def _normalize_heading_levels(self, node: Node):
        """Normalize heading levels to ensure proper hierarchy."""
        # Collect all headings
        headings = []
        self._collect_headings(node, headings)
        
        if not headings:
            return
        
        # Analyze heading structure
        levels_used = set(h.level for h in headings)
        
        # If we're missing level 1, promote headings
        if 1 not in levels_used and levels_used:
            min_level = min(levels_used)
            adjustment = min_level - 1
            
            for heading in headings:
                heading.level = max(1, heading.level - adjustment)
    
    def _collect_headings(self, node: Node, headings: List[HeadingNode]):
        """Collect all heading nodes."""
        if isinstance(node, HeadingNode):
            headings.append(node)
        
        for child in node.children:
            self._collect_headings(child, headings)
    
    def _enhance_sections(self, document: Document):
        """Enhance section detection and metadata."""
        # Only extract sections eagerly if configured to do so
        if not self.config.eager_section_extraction:
            return
            
        # Force section extraction to populate cache
        _ = document.sections
        
        # Add section metadata to nodes
        for section_name, section in document.sections.items():
            # Add section name to all nodes in section
            for node in section.node.walk():
                node.set_metadata('section', section_name)
    
    def _add_statistics(self, document: Document):
        """Add document statistics to metadata."""
        stats = {
            'node_count': sum(1 for _ in document.root.walk()),
            'text_length': len(document.text()),
            'table_count': len(document.tables),
            'heading_count': len(document.headings),
        }
        
        # Only add section count if sections were extracted
        if self.config.eager_section_extraction:
            stats['section_count'] = len(document.sections)
        
        document.metadata.statistics = stats
    
    def _validate_structure(self, document: Document):
        """Validate document structure and fix issues."""
        issues = []
        
        # Check for orphaned nodes
        for node in document.root.walk():
            if node != document.root and node.parent is None:
                issues.append(f"Orphaned node: {node.type}")
                # Fix by adding to root
                document.root.add_child(node)
        
        # Check for circular references
        visited = set()
        
        def check_cycles(node: Node, path: Set[str]):
            if node.id in path:
                issues.append(f"Circular reference detected: {node.type}")
                return
            
            path.add(node.id)
            visited.add(node.id)
            
            for child in node.children:
                if child.id not in visited:
                    check_cycles(child, path.copy())
        
        check_cycles(document.root, set())
        
        # Store validation results
        if issues:
            document.metadata.validation_issues = issues