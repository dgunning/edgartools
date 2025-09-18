import io
import logging
from pathlib import Path
from typing import Any, Dict, Generator, Optional

from lxml import etree as ET

from .data import (
    ClassInfo,
    IncludedManager,
    PrimaryDoc,
    ProxyTable,
    ProxyVoteTable,
    ReportSeriesClassInfo,
    SeriesReport,
    VoteCategory,
    VoteRecord,
)

log = logging.getLogger(__name__)


class BaseExtractor:
    """Base class for XML extractors."""

    def __init__(self, xml_bytes: bytes):
        """Initialize the extractor with raw XML bytes and parse the root element."""
        self.xml_bytes = xml_bytes
        try:
            # Use a recovering parser for robustness against minor XML issues.
            parser = ET.XMLParser(recover=True)
            self.root: Optional[ET._Element] = ET.fromstring(xml_bytes, parser=parser)
            if self.root is None:
                # This might occur if the XML is severely malformed beyond recovery.
                raise ET.ParseError(
                    "Failed to parse XML: root element is None even after recovery."
                )
        except ET.ParseError as e:
            raise ValueError(f"Error parsing XML bytes during initial check: {e}") from e

    @classmethod
    def from_file(cls, xml_file_path: Path) -> "BaseExtractor":
        """Factory method to create an extractor instance from an XML file path."""
        if not xml_file_path.exists():
            raise FileNotFoundError(f"XML file not found: {xml_file_path}")
        xml_bytes = xml_file_path.read_bytes()
        return cls(xml_bytes)

    def extract(self) -> Any:
        """Main extraction method to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement the extract method.")

    def _get_optional_text(
        self,
        element: Optional[ET._Element],
        xpath: str,
        namespaces: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Safely get text from an element, returning None if not found or empty."""
        if element is None:
            return None
        # Ensure namespaces is not None if used; provide an empty dict as default for find if None.
        ns = namespaces if namespaces is not None else {}
        found_element = element.find(xpath, namespaces=ns)
        if found_element is not None and found_element.text:
            return found_element.text.strip()
        return None

    def _get_required_text(
        self,
        element: ET._Element,
        xpath: str,
        namespaces: Optional[Dict[str, str]] = None,
    ) -> str:
        """Get text from an element, raising ValueError if not found or empty."""
        text = self._get_optional_text(element, xpath, namespaces)
        if text is None:
            element_str = ET.tostring(element, pretty_print=True).decode()
            raise ValueError(
                f"Required text not found for xpath: {xpath} in element: {element_str}"
            )
        return text

    def _get_optional_float(
        self,
        element: Optional[ET._Element],
        xpath: str,
        namespaces: Optional[Dict[str, str]] = None,
    ) -> Optional[float]:
        """Safely get float from an element, returning None if not found or not a valid float."""
        text = self._get_optional_text(element, xpath, namespaces)
        if text is None:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _get_required_float(
        self,
        element: ET._Element,
        xpath: str,
        namespaces: Optional[Dict[str, str]] = None,
    ) -> float:
        """Get float from an element, raising ValueError if not found or not a valid float."""
        val = self._get_optional_float(element, xpath, namespaces)
        if val is None:
            element_str = ET.tostring(element, pretty_print=True).decode()
            raise ValueError(
                f"Required float not found or invalid for xpath: {xpath} in element: {element_str}"
            )
        return val


# Namespaces for different filing formats
PRIMARY_DOC_NAMESPACES: Dict[str, str] = {
    "npx": "http://www.sec.gov/edgar/npx",
    "com": "http://www.sec.gov/edgar/common",
}


class PrimaryDocExtractor(BaseExtractor):
    """
    Extracts data from a primary_doc.xml string into a PrimaryDoc dataclass.
    Handles different XML formats including standard N-PX and amendment filings.
    """

    def __init__(self, xml_bytes: bytes):
        """Initialize the extractor with raw XML *bytes*."""
        super().__init__(xml_bytes)
        self.doc_prefix = "npx"

    def _get_submission_type(self) -> Optional[str]:
        """Extract the submission_type from the XML to determine filing type."""
        npx_prefix = "npx"
        path = f"{npx_prefix}:headerData/{npx_prefix}:submissionType"
        return self._get_optional_text(self.root, path, PRIMARY_DOC_NAMESPACES)

    def extract(self) -> PrimaryDoc:
        """
        Parses the XML and populates the PrimaryDoc dataclass.
        Handles both standard N-PX filings and amendment filings with different structures.
        """
        if self.root is None:
            raise ValueError("XML root not parsed. Cannot extract.")

        prefix = self.doc_prefix
        submission_type = self._get_submission_type()
        is_amendment_submission = "/A" in submission_type if submission_type else False

        header_data = self.root.find(f"{prefix}:headerData", PRIMARY_DOC_NAMESPACES)
        if header_data is None:
            raise ValueError("Required <headerData> element not found in XML.")

        form_data = self.root.find(f"{prefix}:formData", PRIMARY_DOC_NAMESPACES)
        if form_data is None:
            raise ValueError("Required <formData> element not found in XML.")

        cover_page = form_data.find(f"{prefix}:coverPage", PRIMARY_DOC_NAMESPACES)
        if cover_page is None:
            raise ValueError(
                f"Required <coverPage> element not found in XML using prefix {prefix}."
            )

        reporting_person = cover_page.find(
            f"{prefix}:reportingPerson", PRIMARY_DOC_NAMESPACES
        )
        if reporting_person is None:
            raise ValueError(
                "Required <reportingPerson> element not found in <coverPage>."
            )

        reporting_person_address = reporting_person.find(
            f"{prefix}:address", PRIMARY_DOC_NAMESPACES
        )
        if reporting_person_address is None:
            raise ValueError(
                "Required <address> element not found in <reportingPerson>."
            )

        agent_for_service = cover_page.find(
            f"{prefix}:agentForService", PRIMARY_DOC_NAMESPACES
        )
        agent_for_service_address = (
            agent_for_service.find(f"{prefix}:address", PRIMARY_DOC_NAMESPACES)
            if agent_for_service is not None
            else None
        )

        signature_page = form_data.find(
            f"{prefix}:signaturePage", PRIMARY_DOC_NAMESPACES
        )
        if signature_page is None:
            raise ValueError(
                f"Required <signaturePage> element not found in XML using prefix {prefix}."
            )

        summary_page = form_data.find(f"{prefix}:summaryPage", PRIMARY_DOC_NAMESPACES)
        series_page = form_data.find(f"{prefix}:seriesPage", PRIMARY_DOC_NAMESPACES)
        report_info = cover_page.find(f"{prefix}:reportInfo", PRIMARY_DOC_NAMESPACES)
        explanatory_info = cover_page.find(
            f"{prefix}:explanatoryInformation", PRIMARY_DOC_NAMESPACES
        )
        amendment_info = cover_page.find(
            f"{prefix}:amendmentInfo", PRIMARY_DOC_NAMESPACES
        )
        contact = header_data.find(f"{prefix}:contact", PRIMARY_DOC_NAMESPACES)

        included_managers = []
        if summary_page is not None:
            other_managers_section = summary_page.find(
                f"{prefix}:otherManagers2", PRIMARY_DOC_NAMESPACES
            )
            if other_managers_section is not None:
                # Corrected XPath to use :manager as per original logic for the parent element
                for manager_elem in other_managers_section.findall(
                    f"{prefix}:investmentManagers", PRIMARY_DOC_NAMESPACES
                ):
                    manager = IncludedManager(
                        # Assuming these sub-elements (serialNo, etc.) exist under each 'manager' element
                        # and align with the IncludedManager dataclass fields.
                        serial_no=self._get_required_text(
                            manager_elem, f"{prefix}:serialNo", PRIMARY_DOC_NAMESPACES
                        ),
                        form13f_file_number=self._get_optional_text(
                            manager_elem,
                            f"{prefix}:form13FFileNumber",
                            PRIMARY_DOC_NAMESPACES,
                        ),
                        name=self._get_required_text(
                            manager_elem, f"{prefix}:name", PRIMARY_DOC_NAMESPACES
                        ),
                        sec_file_number=self._get_optional_text(
                            manager_elem,
                            f"{prefix}:secFileNumber",
                            PRIMARY_DOC_NAMESPACES,
                        ),
                    )
                    included_managers.append(manager)

        report_series_class_infos = []
        series_class_section = header_data.find(
            f"{prefix}:seriesClass", PRIMARY_DOC_NAMESPACES
        )
        if series_class_section is not None:
            report_series_class = series_class_section.find(
                f"{prefix}:reportSeriesClass", PRIMARY_DOC_NAMESPACES
            )
            if report_series_class is not None:
                for rpt_series_class_info_elem in report_series_class.findall(
                    f"{prefix}:rptSeriesClassInfo", PRIMARY_DOC_NAMESPACES
                ):
                    series_id = self._get_required_text(
                        rpt_series_class_info_elem,
                        f"{prefix}:seriesId",
                        PRIMARY_DOC_NAMESPACES,
                    )
                    class_infos = []
                    for class_info_elem in rpt_series_class_info_elem.findall(
                        f"{prefix}:classInfo", PRIMARY_DOC_NAMESPACES
                    ):
                        class_id = self._get_required_text(
                            class_info_elem, f"{prefix}:classId", PRIMARY_DOC_NAMESPACES
                        )
                        class_infos.append(ClassInfo(class_id=class_id))
                    report_series_class_infos.append(
                        ReportSeriesClassInfo(
                            series_id=series_id, class_infos=class_infos
                        )
                    )

        series_reports = []
        if series_page is not None:
            series_details = series_page.find(
                f"{prefix}:seriesDetails", PRIMARY_DOC_NAMESPACES
            )
            if series_details is not None:
                for series_report_elem in series_details.findall(
                    f"{prefix}:seriesReports", PRIMARY_DOC_NAMESPACES
                ):
                    series_reports.append(
                        SeriesReport(
                            id_of_series=self._get_required_text(
                                series_report_elem,
                                f"{prefix}:idOfSeries",
                                PRIMARY_DOC_NAMESPACES,
                            ),
                            name_of_series=self._get_optional_text(
                                series_report_elem,
                                f"{prefix}:nameOfSeries",
                                PRIMARY_DOC_NAMESPACES,
                            ),
                            lei_of_series=self._get_optional_text(
                                series_report_elem,
                                f"{prefix}:leiOfSeries",
                                PRIMARY_DOC_NAMESPACES,
                            ),
                        )
                    )

        return PrimaryDoc(
            cik=self._get_required_text(
                header_data,
                f"{prefix}:filerInfo/{prefix}:filer/{prefix}:issuerCredentials/{prefix}:cik",
                PRIMARY_DOC_NAMESPACES,
            ),
            submission_type=submission_type or "",
            period_of_report=self._get_required_text(
                header_data,
                f"{prefix}:filerInfo/{prefix}:periodOfReport",
                PRIMARY_DOC_NAMESPACES,
            ),
            fund_name=self._get_required_text(
                reporting_person, f"{prefix}:name", PRIMARY_DOC_NAMESPACES
            ),
            phone_number=self._get_optional_text(
                reporting_person, f"{prefix}:phoneNumber", PRIMARY_DOC_NAMESPACES
            ),
            street1=self._get_required_text(
                reporting_person_address, "com:street1", PRIMARY_DOC_NAMESPACES
            ),
            street2=self._get_optional_text(
                reporting_person_address, "com:street2", PRIMARY_DOC_NAMESPACES
            ),
            city=self._get_required_text(
                reporting_person_address, "com:city", PRIMARY_DOC_NAMESPACES
            ),
            state=self._get_required_text(
                reporting_person_address, "com:stateOrCountry", PRIMARY_DOC_NAMESPACES
            ),
            zip_code=self._get_required_text(
                reporting_person_address, "com:zipCode", PRIMARY_DOC_NAMESPACES
            ),
            crd_number=self._get_optional_text(
                cover_page, f"{prefix}:reportingCrdNumber", PRIMARY_DOC_NAMESPACES
            )
            or self._get_optional_text(
                cover_page, f"{prefix}:crdNumber", PRIMARY_DOC_NAMESPACES
            ),
            filer_sec_file_number=self._get_optional_text(
                cover_page, f"{prefix}:reportingSecFileNumber", PRIMARY_DOC_NAMESPACES
            )
            or self._get_optional_text(
                cover_page, f"{prefix}:filerSecFileNumber", PRIMARY_DOC_NAMESPACES
            )
            or self._get_optional_text(
                header_data,
                f"{prefix}:filerInfo/{prefix}:filer/{prefix}:fileNumber",
                PRIMARY_DOC_NAMESPACES,
            ),
            lei_number=self._get_optional_text(
                cover_page, f"{prefix}:lei", PRIMARY_DOC_NAMESPACES
            )
            or self._get_optional_text(
                cover_page, f"{prefix}:leiNumber", PRIMARY_DOC_NAMESPACES
            ),
            report_calendar_year=self._get_required_text(
                cover_page, f"{prefix}:reportCalendarYear", PRIMARY_DOC_NAMESPACES
            ),
            report_type=(
                self._get_required_text(
                    report_info, f"{prefix}:reportType", PRIMARY_DOC_NAMESPACES
                )
                if report_info is not None
                else None
            ),
            confidential_treatment=(
                self._get_optional_text(
                    report_info,
                    f"{prefix}:confidentialTreatment",
                    PRIMARY_DOC_NAMESPACES,
                )
                if report_info is not None
                else None
            ),
            notice_explanation=(
                self._get_optional_text(
                    explanatory_info,
                    f"{prefix}:noticeExplanation",
                    PRIMARY_DOC_NAMESPACES,
                )
                if explanatory_info is not None
                else None
            ),
            npx_file_number=self._get_optional_text(
                cover_page, f"{prefix}:fileNumber", PRIMARY_DOC_NAMESPACES
            ),
            explanatory_choice=(
                self._get_optional_text(
                    explanatory_info,
                    f"{prefix}:explanatoryChoice",
                    PRIMARY_DOC_NAMESPACES,
                )
                if explanatory_info is not None
                else None
            ),
            other_included_managers_count=(
                self._get_optional_text(
                    summary_page,
                    f"{prefix}:otherIncludedManagersCount",
                    PRIMARY_DOC_NAMESPACES,
                )
                if summary_page is not None
                else "0"
            ),
            signer_name=self._get_required_text(
                signature_page, f"{prefix}:txSignature", PRIMARY_DOC_NAMESPACES
            ),
            signer_title=self._get_required_text(
                signature_page, f"{prefix}:txTitle", PRIMARY_DOC_NAMESPACES
            ),
            signature_date=self._get_required_text(
                signature_page, f"{prefix}:txAsOfDate", PRIMARY_DOC_NAMESPACES
            ),
            tx_printed_signature=self._get_optional_text(
                signature_page, f"{prefix}:txPrintedSignature", PRIMARY_DOC_NAMESPACES
            ),
            agent_for_service_name=(
                self._get_optional_text(
                    agent_for_service, f"{prefix}:name", PRIMARY_DOC_NAMESPACES
                )
                if agent_for_service is not None
                else None
            ),
            agent_for_service_address_street1=(
                self._get_optional_text(
                    agent_for_service_address, "com:street1", PRIMARY_DOC_NAMESPACES
                )
                if agent_for_service_address is not None
                else None
            ),
            agent_for_service_address_street2=(
                self._get_optional_text(
                    agent_for_service_address, "com:street2", PRIMARY_DOC_NAMESPACES
                )
                if agent_for_service_address is not None
                else None
            ),
            agent_for_service_address_city=(
                self._get_optional_text(
                    agent_for_service_address, "com:city", PRIMARY_DOC_NAMESPACES
                )
                if agent_for_service_address is not None
                else None
            ),
            agent_for_service_address_state_country=(
                self._get_optional_text(
                    agent_for_service_address,
                    "com:stateOrCountry",
                    PRIMARY_DOC_NAMESPACES,
                )
                if agent_for_service_address is not None
                else None
            ),
            agent_for_service_address_zip_code=(
                self._get_optional_text(
                    agent_for_service_address, "com:zipCode", PRIMARY_DOC_NAMESPACES
                )
                if agent_for_service_address is not None
                else None
            ),
            is_amendment=(
                is_amendment_submission if submission_type is not None else None
            ),
            amendment_no=(
                self._get_optional_text(
                    amendment_info, f"{prefix}:amendmentNo", PRIMARY_DOC_NAMESPACES
                )
                if amendment_info is not None
                else None
            ),
            amendment_type=(
                self._get_optional_text(
                    amendment_info, f"{prefix}:amendmentType", PRIMARY_DOC_NAMESPACES
                )
                if amendment_info is not None
                else None
            ),
            conf_denied_expired=(
                self._get_optional_text(
                    amendment_info,
                    f"{prefix}:confDeniedExpired",
                    PRIMARY_DOC_NAMESPACES,
                )
                if amendment_info is not None
                else None
            ),
            de_novo_request_choice=self._get_optional_text(
                header_data,
                f"{prefix}:filerInfo/{prefix}:deNovoRequestChoice",
                PRIMARY_DOC_NAMESPACES,
            ),
            year_or_quarter=self._get_optional_text(
                cover_page, f"{prefix}:yearOrQuarter", PRIMARY_DOC_NAMESPACES
            ),
            included_managers=included_managers,
            registrant_type=self._get_optional_text(
                header_data,
                f"{prefix}:filerInfo/{prefix}:registrantType",
                PRIMARY_DOC_NAMESPACES,
            ),
            live_test_flag=self._get_optional_text(
                header_data,
                f"{prefix}:filerInfo/{prefix}:liveTestFlag",
                PRIMARY_DOC_NAMESPACES,
            ),
            ccc=self._get_optional_text(
                header_data,
                f"{prefix}:filerInfo/{prefix}:filer/{prefix}:issuerCredentials/{prefix}:ccc",
                PRIMARY_DOC_NAMESPACES,
            ),
            contact_name=(
                self._get_optional_text(
                    contact, f"{prefix}:name", PRIMARY_DOC_NAMESPACES
                )
                if contact is not None
                else None
            ),
            contact_phone_number=(
                self._get_optional_text(
                    contact, f"{prefix}:phoneNumber", PRIMARY_DOC_NAMESPACES
                )
                if contact is not None
                else None
            ),
            contact_email_address=(
                self._get_optional_text(
                    contact, f"{prefix}:emailAddress", PRIMARY_DOC_NAMESPACES
                )
                if contact is not None
                else None
            ),
            override_internet_flag=self._get_optional_text(
                header_data, f"{prefix}:overrideInternetFlag", PRIMARY_DOC_NAMESPACES
            ),
            confirming_copy_flag=self._get_optional_text(
                header_data, f"{prefix}:confirmingCopyFlag", PRIMARY_DOC_NAMESPACES
            ),
            investment_company_type=self._get_optional_text(
                header_data,
                f"{prefix}:filerInfo/{prefix}:investmentCompanyType",
                PRIMARY_DOC_NAMESPACES,
            ),
            rpt_include_all_series_flag=(
                self._get_optional_text(
                    series_class_section.find(
                        f"{prefix}:reportSeriesClass", PRIMARY_DOC_NAMESPACES
                    ),
                    f"{prefix}:rptIncludeAllSeriesFlag",
                    PRIMARY_DOC_NAMESPACES,
                )
                if series_class_section is not None
                and series_class_section.find(
                    f"{prefix}:reportSeriesClass", PRIMARY_DOC_NAMESPACES
                )
                is not None
                else None
            ),
            series_count=self._get_optional_text(
                series_page, f"{prefix}:seriesCount", PRIMARY_DOC_NAMESPACES
            ),
            report_series_class_infos=report_series_class_infos,
            series_reports=series_reports,
        )


# Define the namespace for easier access
PROXY_VOTE_TABLE_NAMESPACES = {
    "inf": "http://www.sec.gov/edgar/document/npxproxy/informationtable"
}


class ProxyVoteTableExtractor(BaseExtractor):
    """
    Extracts proxy vote information from SEC N-PX proxy vote table XML data.
    Uses lxml.etree.iterparse for memory-efficient parsing of potentially large files.
    """

    def __init__(self, xml_bytes: bytes):
        """Initialize the extractor with raw XML *bytes*."""
        super().__init__(xml_bytes)
        # The tag for iterparse should be the fully qualified name of the proxyTable element.
        self.proxy_table_iter_tag = (
            f"{{{PROXY_VOTE_TABLE_NAMESPACES['inf']}}}proxyTable"
        )

    def _extract_proxy_table_generator(self) -> Generator[ProxyTable, None, None]:
        """
        Parses the XML and yields ProxyTable objects.
        This is a generator method, renamed to avoid conflict if extract() was also a generator.

        Yields:
            Generator[ProxyTable, None, None]: A generator of ProxyTable dataclass instances.
        """
        xml_file_like = io.BytesIO(self.xml_bytes)

        context = ET.iterparse(
            xml_file_like,
            events=("end",),
            tag=self.proxy_table_iter_tag,
            recover=True,
        )

        for _, element in context:
            try:
                issuer_name = self._get_required_text(
                    element, "inf:issuerName", PROXY_VOTE_TABLE_NAMESPACES
                )
                meeting_date = self._get_required_text(
                    element, "inf:meetingDate", PROXY_VOTE_TABLE_NAMESPACES
                )
                vote_description = self._get_required_text(
                    element, "inf:voteDescription", PROXY_VOTE_TABLE_NAMESPACES
                )
                shares_voted_val = self._get_required_float(
                    element, "inf:sharesVoted", PROXY_VOTE_TABLE_NAMESPACES
                )
                shares_on_loan_val = self._get_required_float(
                    element, "inf:sharesOnLoan", PROXY_VOTE_TABLE_NAMESPACES
                )

                cusip = self._get_optional_text(
                    element, "inf:cusip", PROXY_VOTE_TABLE_NAMESPACES
                )
                isin = self._get_optional_text(
                    element, "inf:isin", PROXY_VOTE_TABLE_NAMESPACES
                )
                figi = self._get_optional_text(
                    element, "inf:figi", PROXY_VOTE_TABLE_NAMESPACES
                )
                other_vote_desc = self._get_optional_text(
                    element, "inf:otherVoteDescription", PROXY_VOTE_TABLE_NAMESPACES
                )
                vote_source = self._get_optional_text(
                    element, "inf:voteSource", PROXY_VOTE_TABLE_NAMESPACES
                )
                vote_series = self._get_optional_text(
                    element, "inf:voteSeries", PROXY_VOTE_TABLE_NAMESPACES
                )
                vote_other_info = self._get_optional_text(
                    element, "inf:voteOtherInfo", PROXY_VOTE_TABLE_NAMESPACES
                )

                vote_categories_list = []
                vote_categories_element = element.find(
                    "inf:voteCategories", namespaces=PROXY_VOTE_TABLE_NAMESPACES
                )
                if vote_categories_element is not None:
                    for cat_elem in vote_categories_element.findall(
                        "inf:voteCategory", namespaces=PROXY_VOTE_TABLE_NAMESPACES
                    ):
                        category_type = self._get_optional_text(
                            cat_elem, "inf:categoryType", PROXY_VOTE_TABLE_NAMESPACES
                        )
                        if category_type:
                            vote_categories_list.append(
                                VoteCategory(category_type=category_type)
                            )

                vote_records_list = []
                vote_element = element.find(
                    "inf:vote", namespaces=PROXY_VOTE_TABLE_NAMESPACES
                )
                if vote_element is not None:
                    for rec_elem in vote_element.findall(
                        "inf:voteRecord", namespaces=PROXY_VOTE_TABLE_NAMESPACES
                    ):
                        how_voted = self._get_optional_text(
                            rec_elem, "inf:howVoted", PROXY_VOTE_TABLE_NAMESPACES
                        )
                        shares_voted_rec = self._get_optional_float(
                            rec_elem, "inf:sharesVoted", PROXY_VOTE_TABLE_NAMESPACES
                        )
                        mgmt_rec = self._get_optional_text(
                            rec_elem,
                            "inf:managementRecommendation",
                            PROXY_VOTE_TABLE_NAMESPACES,
                        )

                        if (
                            how_voted is not None
                            and shares_voted_rec is not None
                            and mgmt_rec is not None
                        ):
                            vote_records_list.append(
                                VoteRecord(
                                    how_voted=how_voted,
                                    shares_voted=shares_voted_rec,
                                    management_recommendation=mgmt_rec,
                                )
                            )

                other_managers_list = []
                vote_manager_element = element.find(
                    "inf:voteManager", namespaces=PROXY_VOTE_TABLE_NAMESPACES
                )
                if vote_manager_element is not None:
                    for other_managers_container in vote_manager_element.findall(
                        "inf:otherManagers", namespaces=PROXY_VOTE_TABLE_NAMESPACES
                    ):
                        for om_elem in other_managers_container.findall(
                            "inf:otherManager", namespaces=PROXY_VOTE_TABLE_NAMESPACES
                        ):
                            manager_id = om_elem.text.strip() if om_elem.text else None
                            if manager_id:
                                other_managers_list.append(manager_id)

                proxy_table_data = ProxyTable(
                    issuer_name=issuer_name,
                    meeting_date=meeting_date,
                    vote_description=vote_description,
                    shares_voted=shares_voted_val,
                    shares_on_loan=shares_on_loan_val,
                    cusip=cusip,
                    isin=isin,
                    figi=figi,
                    other_vote_description=other_vote_desc,
                    vote_source=vote_source,
                    vote_series=vote_series,
                    vote_other_info=vote_other_info,
                    vote_categories=vote_categories_list,
                    vote_records=vote_records_list,
                    other_managers=other_managers_list,
                )
                yield proxy_table_data

            except (ValueError, TypeError) as e:
                log.error(
                    "Skipping proxyTable due to missing/invalid data or parsing error: %s on element %s", e, element.tag if element is not None else 'Unknown Element'
                )

            if element is not None:
                element.clear()
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)

        del context

    def extract(self) -> ProxyVoteTable:
        """
        Extracts all ProxyTable instances from the XML and returns them in a ProxyVoteTable container.
        This is the main public method for this extractor.
        """
        all_proxy_tables = list(self._extract_proxy_table_generator())
        return ProxyVoteTable(proxy_tables=all_proxy_tables)
