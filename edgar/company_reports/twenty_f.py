"""Form 20-F annual report for foreign private issuers."""
import re
from functools import cached_property
from typing import List

from edgar.company_reports._base import CompanyReport
from edgar.company_reports._structures import FilingStructure, extract_items_from_sections
from edgar.documents import HTMLParser, ParserConfig

__all__ = ['TwentyF']


class TwentyF(CompanyReport):
    structure = FilingStructure({
        "PART I": {
            "ITEM 1": {
                "Title": "Identity of Directors, Senior Management, and Advisers",
                "Description": "Information about the company's directors, senior management, and advisers."
            },
            "ITEM 2": {
                "Title": "Offer Statistics and Expected Timetable",
                "Description": "Details on recent and expected offers of securities."
            },
            "ITEM 3": {
                "Title": "Key Information",
                "Description": "Financial and other key information about the company, including risk factors and ratios."
            },
            "ITEM 4": {
                "Title": "Information on the Company",
                "Description": "Detailed information about the company's operations and properties."
            },
            "ITEM 4A": {
                "Title": "Unresolved Staff Comments",
                "Description": "Any comments from the SEC staff on the company's previous filings that " +
                               "remain unresolved."
            }
        },
        "PART II": {
            "ITEM 5": {
                "Title": "Operating and Financial Review and Prospects",
                "Description": "Management's discussion and analysis of financial condition and results of operations."
            },
            "ITEM 6": {
                "Title": "Directors, Senior Management, and Employees",
                "Description": "Information about the company's directors, senior management, and employees."
            },
            "ITEM 7": {
                "Title": "Major Shareholders and Related Party Transactions",
                "Description": "Information about major shareholders and transactions with related parties."
            },
            "ITEM 8": {
                "Title": "Financial Information",
                "Description": "Audited financial statements and supplementary financial information."
            },
            "ITEM 9": {
                "Title": "The Offer and Listing",
                "Description": "Details on the company's securities and markets where they are traded."
            }
        },
        "PART III": {
            "ITEM 10": {
                "Title": "Additional Information",
                "Description": "Additional information such as share capital, memoranda, and articles of association."
            },
            "ITEM 11": {
                "Title": "Quantitative and Qualitative Disclosures About Market Risk",
                "Description": "Information on the company's exposure to market risk."
            },
            "ITEM 12": {
                "Title": "Description of Securities Other Than Equity Securities",
                "Description": "Detailed information on securities other than equity."
            }
        },
        "PART IV": {
            "ITEM 13": {
                "Title": "Defaults, Dividend Arrearages, and Delinquencies",
                "Description": "Information about defaults on payments and arrearages."
            },
            "ITEM 14": {
                "Title": "Material Modifications to the Rights of Security Holders and Use of Proceeds",
                "Description": "Details on any modifications to the rights of security holders."
            },
            "ITEM 15": {
                "Title": "Controls and Procedures",
                "Description": "Assessment of the effectiveness of disclosure controls and internal controls over financial reporting."
            },
            "ITEM 16": {
                "Title": "Various Disclosures",
                "Description": "Includes disclosures related to audit committee financial experts, code of ethics, " +
                               "principal accountant fees and services, and other corporate governance matters."
            }
        },
        "PART V": {
            "ITEM 17": {
                "Title": "Financial Statements",
                "Description": "Financial statements prepared in accordance with or reconciled to U.S. GAAP or IFRS."
            },
            "ITEM 18": {
                "Title": "Financial Statements",
                "Description": "If different from Item 17, financial statements prepared in accordance with " +
                               "home country standards."
            },
            "ITEM 19": {
                "Title": "Exhibits",
                "Description": "Legal and financial documents supporting the information in the report."
            }
        }
    })

    def __init__(self, filing):
        assert filing.form in ['20-F', '20-F/A'], f"This form should be a 20-F but was {filing.form}"
        super().__init__(filing)

    @cached_property
    def document(self):
        """
        Parse 20-F using new HTMLParser with enhanced section detection.

        This uses the pattern-based section extractor that handles:
        - All 20-F item patterns (Items 1-19 across 5 parts)
        - Bold paragraph fallback detection
        - Table cell detection
        - Various item number formatting variations

        Returns:
            Document object from edgar.documents module with sections property
        """
        html = self._filing.html()
        if not html:
            return None
        config = ParserConfig(form='20-F')
        parser = HTMLParser(config)
        return parser.parse(html)

    @property
    def sections(self):
        """
        Get detected 20-F sections using new parser.

        Returns a Sections dictionary mapping section names to Section objects.
        Section names are normalized (e.g., 'item_5' for Item 5).

        Example:
            >>> twenty_f.sections
            {'item_5': Section(...), 'item_8': Section(...)}
            >>> twenty_f.sections['item_5'].text()
            'Item 5 - Operating and Financial Review...'
        """
        if self.document:
            return self.document.sections
        return {}

    @property
    def items(self) -> List[str]:
        """
        List of detected item names (consistent with sections property).

        Uses chunked_document for 20-F since the pattern-based extractor
        doesn't handle the Table of Contents format well.
        Falls back to new parser sections if chunked_document unavailable.

        Returns:
            List of item titles for backward compatibility (e.g., ['Item 5', 'Item 8'])
        """
        # For 20-F, prefer chunked_document which handles TOC format better
        if self.chunked_document:
            return self.chunked_document.list_items()

        # Fallback to new parser sections
        if self.sections and len(self.sections) > 0:
            item_pattern = re.compile(r'(Item\s+\d+[A-Z]?)', re.IGNORECASE)
            return extract_items_from_sections(self.sections, item_pattern)

        return []

    def __getitem__(self, item_name: str):
        """
        Get section/item text by name or number.

        Supports multiple lookup formats:
        - Section key: 'item_5'
        - Item number: 'Item 5', '5'
        - Natural language: 'Item 5 - Operating and Financial Review'
        - Part lookups: 'Part I', 'Part II'

        Falls back to old chunked_document for backward compatibility.

        Args:
            item_name: Section identifier in various formats

        Returns:
            Section text content as string, or None if not found
        """
        # Try new parser sections first
        if self.sections:
            # Direct key lookup
            if item_name in self.sections:
                return self.sections[item_name].text()

            # Extract item number from input (e.g., "Item 5" → "5", "5" → "5", "Item 16A" → "16a")
            item_match = re.match(r'(?:item\s*)?(\d+[a-z]?)', item_name.lower().strip())
            if item_match:
                item_num = item_match.group(1).lower()

                # Try part-prefixed keys (TOC-based detection uses these)
                # 20-F has Parts I-V, but items map to parts as follows:
                # Part I: Items 1-4A, Part II: Items 5-9 (Note: structure varies)
                # Part III: Items 10-12, Part IV: Items 13-16, Part V: Items 17-19
                for part in ['i', 'ii', 'iii', 'iv', 'v']:
                    key = f'part_{part}_item_{item_num}'
                    if key in self.sections:
                        return self.sections[key].text()

                # Try direct item key (pattern-based detection)
                item_key = f'item_{item_num}'
                if item_key in self.sections:
                    return self.sections[item_key].text()

                # Try "Item X" format (TOC-based with friendly names)
                friendly_key = f'Item {item_num.upper()}'
                if friendly_key in self.sections:
                    return self.sections[friendly_key].text()

        # Fallback to old chunked_document for backward compatibility
        if self.chunked_document:
            try:
                return self.chunked_document[item_name]
            except (KeyError, TypeError):
                pass

        return None

    def __str__(self):
        return f"""TwentyF('{self.company}')"""

    # Convenience properties for common sections
    @property
    def key_information(self):
        """Item 3 - Key Information (includes risk factors and selected financial data)."""
        return self['Item 3']

    @property
    def risk_factors(self):
        """Item 3 - Key Information (contains risk factors section)."""
        return self['Item 3']

    @property
    def business(self):
        """Item 4 - Information on the Company (business overview, operations, properties)."""
        return self['Item 4']

    @property
    def company_information(self):
        """Item 4 - Information on the Company (alias for business)."""
        return self['Item 4']

    @property
    def operating_review(self):
        """Item 5 - Operating and Financial Review and Prospects (similar to MD&A)."""
        return self['Item 5']

    @property
    def management_discussion(self):
        """Item 5 - Operating and Financial Review and Prospects (alias for operating_review)."""
        return self['Item 5']

    @property
    def directors_and_employees(self):
        """Item 6 - Directors, Senior Management and Employees."""
        return self['Item 6']

    @property
    def major_shareholders(self):
        """Item 7 - Major Shareholders and Related Party Transactions."""
        return self['Item 7']

    @property
    def financial_information(self):
        """Item 8 - Financial Information."""
        return self['Item 8']

    @property
    def controls_and_procedures(self):
        """Item 15 - Controls and Procedures."""
        return self['Item 15']
