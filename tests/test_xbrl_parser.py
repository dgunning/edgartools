import asyncio
from pathlib import Path
from typing import Dict

import pytest
from rich import print

from edgar import Filing
from edgar.xbrl.financials import Financials
from edgar.xbrl.parser import (parse_labels, parse_calculation, parse_definitions, XBRLData, XbrlDocuments,
                               XBRLInstance, XBRLPresentation, FinancialStatement, Statements, StatementData)

# Sample XML strings for testing
SAMPLE_INSTANCE_XML = """
<xbrl xml:lang="en-US"
      xmlns="http://www.xbrl.org/2003/instance"
      xmlns:dei="http://xbrl.sec.gov/dei/2023"
      xmlns:us-gaap="http://fasb.org/us-gaap/2023">
    <context id="ctx1">
        <entity><identifier>1234567890</identifier></entity>
        <period>
            <startDate>2023-01-01</startDate>
            <endDate>2023-12-31</endDate>
        </period>
    </context>
    <us-gaap:Assets contextRef="ctx1" unitRef="usd" decimals="-6">1000000</us-gaap:Assets>
    <us-gaap:Liabilities contextRef="ctx1" unitRef="usd" decimals="-6">500000</us-gaap:Liabilities>
    <dei:DocumentPeriodEndDate contextRef="ctx1">2023-12-31</dei:DocumentPeriodEndDate>
</xbrl>
"""

SAMPLE_PRESENTATION_XML = """
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
               xmlns:xlink="http://www.w3.org/1999/xlink"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xsi:schemaLocation="http://www.xbrl.org/2003/linkbase http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd">
<link:roleRef roleURI="http://www.company.com/role/CONSOLIDATEDBALANCESHEETS" xlink:type="simple" xlink:href="aapl-20230930.xsd#CoverPage"/>
<link:presentationLink xlink:role="http://www.company.com/role/CONSOLIDATEDBALANCESHEETS">
    <link:loc xlink:label="loc_assets" xlink:href="#us-gaap_Assets"/>
    <link:loc xlink:label="loc_liabilities" xlink:href="#us-gaap_Liabilities"/>
    <link:presentationArc xlink:from="assets" xlink:to="liabilities" order="1"/>
</link:presentationLink>
</link:linkbase>
"""


@pytest.fixture
def sample_instance():
    return XBRLInstance.parse(SAMPLE_INSTANCE_XML)


@pytest.fixture
def sample_presentation():
    return XBRLPresentation.parse(SAMPLE_PRESENTATION_XML)


@pytest.fixture
def sample_labels():
    return {
        'us-gaap_Assets': {'label': 'Assets'},
        'us-gaap_Liabilities': {'label': 'Liabilities'}
    }


@pytest.fixture
def sample_calculations():
    return {}


@pytest.fixture(scope='module')
def apple_xbrl():
    filing: Filing = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2023-11-03',
                            accession_no='0000320193-23-000106')
    return asyncio.run(XBRLData.from_filing(filing))


@pytest.fixture(scope='module')
def netflix_xbrl():
    filing: Filing = Filing(company='NETFLIX INC', cik=1065280, form='10-Q', filing_date='2024-04-22',
                            accession_no='0001065280-24-000128')
    return asyncio.run(XBRLData.from_filing(filing))


@pytest.fixture(scope='module')
def crowdstrike_xbrl():
    filing = Filing(company='CrowdStrike Holdings, Inc.', cik=1535527, form='10-K', filing_date='2024-03-07',
                    accession_no='0001535527-24-000007')
    return asyncio.run(XBRLData.from_filing(filing))


@pytest.fixture(scope='module')
def orcl_xbrl():
    filing = Filing(company='ORACLE CORP', cik=1341439, form='10-K', filing_date='2024-06-20',
                    accession_no='0000950170-24-075605')
    return asyncio.run(XBRLData.from_filing(filing))


@pytest.fixture(scope='module')
def msft_xbrl():
    filing = Filing(company='MICROSOFT CORP', cik=789019, form='10-K', filing_date='2023-07-27',
                    accession_no='0000950170-23-035122')
    return asyncio.run(XBRLData.from_filing(filing))


def test_xbrl_instance_parsing(sample_instance):
    assert len(sample_instance.facts) == 3
    assert sample_instance.get_document_period() == '2023-12-31'


def test_xbrl_instance_query_facts(sample_instance):
    assets = sample_instance.query_facts(concept='us-gaap:Assets')
    assert len(assets) == 1
    assert assets.iloc[0]['value'] == '1000000'


def test_xbrl_presentation_parsing(sample_presentation):
    assert len(sample_presentation.roles) == 1
    role = "http://www.company.com/role/CONSOLIDATEDBALANCESHEETS"
    assert role in sample_presentation.roles
    assert len(sample_presentation.roles[role].children) == 2


def test_financial_statement_creation(sample_instance, sample_presentation, sample_labels, sample_calculations):
    role = "http://www.company.com/role/CONSOLIDATEDBALANCESHEETS"
    statement = FinancialStatement.create(
        "Balance Sheet",
        sample_presentation.roles[role],
        sample_labels,
        sample_calculations,
        sample_instance
    )
    assert statement.name == "Balance Sheet"
    assert len(statement.line_items) == 2


def test_xbrl_parser_get_financial_statement(sample_instance, sample_presentation, sample_labels, sample_calculations):
    parser = XBRLData(
        instance=sample_instance,
        presentation=sample_presentation,
        labels=sample_labels,
        calculations=sample_calculations
    )
    parser.parse_financial_statements()

    statement: StatementData = parser.get_statement("CONSOLIDATEDBALANCESHEETS")
    assert statement is not None
    assert 'Assets' in statement.labels
    assert 'Liabilities' in statement.labels
    assert '2023' in statement.periods


@pytest.mark.asyncio
async def test_xbrl_parser_from_filing():
    filing = Filing(company='Accenture plc', cik=1467373, form='10-K', filing_date='2023-10-12',
                    accession_no='0001467373-23-000324')

    parser = await XBRLData.from_filing(filing)
    assert isinstance(parser, XBRLData)
    assert isinstance(parser.instance, XBRLInstance)
    assert isinstance(parser.presentation, XBRLPresentation)


def test_parse_xbrl_presentation(apple_xbrl):
    presentation = XBRLPresentation.parse(Path('data/xbrl/datafiles/aapl/aapl-20230930_pre.xml').read_text())
    _repr_ = repr(presentation)
    print(_repr_)
    assert "EntitiesTable" in _repr_
    assert "A1.375NotesDue2024Member" in _repr_


def test_xbrl_presentation_get_structure_for_role():
    presentation = XBRLPresentation.parse(Path('data/xbrl/datafiles/aapl/aapl-20230930_pre.xml').read_text())
    structure = presentation.get_structure('http://www.apple.com/role/CONSOLIDATEDSTATEMENTSOFOPERATIONS')
    assert structure
    print(structure)


def test_xbrl_presentation_list_roles():
    presentation = XBRLPresentation.parse(Path('data/xbrl/datafiles/aapl/aapl-20230930_pre.xml').read_text())
    roles = presentation.list_roles()
    assert 'http://www.apple.com/role/Leases' in roles


def test_xbrl_presentation_role_with_almost_duplicate_name(apple_xbrl):
    statement = apple_xbrl.statements.get('RevenueDeferredRevenueExpectedTimingofRealizationDetails_1')
    assert statement is None


def test_parse_labels():
    labels = parse_labels(Path('data/xbrl/datafiles/aapl/aapl-20230930_lab.xml').read_text())
    assert labels['us-gaap_ResearchAndDevelopmentExpense']['label'] == 'Research and Development Expense'


def test_parse_calculations():
    calculations = parse_calculation(Path('data/xbrl/datafiles/aapl/aapl-20230930_cal.xml').read_text())
    assert calculations
    assert calculations['http://www.apple.com/role/CONSOLIDATEDSTATEMENTSOFOPERATIONS']


def test_parse_definitions():
    definitions = parse_definitions(Path('data/xbrl/datafiles/aapl/aapl-20230930_def.xml').read_text())
    assert definitions


@pytest.mark.asyncio
async def test_get_shareholder_equity_statement_for_10K(apple_xbrl):
    statement: StatementData = apple_xbrl.get_statement_of_shareholders_equity()
    assert statement
    assert len(statement.data) == 18


@pytest.mark.asyncio
def test_get_statement_name(apple_xbrl):
    statement: StatementData = apple_xbrl.get_cash_flow_statement()
    assert statement.get_statement_name() == 'CONSOLIDATED STATEMENTS OF CASH FLOWS'
    assert apple_xbrl.get_statement_of_shareholders_equity().get_statement_name() == 'CONSOLIDATED STATEMENTS OF SHAREHOLDERS EQUITY'


@pytest.mark.asyncio
async def test_statement_get_concept_value(apple_xbrl):
    statement: StatementData = apple_xbrl.get_statement_of_shareholders_equity()
    concept = statement.get_concept('us-gaap_NetIncomeLoss')
    assert concept.value.get('2023') == '96995000000'
    assert concept.value.get('2022') == '99803000000'
    assert concept.value.get('2021') == '94680000000'
    assert concept.label == 'Net income'
    # try with "NetIncomeLoss"
    concept = statement.get_concept('NetIncomeLoss')
    assert concept


def test_get_balance_sheet(apple_xbrl):
    balance_sheet: StatementData = apple_xbrl.get_balance_sheet()
    assert balance_sheet.periods == ['2023', '2022']


def test_cover_page_aapl(apple_xbrl):
    cover_page = apple_xbrl.get_statement('CoverPage')
    assert cover_page is not None
    assert cover_page.get_concept(label='Entity Registrant Name').values == ['Apple Inc.']


def test_get_concept_using_label(apple_xbrl):
    cover_page: StatementData = apple_xbrl.get_statement('CoverPage', include_concept=True)
    assert cover_page is not None
    fact = cover_page.get_concept(label='Entity Registrant Name')
    assert fact.value['2023'] == 'Apple Inc.'
    assert fact.name == 'dei_EntityRegistrantName'


def test_statements_property(apple_xbrl):
    statements: Statements = apple_xbrl.statements
    assert len(statements) == 78
    assert 'CoverPage' in statements


def test_10Q_filings_have_quarterly_dates(netflix_xbrl):
    balance_sheet: StatementData = netflix_xbrl.get_balance_sheet()
    assert balance_sheet.periods == ['Q1 2024', 'Q4 2023']
    for name in netflix_xbrl.list_statements():
        print(name)


@pytest.mark.asyncio
async def test_parse_xbrl_document_for_filing_with_embedded_linkbase():
    filing = Filing(company='HUBSPOT INC', cik=1404655, form='10-K', filing_date='2024-02-14',
                    accession_no='0000950170-24-015277')
    xbrl_documents = XbrlDocuments(filing.attachments)
    instance_xml, presentation_xml, labels, calculations = await xbrl_documents.load()
    assert presentation_xml
    assert labels
    assert calculations
    assert instance_xml

    xbrl_data: XBRLData = await XBRLData.from_filing(filing)
    assert xbrl_data
    print(xbrl_data.list_statements())
    assert len(xbrl_data.statements) == 98
    statement: StatementData = xbrl_data.get_statement('CoverPage')


@pytest.mark.asyncio
async def test_xbrl_financials_using_non_standard_filing_like_crowdstrike(crowdstrike_xbrl):
    financials: Financials = Financials(crowdstrike_xbrl)

    balance_sheet = financials.get_balance_sheet()
    assert balance_sheet

    comprehensive_income_statement = financials.get_statement_of_comprehensive_income()
    assert comprehensive_income_statement

    cashflow_statement = financials.get_cash_flow_statement()
    assert cashflow_statement

    equity_statement = financials.get_statement_of_changes_in_equity()
    assert equity_statement

    cover_page = financials.get_cover_page()
    assert cover_page

    income_statement = financials.get_income_statement()
    assert income_statement

    for statement in crowdstrike_xbrl.list_statements():
        print(statement)


@pytest.mark.asyncio
async def test_labels_for_orcl_10K(orcl_xbrl):
    presentation: XBRLPresentation = orcl_xbrl.presentation
    labels: Dict = orcl_xbrl.labels
    cover_concept = 'dei_CoverAbstract'
    financials: Financials = Financials(orcl_xbrl)
    balance_sheet = financials.get_balance_sheet()
    print(balance_sheet.labels)
    assert not balance_sheet.labels[0].startswith('us-gaap_')

@pytest.mark.asyncio
async def test_labels_for_msft_10K(msft_xbrl):
    financials: Financials = Financials(msft_xbrl)
    balance_sheet = financials.get_balance_sheet()
    print(balance_sheet.display_name)
    first_label = balance_sheet.data.index[0]
    assert first_label == 'Statement of Financial Position [Abstract]'
    assert not '_' in balance_sheet.labels[0]