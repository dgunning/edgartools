from pathlib import Path

import pytest
from rich import print, tree

from edgar.xbrl.presentation import XBRLPresentation, PresentationElement


@pytest.fixture
def rad_presentation():
    presentation_text = Path('data/xbrl/datafiles/radcq/rad-20230304_pre.xml').read_text()
    return XBRLPresentation.parse(presentation_text)


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


def test_get_members_for_axis(rad_presentation):
    role = 'http://www.riteaid.com/role/DisclosureSummaryOfSignificantAccountingPoliciesDescriptionOfBusinessAssetSaleDetails'
    axis = 'srt_OwnershipAxis'
    members = rad_presentation.get_members_for_axis(role, axis)
    assert members == ['rad_WalgreensMember', 'rad_RiteAidSubsidiariesMember']
    rad_presentation.print_structure(role)


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
