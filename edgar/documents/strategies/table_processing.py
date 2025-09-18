"""
Advanced table processing strategy.
"""

import re
from typing import List, Optional

from lxml.html import HtmlElement

from edgar.documents.config import ParserConfig
from edgar.documents.strategies.style_parser import StyleParser
from edgar.documents.table_nodes import Cell, Row, TableNode
from edgar.documents.types import TableType


class TableProcessor:
    """
    Advanced table processing with type detection and structure analysis.
    """

    # HTML entities that need replacement
    ENTITY_REPLACEMENTS = {
        '&horbar;': '-----',
        '&mdash;': '-----',
        '&ndash;': '---',
        '&minus;': '-',
        '&hyphen;': '-',
        '&dash;': '-',
        '&nbsp;': ' ',
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
        '&quot;': '"',
        '&apos;': "'",
        '&#8202;': ' ',
        '&#8203;': '',
        '&#x2014;': '-----',
        '&#x2013;': '---',
        '&#x2212;': '-',
    }

    # Financial keywords for table type detection
    FINANCIAL_KEYWORDS = {
        'revenue', 'income', 'expense', 'asset', 'liability',
        'cash', 'equity', 'profit', 'loss', 'margin',
        'earnings', 'cost', 'sales', 'operating', 'net',
        'gross', 'total', 'balance', 'statement', 'consolidated'
    }

    # Metrics keywords
    METRICS_KEYWORDS = {
        'ratio', 'percentage', 'percent', '%', 'rate',
        'growth', 'change', 'increase', 'decrease',
        'average', 'median', 'total', 'count', 'number'
    }

    def __init__(self, config: ParserConfig):
        """Initialize table processor."""
        self.config = config
        self.style_parser = StyleParser()

    def process(self, element: HtmlElement) -> TableNode:
        """
        Process table element into TableNode.

        Args:
            element: HTML table element

        Returns:
            Processed TableNode
        """
        # Extract table metadata
        table_id = element.get('id')
        table_class = element.get('class', '').split()
        table_style = self.style_parser.parse(element.get('style', ''))

        # Create table node
        table = TableNode(style=table_style)

        # Add metadata
        if table_id:
            table.set_metadata('id', table_id)
        if table_class:
            table.set_metadata('classes', table_class)

        # Extract caption
        caption_elem = element.find('.//caption')
        if caption_elem is not None:
            table.caption = self._extract_text(caption_elem)

        # Extract summary
        summary = element.get('summary')
        if summary:
            table.summary = summary

        # Process table structure
        self._process_table_structure(element, table)

        # Detect table type if configured
        if self.config.detect_table_types:
            table.table_type = self._detect_table_type(table)

        # Extract relationships if configured
        if self.config.extract_table_relationships:
            self._extract_relationships(table)

        return table

    def _process_table_structure(self, element: HtmlElement, table: TableNode):
        """Process table structure (thead, tbody, tfoot)."""
        # Process thead
        thead = element.find('.//thead')
        if thead is not None:
            for tr in thead.findall('.//tr'):
                cells = self._process_row(tr, is_header=True)
                if cells:
                    table.headers.append(cells)

        # Process tbody (or direct rows)
        tbody = element.find('.//tbody')
        rows_container = tbody if tbody is not None else element

        # Track if we've seen headers
        headers_found = bool(table.headers)

        for tr in rows_container.findall('.//tr'):
            # Skip if already processed in thead
            if thead is not None and tr.getparent() == thead:
                continue

            # Check if this might be a header row
            is_header_row = False
            if not headers_found:
                is_header_row = self._is_header_row(tr)

            cells = self._process_row(tr, is_header=is_header_row)
            if cells:
                if is_header_row:
                    table.headers.append(cells)
                    headers_found = True
                else:
                    row = Row(cells=cells, is_header=False)
                    table.rows.append(row)

        # Process tfoot
        tfoot = element.find('.//tfoot')
        if tfoot is not None:
            for tr in tfoot.findall('.//tr'):
                cells = self._process_row(tr, is_header=False)
                if cells:
                    row = Row(cells=cells, is_header=False)
                    table.footer.append(row)

    def _process_row(self, tr: HtmlElement, is_header: bool) -> List[Cell]:
        """Process table row into cells."""
        cells = []

        # Process both td and th elements
        for cell_elem in tr.findall('.//td') + tr.findall('.//th'):
            cell = self._process_cell(cell_elem, is_header or cell_elem.tag == 'th')
            if cell:
                cells.append(cell)

        return cells

    def _process_cell(self, elem: HtmlElement, is_header: bool) -> Optional[Cell]:
        """Process table cell."""
        # Extract cell properties
        colspan = int(elem.get('colspan', '1'))
        rowspan = int(elem.get('rowspan', '1'))
        align = elem.get('align')

        # Extract style
        style = self.style_parser.parse(elem.get('style', ''))
        if style.text_align:
            align = style.text_align

        # Extract content
        content = self._extract_cell_content(elem)

        # Create cell
        cell = Cell(
            content=content,
            colspan=colspan,
            rowspan=rowspan,
            is_header=is_header,
            align=align
        )

        return cell

    def _extract_cell_content(self, elem: HtmlElement) -> str:
        """Extract and clean cell content."""
        # Check for nested structure
        divs = elem.findall('.//div')
        if divs and len(divs) > 1:
            # Multiple divs - likely multi-line content
            lines = []
            for div in divs:
                text = self._extract_text(div)
                if text:
                    lines.append(text)
            return '\n'.join(lines)

        # Handle line breaks
        for br in elem.findall('.//br'):
            br.tail = '\n' + (br.tail or '')

        # Extract text
        text = self._extract_text(elem)

        return text

    def _extract_text(self, elem: HtmlElement) -> str:
        """Extract and clean text from element."""
        # Get text content
        text = elem.text_content()

        # Replace entities
        for entity, replacement in self.ENTITY_REPLACEMENTS.items():
            text = text.replace(entity, replacement)

        # Clean whitespace
        text = text.strip()

        # Normalize internal whitespace but preserve line breaks
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            # Collapse multiple spaces to single space
            line = ' '.join(line.split())
            cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)

    def _is_header_row(self, tr: HtmlElement) -> bool:
        """Detect if row is likely a header row."""
        # Check if contains th elements
        if tr.find('.//th') is not None:
            return True

        # Check if all cells are bold
        cells = tr.findall('.//td')
        if not cells:
            return False

        bold_count = 0
        for cell in cells:
            style = cell.get('style', '')
            if 'font-weight' in style and 'bold' in style:
                bold_count += 1
            elif cell.find('.//b') is not None or cell.find('.//strong') is not None:
                bold_count += 1

        if bold_count == len(cells):
            return True

        # Check if row contains typical header keywords
        text = tr.text_content().lower()
        header_keywords = ['total', 'description', 'amount', 'date', 'period', 'year']
        if any(keyword in text for keyword in header_keywords):
            return True

        return False

    def _detect_table_type(self, table: TableNode) -> TableType:
        """Detect the type of table based on content."""
        # Collect text from headers and first few rows
        text_parts = []

        # Add caption
        if table.caption:
            text_parts.append(table.caption.lower())

        # Add headers
        for header_row in table.headers:
            for cell in header_row:
                text_parts.append(cell.text().lower())

        # Add first few rows
        for row in table.rows[:3]:
            for cell in row.cells:
                text_parts.append(cell.text().lower())

        combined_text = ' '.join(text_parts)

        # Check for financial table
        financial_count = sum(1 for keyword in self.FINANCIAL_KEYWORDS if keyword in combined_text)
        if financial_count >= 3:
            return TableType.FINANCIAL

        # Check for metrics table
        metrics_count = sum(1 for keyword in self.METRICS_KEYWORDS if keyword in combined_text)
        numeric_cells = sum(1 for row in table.rows for cell in row.cells if cell.is_numeric)
        total_cells = sum(len(row.cells) for row in table.rows)

        if total_cells > 0:
            numeric_ratio = numeric_cells / total_cells
            if metrics_count >= 2 or numeric_ratio > 0.5:
                return TableType.METRICS

        # Check for table of contents
        if 'content' in combined_text or 'index' in combined_text:
            # Look for page numbers
            has_page_numbers = any(
                re.search(r'\b\d{1,3}\b', cell.text()) 
                for row in table.rows 
                for cell in row.cells
            )
            if has_page_numbers:
                return TableType.TABLE_OF_CONTENTS

        # Check for exhibit index
        if 'exhibit' in combined_text:
            return TableType.EXHIBIT_INDEX

        # Check for reference table (citations, definitions, etc.)
        if any(word in combined_text for word in ['reference', 'definition', 'glossary', 'citation']):
            return TableType.REFERENCE

        return TableType.GENERAL

    def _extract_relationships(self, table: TableNode):
        """Extract relationships within table data."""
        # This would implement relationship extraction
        # For now, just set a flag that relationships were processed
        table.set_metadata('relationships_extracted', True)

        # Example relationships to extract:
        # - Parent-child relationships (indented rows)
        # - Total rows that sum other rows
        # - Cross-references between cells
        # - Time series relationships

        # Detect total rows
        total_rows = []
        for i, row in enumerate(table.rows):
            if row.is_total_row:
                total_rows.append(i)

        if total_rows:
            table.set_metadata('total_rows', total_rows)

        # Detect indentation patterns (parent-child)
        indentation_levels = []
        for row in table.rows:
            if row.cells:
                first_cell_text = row.cells[0].text()
                # Count leading spaces
                indent = len(first_cell_text) - len(first_cell_text.lstrip())
                indentation_levels.append(indent)

        if any(level > 0 for level in indentation_levels):
            table.set_metadata('has_hierarchy', True)
            table.set_metadata('indentation_levels', indentation_levels)
