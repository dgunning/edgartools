"""Pydantic models for ATS-N filing data.

Models here are pure data containers — no parsing logic, no filing references.
Parsing lives in `edgar.ats.atsn`.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

__all__ = [
    "ATSAddress",
    "ATSNameRecord",
    "FilerContact",
    "ATSIdentifyingInfo",
    "ATSOperatorActivities",
    "ATSOperations",
]


class ATSAddress(BaseModel):
    """Physical server or office address from primary/secondary site records."""
    street1: Optional[str] = None
    street2: Optional[str] = None
    city: Optional[str] = None
    state_or_country: Optional[str] = None
    zip_code: Optional[str] = None


class ATSNameRecord(BaseModel):
    """A single entry from the repeating atsNames/atsName element.

    Some operators run multiple venues under one CIK (e.g. JPM files multiple
    ATS-N/UAs in a single submission batch for different venues).
    """
    ats_name: str
    mpid: Optional[str] = None


class FilerContact(BaseModel):
    """Header-level filer identity and contact information."""
    cik: str
    mpid: Optional[str] = None
    nms_stock_ats_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None


class ATSIdentifyingInfo(BaseModel):
    """Part I — Identifying information about the ATS and its operator."""
    # Cover / Item 1-2
    ats_commercial_name: Optional[str] = None
    operator_legal_name: Optional[str] = None
    supersedes_prior_form_ats: Optional[bool] = None

    # Item 3 — repeating ATS name records (multi-venue operators)
    ats_names: List[ATSNameRecord] = []

    # Item 4 — Broker-dealer registration
    bd_file_number: Optional[str] = None
    bd_crd_number: Optional[str] = None

    # Item 5 — SRO membership + MPID
    sro_name: Optional[str] = None
    nms_stock_mpid: Optional[str] = None

    # Item 6 — Website
    website: Optional[str] = None

    # Item 7 — Server locations (primary + optional secondaries)
    primary_site: Optional[ATSAddress] = None
    secondary_sites: List[ATSAddress] = []


class ATSOperatorActivities(BaseModel):
    """Part II — Activities of the Broker-Dealer Operator.

    Roughly 30 fields: Y/N gate flags paired with free-text narratives.
    All fields are Optional; many are omitted in the XML when a gating
    flag is "No" (the corresponding narrative is only required for "Yes").

    SEC XML quirk: gate flags appear in two patterns within the same filing:
    - As an attribute on a container element (when the flag is "Y" and
      prompts additional narrative children)
    - As a standalone flat element (when the flag is "N" and no narrative
      is required). The parser resolves both.
    """
    # Item 1 — BD units entering orders
    bd_units_permit_order_entry: Optional[bool] = None
    bd_units_description: Optional[str] = None
    bd_services_same_to_all: Optional[bool] = None
    bd_services_difference_explanation: Optional[str] = None
    bd_has_third_party_arrangements: Optional[bool] = None
    can_route_oat_interest: Optional[bool] = None

    # Item 2 — Affiliates entering orders
    affiliates_permit_order_entry: Optional[bool] = None
    affiliates_description: Optional[str] = None
    affiliates_services_same_to_subscribers: Optional[bool] = None
    affiliates_have_third_party_arrangements: Optional[bool] = None
    can_route_oat_interest_via_affl: Optional[bool] = None

    # Item 3 — Subscriber opt-out
    subscribers_can_opt_out_of_bd: Optional[bool] = None
    subscriber_opt_out_bd_explanation: Optional[str] = None
    subscribers_can_opt_out_of_affl: Optional[bool] = None
    subscriber_opt_out_affl_explanation: Optional[str] = None
    opt_out_same_to_all: Optional[bool] = None

    # Item 4 — Arrangements with other trading centers
    has_trading_center_arrangements: Optional[bool] = None
    trading_center_arrangements: Optional[str] = None
    affl_has_trading_center_arrangements: Optional[bool] = None

    # Item 5 — Bundled products / services
    offers_bundled_products: Optional[bool] = None
    bundled_products_description: Optional[str] = None
    bundled_services_same_to_all: Optional[bool] = None
    affl_offers_bundled_products: Optional[bool] = None
    affl_bundled_products_description: Optional[str] = None
    affl_bundled_services_same_to_all: Optional[bool] = None

    # Item 6 — Employees and service providers
    employees_access_confidential: Optional[bool] = None
    employee_services_description: Optional[str] = None
    has_third_party_service_providers: Optional[bool] = None
    service_providers_description: Optional[str] = None
    service_provider_uses_ats_services: Optional[bool] = None

    # Item 7 — Confidentiality safeguards
    safeguards_description: Optional[str] = None
    subscriber_can_consent_to_disclosure: Optional[bool] = None
    roles_responsibilities_summary: Optional[str] = None


class ATSOperations(BaseModel):
    """Part III — Manner of Operations.

    The analytical core of an ATS-N filing. Roughly 60 elements across 26
    items. All fields are Optional because many are gated by sibling Y/N
    flags. Free-text narrative fields are exposed verbatim — no NLP.

    Oversized narrative fields (Items 7a and 9a) may move to sibling PDF
    attachments when too long for XML. The `*_pdf_url` fields surface
    those URLs when the corresponding XML content is empty.
    """
    # Item 1 — Subscriber categories (repeating enumeration)
    subscriber_types: List[str] = []

    # Item 2 — Access conditions
    requires_registered_bd: Optional[bool] = None
    has_other_access_conditions: Optional[bool] = None
    access_conditions_summary: Optional[str] = None
    access_conditions_same_for_all: Optional[bool] = None
    requires_written_agreement: Optional[bool] = None

    # Item 3 — Exclusion of subscribers
    can_exclude_subscribers: Optional[bool] = None
    exclusion_conditions_summary: Optional[str] = None
    exclusion_conditions_same_for_all: Optional[bool] = None

    # Item 4 — Hours of operation
    hours_of_operation: Optional[str] = None
    hours_same_for_all: Optional[bool] = None

    # Item 5 — Order entry protocols (connectivity)
    permits_order_trading_via_protocol: Optional[bool] = None
    protocol_description: Optional[str] = None
    protocol_same_for_all: Optional[bool] = None
    has_other_connectivity_means: Optional[bool] = None
    other_connectivity_description: Optional[str] = None
    other_connectivity_same_for_all: Optional[bool] = None

    # Item 6 — Co-location and proximity services
    offers_colocation_services: Optional[bool] = None
    colocation_description: Optional[str] = None
    colocation_terms_same_for_all: Optional[bool] = None
    has_other_colocation_means: Optional[bool] = None
    offers_reduced_speed_access: Optional[bool] = None

    # Item 7 — Order types (PDF attachment may carry extended version)
    order_types: Optional[str] = None
    order_types_pdf_url: Optional[str] = None
    order_types_same_for_all: Optional[bool] = None

    # Item 8 — Order sizes
    has_size_requirements: Optional[bool] = None
    size_requirements_description: Optional[str] = None
    size_requirements_same_for_all: Optional[bool] = None
    size_requirements_difference_explanation: Optional[str] = None
    accepts_odd_lots: Optional[bool] = None
    accepts_mixed_lots: Optional[bool] = None
    mixed_lots_description: Optional[str] = None
    mixed_lots_same_for_all: Optional[bool] = None

    # Item 9 — Conditional orders / IOIs (oversized-field fallback)
    uses_indication_messages: Optional[bool] = None
    conditional_orders: Optional[str] = None
    conditional_orders_pdf_url: Optional[str] = None
    conditional_orders_same_for_all: Optional[bool] = None

    # Item 10 — Opening / closing / trading halts
    opening_reopening_details: Optional[str] = None
    opening_reopening_same_for_all: Optional[bool] = None
    unexecuted_orders_treatment: Optional[str] = None
    trading_hours_execution_differs: Optional[bool] = None
    pre_open_execution_differs: Optional[bool] = None

    # Item 11 — NMS stock matching (the core of dark-pool analysis)
    nms_stock_structure: Optional[str] = None
    nms_structure_same_for_all: Optional[bool] = None
    nms_matching_rules: Optional[str] = None
    nms_matching_rules_pdf_url: Optional[str] = None
    nms_matching_rules_same_for_all: Optional[bool] = None

    # Item 12 — Informal / formal arrangements with subscribers
    has_informal_arrangements: Optional[bool] = None

    # Item 13 — Segmentation / tiering of order flow
    has_segmentation: Optional[bool] = None
    segmentation_description: Optional[str] = None
    segmentation_description_pdf_url: Optional[str] = None
    segmentation_same_for_all: Optional[bool] = None
    segmentation_category_disclosed: Optional[bool] = None
    segmentation_disclosure_description: Optional[str] = None
    segmentation_disclosure_same_for_all: Optional[bool] = None
    customer_order_segmentation: Optional[bool] = None

    # Item 14 — Counter-party selection
    permits_counterparty_selection: Optional[bool] = None
    counterparty_selection_description: Optional[str] = None
    counterparty_selection_same_for_all: Optional[bool] = None

    # Item 15 — Display of trading interest
    uses_electronic_display_communication: Optional[bool] = None
    displays_subscriber_order_book: Optional[bool] = None
    display_description: Optional[str] = None
    display_same_for_all: Optional[bool] = None

    # Item 16 — Routing instructions
    routes_orders_outside_ats: Optional[bool] = None

    # Item 17 — Order / TI treatment differences
    has_treatment_differences: Optional[bool] = None
    treatment_same_for_all: Optional[bool] = None

    # Item 18 — Outside trading hours
    trades_outside_regular_hours: Optional[bool] = None

    # Item 19 — Fees (three sub-items)
    fees_direct: Optional[str] = None
    fees_bundled: Optional[str] = None
    fees_rebates: Optional[str] = None

    # Item 20 — Suspension procedures
    suspension_procedures: Optional[str] = None
    suspension_procedures_same_for_all: Optional[bool] = None

    # Item 21 — Trade reporting arrangements
    trade_reporting_arrangements: Optional[str] = None
    trade_reporting_same_for_all: Optional[bool] = None

    # Item 22 — Clearance and settlement
    clearance_settlement: Optional[str] = None
    clearance_settlement_same_for_all: Optional[bool] = None

    # Item 23 — Market data sources
    market_data_sources: Optional[str] = None
    market_data_same_for_all: Optional[bool] = None

    # Item 24 — Subscriber orders outside the ATS
    routes_subscriber_orders_outside: Optional[bool] = None

    # Item 25 — Fair Access threshold (regulatory trigger)
    exceeds_fair_access_threshold: Optional[bool] = None

    # Item 26 — Execution-statistics publication
    publishes_execution_stats: Optional[bool] = None
