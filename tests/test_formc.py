from pathlib import Path
from edgar.offerings import FormCOffering


def test_parse_formc_offering():
    offering_xml = Path("data/pickleball.FormC.xml").read_text()
    print(offering_xml)
    formC:FormCOffering = FormCOffering.from_xml(offering_xml)
    assert formC.issuer_information.commission_cik == "0001348811"
    assert formC.issuer_information.commission_file_number == "008-67202"
    assert formC.issuer_information.company_name == "ANDES CAPITAL GROUP, LLC"
    assert formC.issuer_information.legal_status == "Limited Liability Company"
    assert formC.issuer_information.jurisdiction == "CA"
    assert formC.issuer_information.date_of_incorporation== "12-11-2023"

    # Offering Information
    assert formC.offering_information.compensation_amount.startswith("A fee equal of 3%")
    assert formC.offering_information.financial_interest == "No"
    assert formC.offering_information.security_offered_type == "Other"
    assert formC.offering_information.security_offered_other_desc == "Membership Interests"
    assert formC.offering_information.no_of_security_offered == "41666"
    assert formC.offering_information.price == "1.20000"

    # Annual Report
    assert formC.annual_report_disclosure.total_asset_most_recent_fiscal_year == "0.00"

    assert "NJ" in formC.annual_report_disclosure.offering_jurisdictions

    # Signatures
    signature_info = formC.signature_info
    assert signature_info.issuer_signature.issuer == "Pickleball Etc. LLC"
    assert signature_info.issuer_signature.signature == "Steven Raack"
    assert signature_info.issuer_signature.issuer_title == "Managing Member"


def test_formc_offering_with_annual_report_disclosures():
    offering_xml = Path("data/alto.FormC.xml").read_text()
    print(offering_xml)
    formC: FormCOffering = FormCOffering.from_xml(offering_xml)
    assert formC.issuer_information.commission_cik == "0001665160"

    print(formC)