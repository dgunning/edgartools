from pathlib import Path

import pytest
from rich import print

from edgar import *
from edgar.xbrl import get_xbrl_object
from edgar.xbrl.calculations import CalculationLinkbase
from edgar.xbrl.xbrldata import format_xbrl_value
from edgar.xbrl.xbrldata import (parse_label_linkbase, parse_definition_linkbase,
                                 XBRLAttachments,
                                 XBRLInstance, XBRLPresentation, StatementDefinition, Statement)

from tests.samples import SAMPLE_INSTANCE_XML, SAMPLE_PRESENTATION_XML, SAMPLE_CALCULATION_XML

@pytest.fixture
def sample_instance():
    return XBRLInstance.parse(SAMPLE_INSTANCE_XML)


@pytest.fixture
def sample_presentation():
    return XBRLPresentation.parse(SAMPLE_PRESENTATION_XML)


@pytest.fixture
def sample_labels():
    return {
        'us-gaap_StatementOfFinancialPositionAbstract': {
            'label': 'Statement of Financial Position [Abstract]'
        },
        'us-gaap_AssetsAbstract': {
            'label': 'Assets [Abstract]'
        },
        'us-gaap_AssetsCurrent': {
            'label': 'Total Current Assets',
            'totalLabel': 'Total Current Assets'
        },
        'us-gaap_CashAndCashEquivalentsAtCarryingValue': {
            'label': 'Cash and Cash Equivalents',
            'terseLabel': 'Cash and cash equivalents'
        },
        'us-gaap_MarketableSecuritiesCurrent': {
            'label': 'Marketable Securities, Current',
            'terseLabel': 'Marketable securities'
        }
    }



@pytest.fixture
def sample_calculations():
    return CalculationLinkbase.parse(SAMPLE_INSTANCE_XML)


@pytest.fixture
def sample_xbrl_data(sample_labels):
    return XBRLData.parse(
        instance_xml=SAMPLE_INSTANCE_XML,
        presentation_xml=SAMPLE_PRESENTATION_XML,
        labels=sample_labels,
        calculations=CalculationLinkbase.parse(SAMPLE_CALCULATION_XML)
    )


def test_instance_parsing():
    instance = XBRLInstance.parse(SAMPLE_INSTANCE_XML)

    # Test basic instance properties
    assert instance.get_entity_name() == "APPLE INC"
    assert instance.get_document_period() == "2023-09-30"

    # Test fact values
    cash = instance.query_facts(concept='us-gaap:CashAndCashEquivalentsAtCarryingValue')
    assert len(cash) == 1
    assert cash.iloc[0]['value'] == '29965000000'
    assert cash.iloc[0]['decimals'] == '-6'
    assert cash.iloc[0]['units'] == 'USD'




def test_xbrl_instance_parsing(sample_instance):
    assert len(sample_instance.facts) == 5
    assert sample_instance.get_document_period() == '2023-09-30'


def test_xbrl_instance_query_facts(sample_instance):
    assets = sample_instance.query_facts(concept='us-gaap:AssetsCurrent')
    assert len(assets) == 1
    assert assets.iloc[0]['value'] == '154770000000'


def test_financial_statement_creation(sample_instance, sample_presentation, sample_labels, sample_calculations):
    role = "http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS"
    xbrl_data = XBRLData(
        instance=sample_instance,
        presentation=sample_presentation,
        labels=sample_labels,
        calculations=sample_calculations
    )
    statement = StatementDefinition.create(
        "Balance Sheet",
        sample_presentation.roles[role],
        sample_labels,
        xbrl_data
    )
    assert statement.name == "Balance Sheet"
    assert len(statement.line_items) == 3


def test_xbrl_parser_get_financial_statement(sample_instance, sample_presentation, sample_labels, sample_calculations):
    parser = XBRLData(
        instance=sample_instance,
        presentation=sample_presentation,
        labels=sample_labels,
        calculations=sample_calculations
    )
    parser.parse_financial_statements()

    statement: Statement = parser.get_statement("CONSOLIDATEDBALANCESHEETS")
    assert statement is not None
    assert 'Total Current Assets' in [l.strip() for l in statement.labels]
    assert 'Cash and cash equivalents' in [l.strip() for l in statement.labels]
    assert '2023' in statement.periods
    print()
    print(statement)


@pytest.mark.asyncio
async def test_xbrl_parser_from_filing():
    filing = Filing(company='Accenture plc', cik=1467373, form='10-K', filing_date='2023-10-12',
                    accession_no='0001467373-23-000324')

    xbrl_data = await XBRLData.from_filing(filing)
    assert isinstance(xbrl_data, XBRLData)
    assert isinstance(xbrl_data.instance, XBRLInstance)
    assert isinstance(xbrl_data.presentation, XBRLPresentation)


def test_parse_xbrl_presentation():
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




def test_parse_labels():
    labels = parse_label_linkbase(Path('data/xbrl/datafiles/aapl/aapl-20230930_lab.xml').read_text())
    assert labels['us-gaap_ResearchAndDevelopmentExpense']['label'] == 'Research and Development Expense'


def test_parse_definitions():
    definitions = parse_definition_linkbase(Path('data/xbrl/datafiles/aapl/aapl-20230930_def.xml').read_text())
    assert definitions


@pytest.mark.asyncio
async def test_parse_xbrl_document_for_filing_with_embedded_linkbase():
    filing = Filing(company='HUBSPOT INC', cik=1404655, form='10-K', filing_date='2024-02-14',
                    accession_no='0000950170-24-015277')
    xbrl_documents = XBRLAttachments(filing.attachments)
    instance_xml, presentation_xml, labels, calculations = await xbrl_documents.load()
    assert presentation_xml
    assert labels
    assert calculations
    assert instance_xml

    xbrl_data: XBRLData = await XBRLData.from_filing(filing)
    assert xbrl_data
    assert len(xbrl_data.statements) == 98


def test_financial_filing_with_no_attachments():
    filing = Filing(form='10-Q', filing_date='2024-07-15', company='Legacy Education Alliance, Inc.', cik=1561880,
                    accession_no='0001493152-24-027895')
    xbrl_data = XBRLData.extract(filing)
    assert xbrl_data is None


def test_filing_with_no_namespace_labels():
    filing = Filing(form='10-K/A', filing_date='2024-07-25', company='RITE AID CORP',
                    cik=84129, accession_no='0001558370-24-010167')
    xbrl_documents: XBRLAttachments = XBRLAttachments(filing.attachments)
    assert xbrl_documents.get('label') is not None
    print(xbrl_documents)
    xbrl_data: XBRLData = XBRLData.extract(filing)
    print(xbrl_data.labels)


@pytest.fixture(scope='class')
def rbc_424b2():
    return Filing(form='424B2', filing_date='2024-07-30', company='ROYAL BANK OF CANADA', cik=1000275,
                  accession_no='0000950103-24-011024')


@pytest.fixture(scope='class')
def wisdomtree_485bpos_filing():
    return Filing(form='485BPOS', filing_date='2024-07-30', company='WisdomTree Trust', cik=1350487,
                  accession_no='0001214659-24-013179')


def test_get_xbrl_documents_for_offering_xbrl_filing(rbc_424b2):
    xbrl_documents: XBRLAttachments = XBRLAttachments(rbc_424b2.attachments)
    assert not xbrl_documents.empty
    assert xbrl_documents.has_instance_document
    assert xbrl_documents.instance_only

    xbrl_instance: XBRLInstance = xbrl_documents.get_xbrl_instance()
    assert xbrl_instance
    assert len(xbrl_instance.facts) == 8
    print(xbrl_instance)
    print(xbrl_instance.facts)


def test_get_xbrl_data_for_485bpos(wisdomtree_485bpos_filing):
    xbrl_documents: XBRLAttachments = XBRLAttachments(wisdomtree_485bpos_filing.attachments)
    assert not xbrl_documents.empty
    assert xbrl_documents.has_instance_document
    assert not xbrl_documents.instance_only
    xbrl_data: XBRLData = XBRLData.extract(wisdomtree_485bpos_filing)
    assert xbrl_data
    print(xbrl_data)


def test_xbrl_documents_get_xbrlinstance_or_xbrldata(wisdomtree_485bpos_filing, rbc_424b2):
    xbrl_documents: XBRLAttachments = XBRLAttachments(wisdomtree_485bpos_filing.attachments)
    xbrl_data = xbrl_documents.get_xbrl()
    assert xbrl_data
    assert isinstance(xbrl_data, XBRLData)

    xbrl_documents_rbc: XBRLAttachments = XBRLAttachments(rbc_424b2.attachments)
    xbrl_instance = xbrl_documents_rbc.get_xbrl()
    assert xbrl_instance
    assert isinstance(xbrl_instance, XBRLInstance)


def test_xbrl_data_from_485bpos_xbrl(wisdomtree_485bpos_filing):
    xbrl_data: XBRLData = XBRLData.extract(wisdomtree_485bpos_filing)
    assert xbrl_data
    print(xbrl_data.list_statement_definitions())


def _temp_disabled_test_format_xbrl_value():
    # Test case with decimals = '-6'
    assert format_xbrl_value('141988000000', '-6') == '        141,988'
    assert format_xbrl_value('6118000000', '-6') == '          6,118'

    # Test case with decimals = 'INF'
    assert format_xbrl_value('0.62', 'INF') == '           0.62'

    # Test case with decimals = '-3'
    assert format_xbrl_value('1234567', '-3') == '          1,235'
    assert format_xbrl_value('1000', '-3') == '              1'

    # Test case with decimals = '0'
    assert format_xbrl_value('1234', '0') == '          1,234'
    assert format_xbrl_value('0', '0') == '              0'

    # Test case with a non-integer value
    assert format_xbrl_value("non-integer", '0') == '    non-integer'

    # Test case with a negative value and decimals = '-2'
    assert format_xbrl_value('-123456', '-2') == '         -1,235'

    # Test case with a value of zero
    assert format_xbrl_value('0', 'INF') == '            0.0'


def test_get_xbrl():
    # 424B4 should be XBRLInstance
    filing = Filing(form='424B2', filing_date='2024-08-09', company='ROYAL BANK OF CANADA',
                    cik=1000275, accession_no='0000950103-24-012010')
    instance = get_xbrl_object(filing)
    assert isinstance(instance, XBRLInstance)

    # 10-K should be XBRLData
    filing = Filing(form='10-K/A', filing_date='2024-08-09', company='TG THERAPEUTICS, INC.',
                    cik=1001316, accession_no='0001437749-24-025850')
    xbrl_data = get_xbrl_object(filing)
    assert isinstance(xbrl_data, XBRLData)

    # Form D should return None
    filing = Filing(form='D', filing_date='2024-08-09', company='102 Lancaster Partners LLC',
                    cik=2032948, accession_no='0002032948-24-000002')
    assert get_xbrl_object(filing) is None


def test_get_dataframe_for_statement_with_no_units_or_decimals():
    """
    For REGN, the cash flow statement is only available in HTML format.
    """
    filing = Filing(company='REGENERON PHARMACEUTICALS, INC.', cik=872589, form='10-K', filing_date='2024-02-05',
                    accession_no='0001804220-24-000009')
    financials = Financials(filing.xbrl())
    cash_flow_statement = financials.get_cash_flow_statement()
    cashflow_dataframe = cash_flow_statement.get_dataframe(include_concept=True, include_format=True)
    assert cashflow_dataframe is not None
    cols = cashflow_dataframe.columns.tolist()
    assert cols == ['2023', 'concept', 'level', 'style']


def test_xbrl_data_from_files():
    xb = XBRLData.from_files(
        instance_path=Path('data/xbrl/datafiles/aapl/aapl-20230930_htm.xml'),
        label_path=Path('data/xbrl/datafiles/aapl/aapl-20230930_lab.xml'),
        presentation_path=Path('data/xbrl/datafiles/aapl/aapl-20230930_pre.xml'),
        calculation_path=Path('data/xbrl/datafiles/aapl/aapl-20230930_cal.xml')
    )
    assert xb
    bs = xb.get_statement('CONSOLIDATEDBALANCESHEETS')
    assert bs
    assert bs.periods == ['2023', '2022']