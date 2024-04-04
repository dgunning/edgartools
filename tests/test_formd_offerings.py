from pathlib import Path
from edgar import Filing
from edgar.offerings import FormD
from edgar._party import Person
from rich import print

formD_xml1 = Path("data/D.1685REIT.xml").read_text()
formD_xml2 = Path("data/D.APFund.xml").read_text()
formD_xml3 = Path("data/D.Shepards.xml").read_text()


def test_parse_offering_xml():
    offering: FormD = FormD.from_xml(formD_xml1)
    print()
    # print(formD_xml1)
    print(offering)
    assert offering.submission_type == "D"
    assert offering.is_live
    assert offering.primary_issuer.cik == "0001961089"
    assert offering.primary_issuer.primary_address.city == "LOS ANGELES"
    assert offering.primary_issuer.primary_address.state_or_country == "CA"
    assert offering.primary_issuer.primary_address.state_or_country_description == "CALIFORNIA"
    assert offering.primary_issuer.primary_address.street1 == "2029 CENTURY PARK EAST"
    assert offering.primary_issuer.primary_address.street2 == "SUITE 1370"
    assert offering.primary_issuer.jurisdiction == "DELAWARE"
    assert offering.primary_issuer.issuer_previous_names == []
    assert offering.primary_issuer.edgar_previous_names == []
    assert offering.primary_issuer.year_of_incorporation == "2022"
    assert offering.primary_issuer.incorporated_within_5_years

    # Related persons
    related_persons = offering.related_persons
    assert len(related_persons) == 14

    related_person: Person = related_persons[0]
    assert related_person.first_name == "Daniel"
    assert related_person.last_name == "Belldegrun"
    assert related_person.address.state_or_country == "CA"
    assert related_person.address.street2 == "Suite 1370"

    # Offering data
    assert offering.offering_data.revenue_range == "Decline to Disclose"
    assert offering.offering_data.federal_exemptions == ["06b", "3C", "3C.7"]
    assert offering.offering_data.date_of_first_sale == "2023-01-19"
    assert offering.offering_data.more_than_one_year == False
    assert offering.offering_data.is_equity
    assert offering.offering_data.is_pooled_investment

    # business combination
    assert offering.offering_data.business_combination_transaction.is_business_combination == False

    # Investment Fund Info
    assert offering.offering_data.industry_group.industry_group_type == "REITS and Finance"
    assert offering.offering_data.industry_group.investment_fund_info is None

    assert offering.offering_data.offering_sales_amounts.total_offering_amount == "125000"
    assert offering.offering_data.offering_sales_amounts.total_amount_sold == "125000"
    assert offering.offering_data.offering_sales_amounts.total_remaining == "0"

    assert offering.offering_data.investors.has_non_accredited_investors == False
    assert offering.offering_data.investors.total_already_invested == "125"

    assert offering.offering_data.use_of_proceeds.gross_proceeds_used == "0"

    assert offering.signature_block.authorized_representative == False
    assert len(offering.signature_block.signatures) == 1
    assert offering.signature_block.signatures[0].issuer_name == "1685 38th REIT, L.L.C."
    assert offering.signature_block.signatures[0].signature_name == "Daniel Belldegrun"
    assert offering.signature_block.signatures[0].title == "President and CEO"
    assert offering.signature_block.signatures[0].date == "2023-01-27"


def test_parse_offering_with_multiple_signatures():
    offering: FormD = FormD.from_xml(formD_xml2)
    print()
    assert offering.offering_data.industry_group.industry_group_type == "Pooled Investment Fund"
    assert offering.offering_data.industry_group.investment_fund_info

    assert offering.offering_data.industry_group.investment_fund_info.investment_fund_type == "Venture Capital Fund"
    assert not offering.offering_data.industry_group.investment_fund_info.is_40_act
    print(offering)
    assert len(offering.signature_block.signatures) == 2


def test_parse_offering_with_all_states_sales_compensation():
    offering: FormD = FormD.from_xml(formD_xml3)
    print()
    print(offering)
    assert len(offering.offering_data.sales_compensation_recipients) == 1
    assert offering.offering_data.sales_compensation_recipients[0].name == ""
    assert offering.offering_data.sales_compensation_recipients[0].crd == ""
    assert offering.offering_data.sales_compensation_recipients[0].states_of_solicitation == ["All States"]


def test_formd_industry_group_none():
    filing = Filing(form='D', filing_date='2024-04-03', company='Avise Financial Cooperative, Inc.', cik=2013342, accession_no='0002013342-24-000001')
    formd:FormD = filing.obj()
    assert formd.offering_data.industry_group.investment_fund_info is None

def test_formd_business_combination():
    filing = Filing(form='D/A', filing_date='2024-04-03', company='REMY CAPITAL PARTNERS II L P', cik=920660,
           accession_no='0000935836-24-000336')
    formd: FormD = filing.obj()
    assert formd.offering_data.business_combination_transaction.is_business_combination == False
    assert formd.offering_data.business_combination_transaction.clarification_of_response is None



