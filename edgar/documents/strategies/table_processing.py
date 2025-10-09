"""
Advanced table processing strategy.
"""

import re
from functools import lru_cache
from typing import List, Optional

from lxml.html import HtmlElement

from edgar.documents.config import ParserConfig
from edgar.documents.strategies.style_parser import StyleParser
from edgar.documents.table_nodes import TableNode, Cell, Row
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
        'gross', 'total', 'balance', 'statement', 'consolidated',
        'provision', 'tax', 'taxes', 'compensation', 'stock',
        'share', 'shares', 'rsu', 'option', 'grant', 'vest'
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
        
        # Set config for rendering decisions
        table._config = self.config
        
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
        
        # Track if we've seen headers and data rows
        headers_found = bool(table.headers)
        consecutive_header_rows = 0
        data_rows_started = False
        
        for tr in rows_container.findall('.//tr'):
            # Skip if already processed in thead
            if thead is not None and tr.getparent() == thead:
                continue
            
            # Check if this might be a header row
            is_header_row = False
            
            # Continue checking for headers if:
            # 1. We haven't found any headers yet, OR
            # 2. We've found headers but haven't seen data rows yet (multi-row headers)
            if not data_rows_started:
                is_header_row = self._is_header_row(tr)
                
                # Additional check for multi-row headers in financial tables
                # If the previous row was a header and this row has years or units,
                # it's likely part of the header
                if headers_found and not is_header_row:
                    row_text = tr.text_content().strip()
                    # Check for units like "(in millions)" or "(in thousands)"
                    if '(in millions)' in row_text or '(in thousands)' in row_text or '(in billions)' in row_text:
                        is_header_row = True
                    # Check for year rows that follow "Year Ended" headers
                    elif len(table.headers) > 0:
                        last_header_text = ' '.join(cell.text() for cell in table.headers[-1])
                        if 'year ended' in last_header_text.lower() or 'years ended' in last_header_text.lower():
                            # Check if this row has years
                            year_pattern = r'\b(19\d{2}|20\d{2})\b'
                            years_found = re.findall(year_pattern, row_text)
                            if years_found:
                                is_header_row = True
            
            cells = self._process_row(tr, is_header=is_header_row)
            if cells:
                if is_header_row:
                    table.headers.append(cells)
                    headers_found = True
                    consecutive_header_rows += 1
                else:
                    # Only mark data_rows_started if this row has actual content
                    # Empty rows at the beginning shouldn't stop header detection
                    row = Row(cells=cells, is_header=False)
                    table.rows.append(row)
                    
                    # Check if row has significant content that indicates data rows have started
                    # But be smart about it - descriptive rows like "(in millions)" or pure spacing
                    # shouldn't stop header detection
                    has_content = any(cell.text().strip() for cell in cells)
                    if has_content:
                        # Get the row text for smarter analysis
                        row_text = ' '.join(cell.text().strip() for cell in cells).strip()
                        row_text_lower = row_text.lower()
                        
                        # Don't consider this as "data started" if it's likely a header-related row
                        is_header_related = (
                            # Unit descriptions
                            '(in millions)' in row_text_lower or 
                            '(in thousands)' in row_text_lower or 
                            '(in billions)' in row_text_lower or
                            'except per share' in row_text_lower or
                            # Financial period descriptions  
                            'year ended' in row_text_lower or
                            'months ended' in row_text_lower or
                            # Mostly just spacing/formatting
                            len(row_text.strip()) < 5 or
                            # Contains years (might be misclassified header)
                            bool(re.search(r'\b(19\d{2}|20\d{2})\b', row_text))
                        )
                        
                        # Only mark data_rows_started if this seems like actual data, not header-related
                        if not is_header_related:
                            data_rows_started = True
                    
                    consecutive_header_rows = 0
        
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
        # Use itertext() to get all text fragments
        # This preserves spaces better than text_content()
        text_parts = []
        for text in elem.itertext():
            if text:
                text_parts.append(text)
        
        # Join parts, ensuring we don't lose spaces
        # If a part doesn't end with whitespace and the next doesn't start with whitespace,
        # we need to add a space between them
        if not text_parts:
            return ''
        
        result = []
        for i, part in enumerate(text_parts):
            if i == 0:
                result.append(part)
            else:
                prev_part = text_parts[i-1]
                # Check if we need to add a space between parts
                # Don't add space if previous ends with space or current starts with space
                if prev_part and part:
                    if not prev_part[-1].isspace() and not part[0].isspace():
                        # Check for punctuation that shouldn't have space before it
                        if part[0] not in ',.;:!?%)]':
                            result.append(' ')
                result.append(part)
        
        text = ''.join(result)
        
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

    @staticmethod
    @lru_cache(maxsize=1)
    def _get_period_header_pattern():
        """
        Compile comprehensive regex for financial period headers.
        Adapted from old parser's proven patterns.

        Returns:
            Compiled regex pattern matching financial period headers
        """
        # Base components
        periods = r'(?:three|six|nine|twelve|[1-4]|first|second|third|fourth)'
        timeframes = r'(?:month|quarter|year|week)'
        ended_variants = r'(?:ended|ending|end|period)'
        as_of_variants = r'(?:as\s+of|at|as\s+at)'

        # Date pattern
        months = r'(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)'
        day = r'\d{1,2}'
        year = r'(?:19|20)\d{2}'
        date = f'{months}\\s*\\.?\\s*{day}\\s*,?\\s*{year}'

        # Combined patterns
        patterns = [
            # Standard period headers
            f'{periods}\\s+{timeframes}\\s+{ended_variants}(?:\\s+{date})?',
            f'(?:fiscal\\s+)?{timeframes}\\s+{ended_variants}',
            f'{timeframes}\\s+{ended_variants}(?:\\s+{date})?',

            # Balance sheet date headers
            f'{as_of_variants}\\s+{date}',

            # Multiple date sequences
            f'{date}(?:\\s*(?:and|,)\\s*{date})*',

            # Single dates
            f'(?:{ended_variants}\\s+)?{date}'
        ]

        pattern = '|'.join(f'(?:{p})' for p in patterns)
        return re.compile(pattern, re.IGNORECASE)

    def _is_header_row(self, tr: HtmlElement) -> bool:
        """Detect if row is likely a header row in SEC filings."""
        # Check if contains th elements (most reliable indicator)
        if tr.find('.//th') is not None:
            return True
        
        cells = tr.findall('.//td')
        if not cells:
            return False
        
        # Get row text for analysis
        row_text = tr.text_content()
        row_text_lower = row_text.lower()

        # Check for date ranges with financial data (Oracle Table 6 pattern)
        # Date ranges like "March 1, 2024—March 31, 2024" should be data rows, not headers
        date_range_pattern = r'(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},\s*\d{4}\s*[—–-]\s*(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},\s*\d{4}'
        has_date_range = bool(re.search(date_range_pattern, row_text_lower))

        # Check for financial data indicators
        has_currency = bool(re.search(r'\$[\s]*[\d,\.]+', row_text))
        has_decimals = bool(re.search(r'\b\d+\.\d+\b', row_text))
        has_large_numbers = bool(re.search(r'\b\d{1,3}(,\d{3})+\b', row_text))

        # If row has date range + financial data, it's definitely a data row
        if has_date_range and (has_currency or has_decimals or has_large_numbers):
            return False

        # Check for year patterns (very common in financial headers)
        year_pattern = r'\b(19\d{2}|20\d{2})\b'
        years_found = re.findall(year_pattern, row_text)
        if len(years_found) >= 2:  # Multiple years suggest header row
            # IMPORTANT: Check for date ranges and same-year repetition
            # Date ranges like "March 1, 2024—March 31, 2024" contain the same year twice
            # but are data rows, not multi-year comparison headers

            # If all years are the same (date range pattern)
            if len(set(years_found)) == 1:
                # Same year repeated - likely a date range like "Jan 1, 2024 - Mar 31, 2024"
                # Not a multi-year comparison header
                pass  # Don't return True
            # Multiple different years suggest multi-year comparison header
            elif 'total' not in row_text_lower[:20]:  # Check first 20 chars
                return True
        
        # Enhanced year detection - check individual cells for year patterns
        # This handles cases where years are in separate cells
        year_cells = 0
        date_phrases = 0
        for cell in cells:
            cell_text = cell.text_content().strip()
            if cell_text:
                # Check for individual years
                if re.match(r'^\s*(19\d{2}|20\d{2})\s*$', cell_text):
                    year_cells += 1
                # Check for date phrases like "June 30, 2025"
                elif 'june 30' in cell_text.lower() or 'december 31' in cell_text.lower():
                    date_phrases += 1
        
        # If we have multiple year cells or year + date phrases, likely a header
        if year_cells >= 2 or (year_cells >= 1 and date_phrases >= 1):
            if 'total' not in row_text_lower[:20]:
                return True
        
        # Check for comprehensive financial period patterns (from old parser)
        period_pattern = self._get_period_header_pattern()
        if period_pattern.search(row_text_lower):
            # Additional validation: ensure it's not a data row with period text
            # Check for absence of strong data indicators
            data_pattern = r'(?:\$\s*\d|\d+(?:,\d{3})+|\d+\s*[+\-*/]\s*\d+|\(\s*\d+(?:,\d{3})*\s*\))'
            if not re.search(data_pattern, row_text):
                return True

        # Check for units notation (in millions, thousands, billions)
        units_pattern = r'\(in\s+(?:millions|thousands|billions)\)'
        if re.search(units_pattern, row_text_lower):
            return True
        
        # Check for period indicators (quarters, months)
        # But be careful with "fiscal" - it could be data like "Fiscal 2025"
        period_keywords = ['quarter', 'q1', 'q2', 'q3', 'q4', 'month', 
                          'january', 'february', 'march', 'april', 'may', 'june',
                          'july', 'august', 'september', 'october', 'november', 'december',
                          'ended', 'three months', 'six months', 'nine months']
        
        # Special handling for "fiscal" - only treat as header if it's part of a phrase like "fiscal year ended"
        if 'fiscal' in row_text_lower:
            # Check if row has numeric values (suggests it's data, not header)
            # Look for patterns like "Fiscal 2025 $10,612" 
            has_currency_values = bool(re.search(r'\$[\s]*[\d,]+', row_text))
            has_large_numbers = bool(re.search(r'\b\d{1,3}(,\d{3})+\b', row_text))
            
            # If it has currency or large numbers, it's likely data
            if has_currency_values or has_large_numbers:
                return False
            
            # Check if it's just "Fiscal YYYY" which is likely data, not a header
            fiscal_year_only = re.match(r'^\s*fiscal\s+\d{4}\s*$', row_text_lower.strip())
            if fiscal_year_only:
                return False  # This is data, not a header
            
            # Check for header-like phrases with fiscal
            if 'fiscal year' in row_text_lower and ('ended' in row_text_lower or 'ending' in row_text_lower):
                return True
        
        if any(keyword in row_text_lower for keyword in period_keywords):
            # Validate it's not a data row with period keywords
            # Check for strong data indicators
            data_pattern = r'(?:\$\s*\d|\d+(?:,\d{3})+|\d+\.\d+|[(]\s*\d+(?:,\d{3})*\s*[)])'
            if not re.search(data_pattern, row_text):
                return True
        
        # Check for column descriptors (but NOT total)
        # These are words commonly found in headers but not data rows
        header_keywords = ['description', 'item', 'category', 'type', 'classification',
                          'change', 'percent', 'increase', 'decrease', 'variance']
        if any(keyword in row_text_lower for keyword in header_keywords):
            # Make sure it's not a total row
            if 'total' not in row_text_lower[:30]:
                # Additional validation: long narrative text is not a header
                # Headers are typically concise (< 150 chars)
                if len(row_text) > 150:
                    return False
                # Check for data indicators (would indicate data row, not header)
                data_pattern = r'(?:\$\s*\d|\d+(?:,\d{3})+|\d+\.\d+|[(]\s*\d+(?:,\d{3})*\s*[)])'
                if re.search(data_pattern, row_text):
                    return False
                return True
        
        # Check if all cells are bold (common header formatting)
        bold_count = 0
        for cell in cells:
            style = cell.get('style', '')
            if 'font-weight' in style and 'bold' in style:
                bold_count += 1
            elif cell.find('.//b') is not None or cell.find('.//strong') is not None:
                bold_count += 1
        
        # Only consider it a header if ALL cells are bold (not just some)
        if bold_count == len(cells) and bold_count > 0:
            return True
        
        # Check content type ratio - headers usually have more text than numbers
        # Count cells with primarily text vs primarily numbers
        text_cells = 0
        number_cells = 0
        for cell in cells:
            cell_text = cell.text_content().strip()
            if cell_text:
                # Remove common symbols for analysis
                clean_text = cell_text.replace('$', '').replace('%', '').replace(',', '').replace('(', '').replace(')', '')
                if clean_text.replace('.', '').replace('-', '').strip().isdigit():
                    number_cells += 1
                else:
                    text_cells += 1
        
        # Be very careful about treating text-heavy rows as headers
        # Many data rows start with text labels (e.g., "Impact of...", "Effect of...")
        # Only consider it a header if it has mostly text AND doesn't look like a data label
        if text_cells > number_cells * 2 and text_cells >= 3:
            # Check for common data row patterns
            data_row_indicators = [
                'impact of', 'effect of', 'adjustment', 'provision for', 'benefit',
                'expense', 'income from', 'loss on', 'gain on', 'charge', 'credit',
                'earnings', 'computed', 'state taxes', 'research', 'excess tax'
            ]
            
            # If it starts with any of these, it's likely a data row, not a header
            for indicator in data_row_indicators:
                if row_text_lower.startswith(indicator) or indicator in row_text_lower[:50]:
                    return False
            
            # Also not a header if it starts with "total"
            if not row_text_lower.startswith('total'):
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
        if financial_count >= 2:  # Lowered threshold for better detection
            return TableType.FINANCIAL
        
        # Check for metrics table  
        metrics_count = sum(1 for keyword in self.METRICS_KEYWORDS if keyword in combined_text)
        numeric_cells = sum(1 for row in table.rows for cell in row.cells if cell.is_numeric)
        total_cells = sum(len(row.cells) for row in table.rows)
        
        if total_cells > 0:
            numeric_ratio = numeric_cells / total_cells
            # More lenient metrics detection
            if metrics_count >= 1 or numeric_ratio > 0.3:
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