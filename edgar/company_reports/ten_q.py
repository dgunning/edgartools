"""Form 10-Q quarterly report class."""
import re
from functools import cached_property, lru_cache
from typing import List, Optional

from rich import box
from rich.console import Group, Text
from rich.padding import Padding
from rich.panel import Panel
from rich.tree import Tree

from edgar.company_reports._base import CompanyReport
from edgar.company_reports._structures import FilingStructure
from edgar.core import log
from edgar.documents import HTMLParser, ParserConfig
from edgar.files.htmltools import ChunkedDocument
from edgar.formatting import datefmt

__all__ = ['TenQ']


class TenQ(CompanyReport):
    structure = FilingStructure({
        "PART I": {  # Financial Information
            "ITEM 1": {
                "Title": "Financial Statements",
                "Description": "Unaudited financial statements including balance sheets, income statements, " +
                               "and cash flow statements."
            },
            "ITEM 2": {
                "Title": "Management's Discussion and Analysis of Financial Condition and Results of Operations (MD&A)",
                "Description": "Management's perspective on the financial condition and results of operations."
            },
            "ITEM 3": {
                "Title": "Quantitative and Qualitative Disclosures About Market Risk",
                "Description": "Information on the company's exposure to market risk."
            },
            "ITEM 4": {
                "Title": "Controls and Procedures",
                "Description": "Evaluation of the effectiveness of disclosure controls and procedures."
            }
        },
        "PART II": {  # Other Information
            "ITEM 1": {
                "Title": "Legal Proceedings",
                "Description": "Brief description of any significant pending legal proceedings."
            },
            "ITEM 1A": {
                "Title": "Risk Factors",
                "Description": "An update on risk factors that may affect future results."
            },
            "ITEM 2": {
                "Title": "Unregistered Sales of Equity Securities and Use of Proceeds",
                "Description": "Details of unregistered sales of equity securities."
            },
            "ITEM 3": {
                "Title": "Defaults Upon Senior Securities",
                "Description": "Information regarding any defaults on senior securities."
            },
            "ITEM 4": {
                "Title": "Mine Safety Disclosures",
                "Description": "Required for companies with mining operations."
            },
            "ITEM 5": {
                "Title": "Other Information",
                "Description": "Any other information that should be disclosed to investors."
            },
            "ITEM 6": {
                "Title": "Exhibits",
                "Description": "List of exhibits required by Item 601 of Regulation S-K."
            }
        }
    })

    def __init__(self, filing):
        assert filing.form in ['10-Q', '10-Q/A'], f"This form should be a 10-Q but was {filing.form}"
        super().__init__(filing)

    def __str__(self):
        return f"""TenQ('{self.company}')"""

    @cached_property
    def document(self):
        """
        Parse 10-Q using new HTMLParser with enhanced section detection.

        This uses the pattern-based section extractor that handles:
        - All 10-Q item patterns (Items 1-4 in Part I, Items 1-6 in Part II)
        - Part I / Part II boundaries and context
        - Bold paragraph fallback detection
        - Table cell detection
        - Various item number formatting variations

        Returns:
            Document object from edgar.documents module with sections property
        """
        html = self._filing.html()
        if not html:
            return None
        config = ParserConfig(form='10-Q')
        parser = HTMLParser(config)
        return parser.parse(html)

    @property
    def sections(self):
        """
        Get detected 10-Q sections using new parser.

        Returns a Sections dictionary mapping section names to Section objects.
        Section names are part-qualified (e.g., 'part_i_item_1', 'part_ii_item_1').

        Example:
            >>> ten_q.sections
            {'part_i_item_1': Section(...), 'part_ii_item_1': Section(...)}
            >>> ten_q.sections['part_i_item_1'].text()
            'Item 1 - Financial Statements...'
            >>> ten_q.sections['part_ii_item_1'].text()
            'Item 1 - Legal Proceedings...'
        """
        if self.document:
            return self.document.sections
        return {}

    @property
    def items(self) -> List[str]:
        """
        List of detected item names with part qualification.

        Uses new parser's section detection for improved accuracy.
        Returns items in the format "Part I, Item X" or "Part II, Item X"
        to distinguish between same-numbered items in different parts.

        Falls back to old chunked_document if new parser returns no sections.

        Returns:
            List of part-qualified item titles (e.g., ['Part I, Item 1', 'Part II, Item 1'])
        """
        # Try new parser first
        if self.sections:
            items = []
            for key, section in self.sections.items():
                # Handle pattern-based section keys: 'part_i_item_1' -> 'Part I, Item 1'
                if key.startswith('part_'):
                    part = 'Part I' if key.startswith('part_i_') else 'Part II'
                    # Extract item number from key (e.g., 'part_i_item_1a' -> '1a')
                    item_match = re.search(r'item_(\d+[a-z]?)', key, re.IGNORECASE)
                    if item_match:
                        item_num = item_match.group(1).upper()
                        items.append(f"{part}, Item {item_num}")
                # Handle TOC-based section keys: 'Item 1', 'Item 1A' -> 'Item 1', 'Item 1A'
                elif key.lower().startswith('item'):
                    # Extract item number
                    item_match = re.match(r'item\s*(\d+[a-z]?)', key, re.IGNORECASE)
                    if item_match:
                        item_num = item_match.group(1).upper()
                        # Try to determine part from section's part attribute
                        part = None
                        if hasattr(section, 'part') and section.part:
                            part = f"Part {section.part}"
                        if part:
                            items.append(f"{part}, Item {item_num}")
                        else:
                            items.append(f"Item {item_num}")
            return items if items else (self.chunked_document.list_items() if self.chunked_document else [])

        # Fallback to old parser for backward compatibility
        if self.chunked_document:
            return self.chunked_document.list_items()

        return []

    def __getitem__(self, item_or_part: str) -> Optional[str]:
        """
        Get section/item text by name or number.

        Supports multiple lookup formats:
        - Part-qualified: 'Part I, Item 1', 'Part II, Item 1'
        - Section key: 'part_i_item_1', 'part_ii_item_1'
        - Item number: 'Item 1' (returns Part I Item 1 for backward compat)
        - Simple number: '1' (returns Part I Item 1)

        IMPORTANT: For 10-Q filings, Item 1 exists in both Part I (Financial Statements)
        and Part II (Legal Proceedings). Use part-qualified format to distinguish:
        - tenq['Part I, Item 1'] -> Financial Statements
        - tenq['Part II, Item 1'] -> Legal Proceedings
        - tenq['Item 1'] -> Financial Statements (Part I, backward compat)

        Falls back to old chunked_document for backward compatibility.

        Args:
            item_or_part: Section identifier in various formats

        Returns:
            Section text content as string, or None if not found
        """
        # Try new parser sections first
        if self.sections:
            # Direct key lookup (e.g., 'part_i_item_1' or 'Item 1')
            if item_or_part in self.sections:
                return self.sections[item_or_part].text()

            # Parse input to determine part and item
            normalized = item_or_part.lower().strip()

            # Handle 'Part I, Item X' or 'Part II, Item X' format
            part_item_match = re.match(
                r'part\s+(i{1,2}|1|2)\s*,?\s*item\s+(\d+[a-z]?)',
                normalized,
                re.IGNORECASE
            )
            if part_item_match:
                part_num = part_item_match.group(1).lower()
                item_num = part_item_match.group(2).lower()
                # Convert part number to part prefix
                if part_num in ['i', '1']:
                    key = f'part_i_item_{item_num}'
                else:
                    key = f'part_ii_item_{item_num}'
                if key in self.sections:
                    return self.sections[key].text()

            # Handle 'Item X' format
            item_match = re.match(r'item\s+(\d+[a-z]?)', normalized, re.IGNORECASE)
            if item_match:
                item_num = item_match.group(1).lower()
                # Try pattern-based keys first (part-qualified)
                key = f'part_i_item_{item_num}'
                if key in self.sections:
                    return self.sections[key].text()
                key = f'part_ii_item_{item_num}'
                if key in self.sections:
                    return self.sections[key].text()
                # Try TOC-based keys (e.g., 'Item 1', 'Item 1A')
                for section_key in self.sections:
                    if section_key.lower() == f'item {item_num}' or section_key.lower() == f'item{item_num}':
                        return self.sections[section_key].text()

            # Handle simple number format (e.g., '1', '1a')
            if re.match(r'^\d+[a-z]?$', normalized):
                # Try Part I first
                key = f'part_i_item_{normalized}'
                if key in self.sections:
                    return self.sections[key].text()
                # Try Part II
                key = f'part_ii_item_{normalized}'
                if key in self.sections:
                    return self.sections[key].text()
                # Try TOC-based keys
                for section_key in self.sections:
                    if section_key.lower() == f'item {normalized}' or section_key.lower() == f'item{normalized}':
                        return self.sections[section_key].text()

        # Fallback to old chunked_document for backward compatibility
        if self.chunked_document:
            try:
                # Log fallback usage for Phase 1 deprecation tracking
                log.warning(
                    f"TenQ falling back to legacy parser for '{item_or_part}' "
                    f"(filing: {self._filing.accession_number}). "
                    f"New parser sections available: {list(self.sections.keys()) if self.sections else 'none'}. "
                    f"This fallback will be removed in v6.0."
                )
                return self.chunked_document[item_or_part]
            except (KeyError, TypeError):
                pass

        return None

    def get_item_with_part(self, part: str, item: str, markdown: bool = True) -> Optional[str]:
        """
        Get item text with explicit part specification.

        This method allows accessing items that have the same number in different parts.
        For 10-Q filings, Item 1 exists in both Part I (Financial Statements) and
        Part II (Legal Proceedings).

        Args:
            part: Part identifier ('Part I', 'Part II', 'PART I', 'PART II', 'I', 'II')
            item: Item identifier ('Item 1', 'Item 1A', '1', '1A')
            markdown: If True, return markdown formatted text (default True)

        Returns:
            Item text content, or None if not found

        Example:
            >>> ten_q.get_item_with_part('Part I', 'Item 1')  # Financial Statements
            >>> ten_q.get_item_with_part('Part II', 'Item 1')  # Legal Proceedings
            >>> ten_q.get_item_with_part('I', '1')  # Also works
        """
        # Try new parser first
        if self.sections:
            # Normalize part
            part_lower = part.lower().strip()
            if part_lower in ['part i', 'part_i', 'i', '1']:
                part_prefix = 'part_i'
            elif part_lower in ['part ii', 'part_ii', 'ii', '2']:
                part_prefix = 'part_ii'
            else:
                part_prefix = None

            if part_prefix:
                # Normalize item
                item_lower = item.lower().strip()
                item_match = re.match(r'(?:item\s+)?(\d+[a-z]?)', item_lower, re.IGNORECASE)
                if item_match:
                    item_num = item_match.group(1)
                    key = f'{part_prefix}_item_{item_num}'
                    if key in self.sections:
                        return self.sections[key].text()

        # Fallback to old implementations
        if not part:
            return self.id_parse_document(markdown).get(part.lower(), {}).get(item.lower())

        # Try chunked_document
        if self.chunked_document:
            item_text = self.chunked_document.get_item_with_part(part, item, markdown=markdown)
            if item_text and item_text.strip():
                return item_text

        # Final fallback to id_parse_document
        return self.id_parse_document(markdown).get(part.lower(), {}).get(item.lower())

    @lru_cache(maxsize=1)
    def id_parse_document(self, markdown: bool = True):
        from edgar.files.html_documents_id_parser import ParsedHtml10Q
        return ParsedHtml10Q().extract_html(self._filing.html(), self.structure, markdown=markdown)

    @cached_property
    def chunked_document(self):
        return ChunkedDocument(self._filing.html(), prefix_src=self._filing.base_dir)

    def get_structure(self):
        # Create the main tree
        tree = Tree("📄 ")

        # Get the actual items from the filing
        actual_items = self.items

        # Create a set of found items (normalized) for checking
        # Handle both old format 'Item 1' and new format 'Part I, Item 1'
        found_items = set()
        for item in actual_items:
            # Parse 'Part I, Item 1' -> ('I', '1')
            match = re.match(r'Part\s+(I{1,2}),\s*Item\s+(\d+[A-Z]?)', item, re.IGNORECASE)
            if match:
                found_items.add((match.group(1).upper(), match.group(2).upper()))
            else:
                # Old format 'Item 1' - assume Part I for backward compat
                match = re.match(r'Item\s+(\d+[A-Z]?)', item, re.IGNORECASE)
                if match:
                    found_items.add(('I', match.group(1).upper()))

        # Process each part in the structure
        for part, items in self.structure.structure.items():
            # Create a branch for each part
            part_tree = tree.add(f"[bold blue]{part}[/]")

            # Determine part number for lookup
            part_num = 'I' if 'I' in part.upper() and 'II' not in part.upper() else 'II'

            # Add items under each part
            for item_key, item_data in items.items():
                # Extract item number from key (e.g., 'ITEM 1' -> '1', 'ITEM 1A' -> '1A')
                item_num_match = re.match(r'ITEM\s+(\d+[A-Z]?)', item_key, re.IGNORECASE)
                item_num = item_num_match.group(1).upper() if item_num_match else item_key

                # Check if this part+item exists in the actual filing
                if (part_num, item_num) in found_items:
                    item_text = Text.assemble(
                        (f"Item {item_num:<3} ", "bold green"),
                        (f"{item_data['Title']}", "bold"),
                    )
                else:
                    # Item doesn't exist - show in grey
                    item_text = Text.assemble(
                        (f"Item {item_num}: ", "dim"),
                        (f"{item_data['Title']}", "dim"),
                    )

                part_tree.add(item_text)

        return tree

    def __rich__(self):
        title = Text.assemble(
            (f"{self.company}", "bold deep_sky_blue1"),
            (" ", ""),
            (f"{self.form}", "bold"),
        )
        periods = Text.assemble(
            ("Period ending ", "grey70"),
            (f"{datefmt(self.period_of_report, '%B %d, %Y')}", "bold"),
            (" filed on ", "grey70"),
            (f"{datefmt(self.filing_date, '%B %d, %Y')}", "bold"),
        )
        panel = Panel(
            Group(
                periods,
                Padding(" ", (1, 0, 0, 0)),
                self.get_structure(),
                Padding(" ", (1, 0, 0, 0)),
                self.financials or Text("No financial data available", style="italic")
            ),
            title=title,
            box=box.ROUNDED,
        )
        return panel
