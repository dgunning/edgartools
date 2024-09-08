import datetime
import re
from pathlib import Path

import pytest
from rich import print

from edgar import Filing
from edgar.core import extract_text_between_tags
from edgar.filingheader import preprocess_old_headers, FilingHeader, Filer


@pytest.fixture(scope='module')
def carbo_ceramics_header():
    return Filing(form='10-K', company='CARBO CERAMICS INC', cik=1009672, filing_date='2018-03-08',
                  accession_no='0001564590-18-004771').header


@pytest.fixture(scope='module')
def berkshire_hills_header():
    return Filing(form='SC 13G/A', filing_date='2024-01-23', company='BERKSHIRE HILLS BANCORP INC', cik=1108134,
                  accession_no='0001086364-24-001430').header


def test_filing_sec_header(carbo_ceramics_header):
    filing_header: FilingHeader = carbo_ceramics_header
    assert len(filing_header.filers) == 1
    filer = filing_header.filers[0]
    assert filer
    assert filer.company_information.name == 'CARBO CERAMICS INC'
    assert filer.company_information.cik == '0001009672'
    assert filer.company_information.irs_number == '721100013'
    assert filer.company_information.state_of_incorporation == 'DE'
    assert filer.company_information.fiscal_year_end == '1231'
    assert filer.company_information.sic == 'ABRASIVE ASBESTOS & MISC NONMETALLIC MINERAL PRODUCTS [3290]'

    assert filer.filing_information.form == '10-K'
    assert filer.filing_information.file_number == '001-15903'
    assert filer.filing_information.film_number == '18674418'
    assert filer.filing_information.sec_act == '1934 Act'

    assert filer.business_address.street1 == '575 NORTH DAIRY ASHFORD'
    assert filer.business_address.street2 == 'SUITE 300'
    assert filer.business_address.city == 'HOUSTON'
    assert filer.business_address.state_or_country == 'TX'
    assert filer.business_address.zipcode == '77079'


def test_parse_filing_header_with_filer():
    header_content = Path('data/secheader.424B5.abeona.txt').read_text()
    filing_header = FilingHeader.parse_from_sgml_text(header_content)
    print()
    print(filing_header)
    # Metadata
    assert filing_header.filing_metadata
    assert filing_header.filing_metadata['FILED AS OF DATE'] == '2023-06-07'
    assert filing_header.filing_date == '2023-06-07'
    assert filing_header.accession_number == '0001493152-23-020412'
    assert filing_header.acceptance_datetime == datetime.datetime(2023, 6, 7, 16, 10, 23)

    # FILERS
    assert filing_header.filers
    filer = filing_header.filers[0]

    # Company Information
    assert filer.company_information.name == 'ABEONA THERAPEUTICS INC.'
    assert filer.company_information.cik == '0000318306'
    assert filer.company_information.irs_number == '830221517'
    assert filer.company_information.state_of_incorporation == 'DE'
    assert filer.company_information.fiscal_year_end == '1231'
    assert filer.company_information.sic == 'PHARMACEUTICAL PREPARATIONS [2834]'

    # Business Address
    assert filer.business_address.street1 == '6555 CARNEGIE AVE, 4TH FLOOR'
    assert filer.business_address.city == 'CLEVELAND'
    assert filer.business_address.state_or_country == 'OH'
    assert filer.business_address.zipcode == '44103'

    # Mailing Address
    assert filer.mailing_address.street1 == '6555 CARNEGIE AVE, 4TH FLOOR'
    assert filer.mailing_address.city == 'CLEVELAND'
    assert filer.mailing_address.state_or_country == 'OH'
    assert filer.mailing_address.zipcode == '44103'

    assert len(filer.former_company_names) == 3
    assert filer.former_company_names[0].name == 'PLASMATECH BIOPHARMACEUTICALS INC'

    assert not filing_header.reporting_owners
    assert not filing_header.issuers

    # Goldman Sachs
    # This Goldman Sachs filing has an extra : in the Street2 field
    # 		STREET 2:		ATT: PRIVATE CREDIT GROUP
    header_content = Path('data/secheader.N2A.goldman.txt').read_text()
    print(header_content)
    filing_header = FilingHeader.parse_from_sgml_text(header_content)
    assert filing_header.filers[0].business_address.street1 == '200 WEST STREET'
    assert filing_header.filers[0].business_address.street2 == 'ATT: PRIVATE CREDIT GROUP'


def test_parse_filing_header_with_reporting_owner():
    header_content = Path('data/secheader.4.evercommerce.txt').read_text()
    print(header_content)
    filing_header = FilingHeader.parse_from_sgml_text(header_content)
    print(filing_header)

    assert filing_header.filers == []
    reporting_owner = filing_header.reporting_owners[0]
    assert reporting_owner
    assert reporting_owner.owner.name == 'Shane Driggers'
    assert reporting_owner.owner.cik == '0001927858'
    assert reporting_owner.filing_information.form == '4'
    assert reporting_owner.filing_information.file_number == '001-40575'
    assert reporting_owner.filing_information.film_number == '23997535'

    assert filing_header.issuers
    issuer = filing_header.issuers[0]
    assert issuer.company_information.name == 'EverCommerce Inc.'
    assert issuer.company_information.cik == '0001853145'
    assert issuer.company_information.sic == 'SERVICES-PREPACKAGED SOFTWARE [7372]'
    assert issuer.company_information.irs_number == '814063428'
    assert issuer.company_information.state_of_incorporation == 'DE'

    assert issuer.business_address.street1 == '3601 WALNUT STREET'
    assert issuer.business_address.street2 == 'SUITE 400'
    assert issuer.business_address.city == 'DENVER'
    assert issuer.business_address.state_or_country == 'CO'
    assert issuer.business_address.zipcode == '80205'


def test_period_of_report_from_filing_header():
    filing = Filing(form='13F-HR', filing_date='2023-09-21', company='Halpern Financial, Inc.', cik=1994335,
                    accession_no='0001994335-23-000001')
    filing_header = filing.header
    assert filing_header.period_of_report == '2019-12-31'


def test_parse_header_with_subject_company():
    filing_header = FilingHeader.parse_from_sgml_text("""
<ACCEPTANCE-DATETIME>20230612150550
ACCESSION NUMBER:		0001971857-23-000246
CONFORMED SUBMISSION TYPE:	144
PUBLIC DOCUMENT COUNT:		1
FILED AS OF DATE:		20230612
DATE AS OF CHANGE:		20230612

SUBJECT COMPANY:	

	COMPANY DATA:	
		COMPANY CONFORMED NAME:			CONSUMERS ENERGY CO
		CENTRAL INDEX KEY:			0000201533
		STANDARD INDUSTRIAL CLASSIFICATION:	ELECTRIC & OTHER SERVICES COMBINED [4931]
		IRS NUMBER:				380442310
		STATE OF INCORPORATION:			MI
		FISCAL YEAR END:			1231

	FILING VALUES:
		FORM TYPE:		144
		SEC ACT:		1933 Act
		SEC FILE NUMBER:	001-05611
		FILM NUMBER:		231007818

	BUSINESS ADDRESS:	
		STREET 1:		ONE ENERGY PLAZA
		CITY:			JACKSON
		STATE:			MI
		ZIP:			49201
		BUSINESS PHONE:		5177880550

	MAIL ADDRESS:	
		STREET 1:		ONE ENERGY PLAZA
		CITY:			JACKSON
		STATE:			MI
		ZIP:			49201

	FORMER COMPANY:	
		FORMER CONFORMED NAME:	CONSUMERS POWER CO
		DATE OF NAME CHANGE:	19920703

REPORTING-OWNER:	

	COMPANY DATA:	
		COMPANY CONFORMED NAME:			Hendrian Catherine A
		CENTRAL INDEX KEY:			0001701746

	FILING VALUES:
		FORM TYPE:		144

	MAIL ADDRESS:	
		STREET 1:		ONE ENERGY PLAZA
		CITY:			JACKSON
		STATE:			MI
		ZIP:			49201
		""")
    print(filing_header)
    assert filing_header.subject_companies
    subject_company = filing_header.subject_companies[0]
    assert subject_company.company_information.name == 'CONSUMERS ENERGY CO'
    assert subject_company.company_information.cik == '0000201533'
    assert subject_company.company_information.sic == 'ELECTRIC & OTHER SERVICES COMBINED [4931]'
    assert subject_company.company_information.irs_number == '380442310'
    assert subject_company.company_information.state_of_incorporation == 'MI'
    assert subject_company.company_information.fiscal_year_end == '1231'

    assert subject_company.business_address.street1 == 'ONE ENERGY PLAZA'
    assert subject_company.business_address.city == 'JACKSON'
    assert subject_company.business_address.state_or_country == 'MI'
    assert subject_company.business_address.zipcode == '49201'

    assert subject_company.mailing_address.street1 == 'ONE ENERGY PLAZA'
    assert subject_company.mailing_address.city == 'JACKSON'
    assert subject_company.mailing_address.state_or_country == 'MI'
    assert subject_company.mailing_address.zipcode == '49201'

    # Reporting owner
    assert filing_header.reporting_owners
    reporting_owner = filing_header.reporting_owners[0]
    assert reporting_owner.company_information.name == 'Hendrian Catherine A'
    assert reporting_owner.company_information.cik == '0001701746'

    assert len(subject_company.former_company_names) == 1


def test_parse_header_filing_with_multiple_filers():
    # Formatting this file screws up the test. The text should be tight to the left margin
    header_text = Path('data/MultipleFilersHeader.txt').read_text()
    filing_header = FilingHeader.parse_from_sgml_text(header_text)
    print(filing_header)
    assert len(filing_header.filers) == 2

    filer0 = filing_header.filers[0]
    assert filer0.company_information.name == 'First National Master Note Trust'
    assert filer0.company_information.cik == '0001396730'
    assert filer0.company_information.irs_number == '000000000'
    assert filer0.company_information.state_of_incorporation == 'DE'
    assert filer0.filing_information.form == '10-D'
    assert filer0.filing_information.sec_act == '1934 Act'
    assert filer0.filing_information.file_number == '333-140273-01'
    assert filer0.filing_information.film_number == '231004915'
    assert filer0.business_address.street1 == '1620 DODGE STREET STOP CODE 3395'
    assert filer0.business_address.city == 'OMAHA'
    assert filer0.business_address.state_or_country == 'NE'
    assert filer0.business_address.zipcode == '68197'
    assert filer0.mailing_address.street1 == '1620 DODGE STREET STOP CODE 3395'
    assert filer0.mailing_address.city == 'OMAHA'
    assert filer0.mailing_address.state_or_country == 'NE'
    assert filer0.mailing_address.zipcode == '68197'

    filer1 = filing_header.filers[1]
    assert filer1.company_information.name == 'FIRST NATIONAL FUNDING LLC'
    assert filer1.company_information.cik == '0001171040'
    assert filer1.company_information.irs_number == '000000000'
    assert filer1.company_information.state_of_incorporation == 'NE'
    assert filer1.filing_information.form == '10-D'
    assert filer1.filing_information.sec_act == '1934 Act'
    assert filer1.filing_information.file_number == '000-50139'
    assert filer1.filing_information.film_number == '231004916'
    assert not filer1.business_address


def test_parse_header_filing_with_multiple_former_companies():
    header_text = Path('data/MultipleFormerCompaniesHeader.txt').read_text()
    filing_header = FilingHeader.parse_from_sgml_text(header_text)
    print(filing_header)
    assert len(filing_header.filers) == 1
    filer: Filer = filing_header.filers[0]
    assert len(filer.former_company_names) == 3
    assert filer.former_company_names[0].name == 'PEPTIDE TECHNOLOGIES, INC.'
    assert filer.former_company_names[1].name == 'Eternelle Skincare Products Inc.'
    assert filer.former_company_names[2].name == 'PEPTIDE TECHNOLOGIES, INC.'
    assert filer.former_company_names[0].date_of_change == '20180309'
    assert filer.former_company_names[1].date_of_change == '20170621'
    assert filer.former_company_names[2].date_of_change == '20111007'


def test_filing_header_for_fund():
    filing = Filing(form='497K', filing_date='2022-11-01', company='JAMES ADVANTAGE FUNDS', cik=1045487,
                    accession_no='0001398344-22-021082')
    header = filing.header
    # We don't have partially parsed keys like "/SERIES"
    assert header.filing_metadata.get("/SERIES") is None


def test_file_number():
    filing = Filing(form='4', filing_date='2024-01-23', company='22NW Fund GP, LLC', cik=1770575,
                    accession_no='0001193805-24-000084')
    assert '001-39061' in filing.header.file_numbers

    filing = Filing(form='D', filing_date='2024-01-23', company='AE INDUSTRIAL PARTNERS RSA AGGREGATOR, LP - SERIES 1',
                    cik=2009156, accession_no='0002009156-24-000001')
    assert '021-503213' in filing.header.file_numbers


def test_file_number_for_filing_with_many_filers():
    filing = Filing(form='40-APP', filing_date='2024-01-05', company='A-A European Senior Debt Fund, L.P.', cik=1531061,
                    accession_no='0001193125-24-003453')
    assert '812-15538' in filing.header.file_numbers
    assert len(filing.header.file_numbers) == 239


def test_filing_number_from_subject_company(berkshire_hills_header):
    assert '005-60595' in berkshire_hills_header.file_numbers


def test_header_properties(berkshire_hills_header):
    print()
    print(berkshire_hills_header.filing_metadata)
    assert berkshire_hills_header.document_count == 1
    assert berkshire_hills_header.form == 'SC 13G/A'
    assert berkshire_hills_header.date_as_of_change == '2024-01-23'
    assert berkshire_hills_header.filing_date == '2024-01-23'
    assert berkshire_hills_header.acceptance_datetime == datetime.datetime(2024, 1, 23, 11, 52, 32)
    assert berkshire_hills_header.accession_number == '0001086364-24-001430'
    assert berkshire_hills_header.period_of_report is None


def test_parse_header_from_the_1990s():
    header_text = Path('data/1990sheader.txt').read_text()
    header_text = extract_text_between_tags(header_text, 'SEC-HEADER')
    cleaned_header_text = re.sub(r'^(?!<ACCEPTANCE-DATETIME>).*<[^>]+>.*$', '', header_text, flags=re.MULTILINE)
    print(cleaned_header_text)
    # header:FilingHeader = FilingHeader.parse(header_text)


old_text = """
<REPORTING-OWNER>
COMPANY DATA:
    COMPANY CONFORMED NAME:         CANTALUPO JAMES R
    CENTRAL INDEX KEY:              0001012325
    STANDARD INDUSTRIAL CLASSIFICATION:     []
<RELATIONSHIP>DIRECTOR
FILING VALUES:
    FORM TYPE:      4
BUSINESS ADDRESS:
    STREET 1:       100 NORTH RIVERSIDE PLAZA
    CITY:           CHICAGO
    STATE:          IL
    ZIP:            60606
MAIL ADDRESS:
    STREET 1:       100 NORTH RIVERSIDE PLAZA
    CITY:           CHICAGO
    STATE:          IL
    ZIP:            60606
</REPORTING-OWNER>
"""


def test_preprocess_old_headers():
    new_text = preprocess_old_headers(old_text)
    print(new_text)
    assert not "RELATIONSHIP" in new_text
    assert not "REPORTING-OWNER" in new_text
    assert not "DIRECTOR" in new_text


def test_preprocess_actual_old_header():
    header_text = Path('data/1990sheader.txt').read_text()
    new_text = preprocess_old_headers(header_text)

    header: FilingHeader = FilingHeader.parse_from_sgml_text(new_text)
    assert header.accession_number == '0001012325-98-000004'
    assert len(header.subject_companies) == 1

    # Preprocess before parsing
    header: FilingHeader = FilingHeader.parse_from_sgml_text(header_text, preprocess=True)
    assert header.accession_number == '0001012325-98-000004'
    assert len(header.subject_companies) == 1

    # Don't preprocess before parsing
    with pytest.raises(KeyError):
        header: FilingHeader = FilingHeader.parse_from_sgml_text(header_text, preprocess=False)


def test_get_header_from_old_filing():
    filing = Filing(form='4', filing_date='1998-11-20', company='CANTALUPO JAMES R', cik=1012325,
                    accession_no='0001012325-98-000004')
    header = filing.header
    assert header.accession_number == '0001012325-98-000004'


def test_get_header_for_filing_with_no_reportingowner_entity():
    filing = Filing(form='4', filing_date='2024-08-23', company='Hut 8 Corp.', cik=1964789,
                    accession_no='0001127602-24-022866')
    header = filing.header
    assert header

def test_get_header_for_list_fields():
    filing = Filing(form='SC 13G', filing_date='2024-09-06', company='BioCardia, Inc.', cik=925741,
                    accession_no='0001213900-24-076658')
    
    members = filing.header.filing_metadata.get("GROUP MEMBERS") 
    assert members == "DANIEL B. ASHER, MITCHELL P. KOPIN"

def test_get_header_for_list_fields_with_multiple_entries():
    # Inject a new field with multiple entries
    header_content = Path('data/secheader.424B5.abeona.txt').read_text()
    header_content = f"""{header_content[:-len('</SEC-HEADER>')]}
<TEST-FIELD>foo
<TEST-FIELD>bar
</SEC-HEADER>"""

    filing_header = FilingHeader.parse_from_sgml_text(header_content)
    
    assert filing_header.filing_metadata.get("TEST-FIELD") == "foo, bar"