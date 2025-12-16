"""
Data models for Schedule 13D and Schedule 13G beneficial ownership forms.

This module contains frozen dataclasses representing the structured data
from Schedule 13D/G XML filings.
"""
from dataclasses import dataclass
from typing import Optional

from edgar._party import Address

__all__ = [
    'ReportingPerson',
    'IssuerInfo',
    'SecurityInfo',
    'Schedule13DItems',
    'Schedule13GItems',
    'Signature'
]


@dataclass(frozen=True)
class ReportingPerson:
    """
    Individual or entity reporting beneficial ownership.

    Represents a single reporting person from the SC 13D or SC 13G filing.
    Joint filers will have multiple ReportingPerson instances.
    """
    cik: str
    name: str
    citizenship: str
    sole_voting_power: int
    shared_voting_power: int
    sole_dispositive_power: int
    shared_dispositive_power: int
    aggregate_amount: int
    percent_of_class: float
    type_of_reporting_person: str
    fund_type: Optional[str] = None
    comment: Optional[str] = None
    member_of_group: Optional[str] = None  # "a" = group member (joint filer), "b" = separate filer
    is_aggregate_exclude_shares: bool = False  # True if shares excluded from aggregate count
    no_cik: bool = False  # True if reporting person has no CIK assigned

    @property
    def total_voting_power(self) -> int:
        """Total voting power (sole + shared)"""
        return self.sole_voting_power + self.shared_voting_power

    @property
    def total_dispositive_power(self) -> int:
        """Total dispositive power (sole + shared)"""
        return self.sole_dispositive_power + self.shared_dispositive_power


@dataclass(frozen=True)
class IssuerInfo:
    """
    Subject company information.

    The company whose securities are being reported.
    """
    cik: str
    name: str
    cusip: str
    address: Optional[Address] = None


@dataclass(frozen=True)
class SecurityInfo:
    """
    Security class information.

    The class of securities subject to the filing.
    """
    title: str
    cusip: str


@dataclass(frozen=True)
class Schedule13DItems:
    """
    Items 1-7 for Schedule 13D narrative disclosures.

    Schedule 13D requires detailed narrative responses to 7 items,
    with Item 4 (Purpose of Transaction) being the most important for
    understanding activist intent.
    """
    # Item 1: Security and Issuer
    item1_security_title: Optional[str] = None
    item1_issuer_name: Optional[str] = None
    item1_issuer_address: Optional[str] = None

    # Item 2: Identity and Background
    item2_filing_persons: Optional[str] = None
    item2_business_address: Optional[str] = None
    item2_principal_occupation: Optional[str] = None
    item2_convictions: Optional[str] = None
    item2_citizenship: Optional[str] = None

    # Item 3: Source and Amount of Funds
    item3_source_of_funds: Optional[str] = None

    # Item 4: Purpose of Transaction (MOST IMPORTANT)
    item4_purpose_of_transaction: Optional[str] = None

    # Item 5: Interest in Securities of the Issuer
    item5_percentage_of_class: Optional[str] = None
    item5_number_of_shares: Optional[str] = None
    item5_transactions: Optional[str] = None
    item5_shareholders: Optional[str] = None
    item5_date_5pct_ownership: Optional[str] = None

    # Item 6: Contracts, Arrangements, Understandings
    item6_contracts: Optional[str] = None

    # Item 7: Material to be Filed as Exhibits
    item7_exhibits: Optional[str] = None


@dataclass(frozen=True)
class Schedule13GItems:
    """
    Items 1-10 for Schedule 13G.

    Schedule 13G has simpler, more structured responses compared to 13D.
    Many items are simple Y/N flags or references to the cover page.
    """
    # Item 1: Name and address of issuer
    item1_issuer_name: Optional[str] = None
    item1_issuer_address: Optional[str] = None

    # Item 2: Name and address of person filing
    item2_filer_names: Optional[str] = None
    item2_filer_addresses: Optional[str] = None
    item2_citizenship: Optional[str] = None

    # Item 3: If applicable
    item3_not_applicable: bool = True

    # Item 4: Ownership
    item4_amount_beneficially_owned: Optional[str] = None
    item4_percent_of_class: Optional[str] = None
    item4_sole_voting: Optional[str] = None
    item4_shared_voting: Optional[str] = None
    item4_sole_dispositive: Optional[str] = None
    item4_shared_dispositive: Optional[str] = None

    # Item 5: Ownership of 5% or less
    item5_not_applicable: bool = True
    item5_ownership_5pct_or_less: Optional[str] = None

    # Item 6: Ownership of more than 5%
    item6_not_applicable: bool = True

    # Item 7: Identification and classification
    item7_not_applicable: bool = True

    # Item 8: Identification and classification of members
    item8_not_applicable: bool = True

    # Item 9: Notice pursuant to Rule 13d-1(k)
    item9_not_applicable: bool = True

    # Item 10: Certification
    item10_certification: Optional[str] = None


@dataclass(frozen=True)
class Signature:
    """
    Signature information from the filing.

    Each reporting person must sign the filing.
    """
    reporting_person: str
    signature: str
    title: str
    date: str
