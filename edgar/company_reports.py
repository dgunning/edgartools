from functools import lru_cache, partial
from typing import Dict

from rich import print
from rich.console import Group, Text
from rich.panel import Panel

from edgar._rich import repr_rich
from edgar.financials import Financials
from edgar.htmltools import ChunkedDocument, chunks2df, detect_decimal_items, adjust_for_empty_items

__all__ = [
    'TenK',
    'TenQ',
    'TwentyF',
    'is_valid_item_for_filing'
]


class CompanyReport:

    def __init__(self, filing):
        self._filing = filing

    @property
    def form(self):
        return self._filing.form

    @property
    def company(self):
        return self._filing.company

    @property
    def income_statement(self):
        return self.financials.income_statement if self.financials else None

    @property
    def balance_sheet(self):
        return self.financials.balance_sheet if self.financials else None

    @property
    def cash_flow_statement(self):
        return self.financials.cash_flow_statement if self.financials else None

    @property
    @lru_cache(1)
    def financials(self):
        xbrl = self._filing.xbrl()
        if xbrl:
            return Financials.from_gaap(xbrl.gaap)

    @property
    @lru_cache(maxsize=1)
    def chunked_document(self):
        return ChunkedDocument(self._filing.html())

    @property
    def doc(self):
        return self.chunked_document

    def view(self, item_or_part: str):
        """Get the Item or Part from the filing document. e.g. Item 1 Business from 10-K or Part I from 10-Q"""
        item_text = self[item_or_part]
        if item_text:
            print(item_text)

    def __getitem__(self, item_or_part: str):
        # Show the item or part from the filing document. e.g. Item 1 Business from 10-K or Part I from 10-Q
        item_text = self.chunked_document[item_or_part]
        return item_text

    def __rich__(self):
        return Panel(
            Group(
                self._filing.__rich__(),
                self.financials or Text("No financial data available")
            )
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class TenK(CompanyReport):
    structure = structure = {
    "Part I": {
        "Item 1": {
            "Title": "Business",
            "Description": "Overview of the company's business operations, products, services, and market environment."
        },
        "Item 1A": {
            "Title": "Risk Factors",
            "Description": "Discussion of risks and uncertainties that could materially affect the company's " +
                           "financial condition or results of operations."
        },
        "Item 1B": {
            "Title": "Unresolved Staff Comments",
            "Description": "Any comments from the SEC staff on the company’s previous filings that remain unresolved."
        },
        "Item 2": {
            "Title": "Properties",
            "Description": "Information about the physical properties owned or leased by the company."
        },
        "Item 3": {
            "Title": "Legal Proceedings",
            "Description": "Details of significant ongoing legal proceedings."
        },
        "Item 4": {
            "Title": "Mine Safety Disclosures",
            "Description": "Relevant for mining companies, disclosures about mine safety and regulatory compliance."
        }
    },
    "Part II": {
        "Item 5": {
            "Title": "Market for Registrant’s Common Equity",
            "Description": "Information on the company’s equity, including stock performance and shareholder matters."
        },
        "Item 6": {
            "Title": "Selected Financial Data",
            "Description": "Financial data summary for the last five fiscal years."
        },
        "Item 7": {
            "Title": "Management’s Discussion and Analysis (MD&A)",
            "Description": "Management’s perspective on the financial condition, changes in financial condition, " +
                           "and results of operations."
        },
        "Item 7A": {
            "Title": "Quantitative and Qualitative Disclosures About Market Risk",
            "Description": "Information on the company's exposure to market risk, such as interest rate risk, " +
                           "foreign currency exchange risk, commodity price risk, etc."
        },
        "Item 8": {
            "Title": "Financial Statements",
            "Description": "Complete audited financial statements, including balance sheet, income statement, " +
                           "cash flow statement, and notes to the financial statements."
        },
        "Item 9": {
            "Title": "Controls and Procedures",
            "Description": "Evaluation of the effectiveness of the design and operation of the company’s disclosure" +
                           "controls and procedures."
        },
        "Item 9A": {
            "Title": "Controls and Procedures",
            "Description": "Evaluation of internal controls over financial reporting."
        },
        "Item 9B": {
            "Title": "Other Information",
            "Description": "Any other relevant information not covered in other sections."
        }
    },
    "Part III": {
        "Item 10": {
            "Title": "Directors, Executive Officers, and Corporate Governance",
            "Description": "Information about the company's directors, executive officers, and governance policies."
        },
        "Item 11": {
            "Title": "Executive Compensation",
            "Description": "Details of compensation paid to key executives."
        },
        "Item 12": {
            "Title": "Security Ownership of Certain Beneficial Owners and Management",
            "Description": "Information about stock ownership of major shareholders, directors, and management."
        },
        "Item 13": {
            "Title": "Certain Relationships and Related Transactions, and Director Independence",
            "Description": "Information on transactions between the company and its directors, officers, " +
                           "and significant shareholders."
        },
        "Item 14": {
            "Title": "Principal Accounting Fees and Services",
            "Description": "Fees paid to the principal accountant and services rendered."
        }
    },
    "Part IV": {
        "Item 15": {
            "Title": "Exhibits, Financial Statement Schedules",
            "Description": "Legal documents and financial schedules that support the financial statements " +
                           "and disclosures."
        }
    }
}


    def __init__(self, filing):
        assert filing.form in ['10-K', '10-K/A'], f"This form should be a 10-K but was {filing.form}"
        super().__init__(filing)

    def __str__(self):
        return f"""TenK('{self.company}')"""


class TenQ(CompanyReport):
    structure = {
    "Part I - Financial Information": {
        "Item 1": {
            "Title": "Financial Statements",
            "Description": "Unaudited financial statements including balance sheets, income statements, " +
                           "and cash flow statements."
        },
        "Item 2": {
            "Title": "Management’s Discussion and Analysis of Financial Condition and Results of Operations (MD&A)",
            "Description": "Management’s perspective on the financial condition and results of operations."
        },
        "Item 3": {
            "Title": "Quantitative and Qualitative Disclosures About Market Risk",
            "Description": "Information on the company's exposure to market risk."
        },
        "Item 4": {
            "Title": "Controls and Procedures",
            "Description": "Evaluation of the effectiveness of disclosure controls and procedures."
        }
    },
    "Part II - Other Information": {
        "Item 1": {
            "Title": "Legal Proceedings",
            "Description": "Brief description of any significant pending legal proceedings."
        },
        "Item 1A": {
            "Title": "Risk Factors",
            "Description": "An update on risk factors that may affect future results."
        },
        "Item 2": {
            "Title": "Unregistered Sales of Equity Securities and Use of Proceeds",
            "Description": "Details of unregistered sales of equity securities."
        },
        "Item 3": {
            "Title": "Defaults Upon Senior Securities",
            "Description": "Information regarding any defaults on senior securities."
        },
        "Item 4": {
            "Title": "Mine Safety Disclosures",
            "Description": "Required for companies with mining operations."
        },
        "Item 5": {
            "Title": "Other Information",
            "Description": "Any other information that should be disclosed to investors."
        },
        "Item 6": {
            "Title": "Exhibits",
            "Description": "List of exhibits required by Item 601 of Regulation S-K."
        }
    }
}

    def __init__(self, filing):
        assert filing.form in ['10-Q', '10-Q/A'], f"This form should be a 10-Q but was {filing.form}"
        super().__init__(filing)

    def __str__(self):
        return f"""TenQ('{self.company}')"""


class TwentyF(CompanyReport):
    structure = {
        "Part I": {
            "Item 1": {
                "Title": "Identity of Directors, Senior Management, and Advisers",
                "Description": "Information about the company's directors, senior management, and advisers."
            },
            "Item 2": {
                "Title": "Offer Statistics and Expected Timetable",
                "Description": "Details on recent and expected offers of securities."
            },
            "Item 3": {
                "Title": "Key Information",
                "Description": "Financial and other key information about the company, including risk factors " +
                               "and ratios."
            },
            "Item 4": {
                "Title": "Information on the Company",
                "Description": "Detailed information about the company's operations and properties."
            },
            "Item 4A": {
                "Title": "Unresolved Staff Comments",
                "Description": "Any comments from the SEC staff on the company’s previous filings that " +
                               "remain unresolved."
            }
        },
        "Part II": {
            "Item 5": {
                "Title": "Operating and Financial Review and Prospects",
                "Description": "Management’s discussion and analysis of financial condition and results of operations."
            },
            "Item 6": {
                "Title": "Directors, Senior Management, and Employees",
                "Description": "Information about the company's directors, senior management, and employees."
            },
            "Item 7": {
                "Title": "Major Shareholders and Related Party Transactions",
                "Description": "Information about major shareholders and transactions with related parties."
            },
            "Item 8": {
                "Title": "Financial Information",
                "Description": "Audited financial statements and supplementary financial information."
            },
            "Item 9": {
                "Title": "The Offer and Listing",
                "Description": "Details on the company's securities and markets where they are traded."
            }
        },
        "Part III": {
            "Item 10": {
                "Title": "Additional Information",
                "Description": "Additional information such as share capital, memoranda, and articles of association."
            },
            "Item 11": {
                "Title": "Quantitative and Qualitative Disclosures About Market Risk",
                "Description": "Information on the company's exposure to market risk."
            },
            "Item 12": {
                "Title": "Description of Securities Other Than Equity Securities",
                "Description": "Detailed information on securities other than equity."
            }
        },
        "Part IV": {
            "Item 13": {
                "Title": "Defaults, Dividend Arrearages, and Delinquencies",
                "Description": "Information about defaults on payments and arrearages."
            },
            "Item 14": {
                "Title": "Material Modifications to the Rights of Security Holders and Use of Proceeds",
                "Description": "Details on any modifications to the rights of security holders."
            },
            "Item 15": {
                "Title": "Controls and Procedures",
                "Description": "Assessment of the effectiveness of disclosure controls and internal controls " +
                               "over financial reporting."
            },
            "Item 16": {
                "Title": "Various Disclosures",
                "Description": "Includes disclosures related to audit committee financial experts, code of ethics, " +
                               "principal accountant fees and services, and other corporate governance matters."
            }
        },
        "Part V": {
            "Item 17": {
                "Title": "Financial Statements",
                "Description": "Financial statements prepared in accordance with or reconciled to U.S. GAAP or IFRS."
            },
            "Item 18": {
                "Title": "Financial Statements",
                "Description": "If different from Item 17, financial statements prepared in accordance with " +
                               "home country standards."
            },
            "Item 19": {
                "Title": "Exhibits",
                "Description": "Legal and financial documents supporting the information in the report."
            }
        }
    }

    def __init__(self, filing):
        assert filing.form in ['20-F', '20-F/A'], f"This form should be a 20-F but was {filing.form}"
        super().__init__(filing)

    def __str__(self):
        return f"""TwentyF('{self.company}')"""


class EightK(CompanyReport):
    structure = {
        "Item 1.01": {
            "Title": "Entry into a Material Definitive Agreement",
            "Description": "Reports any material agreement not made in the ordinary course of business."
        },
        "Item 1.02": {
            "Title": "Termination of a Material Definitive Agreement",
            "Description": "Reports the termination of any material agreement."
        },
        "Item 1.03": {
            "Title": "Bankruptcy or Receivership",
            "Description": "Reports any bankruptcy or receivership."
        },
        "Item 2.01": {"Title": "Completion of Acquisition or Disposition of Assets",
                      "Description": "Reports the completion of an acquisition or disposition of a significant " +
                                     "amount of assets."},
        "Item 2.02": {"Title": "Results of Operations and Financial Condition",
                      "Description": "Reports on the company's results of operations and financial condition."},
        "Item 2.03": {
            "Title": "Creation of a Direct Financial Obligation or an Obligation under an Off-Balance Sheet " +
                     "Arrangement of a Registrant",
            "Description": "Reports the creation of a direct financial obligation."},
        "Item 2.04": {
            "Title": "Triggering Events That Accelerate or Increase a Direct Financial Obligation or an Obligation "
                     + "under an Off-Balance Sheet Arrangement",
            "Description": "Reports any triggering events."},
        "Item 2.05": {"Title": "Costs Associated with Exit or Disposal Activities",
                      "Description": "Reports costs related to exit or disposal activities."},
        "Item 2.06": {"Title": "Material Impairments", "Description": "Reports on any material impairments."},
        "Item 3.01": {
            "Title": "Notice of Delisting or Failure to Satisfy a Continued Listing Rule or Standard; " +
                     "Transfer of Listing",
            "Description": "Reports on delisting or failure to satisfy listing rules."},
        "Item 3.02": {"Title": "Unregistered Sales of Equity Securities",
                      "Description": "Reports on the sale of unregistered equity securities."},
        "Item 3.03": {"Title": "Material Modification to Rights of Security Holders",
                      "Description": "Reports on any modifications to the rights of security holders."},
        "Item 4.01": {"Title": "Changes in Registrant's Certifying Accountant",
                      "Description": "Reports any change in the company's accountant."},
        "Item 4.02": {
            "Title": "Non-Reliance on Previously Issued Financial Statements or a Related Audit Report or " +
                     "Completed Interim Review",
            "Description": "Reports on non-reliance on previously issued financial statements."},
        "Item 5.01": {"Title": "Changes in Control of Registrant",
                      "Description": "Reports changes in control of the company."},
        "Item 5.02": {
            "Title": "Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain " +
                     "Officers",
            "Description": "Compensatory Arrangements of Certain Officers: Reports any changes in the company's " +
                           "directors or certain officers."},
        "Item 5.03": {"Title": "Amendments to Articles of Incorporation or Bylaws; Change in Fiscal Year",
                      "Description": "Reports on amendments to articles of incorporation or bylaws."},
        "Item 5.04": {
            "Title": "Temporary Suspension of Trading Under Registrant’s Employee Benefit Plans",
            "Description": "Reports on the temporary suspension of trading under the company’s employee benefit plans."
        },
        "Item 5.05": {
            "Title": "Amendment to the Registrant’s Code of Ethics, or Waiver of a Provision of the Code of Ethics",
            "Description": "Reports on amendments or waivers to the code of ethics."},
        "Item 5.06": {"Title": "Change in Shell Company Status",
                      "Description": "Reports a change in the company's shell company status."},
        "Item 5.07": {"Title": "Submission of Matters to a Vote of Security Holders",
                      "Description": "Reports on matters submitted to a vote of security holders."},
        "Item 5.08": {"Title": "Shareholder Director Nominations",
                      "Description": "Reports on shareholder director nominations."},
        "Item 6.01": {"Title": "ABS Informational and Computational Material",
                      "Description": "Reports ABS informational and computational material."},
        "Item 6.02": {"Title": "Change of Servicer or Trustee",
                      "Description": "Reports on the change of servicer or trustee."},
        "Item 6.03": {"Title": "Change in Credit Enhancement or Other External Support",
                      "Description": "Reports on changes in credit enhancement or external support."},
        "Item 6.04": {"Title": "Failure to Make a Required Distribution",
                      "Description": "Reports on the failure to make a required distribution."},
        "Item 6.05": {"Title": "Securities Act Updating Disclosure",
                      "Description": "Reports on Securities Act updating disclosure."},
        "Item 9.01": {
            "Title": "Financial Statements and Exhibits",
            "Description": "Reports financial statements and other exhibits related to the events reported in the 8-K."
        }
    }

    def __init__(self, filing):
        assert filing.form in ['8-K', '8-K/A'], f"This form should be an 8-K but was {filing.form}"
        super().__init__(filing)

    @property
    @lru_cache(maxsize=1)
    def chunked_document(self):
        decimal_chunk_fn = partial(chunks2df,
                                   item_detector=detect_decimal_items,
                                   item_adjuster=adjust_for_empty_items,
                                   item_structure=self.structure)
        return ChunkedDocument(self._filing.html(),
                               chunk_size=400,
                               chunk_fn=decimal_chunk_fn)

    def __str__(self):
        return f"""EightK('{self.company}')"""


def is_valid_item_for_filing(filing_structure: Dict, item: str, part: str = None):
    """Return true if the item is valid"""
    if part:
        return item.upper() in filing_structure[part.upper()]
    else:
        for part in filing_structure.keys():
            if item.upper() in filing_structure[part]:
                return True
    return False
