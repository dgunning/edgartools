from datetime import datetime
from pathlib import Path

import pytest

from edgar import *
from edgar.offerings import FormC, Signer

ALL_FORMC_FIXTURES = [
    ("data/pickleball.FormC.xml", "C"),
    ("data/xml/Anesu.FormC.xml", "C"),
    ("data/xml/alto.FormC.xml", "C"),
    ("data/HiddenSea.FormCU.xml", "C-U"),
    ("data/EVSolar.FormC-AR.xml", "C-AR"),
    ("data/Neurotez.FormCTR.xml", "C-TR"),
]


def test_parse_formc_offering():
    offering_xml = Path("data/pickleball.FormC.xml").read_text()
    formC: FormC = FormC.from_xml(offering_xml, form="C")
    # Filer information (ccc/live_or_test were previously mis-parsed - edgartools-nqoi)
    assert formC.filer_information.cik == "0002011047"
    assert formC.filer_information.ccc == "XXXXXXXX"  # always redacted in disseminated filings
    assert formC.filer_information.live_or_test is True
    assert formC.issuer_information.funding_portal.cik == "0001348811"
    assert formC.issuer_information.funding_portal.file_number == "008-67202"
    assert formC.issuer_information.funding_portal.name == "ANDES CAPITAL GROUP, LLC"
    assert formC.issuer_information.legal_status == "Limited Liability Company"
    assert formC.issuer_information.jurisdiction == "CA"
    assert formC.issuer_information.date_of_incorporation == datetime(2023, 12, 11).date()

    # Offering Information
    assert formC.offering_information.compensation_amount.startswith("A fee equal of 3%")
    assert formC.offering_information.financial_interest == "No"
    assert formC.offering_information.security_offered_type == "Other"
    assert formC.offering_information.security_offered_other_desc == "Membership Interests"
    assert formC.offering_information.no_of_security_offered == "41666"
    assert formC.offering_information.price == "1.20000"
    assert formC.offering_information.over_subscription_accepted == "Y"
    assert formC.offering_information.maximum_offering_amount == 950000.0
    assert formC.offering_information.over_subscription_allocation_type == "First-come, first-served basis"
    assert formC.offering_information.deadline_date == datetime(2024, 12, 31).date()

    # Annual Report
    assert formC.annual_report_disclosure.total_asset_most_recent_fiscal_year == 0.00

    assert "NJ" in formC.annual_report_disclosure.offering_jurisdictions

    # Signatures
    signature_info = formC.signature_info
    assert signature_info.issuer_signature.issuer == "Pickleball Etc. LLC"
    assert signature_info.issuer_signature.signature == "Steven Raack"
    assert signature_info.issuer_signature.title == "Managing Member"
    print(formC)


def test_formc_offering_with_annual_report_disclosures():
    offering_xml = Path("data/xml/Anesu.FormC.xml").read_text()
    formC: FormC = FormC.from_xml(offering_xml, form="C")
    assert formC.filer_information.cik == "0002017182"
    assert formC.issuer_information.funding_portal.cik == "0001707214"
    print()
    # Annual Report
    assert formC.annual_report_disclosure.current_employees == 12
    assert formC.annual_report_disclosure.total_asset_most_recent_fiscal_year == 47586.0
    assert formC.annual_report_disclosure.total_asset_prior_fiscal_year == 152589.00
    assert formC.annual_report_disclosure.tax_paid_prior_fiscal_year == 0.0
    assert formC.annual_report_disclosure.net_income_most_recent_fiscal_year == 58409.0
    assert formC.signature_info.signers == [Signer(name="Douglas D'Orio", titles=['Managing Member'])]


def test_form_CU_offering():
    offering_xml = Path("data/HiddenSea.FormCU.xml").read_text()
    formC: FormC = FormC.from_xml(offering_xml, form="C-U")
    # Issuer Information
    assert formC.issuer_information.name == "Hidden Sea USA Inc"
    assert formC.issuer_information.legal_status == "Corporation"
    assert formC.issuer_information.jurisdiction == "DE"
    assert formC.issuer_information.date_of_incorporation == datetime(2015, 10, 7).date()

    # Offering Information
    assert formC.offering_information.compensation_amount.startswith(
        "The issuer shall pay to the Intermediary at the conclusion")
    assert formC.offering_information.financial_interest.startswith("The Intermediary will also receive")

    # Annual Report
    assert formC.annual_report_disclosure.total_asset_most_recent_fiscal_year == 75182.0
    assert formC.annual_report_disclosure.tax_paid_prior_fiscal_year == 0.0
    assert formC.annual_report_disclosure.net_income_most_recent_fiscal_year == -16620.0
    assert formC.annual_report_disclosure.short_term_debt_prior_fiscal_year == 0.0
    assert formC.annual_report_disclosure.long_term_debt_prior_fiscal_year == 0.0
    assert formC.annual_report_disclosure.short_term_debt_prior_fiscal_year == 0.0

    # Signatures
    signers = formC.signature_info.signers
    assert len(signers) == 1


def test_form_C_offering_annual_report():
    offering_xml = Path("data/EVSolar.FormC-AR.xml").read_text()
    formC: FormC = FormC.from_xml(offering_xml, form="C-AR")

    assert formC.offering_information is None
    assert formC.filer_information.period == datetime(2022, 12, 31).date()
    assert formC.filer_information.cik == "0001932704"

    # Issuer Information
    assert formC.issuer_information.name == "EV Solar Kits LLC"
    assert formC.issuer_information.legal_status == "Limited Liability Company"
    assert formC.issuer_information.jurisdiction == "TX"

    assert formC.issuer_information.funding_portal is None
    # Annual Report
    assert formC.annual_report_disclosure.total_asset_most_recent_fiscal_year == 145529.0
    assert formC.annual_report_disclosure.tax_paid_prior_fiscal_year == 0.0
    assert formC.annual_report_disclosure.net_income_most_recent_fiscal_year == -145529.0
    assert formC.annual_report_disclosure.short_term_debt_prior_fiscal_year == 0.0
    assert formC.annual_report_disclosure.long_term_debt_prior_fiscal_year == 0.0


def test_form_c_obj():
    filing = Filing(form='C/A', filing_date='2024-01-02', company='U.S. Hemp Co Inc', cik=2001951,
                    accession_no='0001669191-24-000002')
    formC: FormC = filing.obj()
    assert isinstance(formC, FormC)

    filing = Filing(form='C-TR', filing_date='2024-03-22', company='ORTEK THERAPEUTICS INC', cik=1070105,
                    accession_no='0001665160-24-000252')
    formC: FormC = filing.obj()
    assert isinstance(formC, FormC)


def test_formc_with_multiple_signers():
    filing = Filing(form='C', filing_date='2024-03-28', company='Deverra Therapeutics, Inc.', cik=1822782,
                    accession_no='0001665160-24-000283')
    formc = filing.obj()

    assert formc.signature_info.signers == [Signer(name='Michael Yurkowsky', titles=['CEO, Director and Chairman']),
                                            Signer(name='Andrew Albert Kucharchuk', titles=['Interim CFO']),
                                            Signer(name='Colleen Delaney', titles=
                                            [
                                                'Scientific Founder and Chief Scientific Officer, EVP of RandD, Director'])]


def test_parse_form_tr():
    """
    This is a C-TR termination of offering so lots of missing data
    """
    offering_xml = Path("data/Neurotez.FormCTR.xml").read_text()
    formC: FormC = FormC.from_xml(offering_xml, form="C-TR")
    assert formC.offering_information is None
    assert formC.filer_information.period is None
    assert formC.filer_information.cik == "0001725567"
    assert formC.filer_information.ccc == "XXXXXXXX"
    assert formC.filer_information.live_or_test is True


def test_form_c_termination_report():
    filing = Filing(form='C-TR', filing_date='2023-12-29', company='H2 Energy Group Inc', cik=1901902,
                    accession_no='0001079973-23-001832')
    formC: FormC = filing.obj()
    assert formC.annual_report_disclosure is None
    assert formC.offering_information is None


def test_formc_with_fundingportal_with_no_crd():
    filing = Filing(form='C/A', filing_date='2023-12-29', company='Origo Brands Inc.', cik=1981723,
                    accession_no='0001665160-23-002050')
    formC = filing.obj()
    funding_portal = formC.issuer_information.funding_portal
    assert funding_portal.cik == "0001665160"
    assert funding_portal.name == "StartEngine Capital, LLC"
    assert funding_portal.file_number == "007-00007"
    assert funding_portal.crd is None


def test_formc_with_empty_offering_tag():
    filing = Filing(form='C-AR', filing_date='2024-07-29', company='Energy Exploration Technologies, Inc.', cik=1830166,
                    accession_no='0001493152-24-029321')
    formC = filing.obj()
    assert formC
    assert formC.offering_information is None


@pytest.mark.parametrize("fixture_path,form", ALL_FORMC_FIXTURES)
def test_formc_parses_all_fixtures(fixture_path, form):
    """Every fixture parses with correct filer credentials across all Form C variants (edgartools-nqoi)."""
    formC: FormC = FormC.from_xml(Path(fixture_path).read_text(), form=form)
    assert formC.form == form
    assert len(formC.filer_information.cik) == 10
    assert formC.filer_information.cik.isdigit()
    # ccc must NOT be the cik (the pre-lxml parser copied filerCik into ccc)
    assert formC.filer_information.ccc == "XXXXXXXX"
    assert formC.filer_information.ccc != formC.filer_information.cik
    # All fixtures are LIVE filings (the pre-lxml parser always returned False)
    assert formC.filer_information.live_or_test is True
    assert formC.issuer_information.name
    assert len(formC.signature_info.signers) >= 1


MINIMAL_FORMC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/formc" xmlns:com="http://www.sec.gov/edgar/common">
  <headerData>
    <submissionType>C-TR</submissionType>
    <filerInfo>
      <filer>
        <filerCredentials>
          <filerCik>0001725567</filerCik>
        </filerCredentials>
      </filer>
      <liveTestFlag>TEST</liveTestFlag>
      <flags/>
    </filerInfo>
  </headerData>
  <formData>
    <issuerInformation>
      <issuerInfo>
        <nameOfIssuer>Minimal Inc.</nameOfIssuer>
        <legalStatus>
          <legalStatusForm>Corporation</legalStatusForm>
          <jurisdictionOrganization>DE</jurisdictionOrganization>
          <dateIncorporation>10-14-2005</dateIncorporation>
        </legalStatus>
        <issuerAddress>
          <com:street1>1 MAIN ST</com:street1>
          <com:city>WILMINGTON</com:city>
          <com:stateOrCountry>DE</com:stateOrCountry>
          <com:zipCode>19801</com:zipCode>
        </issuerAddress>
        <issuerWebsite>https://example.com</issuerWebsite>
      </issuerInfo>
      <isCoIssuer>N</isCoIssuer>
    </issuerInformation>
    <signatureInfo>
      <issuerSignature>
        <issuer>Minimal Inc.</issuer>
        <issuerSignature>Jane Doe</issuerSignature>
        <issuerTitle>CEO</issuerTitle>
      </issuerSignature>
      <signaturePersons>
        <signaturePerson>
          <personSignature>Jane Doe</personSignature>
          <personTitle>CEO</personTitle>
          <signatureDate>03-28-2024</signatureDate>
        </signaturePerson>
      </signaturePersons>
    </signatureInfo>
  </formData>
</edgarSubmission>"""


def test_formc_missing_optional_elements_silence_check():
    """Missing filerCcc, empty flags, TEST filings parse without raising (edgartools-nqoi)."""
    formC: FormC = FormC.from_xml(MINIMAL_FORMC_XML, form="C-TR")
    assert formC.filer_information.ccc is None  # absent element -> None, not an exception
    assert formC.filer_information.live_or_test is False  # TEST filing
    assert formC.filer_information.confirming_copy_flag is False
    assert formC.issuer_information.name == "Minimal Inc."
    assert formC.issuer_information.address.street2 is None
    assert formC.offering_information is None
    assert formC.annual_report_disclosure is None
