import re
from datetime import datetime
from functools import cached_property, lru_cache, partial
from typing import Dict, List, Optional

from rich import box, print
from rich.console import Group, Text
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from edgar._filings import Attachment, Attachments
from edgar._markdown import MarkdownContent
from edgar.files.html import Document
from edgar.files.html_documents import HtmlDocument
from edgar.files.htmltools import ChunkedDocument, adjust_for_empty_items, chunks2df, detect_decimal_items
from edgar.financials import Financials
from edgar.formatting import datefmt
from edgar.richtools import repr_rich, rich_to_text

__all__ = [
    'TenK',
    'TenQ',
    'TwentyF',
    'CurrentReport',
    'SixK',
    'EightK',
    'PressRelease',
    'PressReleases',
    'is_valid_item_for_filing'
]


class CompanyReport:

    def __init__(self, filing):
        self._filing = filing

    @property
    def filing_date(self):
        return self._filing.filing_date

    @property
    def form(self):
        return self._filing.form

    @property
    def company(self):
        return self._filing.company

    @property
    def income_statement(self):
        return self.financials.income_statement() if self.financials else None

    @property
    def balance_sheet(self):
        return self.financials.balance_sheet() if self.financials else None

    @property
    def cash_flow_statement(self):
        return self.financials.cashflow_statement() if self.financials else None

    @cached_property
    def financials(self):
        """Get the financials for this filing"""
        return Financials.extract(self._filing)

    @property
    def period_of_report(self):
        return self._filing.header.period_of_report

    @cached_property
    def chunked_document(self):
        return ChunkedDocument(self._filing.html())

    @property
    def doc(self):
        return self.chunked_document

    @property
    def items(self) -> List[str]:
        return self.chunked_document.list_items()

    def __getitem__(self, item_or_part: str):
        # Show the item or part from the filing document. e.g. Item 1 Business from 10-K or Part I from 10-Q
        item_text = self.chunked_document[item_or_part]
        return item_text

    def view(self, item_or_part: str):
        """Get the Item or Part from the filing document. e.g. Item 1 Business from 10-K or Part I from 10-Q"""
        item_text = self[item_or_part]
        if item_text:
            print(item_text)

    def __rich__(self):
        return Panel(
            Group(
                self._filing.__rich__(),
                self.financials() or Text("No financial data available")
            )
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class FilingStructure:

    def __init__(self, structure: Dict):
        self.structure = structure

    def get_part(self, part: str):
        return self.structure.get(part.upper())

    def get_item(self, item: str, part: str = None):
        item = item.upper()
        if part:
            part_dict = self.get_part(part)
            if part_dict:
                return part_dict.get(item)
        else:
            for _, items in self.structure.items():
                if item in items:
                    return items[item]
        return None

    def is_valid_item(self, item: str, part: str = None):
        return self.get_item(item, part) is not None


class ItemOnlyFilingStructure(FilingStructure):

    def get_part(self, part: str):
        return None

    def get_item(self, item: str, part: str = None):
        return self.structure.get(item.upper())


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
                "Title": "Market for Registrant’s Common Equity",
                "Description": "Information on the company’s equity, including stock performance " +
                               "and shareholder matters."
            },
            "ITEM 6": {
                "Title": "Selected Financial Data",
                "Description": "Financial data summary for the last five fiscal years."
            },
            "ITEM 7": {
                "Title": "Management’s Discussion and Analysis (MD&A)",
                "Description": "Management’s perspective on the financial condition, changes in financial condition, " +
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
                "Description": "Evaluation of the effectiveness of the design and operation of the company’s disclosure controls and procedures."
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

    @lru_cache(maxsize=1)
    def id_parse_document(self, markdown:bool=False):
        from edgar.files.html_documents_id_parser import ParsedHtml10K
        return ParsedHtml10K().extract_html(self._filing.html(), self.structure, markdown=markdown)

    def __str__(self):
        return f"""TenK('{self.company}')"""

    def __getitem__(self, item_or_part: str):
        # Show the item or part from the filing document. e.g. Item 1 Business from 10-K or Part I from 10-Q
        item_text = self.chunked_document[item_or_part]
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


class TenQ(CompanyReport):
    structure = FilingStructure({
        "PART I": {  # Financial Information
            "ITEM 1": {
                "Title": "Financial Statements",
                "Description": "Unaudited financial statements including balance sheets, income statements, " +
                               "and cash flow statements."
            },
            "ITEM 2": {
                "Title": "Management’s Discussion and Analysis of Financial Condition and Results of Operations (MD&A)",
                "Description": "Management’s perspective on the financial condition and results of operations."
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
                "Description": "Any comments from the SEC staff on the company’s previous filings that " +
                               "remain unresolved."
            }
        },
        "PART II": {
            "ITEM 5": {
                "Title": "Operating and Financial Review and Prospects",
                "Description": "Management’s discussion and analysis of financial condition and results of operations."
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

    def __str__(self):
        return f"""TwentyF('{self.company}')"""


class CurrentReport(CompanyReport):
    structure = ItemOnlyFilingStructure({
        "ITEM 1.01": {
            "Title": "Entry into a Material Definitive Agreement",
            "Description": "Reports any material agreement not made in the ordinary course of business."
        },
        "ITEM 1.02": {
            "Title": "Termination of a Material Definitive Agreement",
            "Description": "Reports the termination of any material agreement."
        },
        "ITEM 1.03": {
            "Title": "Bankruptcy or Receivership",
            "Description": "Reports any bankruptcy or receivership."
        },
        "ITEM 2.01": {"Title": "Completion of Acquisition or Disposition of Assets",
                      "Description": "Reports the completion of an acquisition or disposition of a significant " +
                                     "amount of assets."},
        "ITEM 2.02": {"Title": "Results of Operations and Financial Condition",
                      "Description": "Reports on the company's results of operations and financial condition."},
        "ITEM 2.03": {
            "Title": "Creation of a Direct Financial Obligation or an Obligation under an Off-Balance Sheet " +
                     "Arrangement of a Registrant",
            "Description": "Reports the creation of a direct financial obligation."},
        "ITEM 2.04": {
            "Title": "Triggering Events That Accelerate or Increase a Direct Financial Obligation or an Obligation "
                     + "under an Off-Balance Sheet Arrangement",
            "Description": "Reports any triggering events."},
        "ITEM 2.05": {"Title": "Costs Associated with Exit or Disposal Activities",
                      "Description": "Reports costs related to exit or disposal activities."},
        "ITEM 2.06": {"Title": "Material Impairments", "Description": "Reports on any material impairments."},
        "ITEM 3.01": {
            "Title": "Notice of Delisting or Failure to Satisfy a Continued Listing Rule or Standard; " +
                     "Transfer of Listing",
            "Description": "Reports on delisting or failure to satisfy listing rules."},
        "ITEM 3.02": {"Title": "Unregistered Sales of Equity Securities",
                      "Description": "Reports on the sale of unregistered equity securities."},
        "ITEM 3.03": {"Title": "Material Modification to Rights of Security Holders",
                      "Description": "Reports on any modifications to the rights of security holders."},
        "ITEM 4.01": {"Title": "Changes in Registrant's Certifying Accountant",
                      "Description": "Reports any change in the company's accountant."},
        "ITEM 4.02": {
            "Title": "Non-Reliance on Previously Issued Financial Statements or a Related Audit Report or " +
                     "Completed Interim Review",
            "Description": "Reports on non-reliance on previously issued financial statements."},
        "ITEM 5.01": {"Title": "Changes in Control of Registrant",
                      "Description": "Reports changes in control of the company."},
        "ITEM 5.02": {
            "Title": "Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain " +
                     "Officers",
            "Description": "Compensatory Arrangements of Certain Officers: Reports any changes in the company's " +
                           "directors or certain officers."},
        "ITEM 5.03": {"Title": "Amendments to Articles of Incorporation or Bylaws; Change in Fiscal Year",
                      "Description": "Reports on amendments to articles of incorporation or bylaws."},
        "ITEM 5.04": {
            "Title": "Temporary Suspension of Trading Under Registrant’s Employee Benefit Plans",
            "Description": "Reports on the temporary suspension of trading under the company’s employee benefit plans."
        },
        "ITEM 5.05": {
            "Title": "Amendment to the Registrant’s Code of Ethics, or Waiver of a Provision of the Code of Ethics",
            "Description": "Reports on amendments or waivers to the code of ethics."},
        "ITEM 5.06": {"Title": "Change in Shell Company Status",
                      "Description": "Reports a change in the company's shell company status."},
        "ITEM 5.07": {"Title": "Submission of Matters to a Vote of Security Holders",
                      "Description": "Reports on matters submitted to a vote of security holders."},
        "ITEM 5.08": {"Title": "Shareholder Director Nominations",
                      "Description": "Reports on shareholder director nominations."},
        "ITEM 6.01": {"Title": "ABS Informational and Computational Material",
                      "Description": "Reports ABS informational and computational material."},
        "ITEM 6.02": {"Title": "Change of Servicer or Trustee",
                      "Description": "Reports on the change of servicer or trustee."},
        "ITEM 6.03": {"Title": "Change in Credit Enhancement or Other External Support",
                      "Description": "Reports on changes in credit enhancement or external support."},
        "ITEM 6.04": {"Title": "Failure to Make a Required Distribution",
                      "Description": "Reports on the failure to make a required distribution."},
        "ITEM 6.05": {"Title": "Securities Act Updating Disclosure",
                      "Description": "Reports on Securities Act updating disclosure."},
        "ITEM 9.01": {
            "Title": "Financial Statements and Exhibits",
            "Description": "Reports financial statements and other exhibits related to the events reported in the 8-K."
        }
    })

    def __init__(self, filing):
        assert filing.form in ['8-K', '8-K/A', '6-K', '6-K/A'], f"This form should be an 8-K but was {filing.form}"
        super().__init__(filing)

    @property
    def has_press_release(self):
        return self.press_releases is not None

    @property
    def press_releases(self):
        attachments: Attachments = self._filing.attachments
        # This query for press release currently includes EX-99, EX-99.1, EX-99.01 but not EX-99.2
        # Here is what we think so far
        html_document = "document.endswith('.htm')"
        named_release = "re.match('.*RELEASE', description)"
        type_ex_99 = "document_type in ['EX-99.1', 'EX-99', 'EX-99.01']"
        press_release_query = f"{html_document} and ({named_release} or {type_ex_99})"
        press_release_results = attachments.query(press_release_query)
        if press_release_results:
            return PressReleases(press_release_results)

    @cached_property
    def chunked_document(self):
        html = self._filing.html()
        if not html:
            return None
        decimal_chunk_fn = partial(chunks2df,
                                   item_detector=detect_decimal_items,
                                   item_adjuster=adjust_for_empty_items,
                                   item_structure=self.structure)

        return ChunkedDocument(html,
                               chunk_fn=decimal_chunk_fn)

    @property
    def doc(self):
        return self.chunked_document

    @property
    def items(self) -> List[str]:
        if self.chunked_document:
            return self.chunked_document.list_items()
        return []

    def __getitem__(self, item_or_part: str):
        # Show the item or part from the filing document. e.g. Item 1 Business from 10-K or Part I from 10-Q
        item_text = self.chunked_document[item_or_part]
        return item_text

    def view(self, item_or_part: str):
        """Get the Item or Part from the filing document. e.g. Item 1 Business from 10-K or Part I from 10-Q"""
        item_text = self[item_or_part]
        if item_text:
            print(item_text)

    @property
    def date_of_report(self):
        """Return the period of report for this filing"""
        period_of_report_str = self._filing.header.period_of_report
        if period_of_report_str:
            period_of_report = datetime.strptime(period_of_report_str, "%Y-%m-%d")
            return period_of_report.strftime("%B %d, %Y")
        return ""

    def _get_exhibit_content(self, exhibit: Attachment) -> Optional[str]:
        """
        Get the content of the exhibit
        """
        # For old filings the exhibit might not have a document. So we need to get the full text content
        # from the sgml content
        if exhibit.empty:
            # Download the SGML document
            sgml_document = self._filing.sgml().get_document_by_sequence(exhibit.sequence_number)
            if sgml_document:
                exhibit_content = sgml_document.text()
                return exhibit_content
        else:
            html_content = exhibit.download()
            if html_content:
                document = Document.parse(html_content)
                return repr_rich(document, width=200, force_terminal=False)

    def _content_renderables(self):
        """Get the content of the exhibits as renderables"""
        renderables = []
        for exhibit in self._filing.exhibits:
            # Skip binary files
            if exhibit.is_binary():
                continue
            exhibit_content = self._get_exhibit_content(exhibit)

            if exhibit_content:
                # Remove text like [/she] and replace with (she) to prevent it being treated as rich markup
                cleaned_content = re.sub(r'\[(/[^]]*)]', r'(\1)',exhibit_content)
                title = Text.assemble(("Exhibit ", "bold gray54"), (exhibit.document_type, "bold green"))
                renderables.append(Panel(cleaned_content,
                                         title=title,
                                         subtitle=Text(exhibit.description, style="gray54"),
                                         box=box.SIMPLE))
        return Group(*renderables)

    def text(self):
        """Get the text of the EightK filing
           This includes the text content of all the exhibits
        """
        return rich_to_text(self._content_renderables())

    def __rich__(self):

        # Renderables for the panel.
        renderables = []

        # List the exhibits as a table
        exhibit_table = Table("", "Type", "Description",
                      title="Exhibits", show_header=True, header_style="bold", box=box.ROUNDED)
        renderables.append(exhibit_table)
        for exhibit in self._filing.exhibits:
            exhibit_table.add_row(exhibit.sequence_number, exhibit.document_type, exhibit.description)

        panel_title = Text.assemble(
            (f"{self.company}", "bold deep_sky_blue1"),
            (" ", ""),
            (f"{self.form}", "bold green"),
            (" ", ""),
            (f"{self.date_of_report}", "bold yellow")
        )

        # Add the content of the exhibits
        renderables.append(self._content_renderables())

        return Panel(
            Group(*renderables),
            title=panel_title,
            box=box.SIMPLE
        )

    def __str__(self):
        return f"{self.company} {self.form} {self.date_of_report}"

    def __repr__(self):
        return repr_rich(self.__rich__())

# Aliases fpr the current report
EightK = CurrentReport
SixK = CurrentReport

class PressReleases:
    """
    Represent the attachment on an 8-K filing that could be press releases
    """

    def __init__(self, attachments: Attachments):
        self.attachments: Attachments = attachments

    def __len__(self):
        return len(self.attachments)

    def __getitem__(self, item):
        attachment = self.attachments.get_by_index(item)
        if attachment:
            return PressRelease(attachment)

    def __rich__(self):
        return self.attachments.__rich__()

    def __repr__(self):
        return repr_rich(self.__rich__())


class PressRelease:
    """
    Represents a press release attachment from an 8-K filing
    With the Type EX-99.1
    """

    def __init__(self, attachment: Attachment):
        self.attachment: Attachment = attachment

    def url(self):
        return self.attachment.url

    @property
    def document(self) -> str:
        return self.attachment.document

    @property
    def description(self) -> str:
        return self.attachment.description

    @lru_cache(maxsize=1)
    def html(self) -> str:
        return self.attachment.download()

    def text(self) -> str:
        html = self.html()
        if html:
            return HtmlDocument.from_html(html, extract_data=False).text

    def open(self):
        self.attachment.open()

    def view(self):
        return self.to_markdown().view()

    def to_markdown(self):
        html = self.html()
        markdown_content = MarkdownContent.from_html(html, title="8-K Press Release")
        return markdown_content

    def __rich__(self):
        return self.to_markdown()

    def __repr__(self):
        return repr_rich(self.__rich__())


def is_valid_item_for_filing(filing_structure: Dict, item: str, part: str = None):
    """Return true if the item is valid"""
    item = item.upper()
    if part:
        part_dict = filing_structure.get(part.upper())
        if part_dict:
            return item in part_dict
    else:
        for _, items in filing_structure.items():
            if item in items:
                return True
    return False
