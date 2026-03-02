"""Form 10-K annual report class."""
import re
from functools import cached_property, lru_cache

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
from edgar.display.formatting import datefmt

__all__ = ['TenK']


# Item number mapping for Cross Reference Index format
_CROSS_REF_ITEM_MAP = {
    'Item 1': '1',
    'Item 1A': '1A',
    'Item 1B': '1B',
    'Item 1C': '1C',
    'Item 2': '2',
    'Item 3': '3',
    'Item 4': '4',
    'Item 5': '5',
    'Item 6': '6',
    'Item 7': '7',
    'Item 7A': '7A',
    'Item 8': '8',
    'Item 9': '9',
    'Item 9A': '9A',
    'Item 9B': '9B',
    'Item 9C': '9C',
    'Item 10': '10',
    'Item 11': '11',
    'Item 12': '12',
    'Item 13': '13',
    'Item 14': '14',
    'Item 15': '15',
    'Item 16': '16',
}


class TenK(CompanyReport):
    structure = FilingStructure({
        "PART I": {
            # special case for 10-K
            # Items 1 and 2. Business and Properties
            "ITEM 1": {
                "Title": "Business",
                "Description": "Overview of the company's business operations, products, services, and market environment."
            },
            "ITEM 1A": {
                "Title": "Risk Factors",
                "Description": "Discussion of risks and uncertainties that could materially affect the company's " +
                               "financial condition or results of operations."
            },
            "ITEM 1B": {
                "Title": "Unresolved Staff Comments",
                "Description": "Any comments from the SEC staff on the company's previous filings" +
                               "that remain unresolved."
            },
            "ITEM 1C": {
                "Title": "Cybersecurity",
                "Description": "Cybersecurity risk management, strategy, and governance disclosures."
            },
            "ITEM 2": {
                "Title": "Properties",
                "Description": "Information about the physical properties owned or leased by the company."
            },
            "ITEM 3": {
                "Title": "Legal Proceedings",
                "Description": "Details of significant ongoing legal proceedings."
            },
            "ITEM 4": {
                "Title": "Mine Safety Disclosures",
                "Description": "Relevant for mining companies, disclosures about mine safety and regulatory compliance."
            }
        },
        "PART II": {
            "ITEM 5": {
                "Title": "Market for Registrant's Common Equity",
                "Description": "Information on the company's equity, including stock performance " +
                               "and shareholder matters."
            },
            "ITEM 6": {
                "Title": "Selected Financial Data",
                "Description": "Financial data summary for the last five fiscal years."
            },
            "ITEM 7": {
                "Title": "Management's Discussion and Analysis (MD&A)",
                "Description": "Management's perspective on the financial condition, changes in financial condition, " +
                               "and results of operations."
            },
            "ITEM 7A": {
                "Title": "Quantitative and Qualitative Disclosures About Market Risk",
                "Description": "Information on the company's exposure to market risk, such as interest rate risk, " +
                               "foreign currency exchange risk, commodity price risk, etc."
            },
            "ITEM 8": {
                "Title": "Financial Statements",
                "Description": "Complete audited financial statements, including balance sheet, income statement, " +
                               "cash flow statement, and notes to the financial statements."
            },
            "ITEM 9": {
                "Title": "Controls and Procedures",
                "Description": "Evaluation of the effectiveness of the design and operation of the company's disclosure controls and procedures."
            },
            "ITEM 9A": {
                "Title": "Controls and Procedures",
                "Description": "Evaluation of internal controls over financial reporting."
            },
            "ITEM 9B": {
                "Title": "Other Information",
                "Description": "Any other relevant information not covered in other sections."
            },
            "ITEM 9C": {
                "Title": "Disclosure Regarding Foreign Jurisdictions That Prevent Inspections",
                "Description": "Disclosure Regarding Foreign Jurisdictions That Prevent Inspections."
            }
        },
        "PART III": {
            "ITEM 10": {
                "Title": "Directors, Executive Officers, and Corporate Governance",
                "Description": "Information about the company's directors, executive officers, and governance policies."
            },
            "ITEM 11": {
                "Title": "Executive Compensation",
                "Description": "Details of compensation paid to key executives."
            },
            "ITEM 12": {
                "Title": "Security Ownership of Certain Beneficial Owners and Management",
                "Description": "Information about stock ownership of major shareholders, directors, and management."
            },
            "ITEM 13": {
                "Title": "Certain Relationships and Related Transactions, and Director Independence",
                "Description": "Information on transactions between the company and its directors, officers, " +
                               "and significant shareholders."
            },
            "ITEM 14": {
                "Title": "Principal Accounting Fees and Services",
                "Description": "Fees paid to the principal accountant and services rendered."
            }
        },
        "PART IV": {
            "ITEM 15": {
                "Title": "Exhibits, Financial Statement Schedules",
                "Description": "Legal documents and financial schedules that support the financial statements " +
                               "and disclosures."
            },
            "ITEM 16": {
                "Title": "Form 10-K Summary",
                "Description": "Form 10-K Summary"
            }
        }
    })

    def __init__(self, filing):
        assert filing.form in ['10-K', '10-K/A'], f"This form should be a 10-K but was {filing.form}"
        super().__init__(filing)

    @cached_property
    def document(self):
        """
        Parse 10-K using new HTMLParser with enhanced section detection.

        This uses the pattern-based section extractor that handles:
        - All 10-K item patterns (Items 1, 1A, 1B, 1C, 2, 3, 4 in Part I, etc.)
        - Part boundaries and context
        - Bold paragraph fallback detection
        - Table cell detection
        - Various item number formatting variations

        Returns:
            Document object from edgar.documents module with sections property,
            or None if parsing fails (falls back to ChunkedDocument)
        """
        try:
            html = self._filing.html()
            if not html:
                return None
            config = ParserConfig(form='10-K')
            parser = HTMLParser(config)
            return parser.parse(html)
        except Exception as e:
            # If new parser fails, log and return None to fall back to old parser
            import warnings
            warnings.warn(
                f"HTMLParser failed for 10-K filing (falling back to ChunkedDocument): {e}",
                RuntimeWarning,
                stacklevel=2
            )
            return None

    @property
    def sections(self):
        """
        Get detected 10-K sections using new parser.

        Returns a Sections dictionary mapping section names to Section objects.
        Section names use friendly names (e.g., 'business', 'risk_factors', 'mda').

        Example:
            >>> ten_k.sections
            {'business': Section(...), 'risk_factors': Section(...), 'mda': Section(...)}
            >>> ten_k.sections['business'].text()
            'Item 1 - Business...'
            >>> ten_k.sections['mda'].text()
            'Item 7 - Management Discussion and Analysis...'
        """
        if self.document:
            return self.document.sections
        return {}

    @property
    def items(self):
        """
        List of detected item names in standard "Item X" format.

        Uses new parser's section detection for improved accuracy.
        Falls back to old chunked_document if new parser returns no sections.

        Returns:
            List of item titles (e.g., ['Item 1', 'Item 1A', 'Item 2', ...])
        """
        # Mapping from friendly section names to Item numbers
        section_to_item = {
            'business': 'Item 1',
            'risk_factors': 'Item 1A',
            'unresolved_staff_comments': 'Item 1B',
            'cybersecurity': 'Item 1C',
            'properties': 'Item 2',
            'legal_proceedings': 'Item 3',
            'mine_safety': 'Item 4',
            'market_equity': 'Item 5',
            'selected_financial_data': 'Item 6',
            'mda': 'Item 7',
            'market_risk': 'Item 7A',
            'financial_statements': 'Item 8',
            'controls_procedures': 'Item 9',
            'controls_procedures_9a': 'Item 9A',
            'other_information': 'Item 9B',
            'foreign_jurisdictions': 'Item 9C',
            'directors_officers': 'Item 10',
            'executive_compensation': 'Item 11',
            'security_ownership': 'Item 12',
            'relationships_transactions': 'Item 13',
            'accounting_fees': 'Item 14',
            'exhibits': 'Item 15',
            'summary': 'Item 16'
        }

        # Try new parser first
        if self.sections:
            items = []
            for key, section in self.sections.items():
                # Check if section has an item attribute
                if hasattr(section, 'item') and section.item:
                    items.append(f"Item {section.item}")
                # Map friendly names to Item numbers
                elif key in section_to_item:
                    items.append(section_to_item[key])
                # Handle keys that are already in "Item X" format
                elif key.startswith('Item '):
                    items.append(key)
            return items if items else (self.chunked_document.list_items() if self.chunked_document else [])

        # Fallback to old parser for backward compatibility
        if self.chunked_document:
            return self.chunked_document.list_items()

        return []

    @property
    def business(self):
        return self['Item 1']

    @property
    def risk_factors(self):
        return self['Item 1A']

    @property
    def management_discussion(self):
        return self['Item 7']

    @property
    def directors_officers_and_governance(self):
        return self['Item 10']

    @cached_property
    def subsidiaries(self):
        """Subsidiaries from Exhibit 21, if present.

        Returns SubsidiaryList if an EX-21 attachment exists (may be empty),
        or None if the filing has no EX-21 exhibit.
        """
        from edgar.company_reports.subsidiaries import SubsidiaryList, parse_subsidiaries

        for att in self._filing.attachments:
            doc_type = att.document_type or ''
            if doc_type.startswith('EX-21'):
                content = att.content
                if not content:
                    continue
                subs = parse_subsidiaries(content)
                return SubsidiaryList(subs)
        return None

    @cached_property
    def chunked_document(self):
        return ChunkedDocument(self._filing.html(), prefix_src=self._filing.base_dir)

    @cached_property
    def _cross_reference_index(self):
        """
        Lazy-load Cross Reference Index parser.

        Some companies (e.g., GE) use a "Form 10-K Cross Reference Index" table
        instead of standard Item headings. This parser detects and extracts
        Item-to-page mappings when present.

        Returns None if filing uses standard format.
        """
        from edgar.documents import CrossReferenceIndex

        html = self._filing.html()
        index = CrossReferenceIndex(html)

        # Only create parser if Cross Reference Index format is detected
        if index.has_index():
            return index
        return None

    @lru_cache(maxsize=1)
    def id_parse_document(self, markdown:bool=False):
        from edgar.files.html_documents_id_parser import ParsedHtml10K
        return ParsedHtml10K().extract_html(self._filing.html(), self.structure, markdown=markdown)

    def __str__(self):
        return f"""TenK('{self.company}')"""

    def __getitem__(self, item_or_part: str):
        """
        Get section/item text by name or number.

        Supports multiple lookup formats:
        - Standard format: 'Item 1', 'Item 1A', 'Item 7'
        - Short format: '1', '1A', '7', '7A'
        - Friendly names: 'business', 'risk_factors', 'mda'

        Falls back to old chunked_document and Cross Reference Index for backward compatibility.

        Args:
            item_or_part: Section identifier in various formats

        Returns:
            Section text content as string, or None if not found
        """
        # Mapping from Item numbers to friendly section names
        item_to_section = {
            'Item 1': 'business',
            'Item 1A': 'risk_factors',
            'Item 1B': 'unresolved_staff_comments',
            'Item 1C': 'cybersecurity',
            'Item 2': 'properties',
            'Item 3': 'legal_proceedings',
            'Item 4': 'mine_safety',
            'Item 5': 'market_equity',
            'Item 6': 'selected_financial_data',
            'Item 7': 'mda',
            'Item 7A': 'market_risk',
            'Item 8': 'financial_statements',
            'Item 9': 'controls_procedures',
            'Item 9A': 'controls_procedures_9a',
            'Item 9B': 'other_information',
            'Item 9C': 'foreign_jurisdictions',
            'Item 10': 'directors_officers',
            'Item 11': 'executive_compensation',
            'Item 12': 'security_ownership',
            'Item 13': 'relationships_transactions',
            'Item 14': 'accounting_fees',
            'Item 15': 'exhibits',
            'Item 16': 'summary'
        }

        # Reverse mapping: friendly names to Item numbers
        # (TOC-based detection uses "Item X" keys, so we need to map friendly names back)
        section_to_item = {v: k for k, v in item_to_section.items()}

        # Try new parser sections first
        if self.sections:
            # Normalize input
            normalized = item_or_part.strip()

            # PRIORITY 1: Try part-based naming convention first (most reliable)
            # These have proper part context (e.g., "part_i_item_1", "part_ii_item_5")
            item_num = None
            if normalized.startswith('Item '):
                # Extract item number: "Item 1" -> "1", "Item 1A" -> "1a"
                item_num = normalized[5:].strip().lower()
            elif re.match(r'^\d+[A-Z]?$', normalized, re.IGNORECASE):
                # Short format: "1", "1A" -> "1", "1a"
                item_num = normalized.lower()
            elif normalized in section_to_item:
                # Friendly name: "business" -> "Item 1" -> "1"
                item_key = section_to_item[normalized]
                item_num = item_key[5:].strip().lower()

            if item_num:
                # Try Part I first (most common for Items 1-4)
                part_i_key = f'part_i_item_{item_num}'
                if part_i_key in self.sections:
                    text = self.sections[part_i_key].text()
                    if text and text.strip():
                        return text
                # Try Part II for Items 5-9C
                part_ii_key = f'part_ii_item_{item_num}'
                if part_ii_key in self.sections:
                    text = self.sections[part_ii_key].text()
                    if text and text.strip():
                        return text
                # Try Part III for Items 10-14
                part_iii_key = f'part_iii_item_{item_num}'
                if part_iii_key in self.sections:
                    text = self.sections[part_iii_key].text()
                    if text and text.strip():
                        return text
                # Try Part IV for Items 15-16
                part_iv_key = f'part_iv_item_{item_num}'
                if part_iv_key in self.sections:
                    text = self.sections[part_iv_key].text()
                    if text and text.strip():
                        return text

            # PRIORITY 2: Direct key lookup (e.g., 'Item 1', 'business' if pattern-based)
            if item_or_part in self.sections:
                return self.sections[item_or_part].text()

            # PRIORITY 3: Try friendly name -> Item mapping
            if item_or_part in section_to_item:
                item_key = section_to_item[item_or_part]
                if item_key in self.sections:
                    return self.sections[item_key].text()

            # PRIORITY 4: Handle 'Item X' format -> try friendly name
            if normalized in item_to_section:
                friendly_name = item_to_section[normalized]
                if friendly_name in self.sections:
                    return self.sections[friendly_name].text()

            # PRIORITY 5: Handle short format '1', '1A', etc. -> convert to 'Item X'
            if re.match(r'^\d+[A-Z]?$', normalized, re.IGNORECASE):
                item_key = f'Item {normalized.upper()}'
                # Try direct lookup
                if item_key in self.sections:
                    return self.sections[item_key].text()
                # Try friendly name
                if item_key in item_to_section:
                    friendly_name = item_to_section[item_key]
                    if friendly_name in self.sections:
                        return self.sections[friendly_name].text()

            # Legacy fallback: Try part-based naming convention again
            # (This code path may not be reached now, but kept for safety)
            if normalized.startswith('Item '):
                # Extract item number: "Item 1" -> "1", "Item 1A" -> "1a"
                item_num = normalized[5:].strip().lower()
                # Try Part I first (most common for Items 1-4)
                part_i_key = f'part_i_item_{item_num}'
                if part_i_key in self.sections:
                    text = self.sections[part_i_key].text()
                    # Only return if non-empty (otherwise fall back to chunked_document)
                    if text and text.strip():
                        return text
                # Try Part II for Items 5-9C
                part_ii_key = f'part_ii_item_{item_num}'
                if part_ii_key in self.sections:
                    text = self.sections[part_ii_key].text()
                    if text and text.strip():
                        return text
                # Try Part III for Items 10-14
                part_iii_key = f'part_iii_item_{item_num}'
                if part_iii_key in self.sections:
                    text = self.sections[part_iii_key].text()
                    if text and text.strip():
                        return text
                # Try Part IV for Items 15-16
                part_iv_key = f'part_iv_item_{item_num}'
                if part_iv_key in self.sections:
                    text = self.sections[part_iv_key].text()
                    if text and text.strip():
                        return text

            # Also handle if user provides just a number like "1" or "1A"
            elif re.match(r'^\d+[a-z]?$', normalized, re.IGNORECASE):
                item_num = normalized.lower()
                # Try all parts
                for part in ['i', 'ii', 'iii', 'iv']:
                    part_key = f'part_{part}_item_{item_num}'
                    if part_key in self.sections:
                        text = self.sections[part_key].text()
                        # Only return if non-empty
                        if text and text.strip():
                            return text

        # If Cross Reference Index format is detected, prefer it over chunked_document
        # (Some filings like GE, Henry Schein use Cross Reference Index - issue #107)
        if self._cross_reference_index is not None:
            item_id = _CROSS_REF_ITEM_MAP.get(item_or_part)
            if item_id:
                # Extract content using Cross Reference Index parser
                item_text = self._cross_reference_index.extract_item_content(item_id)
                if item_text:
                    # Successfully extracted via Cross Reference Index
                    item_text = item_text.rstrip()
                    last_line = item_text.split("\n")[-1]
                    if re.match(r'^\b(PART\s+[IVXLC]+)\b', last_line):
                        item_text = item_text.rstrip(last_line)
                    return item_text

        # Fall back to chunked document for backward compatibility
        # Log fallback usage for Phase 1 deprecation tracking
        log.warning(
            f"TenK falling back to legacy parser for '{item_or_part}' "
            f"(filing: {self._filing.accession_number}). "
            f"New parser sections available: {list(self.sections.keys()) if self.sections else 'none'}. "
            f"This fallback will be removed in v6.0."
        )
        item_text = self.chunked_document[item_or_part]

        # Clean up the text if found
        if item_text:
            item_text = item_text.rstrip()
            last_line = item_text.split("\n")[-1]
            if re.match(r'^\b(PART\s+[IVXLC]+)\b', last_line):
                item_text = item_text.rstrip(last_line)

        return item_text

    def get_item_with_part(self, part: str, item: str, markdown:bool=True):
        """
        Get item text with explicit part specification.

        Note: For 10-K filings, items are unique across parts, so the part parameter
        is less critical than for 10-Q. This method delegates to __getitem__ for new parser
        support while maintaining backward compatibility.

        Args:
            part: Part identifier (e.g., 'Part I', 'Part II') - largely ignored for 10-K
            item: Item identifier (e.g., 'Item 1', '1', 'business')
            markdown: If True, return markdown formatted text (default True)

        Returns:
            Item text content, or None if not found
        """
        # Try new parser via __getitem__ (which handles various formats)
        if self.sections:
            # Since 10-K items are unique, just use the item lookup
            result = self[item]
            if result:
                return result

        # Fallback to old implementations
        if not part:
            return self.id_parse_document(markdown).get(item.lower())

        # Try chunked_document
        item_text = self.chunked_document.get_item_with_part(part, item, markdown=markdown)
        if item_text and item_text.strip():
            return item_text

        # Final fallback to id_parse_document
        return self.id_parse_document(markdown).get(part.lower(), {}).get(item.lower())

    def get_structure(self):
        # Create the main tree
        tree = Tree("📄 ")

        # Get the actual items from the filing
        actual_items = self.items

        # Create a mapping of uppercase to actual case items
        case_mapping = {item.upper(): item for item in actual_items}

        # Process each part in the structure
        for part, items in self.structure.structure.items():
            # Create a branch for each part
            part_tree = tree.add(f"[bold blue]{part}[/]")

            # Add items under each part
            for item_key, item_data in items.items():
                # Check if this item exists in the actual filing
                if item_key in case_mapping:
                    # Use the actual case from the filing
                    actual_item = case_mapping[item_key]
                    item_text = Text.assemble(
                        (f"{actual_item:<7} ", "bold green"),
                        (f"{item_data['Title']}", "bold"),
                    )
                else:
                    # Item doesn't exist - show in grey with original structure case
                    item_text = Text.assemble(
                        (f"{item_key}: ", "dim"),
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
