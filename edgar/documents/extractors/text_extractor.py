"""
Text extraction from documents with various options.
"""

import re
from typing import List, Optional, Set
from edgar.documents.document import Document
from edgar.documents.nodes import Node, TextNode, HeadingNode, ParagraphNode
from edgar.documents.table_nodes import TableNode
from edgar.documents.types import NodeType


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
                 include_tables: bool = True,
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
        
        # Apply minimal global cleaning - tables are already handled appropriately per node
        if self.clean:
            text = self._clean_document_text(text)
        
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
            text = self._clean_document_text(text)
        
        return text
    
    def _extract_from_node(self, node: Node, parts: List[str], depth: int):
        """Recursively extract text from node - render each node type appropriately."""
        # Skip if already extracted (handles shared nodes)
        if node.id in self._extracted_ids:
            return
        self._extracted_ids.add(node.id)
        
        # Handle based on node type - like old parser's block.get_text()
        if isinstance(node, TableNode):
            if self.include_tables:
                # Tables render themselves - preserve their formatting 
                self._extract_table(node, parts)
        
        elif isinstance(node, HeadingNode):
            # Headings get cleaned text
            self._extract_heading(node, parts, depth)
        
        elif isinstance(node, TextNode):
            # Text nodes get cleaned if cleaning is enabled
            text = node.text()
            if text:
                if self.clean:
                    text = self._clean_text_content(text)  # Clean non-table text
                if self.include_metadata and node.metadata:
                    text = self._annotate_with_metadata(text, node.metadata)
                parts.append(text)
        
        elif isinstance(node, ParagraphNode):
            # Extract paragraph as unified text to maintain flow of inline elements
            text = node.text()
            if text:
                if self.clean:
                    text = self._clean_text_content(text)
                if self.include_metadata and node.metadata:
                    text = self._annotate_with_metadata(text, node.metadata)
                parts.append(text)
            # Don't process children since we already got the paragraph text
            return
        
        else:
            # Check if this looks like a bullet point container that should flow together
            if self._is_bullet_point_container(node):
                # Extract text from bullet point children and join with spaces (not newlines)
                bullet_parts = []
                for child in node.children:
                    child_text = child.text() if hasattr(child, 'text') else ""
                    if child_text and child_text.strip():
                        bullet_parts.append(child_text.strip())
                
                if bullet_parts:
                    # Join with spaces for bullet points
                    text = ' '.join(bullet_parts)
                    if self.clean:
                        text = self._clean_text_content(text)
                    if self.include_metadata and node.metadata:
                        text = self._annotate_with_metadata(text, node.metadata)
                    parts.append(text)
                # Don't process children since we already got the unified text
                return
            
            # For other nodes, extract text content and clean if appropriate
            if hasattr(node, 'content') and isinstance(node.content, str):
                text = node.content
                if text and text.strip():
                    if self.clean:
                        text = self._clean_text_content(text)  # Clean non-table text
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
        """Extract table content - preserve original formatting like old parser."""
        if self.preserve_structure:
            parts.append("[TABLE START]")
        
        # Add table caption if present
        if table.caption:
            caption_text = table.caption
            if self.clean:
                caption_text = self._clean_text_content(caption_text)  # Clean caption but not table content
            if self.preserve_structure:
                parts.append(f"Caption: {caption_text}")
            else:
                parts.append(caption_text)
        
        # Extract table text - PRESERVE FORMATTING (like old parser's TableBlock.get_text())
        table_text = table.text()
        if table_text:
            # Tables render their own formatting - don't apply text cleaning to preserve alignment
            parts.append(table_text)  # Keep original spacing and alignment
        
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
    
    def _clean_text_content(self, text: str) -> str:
        """Clean regular text content (not tables) - like old parser text cleaning."""
        if not text:
            return text
        
        # Replace multiple spaces with single space for regular text
        text = re.sub(r' {2,}', ' ', text)
        
        # Clean up space around newlines
        text = re.sub(r' *\n *', '\n', text)
        
        # Remove leading/trailing whitespace from lines
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        text = '\n'.join(lines)
        
        # Normalize quotes and dashes
        text = self._normalize_punctuation(text)
        
        return text
    
    def _is_bullet_point_container(self, node) -> bool:
        """Check if a container node represents a bullet point that should flow as one line."""
        from edgar.documents.nodes import ContainerNode
        
        if not isinstance(node, ContainerNode):
            return False
        
        # Must have at least 2 children (bullet + content)
        if len(node.children) < 2:
            return False
        
        # Get the text of all children to check for bullet patterns
        all_text = node.text()
        if not all_text:
            return False
        
        # Check if starts with common bullet characters
        bullet_chars = ['•', '●', '▪', '▫', '◦', '‣', '-', '*']
        starts_with_bullet = any(all_text.strip().startswith(char) for char in bullet_chars)
        
        if not starts_with_bullet:
            return False
        
        # Check if container has flex display (common for bullet point layouts)
        if hasattr(node, 'style') and node.style and hasattr(node.style, 'display'):
            if node.style.display == 'flex':
                return True
        
        # Check if it has bullet-like structure: short first child + longer content
        if len(node.children) >= 2:
            first_child_text = node.children[0].text() if hasattr(node.children[0], 'text') else ""
            second_child_text = node.children[1].text() if hasattr(node.children[1], 'text') else ""
            
            # First child is very short (likely bullet), second is longer (content)
            if len(first_child_text.strip()) <= 3 and len(second_child_text.strip()) > 10:
                return True
        
        return False
    
    def _clean_document_text(self, text: str) -> str:
        """Apply minimal document-level cleaning that preserves table formatting."""
        if not text:
            return text
        
        # Only apply global formatting that doesn't affect table alignment:
        
        # Replace excessive newlines (4+ consecutive) with triple newline
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        
        # Remove empty lines at start/end only
        text = text.strip()
        
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