"""
Text extraction from documents with various options.
"""

import re
from typing import List, Optional, Set

from edgar.documents.document import Document
from edgar.documents.nodes import HeadingNode, Node, ParagraphNode, TextNode
from edgar.documents.table_nodes import TableNode


class TextExtractor:
    """
    Extracts text from documents with configurable options.

    Supports:
    - Clean text extraction for AI/NLP
    - Table inclusion/exclusion
    - Metadata annotations
    - Length limiting
    - Smart whitespace handling
    """

    def __init__(self,
                 clean: bool = True,
                 include_tables: bool = False,
                 include_metadata: bool = False,
                 include_links: bool = False,
                 max_length: Optional[int] = None,
                 preserve_structure: bool = False):
        """
        Initialize text extractor.

        Args:
            clean: Clean and normalize text
            include_tables: Include table content
            include_metadata: Include metadata annotations
            include_links: Include link URLs
            max_length: Maximum text length
            preserve_structure: Preserve document structure with markers
        """
        self.clean = clean
        self.include_tables = include_tables
        self.include_metadata = include_metadata
        self.include_links = include_links
        self.max_length = max_length
        self.preserve_structure = preserve_structure

        # Track what we've extracted to avoid duplicates
        self._extracted_ids: Set[str] = set()

    def extract(self, document: Document) -> str:
        """
        Extract text from document.

        Args:
            document: Document to extract from

        Returns:
            Extracted text
        """
        parts = []
        self._extracted_ids.clear()

        # Extract from root
        self._extract_from_node(document.root, parts, depth=0)

        # Join parts
        if self.preserve_structure:
            text = '\n'.join(parts)
        else:
            text = '\n\n'.join(filter(None, parts))

        # Clean if requested
        if self.clean:
            text = self._clean_text(text)

        # Limit length if requested
        if self.max_length and len(text) > self.max_length:
            text = self._truncate_text(text, self.max_length)

        return text

    def extract_from_node(self, node: Node) -> str:
        """Extract text from a specific node."""
        parts = []
        self._extracted_ids.clear()
        self._extract_from_node(node, parts, depth=0)

        text = '\n\n'.join(filter(None, parts))

        if self.clean:
            text = self._clean_text(text)

        return text

    def _extract_from_node(self, node: Node, parts: List[str], depth: int):
        """Recursively extract text from node."""
        # Skip if already extracted (handles shared nodes)
        if node.id in self._extracted_ids:
            return
        self._extracted_ids.add(node.id)

        # Handle based on node type
        if isinstance(node, TableNode):
            if self.include_tables:
                self._extract_table(node, parts)

        elif isinstance(node, HeadingNode):
            self._extract_heading(node, parts, depth)

        elif isinstance(node, TextNode):
            text = node.text()
            if text:
                if self.include_metadata and node.metadata:
                    text = self._annotate_with_metadata(text, node.metadata)
                parts.append(text)

        elif isinstance(node, ParagraphNode):
            # For ParagraphNode, let children be processed naturally
            # to avoid duplicating text
            pass

        else:
            # For other nodes, extract text content
            if hasattr(node, 'content') and isinstance(node.content, str):
                text = node.content
                if text and text.strip():
                    if self.include_metadata and node.metadata:
                        text = self._annotate_with_metadata(text, node.metadata)
                    parts.append(text)

        # Process children
        for child in node.children:
            self._extract_from_node(child, parts, depth + 1)

    def _extract_heading(self, node: HeadingNode, parts: List[str], depth: int):
        """Extract heading with optional structure markers."""
        text = node.text()
        if not text:
            return

        if self.preserve_structure:
            # Add structure markers
            marker = '#' * node.level
            text = f"{marker} {text}"

        if self.include_metadata and node.metadata:
            text = self._annotate_with_metadata(text, node.metadata)

        parts.append(text)

    def _extract_table(self, table: TableNode, parts: List[str]):
        """Extract table content."""
        if self.preserve_structure:
            parts.append("[TABLE START]")

        # Add table caption if present
        if table.caption:
            if self.preserve_structure:
                parts.append(f"Caption: {table.caption}")
            else:
                parts.append(table.caption)

        # Extract table text
        table_text = table.text()
        if table_text:
            parts.append(table_text)

        if self.preserve_structure:
            parts.append("[TABLE END]")

    def _annotate_with_metadata(self, text: str, metadata: dict) -> str:
        """Add metadata annotations to text."""
        annotations = []

        # Add XBRL annotations
        if 'ix_tag' in metadata:
            annotations.append(f"[XBRL: {metadata['ix_tag']}]")

        # Add section annotations
        if 'section_name' in metadata:
            annotations.append(f"[Section: {metadata['section_name']}]")

        # Add semantic type
        if 'semantic_type' in metadata:
            annotations.append(f"[Type: {metadata['semantic_type']}]")

        if annotations:
            return f"{' '.join(annotations)} {text}"

        return text

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Replace multiple newlines with double newline
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Replace multiple spaces with single space
        text = re.sub(r' {2,}', ' ', text)

        # Clean up space around newlines
        text = re.sub(r' *\n *', '\n', text)

        # Remove leading/trailing whitespace from lines
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        text = '\n'.join(lines)

        # Remove empty lines at start/end
        text = text.strip()

        # Normalize quotes and dashes
        if self.clean:
            text = self._normalize_punctuation(text)

        return text

    def _normalize_punctuation(self, text: str) -> str:
        """Normalize punctuation for cleaner text."""
        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")

        # Normalize dashes
        text = text.replace('—', ' - ')  # em dash
        text = text.replace('–', ' - ')  # en dash

        # Fix spacing around punctuation
        text = re.sub(r'\s+([.,;!?])', r'\1', text)
        text = re.sub(r'([.,;!?])\s*', r'\1 ', text)

        # Remove extra spaces
        text = re.sub(r' {2,}', ' ', text)

        return text.strip()

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text intelligently."""
        if len(text) <= max_length:
            return text

        # Try to truncate at sentence boundary
        truncated = text[:max_length]
        last_period = truncated.rfind('.')
        last_newline = truncated.rfind('\n')

        # Choose the better truncation point
        truncate_at = max(last_period, last_newline)
        if truncate_at > max_length * 0.8:  # If we found a good boundary
            return text[:truncate_at + 1].strip()

        # Otherwise truncate at word boundary
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.9:
            return text[:last_space].strip() + '...'

        # Last resort: hard truncate
        return text[:max_length - 3].strip() + '...'
