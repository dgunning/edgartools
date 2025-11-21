"""Form 10-Q quarterly report class."""
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

    def __getitem__(self, item_or_part: str):
        # Show the item or part from the filing document. e.g. Item 1 Business from 10-K or Part I from 10-Q
        item_text = self.chunked_document[item_or_part]
        return item_text

    def get_item_with_part(self, part: str, item: str, markdown:bool=True):
        if not part:
            return self.id_parse_document(markdown).get(part.lower(), {}).get(item.lower())
        # Show the item or part from the filing document. e.g. Item 1 Business from 10-K or Part I from 10-Q
        item_text = self.chunked_document.get_item_with_part(part, item, markdown=markdown)
        # remove first line or last line (redundant part information)
        if not item_text or not item_text.strip():
            return self.id_parse_document(markdown).get(part.lower(), {}).get(item.lower())
        return item_text

    @lru_cache(maxsize=1)
    def id_parse_document(self, markdown:bool=True):
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
