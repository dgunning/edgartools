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
from edgar.files.htmltools import ChunkedDocument
from edgar.formatting import datefmt

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
        # Show the item or part from the filing document. e.g. Item 1 Business from 10-K or Part I from 10-Q

        # Try standard chunked document extraction first
        item_text = self.chunked_document[item_or_part]

        # If standard extraction returned None, try Cross Reference Index format
        if item_text is None and self._cross_reference_index is not None:
            # Map "Item 1A" to "1A" for Cross Reference Index lookup
            item_id = _CROSS_REF_ITEM_MAP.get(item_or_part)
            if item_id:
                # Extract content using Cross Reference Index parser
                item_text = self._cross_reference_index.extract_item_content(item_id)

        # Clean up the text if found
        if item_text:
            item_text = item_text.rstrip()
            last_line = item_text.split("\n")[-1]
            if re.match(r'^\b(PART\s+[IVXLC]+)\b', last_line):
                item_text = item_text.rstrip(last_line)

        return item_text

    def get_item_with_part(self, part: str, item: str, markdown:bool=True):
        if not part:
            return self.id_parse_document(markdown).get(item.lower())
        # Show the item or part from the filing document. e.g. Item 1 Business from 10-K or Part I from 10-Q
        item_text = self.chunked_document.get_item_with_part(part, item, markdown=markdown)
        # remove first line or last line (redundant part information)
        if not item_text or not item_text.strip():
            return self.id_parse_document(markdown).get(part.lower(), {}).get(item.lower())
        return item_text

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
