from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup
from rich import box
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar import Filing
from edgar._party import Address, Name
from edgar.richtools import repr_rich
from edgar.xmltools import child_text, child_texts, child_value

__all__ = [
    'MunicipalAdvisorForm'
]


@dataclass(frozen=True)
class Filer:
    cik: str
    ccc: str


@dataclass(frozen=True)
class Contact:
    name: str
    phone: str
    email: str


@dataclass(frozen=True)
class Employer:
    name: str
    start_date: str
    end_date: Optional[str]
    ma_related: bool
    investment_related: bool
    position: str
    address: Address


@dataclass(frozen=True)
class Office:
    start_date: str
    location_info: str
    address: Address

    @property
    def street1(self):
        return self.address.street1 if self.address and self.address.street1 else ""

    @property
    def street2(self):
        return self.address.street2 if self.address and self.address.street2 else ""

    @property
    def city(self):
        return self.address.city if self.address and self.address.city else ""

    @property
    def state_or_country(self):
        return self.address.state_or_country if self.address and self.address.state_or_country else ""

    @property
    def zipcode(self):
        return self.address.zipcode if self.address and self.address.zipcode else ""


@dataclass(frozen=True)
class MunicipalAdvisorOffice:
    cik: str
    firm_name: str
    is_independent_relationship: bool
    recent_employment_commenced_date: str
    file_number: str
    offices: List[Office]


@dataclass(frozen=True)
class CriminalDisclosure:
    is_convicted_of_felony: bool
    is_charged_with_felony: bool
    is_org_convicted_of_felony: bool
    is_org_charged_with_felony: bool
    is_convicted_of_misdemeanor: bool
    is_charged_with_misdemeanor: bool
    is_org_convicted_of_misdemeanor: bool
    is_org_charged_with_misdemeanor: bool

    def any(self):
        return any([getattr(self, attr) for attr in dir(self) if attr.startswith('is')])


@dataclass(frozen=True)
class RegulatoryDisclosure:
    is_made_false_statement: bool
    is_violated_regulation: bool
    is_cause_of_denial: bool
    is_order_against: bool
    is_imposed_penalty: bool
    is_un_ethical: bool
    is_found_in_violation_of_regulation: bool
    is_found_in_cause_of_denial: bool
    is_order_against_activity: bool
    is_denied_license: bool
    is_found_made_false_statement: bool
    is_found_in_violation_of_rules: bool
    is_found_in_cause_of_suspension: bool
    is_discipliend: bool
    is_authorized_to_act_attorney: bool
    is_regulatory_complaint: bool
    is_violated_security_act: bool
    is_will_fully_aided: bool
    is_failed_to_supervise: bool
    is_found_will_fully_aided: bool
    is_association_bared: bool
    is_final_order: bool
    is_will_fully_violated_security_act: bool
    is_failed_resonably: bool

    def any(self):
        return any([getattr(self, attr) for attr in dir(self) if attr.startswith('is')])


@dataclass(frozen=True)
class CivilDisclosure:
    is_enjoined: bool
    is_found_violation_of_regulation: bool
    is_dismissed: bool
    is_named_in_civil_proceeding: bool

    def any(self):
        return any([getattr(self, attr) for attr in dir(self) if attr.startswith('is')])


@dataclass(frozen=True)
class ComplaintDisclosure:
    is_complaint_pending: bool
    is_complaint_settled: bool
    is_fraud_case_pending: bool
    is_fraud_case_resulting_award: bool
    is_fraud_case_settled: bool

    def any(self):
        return any([getattr(self, attr) for attr in dir(self) if attr.startswith('is')])


@dataclass(frozen=True)
class TerminationDisclosure:
    is_violated_industry_standards: bool
    is_involved_in_fraud: bool
    is_failed_to_supervise: bool

    def any(self):
        return any([getattr(self, attr) for attr in dir(self) if attr.startswith('is')])


@dataclass(frozen=True)
class FinancialDisclosure:
    is_compromised: bool
    is_bankruptcy_petition: bool
    is_trustee_appointed: bool
    is_bond_revoked: bool

    def any(self):
        return any([getattr(self, attr) for attr in dir(self) if attr.startswith('is')])


@dataclass(frozen=True)
class JudgementLienDisclosure:
    is_lien_against: bool

    def any(self):
        return self.is_lien_against


@dataclass(frozen=True)
class InvestigationDisclosure:
    is_investigated: bool


def employment_date(date: str = None) -> str:
    # Convert date from this format 06-2015 to Jun 2015
    if not date:
        return ""
    date_object = datetime.strptime(date, '%m-%Y')
    return date_object.strftime('%b %Y')


class EmploymentHistory:

    def __init__(self,
                 current_employer: Employer,
                 previous_employers: List[Employer]
                 ):
        self.current_employer: Employer = current_employer
        self.previous_employers: List[Employer] = previous_employers

    def __rich__(self):
        employment_history_table = Table("From",
                                         "To",
                                         "Employer",
                                         "Position",
                                         "Muni",
                                         "Investment",
                                         "Location",
                                         box=box.SIMPLE)
        employer = self.current_employer
        employment_history_table.add_row(employer.start_date,
                                         "",
                                         employer.name,
                                         employer.position,
                                         "Yes" if employer.ma_related else "No",
                                         "Yes" if employer.investment_related else "No",
                                         f"{employer.address.city or ''} {employer.address.state_or_country or ''}")

        for employer in self.previous_employers:
            employment_history_table.add_row(employer.start_date,
                                             employer.end_date,
                                             employer.name,
                                             employer.position,

                                             "Yes" if employer.ma_related else "No",
                                             "Yes" if employer.investment_related else "No",
                                             f"{employer.address.city or ''} {employer.address.state_or_country or ''}")
        return employment_history_table

    def __repr__(self):
        return repr_rich(self.__rich__())


class Applicant:

    def __init__(self, name: Name,
                 other_names: List[Name],
                 crd: str,
                 number_of_advisory_firms: int):
        self.name: Name = name
        self.other_names = other_names
        self.crd = crd
        self.number_of_advisory_firms: int = number_of_advisory_firms

    @property
    def full_name(self):
        return self.name.full_name

    def __repr__(self):
        return f"{self.name} (CRD {self.crd})"


@dataclass(frozen=True)
class Disclosures:
    criminal_disclosure: CriminalDisclosure
    regulatory_disclosure: RegulatoryDisclosure
    civil_disclosure: CivilDisclosure
    complaint_disclosure: ComplaintDisclosure
    termination_disclosure: TerminationDisclosure
    financial_disclosure: FinancialDisclosure
    judgement_lien_disclosure: JudgementLienDisclosure
    investigation_disclosure: InvestigationDisclosure

    def any(self):
        return (self.criminal_disclosure.any()
                or self.regulatory_disclosure.any()
                or self.civil_disclosure.any()
                or self.civil_disclosure.any()
                or self.complaint_disclosure.any()
                or self.termination_disclosure.any()
                or self.financial_disclosure.any()
                or self.judgement_lien_disclosure.any()
                or self.investigation_disclosure.is_investigated
                )


@dataclass(frozen=True)
class Signature:
    date_signed: str
    signature: str
    title: str


class MunicipalAdvisorForm:

    def __init__(self,
                 filing: Filing,
                 filer: Filer,
                 is_amendment: bool,
                 is_individual: bool,
                 previous_accession_no: str,
                 contact: Contact,
                 applicant: Applicant,
                 internet_notification_addresses: List[str],
                 municipal_advisor_offices: List[MunicipalAdvisorOffice],
                 employment_history: EmploymentHistory,
                 disclosures: Disclosures,
                 signature: Signature

                 ):
        self.filing: Filing = filing
        self.filer: Filer = filer
        self.is_amendment: bool = is_amendment
        self.is_individual: bool = is_individual
        self.previous_accession_no: str = previous_accession_no
        self.contact: Contact = contact
        self.applicant: Applicant = applicant
        self.municipal_advisor_offices: List[MunicipalAdvisorOffice] = municipal_advisor_offices
        self.internet_notification_addresses = internet_notification_addresses
        self.current_employer: Employer
        self.employment_history: EmploymentHistory = employment_history
        self.disclosures: Disclosures = disclosures
        self.signature = signature

    @classmethod
    def from_filing(cls, filing):
        assert filing.form in ['MA', 'MA/A', 'MA-I', 'MA-I/A'], f"This form should be a Form 144 but was {filing.form}"
        xml = filing.xml()

        if xml:
            ma_objects = cls.from_xml(xml)
            return cls(filing=filing, **ma_objects)

    @classmethod
    def from_xml(cls, xml):
        soup = BeautifulSoup(xml, 'xml')

        root = soup.find('edgarSubmission')
        ma_info = {}

        # Header Data
        header_data = root.find('headerData')
        filer_info_el = header_data.find('filerInfo')

        filer_el = filer_info_el.find('filer')
        ma_info['filer'] = Filer(
            cik=child_text(filer_el, 'filerId'),
            ccc=child_text(filer_el, 'filerCcc')
        )

        contact_el = filer_info_el.find('contact')
        ma_info['contact'] = Contact(
            name=child_text(contact_el, 'name'),
            phone=child_text(contact_el, 'phoneNumber'),
            email=child_text(filer_info_el, 'contactEmail')
        )

        notification_el = root.find('notifications')
        if notification_el:
            ma_info['internet_notification_addresses'] = child_texts(notification_el, 'internetNotificationAddress')
        else:
            ma_info['internet_notification_addresses'] = []

        # Form Data
        form_data_el = root.find('formData')

        ma_info['is_amendment'] = child_text(form_data_el, 'isAmendment') == 'Y'
        ma_info['is_individual'] = child_text(form_data_el, 'isIndividual') == 'Y'
        ma_info['previous_accession_no'] = child_text(form_data_el, 'previousAccessionNumber')

        # Applicant
        applicant_el = form_data_el.find('applicantName')
        applicant = Applicant(
            name=Name(
                first_name=child_text(applicant_el, 'firstName'),
                last_name=child_text(applicant_el, 'lastName'),
                middle_name=child_text(applicant_el, 'middleName'),
                suffix=child_text(applicant_el, 'suffix')
            ),
            other_names=[],
            crd=child_text(form_data_el, 'applicantCrdNum'),
            number_of_advisory_firms=int(child_text(form_data_el, 'noOfAdvisoryFirms'))
        )
        # Other names
        other_names_el = form_data_el.find('otherNames')
        if other_names_el:
            for el in other_names_el.find_all('otherName'):
                applicant.other_names.append(
                    Name(
                        first_name=child_text(el, 'firstName'),
                        last_name=child_text(el, 'lastName'),
                        middle_name=child_text(el, 'middleName'),
                        suffix=child_text(applicant_el, 'suffix')
                    )
                )

        ma_info['applicant'] = applicant
        # Municipal Advisor Offices
        ma_offices_el = form_data_el.find('municipalAdvisorOffices')

        ma_info['municipal_advisor_offices'] = []

        for ma_office_el in ma_offices_el.find_all("municipalAdvisorOffice"):
            municipal_firm_el = ma_office_el.find('municipalFirm')
            filer_el = municipal_firm_el.find('filerId')
            sec_registration_el = ma_office_el.find('secRegistration')
            advisor_offices_el = ma_office_el.find('advisorOffices')
            offices = []

            for advisor_office_el in advisor_offices_el.find_all('advisorOffice'):
                address_el = advisor_office_el.find('address')
                address = Address(
                    street1=child_text(address_el, 'street1'),
                    city=child_text(address_el, 'city'),
                    state_or_country=child_text(address_el, 'stateOrCountry'),
                    zipcode=child_text(address_el, 'zipCode'),
                ) if address_el else None

                office: Office = Office(
                    location_info=child_text(advisor_office_el, 'locationInfo'),
                    start_date=child_text(advisor_office_el, 'startDate'),
                    address=address
                )
                offices.append(office)

            file_number = child_text(sec_registration_el, 'fileNumber') if sec_registration_el else None

            municipal_advisor_office = MunicipalAdvisorOffice(
                cik=filer_el.text if filer_el else "",
                firm_name=child_text(municipal_firm_el, 'municipalFirmName'),
                is_independent_relationship=child_text(municipal_firm_el, 'isIndependentRelationship') == 'Y',
                recent_employment_commenced_date=child_text(municipal_firm_el, 'recentEmploymentCommencedDate'),
                file_number=file_number,
                offices=offices
            )
            ma_info['municipal_advisor_offices'].append(municipal_advisor_office)

        # Employment History
        employment_history_el = form_data_el.find('employmentHistory')
        # Current Employer
        current_employer_el = employment_history_el.find('currentEmployer')
        address_el = current_employer_el.find('addressInfo')
        state_or_country_el = address_el.find('stateOrCountry')
        current_employer = Employer(
            name=child_text(current_employer_el, 'name'),
            start_date=employment_date(child_text(current_employer_el, 'startDate')),
            end_date=None,
            address=Address(
                city=child_text(address_el, 'city'),
                zipcode=child_text(address_el, 'zipCode'),
                state_or_country=child_text(state_or_country_el, 'stateOrCountry'),
            ),
            ma_related=child_text(current_employer_el, 'isRelatedToMunicipalAdvisor') == "Y",
            investment_related=child_text(current_employer_el, 'isRelatedToInvestment') == "Y",
            position=child_text(current_employer_el, 'positionDescription'),
        )

        # Previous employers
        prior_employers_el = employment_history_el.find('priorEmployers')
        prior_employers = []
        if prior_employers_el:

            for prior_employer_el in prior_employers_el.find_all('priorEmployer'):
                address_el = prior_employer_el.find('addressInfo')
                state_or_country_el = address_el.find('stateOrCountry')
                prior_employer = Employer(
                    name=child_text(prior_employer_el, 'name'),
                    start_date=employment_date(child_text(prior_employer_el, 'startDate')),
                    end_date=employment_date(child_text(prior_employer_el, 'endDate')),
                    address=Address(
                        city=child_text(address_el, 'city'),
                        zipcode=child_text(address_el, 'zipCode'),
                        state_or_country=child_text(state_or_country_el, 'stateOrCountry'),
                    ),
                    ma_related=child_text(prior_employer_el, 'isRelatedToMunicipalAdvisor') == "Y",
                    investment_related=child_text(prior_employer_el, 'isRelatedToInvestment') == "Y",
                    position=child_text(prior_employer_el, 'positionDescription'),
                )
                prior_employers.append(prior_employer)

        ma_info['employment_history'] = EmploymentHistory(
            current_employer=current_employer,
            previous_employers=prior_employers
        )

        # Disclosure Questions
        disclosure_questions_el = form_data_el.find('disclosureQuestions')
        # Criminal Disclosure
        criminal_disclosure_el = disclosure_questions_el.find('criminalDisclosure')
        criminal_disclosure_common_el = criminal_disclosure_el.find('criminalDisclosureCommonQuestion')
        criminal_disclosure = CriminalDisclosure(
            is_convicted_of_felony=child_value(criminal_disclosure_common_el, 'isConvictedOfFelony') == "Y",
            is_charged_with_felony=child_value(criminal_disclosure_common_el, 'isChargedWithFelony') == "Y",
            is_org_convicted_of_felony=child_value(criminal_disclosure_common_el, 'isOrgConvictedOfFelony') == "Y",
            is_org_charged_with_felony=child_value(criminal_disclosure_common_el, 'isOrgChargedWithFelony') == "Y",
            is_convicted_of_misdemeanor=child_value(criminal_disclosure_el, 'isConvictedOfMisdemeanor') == "Y",
            is_charged_with_misdemeanor=child_value(criminal_disclosure_el, 'isChargedWithMisdemeanor') == "Y",
            is_org_charged_with_misdemeanor=child_value(criminal_disclosure_el,
                                                        'isOrgChargedWithMisdemeanor') == "Y",
            is_org_convicted_of_misdemeanor=child_value(criminal_disclosure_el,
                                                        'isOrgConvictedOfMisdemeanor') == "Y",
        )
        criminal_disclosure = criminal_disclosure

        # Regulatory Disclosure
        regulatory_disclosure_el = disclosure_questions_el.find('regulatoryDisclosure')
        regulatory_disclosure_common_el = regulatory_disclosure_el.find('regulatoryDisclosureCommonQuestion')
        regulatory_disclosure = RegulatoryDisclosure(
            is_made_false_statement=child_value(regulatory_disclosure_common_el, 'isMadeFalseStatement') == "Y",
            is_violated_regulation=child_value(regulatory_disclosure_common_el, 'isViolatedRegulation') == "Y",
            is_cause_of_denial=child_value(regulatory_disclosure_common_el, 'isCauseOfDenial') == "Y",
            is_order_against=child_value(regulatory_disclosure_common_el, 'isOrderAgainst') == "Y",
            is_imposed_penalty=child_value(regulatory_disclosure_common_el, 'isImposedPenalty') == "Y",
            is_un_ethical=child_value(regulatory_disclosure_common_el, 'isUnEthical') == "Y",
            is_found_in_violation_of_regulation=child_value(regulatory_disclosure_common_el,
                                                            'isFoundInViolationOfRegulation') == "Y",
            is_found_in_violation_of_rules=child_value(regulatory_disclosure_common_el,
                                                       'isFoundInViolationOfRules') == "Y",
            is_found_in_cause_of_denial=child_value(regulatory_disclosure_common_el,
                                                    'isFoundInCauseOfDenial') == "Y",
            is_order_against_activity=child_value(regulatory_disclosure_common_el,
                                                  'isOrderAgainstActivity') == "Y",
            is_denied_license=child_value(regulatory_disclosure_common_el, 'isDeniedLicense') == "Y",
            is_found_in_cause_of_suspension=child_value(regulatory_disclosure_common_el,
                                                        'isFoundInCauseOfSuspension') == "Y",
            is_discipliend=child_value(regulatory_disclosure_common_el, 'isDiscipliend') == "Y",
            is_authorized_to_act_attorney=child_value(regulatory_disclosure_common_el,
                                                      'isAuthorizedToActAttorney') == "Y",
            is_regulatory_complaint=child_value(regulatory_disclosure_common_el, 'isRegulatoryComplaint') == "Y",
            is_violated_security_act=child_value(regulatory_disclosure_el, 'isViolatedSecurityAct') == "Y",
            is_will_fully_aided=child_value(regulatory_disclosure_el, 'isWillFullyAided') == "Y",
            is_failed_to_supervise=child_value(regulatory_disclosure_el, 'isFailedToSupervise') == "Y",
            is_found_will_fully_aided=child_value(regulatory_disclosure_el, 'isFoundWillFullyAided') == "Y",
            is_association_bared=child_value(regulatory_disclosure_el, 'isAssociationBared') == "Y",
            is_final_order=child_value(regulatory_disclosure_el, 'isFinalOrder') == "Y",
            is_will_fully_violated_security_act=child_value(regulatory_disclosure_el,
                                                            'isWillFullyViolatedSecurityAct') == "Y",
            is_failed_resonably=child_value(regulatory_disclosure_el, 'isFailedResonably') == "Y",
            is_found_made_false_statement=child_value(regulatory_disclosure_el,
                                                      'isFoundMadeFalseStatement') == "Y"
        )
        regulatory_disclosure = regulatory_disclosure

        # Investigation Disclosure
        investigation_disclosure_el = disclosure_questions_el.find('investigationDisclosure')
        investigation_disclosure = InvestigationDisclosure(
            is_investigated=child_text(investigation_disclosure_el, 'isInvestigated') == "Y")

        # Civil Disclosure
        civil_disclosure_el = disclosure_questions_el.find('civilDisclosure')
        civil_disclosure = CivilDisclosure(
            is_enjoined=child_value(civil_disclosure_el, 'isEnjoined') == "Y",
            is_found_violation_of_regulation=child_value(civil_disclosure_el,
                                                         'isFoundViolationOfRegulation') == "Y",
            is_dismissed=child_value(civil_disclosure_el, 'isDismissed') == "Y",
            is_named_in_civil_proceeding=child_value(civil_disclosure_el,
                                                     'isNamedInCivilProceeding') == "Y")

        # Complaint Disclosure
        complaint_disclosure_el = disclosure_questions_el.find('complaintDisclosure')
        complaint_disclosure = ComplaintDisclosure(
            is_complaint_pending=child_value(complaint_disclosure_el, 'isComplaintPending') == "Y",
            is_complaint_settled=child_value(complaint_disclosure_el, 'isComplaintSettled') == "Y",
            is_fraud_case_pending=child_value(complaint_disclosure_el, 'isFraudCasePending') == "Y",
            is_fraud_case_resulting_award=child_value(complaint_disclosure_el,
                                                      'isFraudCaseResultingAward') == "Y",
            is_fraud_case_settled=child_value(complaint_disclosure_el, 'isFraudCaseSettled') == "Y"
        )

        # Termination Disclosure
        termination_disclosure_el = disclosure_questions_el.find('terminationDisclosure')
        termination_disclosure = TerminationDisclosure(
            is_violated_industry_standards=child_value(termination_disclosure_el,
                                                       'isViolatedIndustryStandards') == "Y",
            is_involved_in_fraud=child_value(termination_disclosure_el, 'isInvolvedInFraud') == "Y",
            is_failed_to_supervise=child_value(termination_disclosure_el, 'isFailedToSupervise') == "Y"
        )
        # Financial Disclosure
        financial_disclosure_el = disclosure_questions_el.find('financialDisclosure')
        financial_disclosure = FinancialDisclosure(
            is_compromised=child_value(financial_disclosure_el, 'isCompromised') == "Y",
            is_bankruptcy_petition=child_value(financial_disclosure_el, 'isBankruptcyPetition') == "Y",
            is_trustee_appointed=child_value(financial_disclosure_el, 'isTrusteeAppointed') == "Y",
            is_bond_revoked=child_value(financial_disclosure_el, 'isBondRevoked') == "Y"
        )
        # Judgement Lien Disclosure
        judgement_lien_disclosure_el = disclosure_questions_el.find('judgmentLienDisclosure')
        judgement_lien_disclosure = JudgementLienDisclosure(
            is_lien_against=child_value(judgement_lien_disclosure_el, 'isLienAgainst') == "Y"
        )

        # Signature
        signature_el = form_data_el.find('signature')
        ma_info['signature'] = Signature(
            signature=child_text(signature_el, 'signature'),
            date_signed=child_text(signature_el, 'dateSigned'),
            title=child_text(signature_el, 'title')
        )

        ma_info['disclosures'] = Disclosures(
            criminal_disclosure=criminal_disclosure,
            regulatory_disclosure=regulatory_disclosure,
            civil_disclosure=civil_disclosure,
            complaint_disclosure=complaint_disclosure,
            termination_disclosure=termination_disclosure,
            financial_disclosure=financial_disclosure,
            judgement_lien_disclosure=judgement_lien_disclosure,
            investigation_disclosure=investigation_disclosure
        )

        return ma_info



    def __rich__(self):

        PAD = 80

        def text(label: str, value: str) -> Columns:
            return Columns([Text(label.ljust(PAD), style="bold"), Text(value)])

        def yes_no(label: str, value: bool) -> Columns:
            return Columns([Text(label.ljust(PAD), style="bold"), Text("Yes" if value else "No")])

        # Other Names
        other_names_group = []
        for index, other_name in enumerate(self.applicant.other_names):
            other_names_group.append(
                Group(
                    Text(f"{'First Name:'.ljust(20)}{'Middle Name:'.ljust(20)}{'Last Name:'.ljust(20)}"),
                    Text(
                        (f"{other_name.first_name.ljust(20)}"
                         f"{other_name.middle_name.ljust(20)}"
                         f"{other_name.last_name.ljust(20)}")
                    ),
                )
            )
            if index < len(self.applicant.other_names) - 1:
                other_names_group.append(Text("-" * 50))

        display = Group(
            Panel(
                Group(
                    Text(f"Filer CIK: {self.filer.cik.ljust(30)}Filer CCC: {self.filer.ccc}"),
                ), title=f"Form {self.filing.form} Applicant's Information",
            ),
            Panel(
                Group(
                    Text(f"Name: {self.contact.name.ljust(35)}Phone: {self.contact.phone}"),
                ), title="Submission Contact Information",
            ),
            Panel(
                Group(
                    *[Text(f"Email Address: {address}", address)
                      for address in self.internet_notification_addresses]
                ), title="Notification Information",
            ),
            Panel(
                Group(
                    Text(f"{'First Name:'.ljust(20)}{'Middle Name:'.ljust(20)}{'Last Name:'.ljust(20)}"),
                    Text(
                        (f"{self.applicant.name.first_name.ljust(20)}"
                         f"{self.applicant.name.middle_name.ljust(20)}"
                         f"{self.applicant.name.last_name.ljust(20)}")
                    ),

                ), title="The Individual",
            ),
            Panel(
                Group(*other_names_group), title="Other Names",
            ),
            Panel(
                Group(
                    text("Number of firms:", str(self.applicant.number_of_advisory_firms)),
                    text("Municipal firm's CIK:", self.municipal_advisor_offices[0].cik),
                    text("Full legal name:", self.municipal_advisor_offices[0].firm_name),
                    text("Employment start date:", self.municipal_advisor_offices[0].recent_employment_commenced_date),
                    text("Has independent relationship:",
                         "Yes" if self.municipal_advisor_offices[0].is_independent_relationship else "No")
                ), title="Municipal Advisory Firms Where The Individual is Employed",
            ),
            Panel(
                self.employment_history.__rich__(), title="Employment History"
            ),
            Panel(
                Group(
                    text("Edgar CIK Number", self.municipal_advisor_offices[0].cik),

                ), title="Municipal Advisory Firms Registration Information"
            ),
            Panel(
                Group(
                    text("Start Date", self.municipal_advisor_offices[0].offices[0].start_date),
                    text("Street Address 1", self.municipal_advisor_offices[0].offices[0].street1),
                    text("Street Address 2", self.municipal_advisor_offices[0].offices[0].street2),
                    text("City", self.municipal_advisor_offices[0].offices[0].city),
                    text("State", self.municipal_advisor_offices[0].offices[0].state_or_country),
                    text("Postal Code", self.municipal_advisor_offices[0].offices[0].zipcode),
                ), title="Office"
            ),
            Panel(
                Group(
                    Text("Has the individual ever:\n"),
                    yes_no("Been convicted of a felony", self.disclosures.criminal_disclosure.is_convicted_of_felony),
                    yes_no("Been charged with a felony", self.disclosures.criminal_disclosure.is_charged_with_felony),
                    yes_no("Caused an organization to be convicted of a felony",
                           self.disclosures.criminal_disclosure.is_convicted_of_felony),
                    yes_no("Caused an organization to be charged with a felony",
                           self.disclosures.criminal_disclosure.is_charged_with_felony),
                    yes_no("Been convicted of a misdemeanor",
                           self.disclosures.criminal_disclosure.is_convicted_of_misdemeanor),
                    yes_no("Been charged with a misdemeanor",
                           self.disclosures.criminal_disclosure.is_charged_with_misdemeanor),
                    yes_no("Caused an organization to be convicted of misdemeanor",
                           self.disclosures.criminal_disclosure.is_convicted_of_misdemeanor),
                    yes_no("Caused an organization to be charged with misdemeanor",
                           self.disclosures.criminal_disclosure.is_charged_with_misdemeanor),

                ), title="Criminal Action Disclosure",
            ),
            Panel(
                Group(
                    Text("Has the SEC or the CFTC ever:\n"),
                    # <com:isMadeFalseStatement>N</com:isMadeFalseStatement>
                    yes_no("Found that the individual made a false statement",
                           self.disclosures.regulatory_disclosure.is_found_made_false_statement),
                    # <com:isViolatedRegulation>N</com:isViolatedRegulation>
                    yes_no("Found the individual in violation of an SEC or CFTC regulation",
                           self.disclosures.regulatory_disclosure.is_violated_regulation),

                    # <com:isCauseOfDenial>N</com:isCauseOfDenial>
                    yes_no("Found the individual caused a suspension of a MA business",
                           self.disclosures.regulatory_disclosure.is_cause_of_denial),

                    # <com:isOrderAgainst>N</com:isOrderAgainst>
                    yes_no("Entered an order against the individual connected to MA or investment activity",
                           self.disclosures.regulatory_disclosure.is_order_against),

                    # <com:isImposedPenalty>N</com:isImposedPenalty>
                    yes_no("Imposed a penalty on the individual",
                           self.disclosures.regulatory_disclosure.is_imposed_penalty),

                    # <com:isUnEthical>N</com:isUnEthical>
                    yes_no("Found the individual to have been dishonest or unethical",
                           self.disclosures.regulatory_disclosure.is_un_ethical),

                    # <com:isFoundInViolationOfRegulation>N</com:isFoundInViolationOfRegulation>
                    yes_no("Found the individual to have willfully violated a Securities or Investment Act",
                           self.disclosures.regulatory_disclosure.is_found_in_violation_of_regulation),

                    # <com:isFoundInCauseOfDenial>N</com:isFoundInCauseOfDenial>
                    yes_no("Found the individual a cause of a denial of auth of muni-advisor business",
                           self.disclosures.regulatory_disclosure.is_found_in_cause_of_denial),

                    # <com:isOrderAgainstActivity>N</com:isOrderAgainstActivity>
                    yes_no("Entered an order against the individual's activities",
                           self.disclosures.regulatory_disclosure.is_order_against_activity),

                    # <com:isDeniedLicense>N</com:isDeniedLicense>
                    yes_no("Denied, suspended or revoked the individual's license",
                           self.disclosures.regulatory_disclosure.is_denied_license),

                    # <com:isFoundMadeFalseStatement>N</com:isFoundMadeFalseStatement>
                    yes_no("Found the individual to have made a false statement",
                           self.disclosures.regulatory_disclosure.is_found_made_false_statement),

                    # <com:isFoundInViolationOfRules>N</com:isFoundInViolationOfRules>
                    yes_no("Found the individual to be in violation of rules",
                           self.disclosures.regulatory_disclosure.is_found_in_violation_of_rules),

                    # <com:isFoundInCauseOfSuspension>N</com:isFoundInCauseOfSuspension>
                    yes_no("Found the individual a cause of suspension of a muni-advisor business",
                           self.disclosures.regulatory_disclosure.is_found_in_cause_of_suspension),

                    # <com:isDiscipliend>N</com:isDiscipliend>
                    yes_no("Disciplined the individual by expelling or barring from membership",
                           self.disclosures.regulatory_disclosure.is_discipliend),

                    # <com:isAuthorizedToActAttorney>N</com:isAuthorizedToActAttorney>
                    yes_no("Has the individual ever had an authorization to act as attorney suspended",
                           self.disclosures.regulatory_disclosure.is_authorized_to_act_attorney),

                    # <com:isRegulatoryComplaint>N</com:isRegulatoryComplaint>
                    yes_no("Has the individual ever been notified of a regulatory complaint against them",
                           self.disclosures.regulatory_disclosure.is_regulatory_complaint),

                    # <isViolatedSecurityAct>N</isViolatedSecurityAct>
                    yes_no("Found the individual to have violated the Securities Act",
                           self.disclosures.regulatory_disclosure.is_violated_security_act),

                    # <isWillFullyAided>N</isWillFullyAided>
                    yes_no("Found the individual to have willfully aided a violation",
                           self.disclosures.regulatory_disclosure.is_will_fully_aided),

                    # <isFailedToSupervise>N</isFailedToSupervise>
                    yes_no("Found the individual to have failed to supervise another individual",
                           self.disclosures.regulatory_disclosure.is_failed_to_supervise),

                ), title="Regulatory Disclosure",
            ),
            Panel(
                Group(
                    Text("Has any other federal or state or foreign regulatory agency ever:\n"),

                    # <isWillFullyAided>N</isWillFullyAided>
                    yes_no("Found the individual to have willfully aided a violation",
                           self.disclosures.regulatory_disclosure.is_found_will_fully_aided),

                    # <isAssociationBared>N</isAssociationBared>
                    yes_no("Barred the individual from association with a regulated agancy",
                           self.disclosures.regulatory_disclosure.is_association_bared),

                    # <isFinalOrder>N</isFinalOrder>
                    yes_no("Entered a final order against the individual",
                           self.disclosures.regulatory_disclosure.is_final_order),
                ), title="Regulatory Disclosure",
            ),
            Panel(
                yes_no("Is the individual currently being investigated:",
                       self.disclosures.investigation_disclosure.is_investigated),
                title="Investigation Disclosure",
            ),
            Panel(
                Group(
                    Text("Has any domestic of foreign court ever:\n"),
                    yes_no("Enjoined the individual in connection with a muni advisor business",
                           self.disclosures.civil_disclosure.is_enjoined),
                    yes_no("Found the individual to have violated any law or regulation",
                           self.disclosures.civil_disclosure.is_found_violation_of_regulation),
                    yes_no("Dismissed with a settleent a civil action against the individual",
                           self.disclosures.civil_disclosure.is_dismissed),
                    yes_no("Is the individual named in any current civil proceeding",
                           self.disclosures.civil_disclosure.is_named_in_civil_proceeding
                           )
                ), title="Civil Disclosure"
            ),
            Panel(
                Group(
                    Text("Has the individual ever been the subject of a muni-advisor related complaint which:\n"),
                    yes_no("Is still pending", self.disclosures.complaint_disclosure.is_complaint_pending),
                    yes_no("Is settled", self.disclosures.complaint_disclosure.is_complaint_settled),
                    Text("\n"
                         "Has the individual ever been the subject of a muni-advisor related fraud proceeding which\n"),
                    yes_no("Is still pending", self.disclosures.complaint_disclosure.is_fraud_case_pending),
                    yes_no("Resulted in an award", self.disclosures.complaint_disclosure.is_fraud_case_resulting_award),
                    yes_no("Is settled", self.disclosures.complaint_disclosure.is_fraud_case_settled),
                ), title="Complaint Disclosure",
            ),
            Panel(
                Group(
                    Text("Has the individual ever been terminated or permitted to resign after allegations of:\n"),
                    yes_no("Violations of industry standards",
                           self.disclosures.termination_disclosure.is_violated_industry_standards),
                    yes_no("Involvement in fraud", self.disclosures.termination_disclosure.is_involved_in_fraud),
                    yes_no("Failure to supervise", self.disclosures.termination_disclosure.is_failed_to_supervise),
                ), title="Termination Disclosure",
            ),
            Panel(
                Group(
                    Text("Within the past 10 years:\n"),
                    yes_no("Has the individual made a compromise with creditors",
                           self.disclosures.financial_disclosure.is_compromised),
                    yes_no("Has an organization under the individual's control ever filed for bankruptcy",
                           self.disclosures.financial_disclosure.is_bankruptcy_petition),
                    yes_no("Has an organization under the individual's control ever has a trustee appointed",
                           self.disclosures.financial_disclosure.is_trustee_appointed),
                    yes_no("Has a bonding company ever denied/paid out/revoked a bond for the individual",
                           self.disclosures.financial_disclosure.is_bond_revoked),
                ), title="Financial Disclosure",
            ),
            Panel(
                Group(
                    yes_no("Are there currently any judgment liens against the individual",
                           self.disclosures.judgement_lien_disclosure.is_lien_against),
                ),
                title="Judgement/Lien Disclosure",
            ),
            Panel(
                Group(
                    Text(f"{'By:'.ljust(32)}{'Title:'.ljust(60)}{'Date:'}"),
                    Text((f"{self.signature.signature.ljust(32)}"
                          f"{self.signature.title.ljust(60)}"
                          f"{self.signature.date_signed}")),
                ), title="Signature"
            )
        )
        return display

    def __repr__(self):
        return repr_rich(self.__rich__())
