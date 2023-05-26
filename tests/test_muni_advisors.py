from pathlib import Path
from edgar.muniadvisors import MunicipalAdvisorForm
from rich import print
from edgar import Filing


def test_muni_advisors():
    xml = Path('data/MuniAdvisors/goldman.MA-I.xml').read_text()
    ma = MunicipalAdvisorForm.from_xml(xml)

    print(ma)
    # Filer
    assert ma['filer'].cik == '0000769993'


def test_muni_advisors_from_filing():
    filing = Filing(form='MA-I/A', filing_date='2022-12-20', company='RBC Capital Markets, LLC', cik=50916,
                    accession_no='0000050916-22-000028')
    ma = MunicipalAdvisorForm.from_filing(filing)
    assert ma.filing.filing_date == "2022-12-20"
    assert ma.filing.cik == 50916
    # Contact
    assert ma.contact.name == "CHAD EVANS"
    assert ma.contact.phone == "319-350-0507"
    assert ma.contact.email == "CHAD.EVANS@RBC.COM"

    assert ma.internet_notification_addresses == ['SecuritiesLicensingSpecialists@rbc.com']

    assert ma.applicant.name.first_name == "MICHAEL"
    assert ma.applicant.name.middle_name == "REY"
    assert ma.applicant.name.last_name == "MCCAIG"

    assert ma.applicant.number_of_advisory_firms == 1

    # Employment History
    assert ma.employment_history.current_employer.name == "RBC CAPITAL MARKETS, LLC"
    assert ma.employment_history.current_employer.start_date == "06-2016"
    assert ma.employment_history.current_employer.address.city == "LANCASTER"
    assert ma.employment_history.current_employer.address.state_or_country == "PA"
    assert ma.employment_history.current_employer.is_related_to_municipal_advisor == False
    assert ma.employment_history.current_employer.is_related_to_investment == False
    assert ma.employment_history.current_employer.position == "MUNI FINANCE INVESTMENT BANKER"
    assert ma.is_amendment == False
    assert ma.is_individual == True

    assert len(ma.employment_history.previous_employers) == 2
    assert ma.employment_history.previous_employers.iloc[0]['name'] == "JANNY MONTGOMERY SCOTT LLC"
    assert ma.employment_history.previous_employers.iloc[0]['start_date'] == "08-2012"
    assert ma.employment_history.previous_employers.iloc[0]['end_date'] == "05-2016"
    assert ma.employment_history.previous_employers.iloc[0]['is_related_to_municipal_advisor'] == True
    assert ma.employment_history.previous_employers.iloc[0]['is_related_to_investment'] == False

    # Disclosures

    # Criminal Disclosure
    assert ma.disclosures.criminal_disclosure.is_org_convicted_of_felony == False
    assert ma.disclosures.criminal_disclosure.is_org_charged_with_felony == False
    assert ma.disclosures.criminal_disclosure.is_convicted_of_felony == False
    assert ma.disclosures.criminal_disclosure.is_charged_with_felony == False
    assert ma.disclosures.criminal_disclosure.is_charged_with_misdemeanor == False
    assert ma.disclosures.criminal_disclosure.is_convicted_of_misdemeanor == False
    assert ma.disclosures.criminal_disclosure.is_org_convicted_of_misdemeanor == False
    assert ma.disclosures.criminal_disclosure.is_org_charged_with_misdemeanor == False

    # Regulatory Disclosure
    assert ma.disclosures.regulatory_disclosure.is_made_false_statement == False
    assert ma.disclosures.regulatory_disclosure.is_found_made_false_statement == False
    assert ma.disclosures.regulatory_disclosure.is_found_in_cause_of_suspension == False
    assert ma.disclosures.regulatory_disclosure.is_found_in_cause_of_denial == False
    assert ma.disclosures.regulatory_disclosure.is_found_will_fully_aided == False
    assert ma.disclosures.regulatory_disclosure.is_regulatory_complaint == False
    assert ma.disclosures.regulatory_disclosure.is_discipliend == False
    assert ma.disclosures.regulatory_disclosure.is_discipliend == False
    assert ma.disclosures.regulatory_disclosure.is_association_bared == False
    assert ma.disclosures.regulatory_disclosure.is_cause_of_denial == False
    assert ma.disclosures.regulatory_disclosure.is_failed_resonably == False
    assert ma.disclosures.regulatory_disclosure.is_failed_to_supervise == False
    assert ma.disclosures.regulatory_disclosure.is_authorized_to_act_attorney == False
    assert ma.disclosures.regulatory_disclosure.is_final_order == False
    assert ma.disclosures.regulatory_disclosure.is_imposed_penalty == False

    # Investment Disclosure
    assert ma.disclosures.investigation_disclosure.is_investigated == False

    # Civil Disclosure
    assert ma.disclosures.civil_disclosure.is_named_in_civil_proceeding == False
    assert ma.disclosures.civil_disclosure.is_dismissed == False
    assert ma.disclosures.civil_disclosure.is_enjoined == False
    assert ma.disclosures.civil_disclosure.is_found_violation_of_regulation == False

    # Complaint Disclosure
    assert ma.disclosures.complaint_disclosure.is_complaint_pending == False
    assert ma.disclosures.complaint_disclosure.is_complaint_settled == False
    assert ma.disclosures.complaint_disclosure.is_fraud_case_pending == False
    assert ma.disclosures.complaint_disclosure.is_fraud_case_resulting_award == False
    assert ma.disclosures.complaint_disclosure.is_fraud_case_settled == False

    # Termination Disclosure
    assert ma.disclosures.termination_disclosure.is_violated_industry_standards == False
    assert ma.disclosures.termination_disclosure.is_failed_to_supervise == False
    assert ma.disclosures.termination_disclosure.is_involved_in_fraud == False

    # Financial Disclosure
    assert ma.disclosures.financial_disclosure.is_compromised == False
    assert ma.disclosures.financial_disclosure.is_bankruptcy_petition == False
    assert ma.disclosures.financial_disclosure.is_trustee_appointed == False
    assert ma.disclosures.financial_disclosure.is_bond_revoked == False

    # Judgement Disclosure
    assert ma.disclosures.judgement_lien_disclosure.is_lien_against == False

    # Signatures
    assert ma.signature.signature == "CHAD EVANS"
    assert ma.signature.date_signed == "12-20-2022"
    assert ma.signature.title == "Licensing Specialist"

    print()
    print(ma)


def test_municipal_advisors_obj():
    filing = Filing(form='MA-I', filing_date='2023-05-05', company='Bremer Bank National Association', cik=1775321,
                    accession_no='0001775321-23-000007')
    ma: MunicipalAdvisorForm = filing.obj()
    assert ma.filing.form == 'MA-I'
    assert ma.filing.filing_date == '2023-05-05'
