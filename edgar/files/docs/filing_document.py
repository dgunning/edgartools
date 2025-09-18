"""
Enhanced SEC filing document representation with structured item extraction.

This module provides a high-level document class specialized for SEC filings, with
rich support for extracting items, tables, and table of contents.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Pattern

import pandas as pd

from edgar.files.html import BaseNode, Document, HeadingNode, TableNode


class Table:
    """Rich representation of a table in a document."""

    def __init__(self, table_node: TableNode):
        self._node = table_node
        self._processed = None  # Lazy-loaded processed table

    @property
    def rows(self) -> int:
        """Get the number of rows in the table."""
        processed = self._get_processed()
        if processed is None:
            return 0

        # Count header row if present plus data rows
        has_header = processed.headers is not None and len(processed.headers) > 0
        return len(processed.data_rows) + (1 if has_header else 0)

    @property
    def columns(self) -> int:
        """Get the number of columns in the table."""
        processed = self._get_processed()
        if processed is None:
            return 0

        # Use headers if available, otherwise first data row
        if processed.headers and len(processed.headers) > 0:
            return len(processed.headers)
        elif processed.data_rows and len(processed.data_rows) > 0:
            return len(processed.data_rows[0])
        return 0

    def _get_processed(self):
        """Get or create the processed table."""
        if self._processed is None:
            if hasattr(self._node, '_processed'):
                self._processed = self._node._processed
            # Handle case where node doesn't have processed table yet
            if self._processed is None and hasattr(self._node, '_get_processed'):
                # Call node's processing method if available
                self._processed = self._node._get_processed()
        return self._processed

    def to_dataframe(self) -> pd.DataFrame:
        """Convert this table to a pandas DataFrame."""
        processed = self._get_processed()
        if processed and processed.headers and processed.data_rows:
            # Create DataFrame with proper headers and data
            return pd.DataFrame(processed.data_rows, columns=processed.headers)
        elif processed and processed.data_rows:
            # No headers, use numeric column names
            return pd.DataFrame(processed.data_rows)
        return pd.DataFrame()

    def to_markdown(self) -> str:
        """Convert this table to markdown format."""
        df = self.to_dataframe()
        if not df.empty:
            return df.to_markdown()
        return ""

    def get_cell(self, row: int, col: int) -> str:
        """Get the content of a specific cell."""
        processed = self._get_processed()
        if processed is None:
            return ""

        # Handle header row (row 0)
        if row == 0 and processed.headers and col < len(processed.headers):
            return processed.headers[col]

        # Adjust row index if we have headers (data rows start at index 1)
        data_row_idx = row if processed.headers is None else row - 1

        # Get data from data rows
        if processed.data_rows and 0 <= data_row_idx < len(processed.data_rows):
            data_row = processed.data_rows[data_row_idx]
            if 0 <= col < len(data_row):
                return data_row[col]

        return ""

    def contains(self, text: str) -> bool:
        """Check if the table contains the specified text."""
        processed = self._get_processed()
        if not processed:
            return False

        # Check headers
        if processed.headers and any(text.lower() in str(header).lower() for header in processed.headers):
            return True

        # Check data rows
        for row in processed.data_rows:
            if any(text.lower() in str(cell).lower() for cell in row):
                return True

        return False

    def __str__(self) -> str:
        return self.to_markdown()

    def __repr__(self) -> str:
        return f"Table({self.rows}×{self.columns})"


@dataclass
class TocEntry:
    """Entry in a table of contents."""

    text: str
    level: int
    page: Optional[int] = None
    reference: Optional[str] = None  # Item reference, if applicable

    def __repr__(self) -> str:
        return f"TocEntry('{self.text}', level={self.level}, page={self.page})"


class TableOfContents:
    """Table of contents extracted from a document."""

    def __init__(self, entries: List[TocEntry]):
        self.entries = entries

    @classmethod
    def extract(cls, document: Document) -> 'TableOfContents':
        """Extract table of contents from document."""
        entries = []

        # Find TOC section (usually at the beginning)
        toc_node_index = cls._find_toc_section(document)
        if toc_node_index is None:
            return cls([])

        # Get nodes after TOC heading until the next major heading
        toc_nodes = cls._get_toc_nodes(document, toc_node_index)

        # Process nodes to extract entries
        entries = cls._process_toc_nodes(toc_nodes)

        # Match entries to actual items
        cls._match_entries_to_items(entries, document)

        return cls(entries)

    @staticmethod
    def _find_toc_section(document: Document) -> Optional[int]:
        """Find the TOC section in the document."""
        # Look for "Table of Contents" heading
        toc_patterns = [
            re.compile(r'table\s+of\s+contents', re.IGNORECASE),
            re.compile(r'contents', re.IGNORECASE)
        ]

        for i, node in enumerate(document.nodes):
            if node.type == 'heading':
                for pattern in toc_patterns:
                    if pattern.search(node.content):
                        return i
        return None

    @staticmethod
    def _get_toc_nodes(document: Document, start_index: int) -> List[BaseNode]:
        """Get nodes belonging to the TOC section."""
        # Get nodes between TOC heading and next heading of same or higher level
        nodes = []
        toc_heading = document.nodes[start_index]
        heading_level = toc_heading.level if hasattr(toc_heading, 'level') else 1

        for i in range(start_index + 1, len(document.nodes)):
            node = document.nodes[i]
            if node.type == 'heading' and hasattr(node, 'level') and node.level <= heading_level:
                break
            nodes.append(node)

        return nodes

    @staticmethod
    def _process_toc_nodes(nodes: List[BaseNode]) -> List[TocEntry]:
        """Process TOC nodes to extract entries."""
        entries = []

        # Patterns for detecting TOC entries
        item_pattern = re.compile(r'(item\s+\d+[A-Za-z]?)', re.IGNORECASE)
        page_pattern = re.compile(r'(\d+)$')

        for node in nodes:
            if node.type == 'text_block':
                # Process each line in the text block
                lines = node.content.splitlines()
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    # Extract indentation as a proxy for level
                    leading_spaces = len(line) - len(line.lstrip())
                    level = leading_spaces // 2 + 1  # Rough estimate of level

                    # Extract page number if present
                    page_match = page_pattern.search(line)
                    page = int(page_match.group(1)) if page_match else None

                    # Clean the text
                    text = line
                    if page_match:
                        text = line[:page_match.start()].strip()

                    # Check for Item reference
                    item_match = item_pattern.search(text)
                    reference = item_match.group(1) if item_match else None

                    entries.append(TocEntry(text, level, page, reference))

            elif node.type == 'table':
                # Process table rows as TOC entries
                table = Table(node)
                df = table.to_dataframe()

                if not df.empty:
                    for _, row in df.iterrows():
                        if len(row) >= 2:  # Assume col 0 is text, col 1 might be page
                            text = str(row[0]).strip()
                            if not text:
                                continue

                            # Try to extract page number
                            page = None
                            if len(row) > 1:
                                try:
                                    page = int(row[1])
                                except (ValueError, TypeError):
                                    pass

                            # Extract level from indentation or formatting
                            level = 1  # Default level
                            leading_spaces = len(text) - len(text.lstrip())
                            if leading_spaces > 0:
                                level = leading_spaces // 2 + 1

                            # Check for Item reference
                            item_match = item_pattern.search(text)
                            reference = item_match.group(1) if item_match else None

                            entries.append(TocEntry(text, level, page, reference))

        return entries

    @staticmethod
    def _match_entries_to_items(entries: List[TocEntry], document: Document) -> None:
        """Match TOC entries to actual items in the document."""
        # Create dictionary of potential item headings in the document
        item_headings = {}
        item_pattern = re.compile(r'(item\s+\d+[A-Za-z]?)', re.IGNORECASE)

        for i, node in enumerate(document.nodes):
            if node.type == 'heading':
                match = item_pattern.search(node.content)
                if match:
                    item_key = match.group(1).upper()
                    item_headings[item_key] = i

        # Match entries to items
        for entry in entries:
            if entry.reference:
                # Try to match reference to actual item
                item_key = entry.reference.upper()
                if item_key in item_headings:
                    entry.reference = item_key

    def find(self, text: str) -> Optional[TocEntry]:
        """Find a TOC entry by text."""
        text = text.lower()
        for entry in self.entries:
            if text in entry.text.lower():
                return entry
        return None

    def __iter__(self) -> Iterator[TocEntry]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)


class Item:
    """Represents a logical item in an SEC filing."""

    def __init__(self, 
                 name: str, 
                 heading_node: Optional[HeadingNode],
                 content_nodes: List[BaseNode],
                 metadata: Dict[str, Any] = None):
        self.name = name
        self.heading_node = heading_node
        self.content_nodes = content_nodes
        self.metadata = metadata or {}

    @property
    def title(self) -> str:
        """Get the title of this item."""
        if self.heading_node:
            # Extract title by removing the item number
            item_pattern = re.compile(r'^item\s+\d+[A-Za-z]?\.?\s*', re.IGNORECASE)
            return item_pattern.sub('', self.heading_node.content).strip()
        return ""

    @property
    def text(self) -> str:
        """Get the text content of this item."""
        parts = []
        for node in self.content_nodes:
            if hasattr(node, 'content'):
                if isinstance(node.content, str):
                    parts.append(node.content)
                elif isinstance(node.content, list):
                    # Handle list content (likely a table)
                    parts.append(str(node))
                else:
                    parts.append(str(node.content))
            else:
                parts.append(str(node))
        return "\n".join(parts)

    @property
    def tables(self) -> List[Table]:
        """Get all tables within this item."""
        return [
            Table(node) for node in self.content_nodes 
            if node.type == 'table'
        ]

    def get_table(self, index: int) -> Optional[Table]:
        """Get a specific table by index."""
        tables = self.tables
        return tables[index] if 0 <= index < len(tables) else None

    def find_tables(self, pattern: str) -> List[Table]:
        """Find tables containing the specified text pattern."""
        tables = []
        for table in self.tables:
            if table.contains(pattern):
                tables.append(table)
        return tables

    def get_subsections(self) -> List['Item']:
        """Extract nested subsections within this item."""
        subsections = []

        # Find heading nodes with higher level than the main item heading
        item_level = self.heading_node.level if self.heading_node else 0

        # Find all subsection headings
        subsection_indices = []
        for i, node in enumerate(self.content_nodes):
            if node.type == 'heading' and node.level > item_level:
                subsection_indices.append((i, node))

        # Create subsections
        for i, (idx, heading) in enumerate(subsection_indices):
            next_idx = subsection_indices[i+1][0] if i+1 < len(subsection_indices) else len(self.content_nodes)
            subsection_content = self.content_nodes[idx+1:next_idx]

            # Create an item for this subsection
            subsection = Item(
                name=heading.content,
                heading_node=heading,
                content_nodes=subsection_content
            )
            subsections.append(subsection)

        return subsections

    def to_markdown(self) -> str:
        """Convert this item to markdown format."""
        parts = []

        # Add heading
        if self.heading_node:
            parts.append(f"# {self.heading_node.content}\n")

        # Process content nodes
        for node in self.content_nodes:
            if node.type == 'heading':
                # Add appropriate heading level
                level = min(node.level + 1, 6)  # Ensure we don't exceed markdown's 6 levels
                parts.append(f"{'#' * level} {node.content}\n")

            elif node.type == 'text_block':
                parts.append(f"{node.content}\n\n")

            elif node.type == 'table':
                table = Table(node)
                parts.append(f"{table.to_markdown()}\n\n")

        return "\n".join(parts)

    def to_html(self) -> str:
        """Convert this item to HTML format."""
        parts = []

        # Add heading
        if self.heading_node:
            parts.append(f"<h1>{self.heading_node.content}</h1>")

        # Process content nodes
        for node in self.content_nodes:
            if node.type == 'heading':
                # Add appropriate heading level
                level = min(node.level + 1, 6)  # Ensure we don't exceed HTML's 6 levels
                parts.append(f"<h{level}>{node.content}</h{level}>")

            elif node.type == 'text_block':
                lines = node.content.split('\n')
                paragraphs = [f"<p>{line}</p>" for line in lines if line.strip()]
                parts.append("\n".join(paragraphs))

            elif node.type == 'table':
                # Convert the table to HTML
                table = Table(node)
                df = table.to_dataframe()
                parts.append(df.to_html(index=False))

        return "\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert this item to a dictionary."""
        return {
            'name': self.name,
            'title': self.title,
            'text': self.text,
            'metadata': self.metadata
        }

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"Item('{self.name}', title='{self.title}')"


class ItemCollection:
    """Collection of items in a document with convenient access methods."""

    def __init__(self, items: Dict[str, Item]):
        self._items = items

    def __getitem__(self, key: str) -> Item:
        """Get an item by name, with flexible matching."""
        # Case-insensitive lookup
        key = key.strip().upper()

        # Direct lookup
        if key in self._items:
            return self._items[key]

        # Remove any trailing periods for matching
        clean_key = key.rstrip('.')
        if clean_key in self._items:
            return self._items[clean_key]

        # Normalize for comparison (remove spaces and periods)
        normalized_key = re.sub(r'[.\s]', '', key)

        # Try to match normalized keys
        for item_key in self._items:
            normalized_item_key = re.sub(r'[.\s]', '', item_key)
            if normalized_key == normalized_item_key:
                return self._items[item_key]

        # Partial match (e.g., "1" matches "ITEM 1")
        if normalized_key.isdigit() or (len(normalized_key) > 1 and normalized_key[0].isdigit()):
            for item_key in self._items:
                normalized_item_key = re.sub(r'[.\s]', '', item_key)
                if normalized_key in normalized_item_key:
                    return self._items[item_key]

        raise KeyError(f"Item '{key}' not found")

    def __contains__(self, key: str) -> bool:
        """Check if an item exists."""
        try:
            self[key]
            return True
        except KeyError:
            return False

    def __iter__(self) -> Iterator[Item]:
        """Iterate through items in order."""
        for key in sorted(self._items.keys()):
            yield self._items[key]

    def __len__(self) -> int:
        """Get the number of items."""
        return len(self._items)

    def list(self) -> List[str]:
        """Get a list of item names."""
        return sorted(self._items.keys())


class DocumentIndex:
    """Index of document structure for efficient lookups."""

    def __init__(self):
        self._headings = {}  # Map of heading text to node index
        self._items = {}     # Map of item name to Item object

    @classmethod
    def build(cls, document: Document, filing_type: str = None) -> 'DocumentIndex':
        """Build an index from a document."""
        index = cls()
        index._build_heading_index(document)
        index._build_item_index(document, filing_type)
        return index

    def _build_heading_index(self, document: Document) -> None:
        """Build an index of all headings in the document."""
        for i, node in enumerate(document.nodes):
            if node.type == 'heading':
                self._headings[node.content] = i

    def _build_item_index(self, document: Document, filing_type: str = None) -> None:
        """Build an index of items in the document."""
        # Get appropriate item pattern based on filing type
        item_pattern = self._get_item_pattern(filing_type)

        # Find all item headings
        item_headings = []
        for i, node in enumerate(document.nodes):
            if node.type == 'heading':
                match = item_pattern.search(node.content)
                if match:
                    item_name = match.group(1).strip().upper()
                    item_headings.append((item_name, i, node))

        # If no heading-based items found, use fallback text-based detection
        if not item_headings:
            item_headings = self._fallback_item_detection(document, item_pattern)

        # Sort by position in document
        item_headings.sort(key=lambda x: x[1])

        # Create items
        for i, (item_name, node_idx, heading_node) in enumerate(item_headings):
            # Find content nodes
            start_idx = node_idx + 1
            end_idx = (item_headings[i+1][1] 
                      if i+1 < len(item_headings) else len(document.nodes))
            content_nodes = document.nodes[start_idx:end_idx]

            # Create item
            self._items[item_name] = Item(item_name, heading_node, content_nodes)

    def _fallback_item_detection(self, document: Document, item_pattern: re.Pattern) -> list:
        """
        Fallback item detection when heading-based detection fails.
        Uses text content and positional analysis to identify items.
        """
        from edgar.files.html import HeadingNode
        from edgar.files.styles import StyleInfo

        # Create reusable heading nodes
        def create_heading_node(content, level=2):
            return HeadingNode(
                content=content,
                style=StyleInfo(font_weight='bold'),  # minimal required style
                level=level,
                metadata={}
            )

        item_headings = []

        # Step 1: Oracle-specific table-based TOC detection (handles Oracle 10-K format)
        # First check for a table that contains item patterns and looks like a TOC
        table_nodes = [node for node in document.nodes if node.type == 'table']

        # Create a map of item references to detect in content
        item_references = {}
        toc_table_idx = None

        # First pass: find the table of contents and extract item references
        for table_idx, node in enumerate(table_nodes):
            toc_candidate = False
            item_to_content_map = {}

            # Check if this looks like a TOC table
            if hasattr(node, 'content') and isinstance(node.content, list):
                rows = node.content

                # Process each row to find item patterns
                for row_idx, row in enumerate(rows):
                    if not hasattr(row, 'cells'):
                        continue

                    # Check if this row contains an item pattern
                    for cell_idx, cell in enumerate(row.cells):
                        cell_content = cell.content if hasattr(cell, 'content') else ""
                        if not isinstance(cell_content, str):
                            continue

                        # Look for item pattern in this cell
                        match = item_pattern.search(cell_content)
                        if match:
                            toc_candidate = True
                            item_name = match.group(1).strip().upper()

                            # Extract title - could be in same cell after item name or in next cell
                            title = ""
                            # First look in the same cell after the item name
                            remaining_content = cell_content[match.end():].strip()
                            if remaining_content:
                                title = remaining_content
                            # If no title found in same cell, check next cell
                            elif cell_idx + 1 < len(row.cells):
                                next_cell = row.cells[cell_idx + 1]
                                next_content = next_cell.content if hasattr(next_cell, 'content') else ""
                                if isinstance(next_content, str):
                                    title = next_content.strip()

                            # Look for page number or anchor reference in later cells
                            ref = None
                            if cell_idx + 2 < len(row.cells):
                                ref_cell = row.cells[cell_idx + 2]
                                ref_content = ref_cell.content if hasattr(ref_cell, 'content') else ""
                                if isinstance(ref_content, str) and ref_content.strip():
                                    ref = ref_content.strip()

                            # Store item details with full context
                            item_to_content_map[item_name] = {
                                'title': title,
                                'reference': ref,
                                'row_idx': row_idx
                            }

                            # Add to global item references
                            item_references[item_name] = {
                                'title': title,
                                'reference': ref,
                                'found': False  # Will be set to True when we find the content
                            }

            # If this table is a TOC candidate with multiple items, remember it
            if toc_candidate and len(item_to_content_map) >= 2:
                toc_table_idx = table_idx

        # Second pass: if we found a TOC table, look for items in the document
        if item_references:
            # Look for anchor IDs that match item references
            anchor_nodes = {}
            for i, node in enumerate(document.nodes):
                # Check for id attribute that might be a target for TOC links
                if hasattr(node, 'attrs') and node.attrs.get('id'):
                    anchor_id = node.attrs.get('id')
                    anchor_nodes[anchor_id] = i

            # Look for nodes that might contain items
            for i, node in enumerate(document.nodes):
                # Skip nodes before the TOC table if we found one
                if toc_table_idx is not None and i <= toc_table_idx:
                    continue

                # Get node content
                if not hasattr(node, 'content'):
                    continue

                node_content = node.content
                if not isinstance(node_content, str):
                    continue

                # Check for each item in our reference map
                for item_name, item_info in item_references.items():
                    if item_info['found']:
                        continue  # Already found this item

                    # Method 1: Look for exact item pattern at start of text
                    if node_content.strip().upper().startswith(item_name):
                        # Found item directly
                        content = f"{item_name} {item_info['title']}".strip()
                        heading_node = create_heading_node(content)
                        item_headings.append((item_name, i, heading_node))
                        item_references[item_name]['found'] = True
                        break

                    # Method 2: Look for the title text if we have it
                    if item_info['title'] and item_info['title'].strip():
                        # This can have false positives, so make sure it's a good match
                        title = item_info['title'].strip()
                        # Check if the title appears together with the item name
                        if (f"{item_name} {title}".upper() in node_content.upper() or
                            title.upper() in node_content.upper() and 
                            "ITEM" in node_content.upper()):

                            content = f"{item_name} {title}".strip()
                            heading_node = create_heading_node(content)
                            item_headings.append((item_name, i, heading_node))
                            item_references[item_name]['found'] = True
                            break

            # If we found items from the TOC references, return them
            if any(info['found'] for info in item_references.values()):
                # Sort by position in document
                item_headings.sort(key=lambda x: x[1])
                return item_headings

        # Step 2: Oracle table cell detection
        # This specifically targets Oracle 10-K's format where items are in table cells
        # but not marked as headings and not part of a formal TOC
        item_section_map = {}

        for table_idx, node in enumerate(table_nodes):
            if hasattr(node, 'content') and isinstance(node.content, list):
                rows = node.content

                for row_idx, row in enumerate(rows):
                    if not hasattr(row, 'cells'):
                        continue

                    for cell_idx, cell in enumerate(row.cells):
                        cell_content = cell.content if hasattr(cell, 'content') else ""
                        if not isinstance(cell_content, str):
                            continue

                        # Check if this cell contains an item pattern as an isolated entry
                        # This is common in Oracle 10-K where items are in cells by themselves
                        match = item_pattern.search(cell_content)
                        if match and len(cell_content.strip()) < 50:  # Short isolated item cell
                            item_name = match.group(1).strip().upper()

                            # Look for the title in adjacent cells
                            title = ""
                            if cell_idx + 1 < len(row.cells):
                                next_cell = row.cells[cell_idx + 1]
                                next_content = next_cell.content if hasattr(next_cell, 'content') else ""
                                if isinstance(next_content, str):
                                    title = next_content.strip()

                            # Check for bold text or other emphasis indicators
                            is_emphasized = False
                            if hasattr(cell, 'style'):
                                if hasattr(cell.style, 'font_weight') and cell.style.font_weight in ['bold', '700', '800', '900']:
                                    is_emphasized = True
                                elif hasattr(cell.style, 'font_style') and cell.style.font_style == 'italic':
                                    is_emphasized = True

                            # Store the item with its table position for later extraction
                            item_section_map[item_name] = {
                                'table_idx': table_idx,
                                'row_idx': row_idx,
                                'title': title,
                                'emphasized': is_emphasized
                            }

        # If we found items in tables, try to map them to content sections
        if item_section_map:
            # Create a mapping of items to their positions in the document
            table_positions = {}
            for i, node in enumerate(document.nodes):
                if node.type == 'table':
                    table_positions[node] = i

            for item_name, info in item_section_map.items():
                # Create a heading node with the item and title
                content = f"{item_name} {info['title']}".strip()
                heading_node = create_heading_node(content)

                # Find this table's position in the document
                target_table = table_nodes[info['table_idx']]
                if target_table in table_positions:
                    table_pos = table_positions[target_table]
                    # Add this item, prioritizing emphasized ones
                    if info['emphasized']:
                        item_headings.insert(0, (item_name, table_pos, heading_node))
                    else:
                        item_headings.append((item_name, table_pos, heading_node))

        # Sort item headings by position and check if we found enough
        if item_headings:
            item_headings.sort(key=lambda x: x[1])
            # If we found multiple items from tables, return them
            if len(item_headings) >= 2:
                return item_headings

        # Step 3: Iterate through all nodes looking for text blocks that might be item headings
        for i, node in enumerate(document.nodes):
            # Check text blocks that might be mis-classified headings
            if node.type == 'text_block':
                # Use only the first line to avoid matching within paragraphs
                first_line = node.content.split('\n')[0] if hasattr(node, 'content') else ''
                match = item_pattern.search(first_line)

                if match:
                    item_name = match.group(1).strip().upper()

                    # Additional validation to reduce false positives
                    # Check if this looks like a real item heading:
                    # 1. Should be relatively short
                    # 2. Should start with the matched pattern
                    # 3. Should not be part of a longer paragraph
                    if (len(first_line) < 100 and 
                        first_line.lower().startswith(match.group(1).lower()) and
                        len(first_line.split()) < 15):

                        # Check for bold font-weight in the node's style if available
                        is_bold = False
                        if hasattr(node, 'style') and hasattr(node.style, 'font_weight'):
                            fw = node.style.font_weight
                            is_bold = fw in ['bold', '700', '800', '900']

                        # Prioritize bold text that matches item patterns
                        if is_bold:
                            item_headings.insert(0, (item_name, i, node))
                        else:
                            item_headings.append((item_name, i, node))

        # If we found items, return them
        if item_headings:
            return item_headings

        # Step 4: Last resort - check all nodes for ANY mention of items
        # This is a last resort to find something when other methods fail
        for i, node in enumerate(document.nodes):
            if hasattr(node, 'content') and isinstance(node.content, str):
                lines = node.content.split('\n')
                for _line_idx, line in enumerate(lines):
                    match = item_pattern.search(line)
                    if match and len(line.strip()) < 100:  # Avoid matching in long paragraphs
                        item_name = match.group(1).strip().upper()

                        # Create a heading node with just the matching line
                        heading_node = create_heading_node(line)

                        # We'll use the position of the node containing the pattern
                        item_headings.append((item_name, i, heading_node))

        return item_headings

    @staticmethod
    def _get_item_pattern(filing_type: str) -> Pattern:
        """Get the regex pattern for identifying items in this filing type."""
        # Default to standard 10-K/10-Q item pattern
        if filing_type in ('10-K', '10-K/A', '10-Q', '10-Q/A', '20-F', '20-F/A'):
            # Enhanced pattern to better handle different formats:
            # - Normal format: "Item 1." or "ITEM 1"
            # - Oracle format: "ITEM 1." or "Item 1"
            # - With periods: "Item 1." or without "Item 1"
            # - With trailing spaces: "Item 1 " 
            # - With different spacing: "Item1" or "ITEM  1"
            return re.compile(r'(item\s*\d+[A-Za-z]?)\.?\s*', re.IGNORECASE)
        elif filing_type in ('8-K', '8-K/A', '6-K', '6-K/A'):
            # 8-K uses decimal format like "Item 1.01"
            return re.compile(r'(item\s*\d+\.\d+)\.?\s*', re.IGNORECASE)
        else:
            # Default pattern for other filings - most flexible
            return re.compile(r'(item\s*\d+(?:\.\d+)?[A-Za-z]?)\.?\s*', re.IGNORECASE)

    @property
    def items(self) -> ItemCollection:
        """Get the collection of items in this document."""
        return ItemCollection(self._items)


class FilingDocument:
    """High-level document class specialized for SEC filings."""

    def __init__(self, html: str, filing_type: str = None):
        self._document = Document.parse(html)
        self._filing_type = filing_type
        self._index = None  # Lazy-loaded
        self._toc = None    # Lazy-loaded

    @property
    def document(self) -> Document:
        """Access the underlying Document instance."""
        return self._document

    @property
    def index(self) -> DocumentIndex:
        """Get or create the document index."""
        if self._index is None:
            self._index = DocumentIndex.build(self._document, self._filing_type)
        return self._index

    @property
    def items(self) -> ItemCollection:
        """Access items in the document."""
        return self.index.items

    @property
    def table_of_contents(self) -> TableOfContents:
        """Get the table of contents for this document."""
        if self._toc is None:
            self._toc = TableOfContents.extract(self._document)
        return self._toc

    @property
    def tables(self) -> List[Table]:
        """Get all tables in the document."""
        return [
            Table(node) for node in self._document.nodes 
            if node.type == 'table'
        ]

    def __getitem__(self, key: str) -> Item:
        """Dictionary-style access to items."""
        return self.items[key]
