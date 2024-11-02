from pathlib import Path

import pytest
from rich import print, tree

from edgar.xbrl import XBRLData, StatementDefinition
from edgar.xbrl.calculations import CalculationLinkbase

from edgar.xbrl.presentation import XBRLPresentation, PresentationElement, get_root_element, get_members_for_axis
from tests.samples import SAMPLE_PRESENTATION_XML, SAMPLE_INSTANCE_XML, SAMPLE_CALCULATION_XML
from edgar.xbrl.presentation import get_axes_for_role


@pytest.fixture
def sample_presentation():
    return XBRLPresentation.parse(SAMPLE_PRESENTATION_XML)


@pytest.fixture
def apple_presentation():
    return XBRLPresentation.parse(Path('data/xbrl/datafiles/aapl/aapl-20230930_pre.xml').read_text())

@pytest.fixture
def sample_xbrl_data(sample_labels):
    return XBRLData.parse(
        instance_xml=SAMPLE_INSTANCE_XML,
        presentation_xml=SAMPLE_PRESENTATION_XML,
        labels=sample_labels,
        calculations=CalculationLinkbase.parse(SAMPLE_CALCULATION_XML))

@pytest.fixture
def rad_presentation():
    presentation_text = Path('data/xbrl/datafiles/radcq/rad-20230304_pre.xml').read_text()
    return XBRLPresentation.parse(presentation_text)

def test_get_root_element(sample_presentation):
    role = sample_presentation.roles['http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS']
    root = get_root_element(role)
    assert root.concept == 'http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS'

    # Test child
    child = root.children[0]
    assert get_root_element(child) == root

    # Test grandchild
    grandchild = root.children[0].children[0]
    assert get_root_element(grandchild) == root





def test_parse_labels_with_namespace():
    presentation_text = Path('data/xbrl/datafiles/aapl/aapl-20230930_pre.xml').read_text()
    presentation: XBRLPresentation = XBRLPresentation.parse(presentation_text)
    print(presentation)


def test_parse_presentation_with_no_namespace(rad_presentation):
    structure = rad_presentation.print_structure()
    print(structure)


def test_presentation_get_structure(rad_presentation):
    structure = rad_presentation.get_structure(detailed=True)
    assert isinstance(structure, tree.Tree)
    assert len(structure.children) > 100


def test_get_axes_for_role(rad_presentation):
    axes = rad_presentation.get_axes_for_role('http://www.riteaid.com/role/StatementConsolidatedBalanceSheets')
    assert axes == []
    role = 'http://www.riteaid.com/role/StatementConsolidatedStatementsOfStockholdersDeficitEquity'
    axes = rad_presentation.get_axes_for_role(role)
    assert axes[0].concept == 'us-gaap_StatementEquityComponentsAxis'

    role = 'http://www.riteaid.com/role/DisclosureSummaryOfSignificantAccountingPoliciesDescriptionOfBusinessAssetSaleDetails'
    axes = rad_presentation.get_axes_for_role(role)
    assert [a.concept for a in axes] == ['srt_OwnershipAxis',
                                         'dei_LegalEntityAxis',
                                         'us-gaap_DisposalGroupClassificationAxis',
                                         'us-gaap_IncomeStatementBalanceSheetAndAdditionalDisclosuresByDisposalGroupsIncludingDiscontinuedOperationsAxis']

def test_get_axes_for_role_with_no_axis(sample_presentation):
    role = sample_presentation.roles['http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS']
    axes = get_axes_for_role(role)
    assert axes == []


def test_get_members_for_axis(rad_presentation):
    role = rad_presentation.roles['http://www.riteaid.com/role/DisclosureSummaryOfSignificantAccountingPoliciesDescriptionOfBusinessAssetSaleDetails']
    axis = get_axes_for_role(role)[0]
    members = rad_presentation.get_members_for_axis(axis)
    assert [m.concept for m in members] == ['rad_WalgreensMember',  'rad_RiteAidSubsidiariesMember']
    #rad_presentation.print_structure(role)


def test_presentation_elements_node_type():
    p = PresentationElement(label='Earnings Per Share', concept='us-gaap:BasicEarningsLossPerShare', order=1, href='#')
    assert p.node_type == 'LineItem'
    # Test Abstract
    p = PresentationElement(label='Abstract', concept='us-gaap:Abstract', order=1, href='#')
    assert p.node_type == 'Abstract'
    # Test Table
    p = PresentationElement(label='Table', concept='us-gaap:SampleTable', order=1, href='#')
    assert p.node_type == 'Table'

    p = PresentationElement(label='Domain', concept='us-gaap:SampleDomain', order=1, href='#')
    assert p.node_type == 'Domain'
    # Test Member
    p = PresentationElement(label='Member', concept='us-gaap:SampleMember', order=1, href='#')
    assert p.node_type == 'Member'
    # Test Axis
    p = PresentationElement(label='Axis', concept='us-gaap:SampleAxis', order=1, href='#')
    assert p.node_type == 'Axis'


def test_presentation_parsing_from_sample():
    presentation = XBRLPresentation.parse(SAMPLE_PRESENTATION_XML)

    # Test role exists
    assert "http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS" in presentation.roles

    # Get the balance sheet root element
    root = presentation.roles["http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS"]

    # Test presentation structure
    assert root.node_type == "Statement"
    assert len(root.children) > 0

    # Test ordering
    statement_abstract = root.children[0]
    assert statement_abstract.node_type == "Abstract"
    statement_table  = statement_abstract.children[0]
    assert statement_table.node_type == "Table"

    # Test that cash and marketable securities are in correct order
    line_items = statement_table.children[0]
    assert line_items.node_type == "LineItems"

    assets_abstract = line_items.children[0]
    assert assets_abstract.node_type == "Abstract"

    current_assets = assets_abstract.children[0]
    assert current_assets.node_type == "LineItem"
    cash = current_assets.children[0]
    assert cash.href.endswith('us-gaap_CashAndCashEquivalentsAtCarryingValue')
    securities = current_assets.children[1]
    assert cash.href.endswith('CashAndCashEquivalentsAtCarryingValue')
    assert securities.href.endswith('MarketableSecuritiesCurrent')
    assert cash.order < securities.order


def test_presentation_node_types():
    presentation = XBRLPresentation.parse(SAMPLE_PRESENTATION_XML)
    root = presentation.roles["http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS"]

    # Test the hierarchy
    assert root.node_type == "Statement"  # StatementOfFinancialPositionAbstract

    table = root.children[0]
    assert table.node_type == "Abstract"  # StatementTable

    line_items = table.children[0]
    assert line_items.node_type == "Table"  # StatementLineItems

    assets = line_items.children[0]
    assert assets.node_type == "LineItems"  # AssetsAbstract

    current_assets = assets.children[0]
    assert current_assets.node_type == "Abstract"  # AssetsCurrent

    # Test finding line items container
    line_items_container = StatementDefinition._find_line_items_container(root)
    assert line_items_container is not None
    assert line_items_container.node_type == "LineItems"
    assert line_items_container.concept.endswith('StatementLineItems')

def test_xbrl_presentation_list_roles():
    presentation = XBRLPresentation.parse(Path('data/xbrl/datafiles/aapl/aapl-20230930_pre.xml').read_text())
    roles = presentation.list_roles()
    assert 'http://www.apple.com/role/Leases' in roles



