"""What `MunicipalAdvisorForm.from_xml` owes its callers, with no network.

`edgar/muniadvisors/core.py` (then `edgar/muniadvisors.py`) moved from BeautifulSoup to lxml under
edgartools-07lk.11.3. MA-I is a heavily namespaced form — a default
`http://www.sec.gov/edgar/maifiler` namespace for the form's own elements plus
two prefixed ones (`common_ma`, `common`) that carry most of the leaf values —
so a plain lxml `.//name` matches nothing at all for the majority of the fields
here. Everything routes through the local-name matching in `edgar/xmltools.py`
instead, and the tests below name the namespace each value lives in so a
regression points at the axis that broke.

The other hazard is the guards. `<otherNames>`, `<notifications>`,
`<priorEmployers>`, `<secRegistration>` and `<address>` are all optional, and
each was guarded on truthiness, which an lxml element with no children fails
even when it is present. Those are `is not None` now, and the absent-section
cases below exercise both sides.

`tests/test_muni_advisors.py` matches `test_muni` in `NETWORK_PATTERNS`, so
nothing added there runs in the fast job. Ground truth is the MA-I/A notice
checked in at `data/MuniAdvisors/goldman.MA-I.xml`.
"""
from pathlib import Path

import pytest

from edgar.muniadvisors import MunicipalAdvisorForm

GOLDMAN = Path('data/MuniAdvisors/goldman.MA-I.xml')

# A minimal MA-I carrying only what `from_xml` requires, with every optional
# section left out. Namespaces and nesting match the real form.
MINIMAL = """<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/maifiler"
                 xmlns:com="http://www.sec.gov/edgar/common_ma"
                 xmlns:com1="http://www.sec.gov/edgar/common">
  <headerData>
    <filerInfo>
      <com:filer><com1:filerId>0000000001</com1:filerId><com1:filerCcc>XXXXXXXX</com1:filerCcc></com:filer>
      <com:contact><com1:name>PAT LEE</com1:name><com1:phoneNumber>555-0100</com1:phoneNumber></com:contact>
      <com:contactEmail>pat@example.com</com:contactEmail>
    </filerInfo>
  </headerData>
  <formData>
    <isAmendment>Y</isAmendment>
    <isIndividual>N</isIndividual>
    <applicantName><com:firstName>PAT</com:firstName><com:lastName>LEE</com:lastName></applicantName>
    <applicantCrdNum>999</applicantCrdNum>
    <noOfAdvisoryFirms>1</noOfAdvisoryFirms>
    <municipalAdvisorOffices>
      <municipalAdvisorOffice>
        <municipalFirm>
          <municipalFiler><filerId>0000000002</filerId></municipalFiler>
          <municipalFirmName>EXAMPLE ADVISORS LLC</municipalFirmName>
          <recentEmploymentCommencedDate>01-02-2024</recentEmploymentCommencedDate>
        </municipalFirm>
        <advisorOffices>
          <advisorOffice><locationInfo>LOCATED</locationInfo><startDate>01-02-2024</startDate></advisorOffice>
        </advisorOffices>
      </municipalAdvisorOffice>
    </municipalAdvisorOffices>
    <employmentHistory>
      <currentEmployer>
        <startDate>01-2024</startDate>
        <name>EXAMPLE ADVISORS LLC</name>
        <addressInfo>
          <city>BOISE</city>
          <stateOrCountry><com1:stateOrCountry>ID</com1:stateOrCountry></stateOrCountry>
          <zipCode>83702</zipCode>
        </addressInfo>
        <isRelatedToMunicipalAdvisor>N</isRelatedToMunicipalAdvisor>
        <isRelatedToInvestment>N</isRelatedToInvestment>
        <positionDescription>ANALYST</positionDescription>
      </currentEmployer>
    </employmentHistory>
    <disclosureQuestions>
      <criminalDisclosure><criminalDisclosureCommonQuestion/></criminalDisclosure>
      <regulatoryDisclosure><regulatoryDisclosureCommonQuestion/></regulatoryDisclosure>
      <investigationDisclosure><isInvestigated>Y</isInvestigated></investigationDisclosure>
      <civilDisclosure/>
      <complaintDisclosure/>
      <terminationDisclosure/>
      <financialDisclosure/>
      <judgmentLienDisclosure/>
    </disclosureQuestions>
    <signatureInfo>
      <com:signature>
        <com:dateSigned>01-03-2024</com:dateSigned>
        <com:signature>PAT LEE</com:signature>
        <com:title>PARTNER</com:title>
      </com:signature>
    </signatureInfo>
  </formData>
</edgarSubmission>"""


@pytest.fixture(scope="module")
def goldman():
    return MunicipalAdvisorForm.from_xml(GOLDMAN.read_text())


@pytest.fixture(scope="module")
def minimal():
    return MunicipalAdvisorForm.from_xml(MINIMAL)


def test_the_header_block_is_read(goldman):
    """`filerId`, `filerCcc`, `name` and `phoneNumber` live in the `common`
    namespace and `contactEmail` in `common_ma`, none of them the document's
    default — so all five are found by local name or not at all."""
    assert goldman['filer'].cik == '0000769993'
    assert goldman['filer'].ccc == 'XXXXXXXX'
    assert goldman['contact'].name == 'CHAD CHRISTENSEN'
    assert goldman['contact'].phone == '801-741-5676'
    assert goldman['contact'].email == 'CHAD.CHRISTENSEN@GS.COM'


def test_every_notification_address_is_collected(goldman):
    assert goldman['internet_notification_addresses'] == [
        'WILLIAM.JENSEN@GS.COM', 'CAYDEN.GROICHER@GS.COM']


def test_a_filing_with_no_notifications_block_gets_an_empty_list(minimal):
    """The `<notifications>` guard. It was `if notification_el:`, which an lxml
    element fails whenever it has no children."""
    assert minimal['internet_notification_addresses'] == []


def test_the_applicant_and_their_other_names_are_read(goldman):
    applicant = goldman['applicant']
    assert applicant.name.first_name == 'ELAINE'
    assert applicant.name.middle_name == 'YUEN-WEN'
    assert applicant.name.last_name == 'YAO'
    assert applicant.crd == '2536120'
    assert applicant.number_of_advisory_firms == 1
    assert [(n.first_name, n.middle_name, n.last_name) for n in applicant.other_names] == [
        ('ELAINE', 'Y', 'YAO')]


def test_a_filing_with_no_other_names_block_leaves_the_list_empty(minimal):
    assert minimal['applicant'].other_names == []
    assert minimal['applicant'].name.first_name == 'PAT'
    assert minimal['applicant'].name.last_name == 'LEE'


def test_the_amendment_flags_are_read(goldman, minimal):
    assert goldman['is_amendment'] is False
    assert goldman['is_individual'] is True
    assert goldman['previous_accession_no'] == '0000769993-21-000270'
    assert minimal['is_amendment'] is True
    assert minimal['is_individual'] is False
    assert minimal['previous_accession_no'] is None


def test_the_advisory_office_and_its_address_are_read(goldman):
    offices = goldman['municipal_advisor_offices']
    assert len(offices) == 1
    office = offices[0]
    assert office.cik == '0000769993'
    assert office.firm_name == 'GOLDMAN SACHS & CO. LLC'
    assert office.recent_employment_commenced_date == '06-14-2021'
    assert office.file_number == '867-01181'

    assert len(office.offices) == 1
    assert office.offices[0].location_info == 'LOCATED'
    assert office.offices[0].start_date == '06-14-2021'
    assert office.offices[0].street1 == '200 WEST STREET'
    assert office.offices[0].city == 'NEW YORK'
    assert office.offices[0].state_or_country == 'NY'
    assert office.offices[0].zipcode == '10282'


def test_an_office_with_no_registration_or_address_still_parses(minimal):
    """Both `<secRegistration>` and `<address>` were guarded on truthiness, so a
    section that is merely empty took the same branch as an absent one."""
    office = minimal['municipal_advisor_offices'][0]
    assert office.cik == '0000000002'
    assert office.firm_name == 'EXAMPLE ADVISORS LLC'
    assert office.file_number is None
    assert office.offices[0].address is None
    assert office.offices[0].street1 == ''
    assert office.offices[0].city == ''


def test_employment_history_keeps_every_prior_employer(goldman):
    """`stateOrCountry` nests a `common`-namespaced element inside a default-
    namespaced one of the same local name, which is the read most sensitive to
    how the descendant search resolves namespaces."""
    history = goldman['employment_history']
    current = history.current_employer
    assert current.name == 'GOLDMAN SACHS & CO. LLC'
    assert current.start_date == 'Jun 2021'
    assert current.end_date is None
    assert current.position == 'VICE PRESIDENT'
    assert current.ma_related is True
    assert current.investment_related is True
    assert current.address.city == 'NEW YORK'
    assert current.address.state_or_country == 'NY'
    assert current.address.zipcode == '10282'

    assert [(e.name, e.start_date, e.end_date, e.address.state_or_country)
            for e in history.previous_employers] == [
        ('H2C SECURITIES INC.', 'Sep 2011', 'May 2021', 'CA'),
        ('MORGAN KEEGAN & COMPANY', 'Jun 2007', 'Aug 2011', 'NY')]


def test_a_filing_with_no_prior_employers_block_gets_an_empty_list(minimal):
    assert minimal['employment_history'].previous_employers == []
    assert minimal['employment_history'].current_employer.name == 'EXAMPLE ADVISORS LLC'
    assert minimal['employment_history'].current_employer.address.state_or_country == 'ID'


def test_the_signature_block_is_read(goldman, minimal):
    """`<com:signature>` wraps a `<com:signature>` of the same local name, so the
    outer element is found first and the inner one read from inside it."""
    assert goldman['signature'].signature == "JOHN O'CONNELL"
    assert goldman['signature'].date_signed == '05-11-2023'
    assert goldman['signature'].title == 'CHIEF COMPLIANCE OFFICER'
    assert minimal['signature'].signature == 'PAT LEE'


def test_the_investigation_answer_is_read(goldman, minimal):
    """The one disclosure field parsed with `child_text`, and so the one that
    reflects what the filing actually says — see edgartools-9fy0."""
    assert goldman['disclosures'].investigation_disclosure.is_investigated is False
    assert minimal['disclosures'].investigation_disclosure.is_investigated is True


def test_disclosure_answers_are_read_from_the_elements_own_text(goldman):
    """edgartools-9fy0: 40 of the 45 disclosure booleans were parsed with
    `xmltools.child_value`, which reads the text of a `<value>` CHILD. MA-I
    disclosure elements have no `<value>` child — they hold the answer as their
    own text, e.g. `<com:isConvictedOfFelony>Y</com:isConvictedOfFelony>` — so
    `child_value` returned `''` and the `== "Y"` comparison was always False.
    Fixed by switching these reads to `child_text`, the pattern already used by
    `investigation_disclosure.is_investigated`.

    The checked-in Goldman fixture answers N to every disclosure question, so
    this asserts on a copy with one answer flipped to Y.
    """
    xml = GOLDMAN.read_text().replace('<com:isConvictedOfFelony>N<',
                                      '<com:isConvictedOfFelony>Y<')
    assert '<com:isConvictedOfFelony>Y<' in xml
    disclosures = MunicipalAdvisorForm.from_xml(xml)['disclosures']
    assert disclosures.criminal_disclosure.is_convicted_of_felony is True
    assert disclosures.any() is True

    # And the clean fixture still reads as clean.
    assert goldman['disclosures'].criminal_disclosure.is_convicted_of_felony is False
    assert goldman['disclosures'].any() is False


def test_is_independent_relationship_is_read_from_the_real_sec_element_name():
    """edgartools-x2ko: the parser searched for `isIndependentRelationship`; the
    SEC schema spells it `isIndependentRelatioship` (its own typo, present in
    40/40 sampled MA-I filings). The search found nothing, so the field was
    False for every MA-I ever filed. Fixed by searching for the real name.
    """
    xml = GOLDMAN.read_text().replace('<isIndependentRelatioship>N<',
                                      '<isIndependentRelatioship>Y<')
    assert '<isIndependentRelatioship>Y<' in xml
    offices = MunicipalAdvisorForm.from_xml(xml)['municipal_advisor_offices']
    assert offices[0].is_independent_relationship is True


def test_civil_disclosure_is_read_from_the_real_sec_element_name():
    """edgartools-x2ko: the parser searched for `isFoundViolationOfRegulation`;
    the SEC schema spells it `isFoundInViolationOfRegulation` (40/40 sampled).
    Also depends on the 9fy0 child_text fix, since this field is nested inside
    `<civilDisclosure>` with no `<value>` child."""
    xml = GOLDMAN.read_text().replace('<com:isFoundInViolationOfRegulation>N</com:isFoundInViolationOfRegulation>\n        <com:isDismissed>',
                                      '<com:isFoundInViolationOfRegulation>Y</com:isFoundInViolationOfRegulation>\n        <com:isDismissed>')
    assert '<com:isFoundInViolationOfRegulation>Y</com:isFoundInViolationOfRegulation>\n        <com:isDismissed>' in xml
    disclosures = MunicipalAdvisorForm.from_xml(xml)['disclosures']
    assert disclosures.civil_disclosure.is_found_violation_of_regulation is True
    assert disclosures.civil_disclosure.any() is True


def test_complaint_disclosure_is_read_from_the_real_sec_element_name():
    """edgartools-x2ko: the parser searched for `isFraudCaseResultingAward`; the
    SEC schema spells it `isFraudCaseResultedAward` (its own typo, 40/40 sampled)."""
    xml = GOLDMAN.read_text().replace('<isFraudCaseResultedAward>N<',
                                      '<isFraudCaseResultedAward>Y<')
    assert '<isFraudCaseResultedAward>Y<' in xml
    disclosures = MunicipalAdvisorForm.from_xml(xml)['disclosures']
    assert disclosures.complaint_disclosure.is_fraud_case_resulting_award is True
    assert disclosures.complaint_disclosure.any() is True


def test_termination_disclosure_is_read_from_the_real_sec_element_name():
    """edgartools-x2ko: the parser searched for `isViolatedIndustryStandards`;
    the SEC schema spells it `isViloatedIndustryStandard` (its own typo, 40/40
    sampled)."""
    xml = GOLDMAN.read_text().replace('<isViloatedIndustryStandard>N<',
                                      '<isViloatedIndustryStandard>Y<')
    assert '<isViloatedIndustryStandard>Y<' in xml
    disclosures = MunicipalAdvisorForm.from_xml(xml)['disclosures']
    assert disclosures.termination_disclosure.is_violated_industry_standards is True
    assert disclosures.termination_disclosure.any() is True


def test_financial_disclosure_is_read_from_the_real_sec_element_name():
    """edgartools-x2ko: the parser searched for `isTrusteeAppointed`; the SEC
    schema spells it `isTrusteeApointed` (its own typo, 40/40 sampled)."""
    xml = GOLDMAN.read_text().replace('<isTrusteeApointed>N<',
                                      '<isTrusteeApointed>Y<')
    assert '<isTrusteeApointed>Y<' in xml
    disclosures = MunicipalAdvisorForm.from_xml(xml)['disclosures']
    assert disclosures.financial_disclosure.is_trustee_appointed is True
    assert disclosures.financial_disclosure.any() is True


def test_from_xml_rejects_a_document_that_is_not_an_edgar_submission():
    with pytest.raises(ValueError, match="edgarSubmission"):
        MunicipalAdvisorForm.from_xml("<?xml version='1.0'?><ownershipDocument><a/></ownershipDocument>")


def test_from_xml_absorbs_whitespace_before_the_declaration():
    """`parse_xml` handles what bs4 absorbed silently and bare lxml raises on."""
    assert MunicipalAdvisorForm.from_xml("\n  " + MINIMAL)['filer'].cik == '0000000001'
