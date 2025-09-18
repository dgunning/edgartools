from dataclasses import dataclass, field
from typing import List, Optional


# Dataclasses for raw data from primary_doc.xml files in all filings
@dataclass
class PrimaryDoc:
    cik: str
    fund_name: str
    street1: str
    city: str
    state: str
    zip_code: str
    period_of_report: str
    submission_type: str
    report_calendar_year: str
    signer_name: str
    signer_title: str
    signature_date: str
    phone_number: Optional[str] = None
    street2: Optional[str] = None
    crd_number: Optional[str] = None
    filer_sec_file_number: Optional[str] = None
    lei_number: Optional[str] = None
    report_type: Optional[str] = None
    notice_explanation: Optional[str] = None
    confidential_treatment: Optional[str] = None
    npx_file_number: Optional[str] = None
    explanatory_choice: Optional[str] = None
    other_included_managers_count: Optional[str] = None
    tx_printed_signature: Optional[str] = None
    agent_for_service_name: Optional[str] = None
    agent_for_service_address_street1: Optional[str] = None
    agent_for_service_address_street2: Optional[str] = None
    agent_for_service_address_city: Optional[str] = None
    agent_for_service_address_state_country: Optional[str] = None
    agent_for_service_address_zip_code: Optional[str] = None
    is_amendment: Optional[bool] = None
    amendment_no: Optional[str] = None
    amendment_type: Optional[str] = None
    de_novo_request_choice: Optional[str] = None
    year_or_quarter: Optional[str] = None
    conf_denied_expired: Optional[str] = None
    included_managers: List["IncludedManager"] = field(default_factory=list)
    registrant_type: Optional[str] = None
    live_test_flag: Optional[str] = None
    ccc: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone_number: Optional[str] = None
    contact_email_address: Optional[str] = None
    override_internet_flag: Optional[str] = None
    confirming_copy_flag: Optional[str] = None
    investment_company_type: Optional[str] = None
    rpt_include_all_series_flag: Optional[str] = None
    series_count: Optional[str] = None
    report_series_class_infos: List["ReportSeriesClassInfo"] = field(
        default_factory=list
    )
    series_reports: List["SeriesReport"] = field(default_factory=list)


@dataclass
class IncludedManager:
    serial_no: str
    form13f_file_number: Optional[str]
    name: str
    sec_file_number: Optional[str] = None


@dataclass
class VoteCategory:
    category_type: str


@dataclass
class VoteRecord:
    how_voted: str
    shares_voted: float
    management_recommendation: str


@dataclass
class ProxyTable:
    """Represents a single proxy vote table entry from the XML file."""

    issuer_name: str
    meeting_date: str  # Consider converting to date object later
    vote_description: str
    shares_voted: float  # Or int
    shares_on_loan: float  # Or int

    # Optional fields from XML
    cusip: Optional[str] = None
    isin: Optional[str] = None
    figi: Optional[str] = None
    other_vote_description: Optional[str] = None
    vote_source: Optional[str] = None
    vote_series: Optional[str] = None
    vote_other_info: Optional[str] = None

    # Nested lists
    vote_categories: List[VoteCategory] = field(default_factory=list)
    vote_records: List[VoteRecord] = field(default_factory=list)
    other_managers: List[str] = field(default_factory=list)


@dataclass
class ProxyVoteTable:
    """Container for all vote tables in a single filing."""

    proxy_tables: List[ProxyTable] = field(default_factory=list)


@dataclass
class ClassInfo:
    class_id: str


@dataclass
class ReportSeriesClassInfo:
    series_id: str
    class_infos: List[ClassInfo] = field(default_factory=list)


@dataclass
class SeriesReport:
    id_of_series: str
    name_of_series: Optional[str] = None
    lei_of_series: Optional[str] = None
