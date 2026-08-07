"""ATS-N parser and top-level data objects.

Parses `primary_doc.xml` from ATS-N family filings (ATS-N, ATS-N/MA,
ATS-N/UA, ATS-N/CA, ATS-N-W) using lxml, mirroring the pattern in
`edgar/funds/nmfp3.py` and `edgar/funds/ncen.py`.
"""
from __future__ import annotations

import logging
from typing import Optional, Union

from lxml import etree
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from edgar.funds.reports import _strip_namespaces, _text
from edgar.richtools import repr_rich

from edgar.ats.models import (
    ATSAddress,
    ATSIdentifyingInfo,
    ATSNameRecord,
    ATSOperations,
    ATSOperatorActivities,
    FilerContact,
)

log = logging.getLogger(__name__)

__all__ = [
    "AlternativeTradingSystem",
    "AlternativeTradingSystemWithdrawal",
    "from_atsn_filing",
]


def _opt_flag(parent, tag) -> Optional[bool]:
    """Parse Y/N to Optional[bool]. Returns None when element is missing or blank."""
    text = _text(parent, tag)
    if text is None or text == "":
        return None
    return text.upper() == "Y"


def _gate(parent, flag_name) -> Optional[bool]:
    """Resolve a Y/N gate flag that may appear as either a flat element OR as an
    attribute on a container, at any descendant depth.

    SEC ATS-N XML uses both patterns in the same filing: when a flag is "Y" and
    prompts additional narrative, it appears as an attribute on the narrative
    container; when "N", it appears as a flat element with text. The attribute
    name and flat-element tag are identical (e.g. rbPart2Item1cAreThereArrangements).

    Gate flags for sub-items are nested inside their parent item's container,
    so this function searches all descendants rather than just direct children.
    """
    if parent is None:
        return None
    flat = parent.find(f".//{flag_name}")
    if flat is not None and flat.text is not None and flat.text.strip():
        return flat.text.strip().upper() == "Y"
    for el in parent.iter():
        if flag_name in el.attrib:
            val = el.get(flag_name)
            if val:
                return val.upper() == "Y"
    return None


def _desc_text(parent, tag) -> Optional[str]:
    """Find first descendant with tag and return its text, stripped.

    Needed because Part II free-text fields are sometimes nested inside
    a container keyed by the corresponding gate flag attribute.
    """
    if parent is None:
        return None
    found = parent.find(f".//{tag}")
    if found is not None and found.text:
        return found.text.strip()
    return None


def _parse_address(el) -> Optional[ATSAddress]:
    """Parse a primary/secondary site address block.

    After _strip_namespaces, children are plain-tagged: street1, street2,
    city, state, zip.
    """
    if el is None:
        return None
    addr = ATSAddress(
        street1=_text(el, "street1"),
        street2=_text(el, "street2"),
        city=_text(el, "city"),
        state_or_country=_text(el, "state"),
        zip_code=_text(el, "zip"),
    )
    # Treat entirely-empty address as None
    if not any([addr.street1, addr.street2, addr.city, addr.state_or_country, addr.zip_code]):
        return None
    return addr


class AlternativeTradingSystem:
    """ATS-N filing data object (initial and all amendment variants)."""

    def __init__(
        self,
        form_type: str,
        amended_accession_number: Optional[str],
        filer: FilerContact,
        amendment_statement: Optional[str],
        identifying_info: ATSIdentifyingInfo,
        operator_activities: ATSOperatorActivities,
        operations: ATSOperations,
    ):
        self.form_type = form_type
        self.amended_accession_number = amended_accession_number
        self.filer = filer
        self.amendment_statement = amendment_statement
        self.identifying_info = identifying_info
        self.operator_activities = operator_activities
        self.operations = operations
        self._filing = None

    # ---- Convenience properties ----
    @property
    def cik(self) -> str:
        return self.filer.cik

    @property
    def mpid(self) -> Optional[str]:
        return self.identifying_info.nms_stock_mpid or self.filer.mpid

    @property
    def ats_name(self) -> Optional[str]:
        return self.identifying_info.ats_commercial_name or self.filer.nms_stock_ats_name

    @property
    def operator_name(self) -> Optional[str]:
        return self.identifying_info.operator_legal_name

    @property
    def is_amendment(self) -> bool:
        return self.form_type in ("ATS-N/MA", "ATS-N/UA", "ATS-N/CA")

    @property
    def subscriber_types(self) -> list:
        return self.operations.subscriber_types

    @property
    def order_types(self) -> Optional[str]:
        return self.operations.order_types

    @property
    def fees(self) -> dict:
        return {
            "direct": self.operations.fees_direct,
            "bundled": self.operations.fees_bundled,
            "rebates": self.operations.fees_rebates,
        }

    # ---- Display ----
    def __rich__(self):
        return _render_atsn(self)

    def __repr__(self):
        return repr_rich(self.__rich__())

    def to_context(self, detail: str = "standard") -> str:
        """Compact, AI-friendly string representation.

        detail: 'minimal' (identity only), 'standard' (+ key Part III flags),
        'full' (+ truncated narratives).
        """
        lines = [
            f"{self.form_type} — {self.ats_name or '?'}",
            f"  Operator: {self.operator_name or '?'} (CIK {self.cik})",
            f"  MPID: {self.mpid or 'n/a'}",
        ]
        if self.is_amendment:
            lines.append(f"  Amends: {self.amended_accession_number or 'n/a'}")
        if detail == "minimal":
            return "\n".join(lines)

        ops = self.operations
        lines.append(f"  Subscriber types ({len(ops.subscriber_types)}): {', '.join(ops.subscriber_types) or 'n/a'}")
        lines.append(f"  Fair-access threshold exceeded: {_flag_str(ops.exceeds_fair_access_threshold)}")
        lines.append(f"  Publishes execution stats: {_flag_str(ops.publishes_execution_stats)}")
        lines.append(f"  Segmentation: {_flag_str(ops.has_segmentation)}")
        lines.append(f"  Order types (len): {len(ops.order_types or '')}")
        if detail == "standard":
            return "\n".join(lines)

        # full
        if ops.order_types:
            lines.append("")
            lines.append("ORDER TYPES (truncated):")
            lines.append(_truncate(ops.order_types, 600))
        if ops.fees_direct:
            lines.append("")
            lines.append("FEES (direct, truncated):")
            lines.append(_truncate(ops.fees_direct, 400))
        return "\n".join(lines)

    # ---- Parser entry points ----
    _OVERSIZED_PDF_MAP = {
        "ATS-N PART3 ITM.7A": "order_types_pdf_url",
        "ATS-N PART3 ITM.9A": "conditional_orders_pdf_url",
        "ATS-N PART3 ITM.11C": "nms_matching_rules_pdf_url",
        "ATS-N PART3 ITM.13A": "segmentation_description_pdf_url",
    }

    @classmethod
    def from_filing(cls, filing) -> Optional["AlternativeTradingSystem"]:
        """Parse an ATS-N family filing into an AlternativeTradingSystem."""
        xml = filing.xml()
        if not xml:
            return None
        try:
            obj = cls._parse_xml(xml)
        except etree.XMLSyntaxError as e:
            log.warning("ATS-N XML parse failed for %s: %s", filing.accession_no, e)
            return None
        if obj is None:
            return None
        obj._filing = filing
        obj._apply_oversized_pdfs(filing)
        return obj

    def _apply_oversized_pdfs(self, filing) -> None:
        """Surface PDF attachment URLs for Part III items whose narrative may
        overflow XML length limits (Items 7A, 9A, 11C, 13A).

        We always record the URL when the attachment exists — the PDF
        typically carries an extended/authoritative version of the
        corresponding XML text, not a replacement for a missing XML field.
        """
        for att in filing.attachments:
            doc_type = (att.document_type or "").upper().strip()
            field = self._OVERSIZED_PDF_MAP.get(doc_type)
            if field is not None:
                setattr(self.operations, field, att.url)

    @classmethod
    def _parse_xml(cls, xml: Union[str, bytes]) -> Optional["AlternativeTradingSystem"]:
        xml_bytes = xml.encode("utf-8") if isinstance(xml, str) else xml
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError:
            root = etree.fromstring(xml_bytes, parser=etree.XMLParser(recover=True))
        _strip_namespaces(root)

        if root.tag != "edgarSubmission":
            found = root.find(".//edgarSubmission")
            if found is not None:
                root = found

        header = root.find("headerData")
        form_type = _text(header, "submissionType") or ""
        amended_accession_number = _text(header, "accessionNumber")
        filer = cls._parse_filer(header)

        form_data = root.find("formData")
        if form_data is None:
            return None

        cover = form_data.find("cover")
        amendment_statement = _text(cover, "taStatementAboutAmendment") if cover is not None else None

        return cls(
            form_type=form_type,
            amended_accession_number=amended_accession_number,
            filer=filer,
            amendment_statement=amendment_statement,
            identifying_info=cls._parse_part_one(form_data),
            operator_activities=cls._parse_part_two(form_data),
            operations=cls._parse_part_three(form_data),
        )

    @staticmethod
    def _parse_filer(header) -> FilerContact:
        """Extract CIK + filer identity fields from headerData.

        Primary ATS-N filings typically carry only CIK here (identity lives
        in Part I). Withdrawals (ATS-N-W) include MPID, NMSStockATSName, and
        a contact block since there is no Part I. This method handles both.
        """
        if header is None:
            return FilerContact(cik="")
        filer_info = header.find("filerInfo")
        if filer_info is None:
            return FilerContact(cik="")

        cik = ""
        mpid = None
        nms_ats_name = None
        filer_el = filer_info.find("filer")
        if filer_el is not None:
            creds = filer_el.find("filerCredentials")
            if creds is not None:
                cik_text = _text(creds, "cik")
                if cik_text:
                    cik = cik_text.lstrip("0") or "0"
            mpid = _text(filer_el, "MPID")
            nms_ats_name = _text(filer_el, "NMSStockATSName")

        contact_el = filer_info.find("contact")
        contact_name = _text(contact_el, "contactName") if contact_el is not None else None
        contact_phone = _text(contact_el, "contactPhoneNumber") if contact_el is not None else None
        contact_email = _text(contact_el, "contactEmailAddress") if contact_el is not None else None

        return FilerContact(
            cik=cik,
            mpid=mpid,
            nms_stock_ats_name=nms_ats_name,
            contact_name=contact_name,
            contact_phone=contact_phone,
            contact_email=contact_email,
        )

    @staticmethod
    def _parse_part_one(form_data) -> ATSIdentifyingInfo:
        """Parse Part I — Identifying Information."""
        info = ATSIdentifyingInfo()
        if form_data is None:
            return info

        cover = form_data.find("cover")
        if cover is not None:
            info.ats_commercial_name = _text(cover, "txNMSStockATSName")
            info.supersedes_prior_form_ats = _opt_flag(cover, "rbOperatesPursuantToFormATS")

        part_one = form_data.find("partOne")
        if part_one is None:
            return info

        info.operator_legal_name = _text(part_one, "txPart1Item2ATSName")
        info.bd_file_number = _text(part_one, "txPart1Item4aBdFileNumber")
        info.bd_crd_number = _text(part_one, "txPart1Item4aBdCrdNumber")
        info.sro_name = _text(part_one, "txPart1Item5aNsaFullName")
        info.nms_stock_mpid = _text(part_one, "txtPart1Item5cNmsStockMPID")
        info.website = _text(part_one, "txtPart1Item6uwebsite")

        # Item 3 — ATS names (repeating). Name lives in attribute, not text.
        ats_names_el = part_one.find("atsNames")
        if ats_names_el is not None:
            for name_el in ats_names_el.findall("atsName"):
                name_val = name_el.get("txPart1Item3ATSName")
                if name_val:
                    info.ats_names.append(ATSNameRecord(ats_name=name_val))

        # Item 7 — Primary site
        primary_el = part_one.find("part1Item7PrimarySite")
        info.primary_site = _parse_address(primary_el)

        # Item 7 — Secondary sites (repeating container)
        secondaries = part_one.find("part1Item7SecondarySiteRecords")
        if secondaries is not None:
            for site_el in secondaries.findall("part1Item7SecondarySite"):
                addr = _parse_address(site_el)
                if addr is not None:
                    info.secondary_sites.append(addr)

        return info

    @staticmethod
    def _parse_part_two(form_data) -> ATSOperatorActivities:
        """Parse Part II — Broker-Dealer Operator Activities."""
        acts = ATSOperatorActivities()
        if form_data is None:
            return acts
        pt = form_data.find("partTwo")
        if pt is None:
            return acts

        # Item 1 — BD units entering orders
        acts.bd_units_permit_order_entry = _gate(pt, "rbPart2Item1aArePermittedToEnterInterest")
        acts.bd_units_description = _desc_text(pt, "taPart2Item1aUnitNamesEnterInterest")
        acts.bd_services_same_to_all = _gate(pt, "rbPart2Item1bAreSevicesSametoAllSubscribers")
        acts.bd_services_difference_explanation = _desc_text(pt, "taPart2Item2bExplainDiff")
        acts.bd_has_third_party_arrangements = _gate(pt, "rbPart2Item1cAreThereArrangements")
        acts.can_route_oat_interest = _gate(pt, "rbPart2Item1dCanOATInterestBeRouted")

        # Item 2 — Affiliates
        acts.affiliates_permit_order_entry = _gate(pt, "rbPart2Item2aAreAfflPermittedToEnterInterest")
        acts.affiliates_description = _desc_text(pt, "taPart2Item2aAfflThatEnterInterest")
        acts.affiliates_services_same_to_subscribers = _gate(pt, "rbPart2Item2bAreSevicestoAfflSametoSubscribers")
        acts.affiliates_have_third_party_arrangements = _gate(pt, "rbPart2Item2cAreThereArrangementsWithAffl")
        acts.can_route_oat_interest_via_affl = _gate(pt, "rbPart2Item2dCanOATIBeRoutedByAffl")

        # Item 3 — Subscriber opt-out
        acts.subscribers_can_opt_out_of_bd = _gate(pt, "rbPart2Item3aCanSubscrOptOutWithOATIOfBD")
        acts.subscriber_opt_out_bd_explanation = _desc_text(pt, "taPart2Item3aExplianOptOut")
        acts.subscribers_can_opt_out_of_affl = _gate(pt, "rbPart2Item3aCanSubscrOptOutWithOATIOfAffl")
        acts.subscriber_opt_out_affl_explanation = _desc_text(pt, "taPart2Item3bExplianOptOut")
        acts.opt_out_same_to_all = _gate(pt, "rbPart2Item3cAreOptOutSametoAllSubscribers")

        # Item 4 — Trading-center arrangements
        acts.has_trading_center_arrangements = _gate(pt, "rbPart2Item4aAreThereArrangementsBtwBDAndTC")
        acts.trading_center_arrangements = _desc_text(pt, "taPart2Item4aTDAndATSServices")
        acts.affl_has_trading_center_arrangements = _gate(pt, "rbPart2Item4bAreThereArrangementsBtwAfflAndTC")

        # Item 5 — Bundled products/services
        acts.offers_bundled_products = _gate(pt, "rbPart2Item5aDoesOfferProductsAndServices")
        acts.bundled_products_description = _desc_text(pt, "taPart2Item5aProductsAndServices")
        acts.bundled_services_same_to_all = _gate(pt, "rbPart2Item5bAreSevicesSametoAllSubscribersAndBD")
        acts.affl_offers_bundled_products = _gate(pt, "rbPart2Item5cDoesAfflOfferProductsAndServices")
        acts.affl_bundled_products_description = _desc_text(pt, "taPart2Item5cAfflProvidedProductsAndServices")
        acts.affl_bundled_services_same_to_all = _gate(pt, "rbPart2Item5dAreTCOfSevicesSametoAll")

        # Item 6 — Employees & service providers
        acts.employees_access_confidential = _gate(pt, "rbPart2Item6aDoesEmployeeAccessConfidentialInfo")
        acts.employee_services_description = _desc_text(pt, "taPart2Item6aUnitAfflEmployeeServices")
        acts.has_third_party_service_providers = _gate(pt, "rbPart2Item6bDoesAnyEntitySupportServices")
        acts.service_providers_description = _desc_text(pt, "taPart2Item6bServiceProvider")
        acts.service_provider_uses_ats_services = _gate(pt, "rbPart2Item6cDoesServiceProviderUseATSServices")

        # Item 7 — Confidentiality safeguards
        acts.safeguards_description = _desc_text(pt, "taPart2Item7aDescrOfSafeGaurdsAndProcedures")
        acts.subscriber_can_consent_to_disclosure = _gate(pt, "rbPart2Item7bCanSubscriberConsentToDisclosure")
        acts.roles_responsibilities_summary = _desc_text(pt, "taPart2Item7dSummaryOfRolesRespOfPersons")

        return acts

    @staticmethod
    def _parse_part_three(form_data) -> ATSOperations:
        """Parse Part III — Manner of Operations."""
        ops = ATSOperations()
        if form_data is None:
            return ops
        pt = form_data.find("partThree")
        if pt is None:
            return ops

        # Item 1 — Subscriber types (repeating)
        for el in pt.findall("taPart3Item1SubscriberType"):
            if el.text and el.text.strip():
                ops.subscriber_types.append(el.text.strip())

        # Item 2 — Access conditions
        ops.requires_registered_bd = _gate(pt, "rbPart3Item2aRegisteredBD")
        ops.has_other_access_conditions = _gate(pt, "rbPart3Item2bIsThereOtherConditions")
        ops.access_conditions_summary = _desc_text(pt, "taPart3Item2bSummaryOfCndtns")
        ops.access_conditions_same_for_all = _gate(pt, "rbPart3Item2cIsConditionsSameForAll")
        ops.requires_written_agreement = _gate(pt, "rbPart3Item2dIsThereWrittenAgreement")

        # Item 3 — Exclusion
        ops.can_exclude_subscribers = _gate(pt, "rbPart3Item3aIsExcludeSubscriber")
        ops.exclusion_conditions_summary = _desc_text(pt, "taPart3Item3aExcludngSumryDtls")
        ops.exclusion_conditions_same_for_all = _gate(pt, "rbPart3Item3bIsCondtnsSameForAll")

        # Item 4 — Hours
        ops.hours_of_operation = _desc_text(pt, "taPart3Item4aHrsOfOperation")
        ops.hours_same_for_all = _gate(pt, "rbPart3Item4bIsHrsOfOperationsame")

        # Item 5 — Order entry protocols
        ops.permits_order_trading_via_protocol = _gate(pt, "rbPart3Item5aIsPermitOrdrTradng")
        ops.protocol_description = _desc_text(pt, "taPart3Item5aProtocolused")
        ops.protocol_same_for_all = _gate(pt, "rbPart3Item5bIsProtclsameForAll")
        ops.has_other_connectivity_means = _gate(pt, "rbPart3Item5cIsAnyOtherMeans")
        ops.other_connectivity_description = _desc_text(pt, "taPart3Item5cOthrMeansDtls")
        ops.other_connectivity_same_for_all = _gate(pt, "rbPart3Item5dIsTnCSameForAll")

        # Item 6 — Co-location
        ops.offers_colocation_services = _gate(pt, "rbPart3Item6aIsCoLocRltdSrvcsOfrd")
        ops.colocation_description = _desc_text(pt, "taPart3Item6aCoLocRltdSrvcsDtls")
        ops.colocation_terms_same_for_all = _gate(pt, "rbPart3Item6bIsTNCsameForAll")
        ops.has_other_colocation_means = _gate(pt, "rbPart3Item6cIsAnyOtherMeans")
        ops.offers_reduced_speed_access = _gate(pt, "rbPart3Item6eIsAnyRducdSpOfCom")

        # Item 7 — Order types
        ops.order_types = _desc_text(pt, "taPart3Item7AOrdrTypExplain")
        ops.order_types_same_for_all = _gate(pt, "rbPart3Item7bIsTnCSameForAll")

        # Item 8 — Order sizes
        ops.has_size_requirements = _gate(pt, "rbPart3Item8aIsMinOrMaxSizeReqd")
        ops.size_requirements_description = _desc_text(pt, "taPart3Item8aOtiSizeReqrmns")
        ops.size_requirements_same_for_all = _gate(pt, "rbPart3Item8bIsReqProcSameForAll")
        ops.size_requirements_difference_explanation = _desc_text(pt, "taPart3Item8bDiffrncsInOtiReqrmnts")
        ops.accepts_odd_lots = _gate(pt, "rbPart3Item8cIsOddLotsAcptdExecutd")
        ops.accepts_mixed_lots = _gate(pt, "rbPart3Item8eIsMixLotOrdrsAcptdExecutd")
        ops.mixed_lots_description = _desc_text(pt, "taPart3Item8eMixltOrdrReqsProcDtls")
        ops.mixed_lots_same_for_all = _gate(pt, "rbPart3Item8fIsRecProcSameForAll")

        # Item 9 — Conditional orders / IOIs
        ops.uses_indication_messages = _gate(pt, "rbPart3Item9aIsAnyMsgToIndicTI")
        ops.conditional_orders = _desc_text(pt, "taPart3Item9aMsgUsgDtls")
        ops.conditional_orders_same_for_all = _gate(pt, "rbPart3Item9bIsIndIntrstSameForAll")

        # Item 10 — Opening / closing
        ops.opening_reopening_details = _desc_text(pt, "taPart3Item10aOpenReOpenDtls")
        ops.opening_reopening_same_for_all = _gate(pt, "rbPart3Item10bIsOpnReopnSameForAll")
        ops.unexecuted_orders_treatment = _desc_text(pt, "taPart3Item10cUnexeOrdrTIDtls")
        ops.trading_hours_execution_differs = _gate(pt, "rbPart3Item10dIsAnyDifBtwnExeProcTrdHrs")
        ops.pre_open_execution_differs = _gate(pt, "rbPart3Item10eIsAnyDifBtwnPreOpExecFlwngStpg")

        # Item 11 — NMS stock matching
        ops.nms_stock_structure = _desc_text(pt, "taPart3Item11aStrucOfNmsStk")
        ops.nms_structure_same_for_all = _gate(pt, "rbPart3Item11bIsMeansFeciltsSameForAll")
        ops.nms_matching_rules = _desc_text(pt, "taPart3Item11cRulsProcsOfNmsStk")
        ops.nms_matching_rules_same_for_all = _gate(pt, "rbPart3Item11dIsProcsRulsSameForAll")

        # Item 12 — Informal arrangements
        ops.has_informal_arrangements = _gate(pt, "rbPart3Item12aIsAnyFrmlInfrmlArngmnts")

        # Item 13 — Segmentation
        ops.has_segmentation = _gate(pt, "rbPart3Item13aIsOrdrTiSegmntd")
        ops.segmentation_description = _desc_text(pt, "taPart3Item13aSegProcdurDtls")
        ops.segmentation_same_for_all = _gate(pt, "rbPart3Item13bIsSegmntatnSameForAll")
        ops.segmentation_category_disclosed = _gate(pt, "rbPart3Item13dIsSegCatgDisclosd")
        ops.segmentation_disclosure_description = _desc_text(pt, "taPart3Item13dDsclosrContntDtls")
        ops.segmentation_disclosure_same_for_all = _gate(pt, "rbPart3Item13eIsDsclosrSameForAll")
        ops.customer_order_segmentation = _gate(pt, "rbPart3Item13cIsCustmrOrdr")

        # Item 14 — Counter-party selection
        ops.permits_counterparty_selection = _gate(pt, "rbPart3Item14aIsDsgToIntrctOrNot")
        ops.counterparty_selection_description = _desc_text(pt, "taPart3Item14aCntrPrtyDtls")
        ops.counterparty_selection_same_for_all = _gate(pt, "rbPart3Item14bIsSelectnSameForAll")

        # Item 15 — Display
        ops.uses_electronic_display_communication = _gate(pt, "rbPart3Item15aIsElectrncCommu")
        ops.displays_subscriber_order_book = _gate(pt, "rbPart3Item15bIsSubScrbOrdBnd")
        ops.display_description = _desc_text(pt, "taPart3Item15bSubscrBndDtls")
        ops.display_same_for_all = _gate(pt, "rbPart3Item15cIsDsplyProcSameForAll")

        # Item 16 — Routing
        ops.routes_orders_outside_ats = _gate(pt, "rbPart3Item16aIsInstRoutd")

        # Item 17 — Treatment differences
        ops.has_treatment_differences = _gate(pt, "rbPart3Item17aIsDiffBtwnOrdTITrtmnt")
        ops.treatment_same_for_all = _gate(pt, "rbPart3Item17bIsTrtmntSameForAll")

        # Item 18 — Outside trading hours
        ops.trades_outside_regular_hours = _gate(pt, "rbPart3Item18aIsOutsdeTrdingHrs")

        # Item 19 — Fees
        ops.fees_direct = _desc_text(pt, "taPart3Item19aSrvcUsgFees")
        ops.fees_bundled = _desc_text(pt, "taPart3Item19bBundldSrvcUsgFees")
        ops.fees_rebates = _desc_text(pt, "taPart3Item19cRbtDiscOfFees")

        # Item 20 — Suspension procedures
        ops.suspension_procedures = _desc_text(pt, "taPart3Item20aSuspndProcdur")
        ops.suspension_procedures_same_for_all = _gate(pt, "rbPart3Item20bIsSuspndProcdurSameFrAll")

        # Item 21 — Trade reporting
        ops.trade_reporting_arrangements = _desc_text(pt, "taPart3Item21aMtrlArngmntDtls")
        ops.trade_reporting_same_for_all = _gate(pt, "rbPart3Item21bIsMtrlArngmtSameFrAll")

        # Item 22 — Clearance / settlement
        ops.clearance_settlement = _desc_text(pt, "taPart3Item22aMtrlArngmntDtls")
        ops.clearance_settlement_same_for_all = _gate(pt, "rbPart3Item22bIsMtrlArngmtSameFrAll")

        # Item 23 — Market data sources
        ops.market_data_sources = _desc_text(pt, "taPart3Item23aMrktDatSrc")
        ops.market_data_same_for_all = _gate(pt, "rbPart3Item23bIsSrcSameFrAll")

        # Item 24 — Subscriber orders outside
        ops.routes_subscriber_orders_outside = _gate(pt, "rbPart3Item24aIsSubScrbrOrdr")

        # Item 25 — Fair Access threshold
        ops.exceeds_fair_access_threshold = _gate(pt, "rbPart3Item25aIsAvgDlyTradinVolExcd")

        # Item 26 — Execution statistics publication
        ops.publishes_execution_stats = _gate(pt, "rbPart3Item26IsOrdrFloExecStatsPublshd")

        return ops


class AlternativeTradingSystemWithdrawal:
    """ATS-N-W withdrawal filing — lightweight stub, no Parts I-III data.

    Withdrawals use the `atsncw` namespace and carry an empty `formData`
    element. Identity (MPID, ATS name, contact info) lives in headerData.
    """

    def __init__(
        self,
        form_type: str,
        withdrawn_accession_number: Optional[str],
        filer: FilerContact,
        withdrawal_statement: Optional[str] = None,
    ):
        self.form_type = form_type
        self.withdrawn_accession_number = withdrawn_accession_number
        self.filer = filer
        self.withdrawal_statement = withdrawal_statement
        self._filing = None

    @property
    def cik(self) -> str:
        return self.filer.cik

    @property
    def mpid(self) -> Optional[str]:
        return self.filer.mpid

    @property
    def ats_name(self) -> Optional[str]:
        return self.filer.nms_stock_ats_name

    @classmethod
    def from_filing(cls, filing) -> Optional["AlternativeTradingSystemWithdrawal"]:
        """Parse an ATS-N-W withdrawal filing."""
        xml = filing.xml()
        if not xml:
            return None
        xml_bytes = xml.encode("utf-8") if isinstance(xml, str) else xml
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError:
            try:
                root = etree.fromstring(xml_bytes, parser=etree.XMLParser(recover=True))
            except etree.XMLSyntaxError as e:
                log.warning("ATS-N-W XML parse failed for %s: %s", filing.accession_no, e)
                return None
        _strip_namespaces(root)

        if root.tag != "edgarSubmission":
            found = root.find(".//edgarSubmission")
            if found is not None:
                root = found

        header = root.find("headerData")
        form_type = _text(header, "submissionType") or "ATS-N-W"
        withdrawn = _text(header, "accessionNumber")
        filer = AlternativeTradingSystem._parse_filer(header)

        # Withdrawals occasionally carry a cover statement; most are empty.
        withdrawal_statement = None
        form_data = root.find("formData")
        if form_data is not None:
            cover = form_data.find("cover")
            if cover is not None:
                withdrawal_statement = _text(cover, "taStatementAboutAmendment")

        obj = cls(
            form_type=form_type,
            withdrawn_accession_number=withdrawn,
            filer=filer,
            withdrawal_statement=withdrawal_statement,
        )
        obj._filing = filing
        return obj

    def __rich__(self):
        return _render_withdrawal(self)

    def __repr__(self):
        return repr_rich(self.__rich__())


def from_atsn_filing(
    filing,
) -> Optional[Union[AlternativeTradingSystem, AlternativeTradingSystemWithdrawal]]:
    """Dispatch helper — routes ATS-N-W to the withdrawal stub, everything else
    to the full AlternativeTradingSystem parser."""
    if filing.form == "ATS-N-W":
        return AlternativeTradingSystemWithdrawal.from_filing(filing)
    return AlternativeTradingSystem.from_filing(filing)


# ---------------------------------------------------------------------------
# Rich rendering
# ---------------------------------------------------------------------------

def _flag_str(val: Optional[bool]) -> str:
    if val is True:
        return "Yes"
    if val is False:
        return "No"
    return "—"


def _truncate(s: Optional[str], n: int) -> str:
    if not s:
        return ""
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "…"


def _render_atsn(ats: "AlternativeTradingSystem") -> Panel:
    """Render an AlternativeTradingSystem as a Rich Panel."""
    ii = ats.identifying_info
    ops = ats.operations

    # Identity table
    id_tbl = Table(box=box.SIMPLE, show_header=False, padding=(0, 1), expand=False)
    id_tbl.add_column(style="dim", no_wrap=True)
    id_tbl.add_column()
    id_tbl.add_row("Form", ats.form_type)
    id_tbl.add_row("CIK", ats.cik)
    id_tbl.add_row("MPID", ats.mpid or "—")
    id_tbl.add_row("ATS Name", ats.ats_name or "—")
    id_tbl.add_row("Operator", ats.operator_name or "—")
    if ii.bd_file_number:
        id_tbl.add_row("BD File #", ii.bd_file_number)
    if ii.bd_crd_number:
        id_tbl.add_row("CRD #", ii.bd_crd_number)
    if ii.sro_name:
        id_tbl.add_row("SRO", ii.sro_name)
    if ii.website:
        id_tbl.add_row("Website", ii.website)
    if ii.primary_site is not None and ii.primary_site.city:
        loc = ii.primary_site.city
        if ii.primary_site.state_or_country:
            loc += f", {ii.primary_site.state_or_country}"
        id_tbl.add_row("Primary Site", loc)
    if ats.is_amendment and ats.amended_accession_number:
        id_tbl.add_row("Amends", ats.amended_accession_number)

    blocks = [id_tbl]

    # Subscriber types
    if ops.subscriber_types:
        types_tbl = Table(
            title=f"Subscriber Types ({len(ops.subscriber_types)})",
            title_style="bold",
            box=box.SIMPLE,
            show_header=False,
            padding=(0, 1),
        )
        types_tbl.add_column()
        types_tbl.add_column()
        # Two columns
        items = list(ops.subscriber_types)
        mid = (len(items) + 1) // 2
        left, right = items[:mid], items[mid:]
        for i in range(max(len(left), len(right))):
            l = left[i] if i < len(left) else ""
            r = right[i] if i < len(right) else ""
            types_tbl.add_row(l, r)
        blocks.append(types_tbl)

    # Part III summary
    ops_tbl = Table(box=box.SIMPLE, show_header=False, padding=(0, 1), title="Operations", title_style="bold")
    ops_tbl.add_column(style="dim", no_wrap=True)
    ops_tbl.add_column()
    if ops.hours_of_operation:
        ops_tbl.add_row("Hours", _truncate(ops.hours_of_operation, 120))
    order_types_line = _truncate(ops.order_types or "", 160)
    if ops.order_types_pdf_url:
        order_types_line = (order_types_line + " [see PDF]").strip()
    if order_types_line:
        ops_tbl.add_row("Order Types", order_types_line)
    if ops.nms_matching_rules:
        matching = _truncate(ops.nms_matching_rules, 160)
        if ops.nms_matching_rules_pdf_url:
            matching = (matching + " [see PDF]").strip()
        ops_tbl.add_row("Matching Rules", matching)
    if ops.fees_direct:
        ops_tbl.add_row("Fees (direct)", _truncate(ops.fees_direct, 120))
    ops_tbl.add_row("Segmentation", _flag_str(ops.has_segmentation))
    ops_tbl.add_row("Counter-party Selection", _flag_str(ops.permits_counterparty_selection))
    ops_tbl.add_row("Fair-Access Exceeded", _flag_str(ops.exceeds_fair_access_threshold))
    ops_tbl.add_row("Publishes Stats", _flag_str(ops.publishes_execution_stats))
    blocks.append(ops_tbl)

    title = ats.ats_name or ats.operator_name or ats.form_type
    subtitle_parts = [ats.form_type]
    if ats._filing is not None and getattr(ats._filing, "filing_date", None):
        subtitle_parts.append(str(ats._filing.filing_date))
    return Panel(
        Group(*blocks),
        title=f"[bold]{title}[/bold]",
        subtitle=" · ".join(subtitle_parts),
        border_style="bright_blue",
    )


def _render_withdrawal(w: "AlternativeTradingSystemWithdrawal") -> Panel:
    """Render an ATS-N-W as a Rich Panel."""
    tbl = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    tbl.add_column(style="dim", no_wrap=True)
    tbl.add_column()
    tbl.add_row("Form", w.form_type)
    tbl.add_row("CIK", w.cik)
    tbl.add_row("MPID", w.mpid or "—")
    tbl.add_row("ATS Name", w.ats_name or "—")
    if w.withdrawn_accession_number:
        tbl.add_row("Withdraws", w.withdrawn_accession_number)
    if w.filer.contact_name:
        tbl.add_row("Contact", w.filer.contact_name)
    if w.filer.contact_email:
        tbl.add_row("Email", w.filer.contact_email)
    if w.withdrawal_statement:
        tbl.add_row("Statement", _truncate(w.withdrawal_statement, 240))

    title = w.ats_name or f"CIK {w.cik}"
    subtitle_parts = ["ATS-N-W (withdrawal)"]
    if w._filing is not None and getattr(w._filing, "filing_date", None):
        subtitle_parts.append(str(w._filing.filing_date))
    return Panel(
        tbl,
        title=f"[bold]{title}[/bold]",
        subtitle=" · ".join(subtitle_parts),
        border_style="yellow",
    )
