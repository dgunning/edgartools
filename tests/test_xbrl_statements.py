from pathlib import Path
from rich import print
import pytest
from typing import Dict, Tuple

from edgar import Financials
from edgar.xbrl import XBRLData, Statement
from edgar.xbrl.xbrldata import StatementDefinition

import pandas as pd


@pytest.fixture
def aapl_xbrl():
    return XBRLData.from_files(
        instance_path=Path('data/xbrl/datafiles/aapl/aapl-20230930_htm.xml'),
        label_path=Path('data/xbrl/datafiles/aapl/aapl-20230930_lab.xml'),
        presentation_path=Path('data/xbrl/datafiles/aapl/aapl-20230930_pre.xml'),
        calculation_path=Path('data/xbrl/datafiles/aapl/aapl-20230930_cal.xml')
    )

def test_cover_page_renders_with_values(aapl_xbrl:XBRLData):
    cover_page:Statement = aapl_xbrl.get_statement('CoverPage')
    assert cover_page
    cover_repr = repr(cover_page)
    print(cover_repr)
    assert "One Apple Park Way" in cover_repr


def test_get_presentation_structure_for_non_dimensioned_statement(aapl_xbrl):
    bs = Financials(aapl_xbrl).get_balance_sheet()
    bs.print_structure()

def test_get_presentation_structure_for_dimensioned_statement(aapl_xbrl):
    sd = aapl_xbrl.get_statement_definition('RevenueNetSalesDisaggregatedbySignificantProductsandServicesDetails')
    sd.print_items()

def test_statement_displays_with_correct_segments(aapl_xbrl:XBRLData):
    sd = aapl_xbrl.get_statement_definition('RevenueNetSalesDisaggregatedbySignificantProductsandServicesDetails')
    line_items = sd.line_items
    assert len(line_items) == 6
    #assert len(statement_definition.line_items) == 6
    line_item = line_items[0]
    assert line_item.concept == 'us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax'
    assert line_item.label == 'Net sales'
    assert line_item.segment == None

    line_item = line_items[1]
    assert line_item.concept == 'us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax'
    assert line_item.label == 'iPhone'
    assert line_item.segment == 'aapl:IPhoneMember'

    statement:Statement = aapl_xbrl.get_statement('RevenueNetSalesDisaggregatedbySignificantProductsandServicesDetails')
    statement_repr = repr(statement)
    print(statement)
    #assert all(label in statement_repr for label in ['Net sales', 'iPhone', 'iPad', 'Mac', 'Wearables', 'Services'])


def test_list_axes_for_statement_definition(aapl_xbrl:XBRLData):
    print()
    print(aapl_xbrl.statements)
    print(aapl_xbrl.statements[7])


def test_statement_dimensional_handling():
    """Test dimensional handling using realistic SEC filing data structure"""

    def create_test_labels() -> Dict:
        """Create a realistic label dictionary as would come from label linkbase"""
        return {
            'us-gaap_Revenue': {
                'label': 'Revenue',
                'terseLabel': 'Revenue',
                'totalLabel': 'Total revenue'
            },
            'us-gaap_GeographicAreasAxis': {
                'label': 'Geographic areas [Axis]',
                'terseLabel': 'Geographic areas'
            },
            'us-gaap_GeographicAreasDomain': {
                'label': 'Geographic areas [Domain]',
                'terseLabel': 'Geographic areas'
            },
            'us-gaap_DomesticOperationsMember': {
                'label': 'Domestic Operations [Member]',
                'terseLabel': 'Domestic'
            },
            'us-gaap_ForeignOperationsMember': {
                'label': 'Foreign Operations [Member]',
                'terseLabel': 'Foreign'
            },
            'us-gaap_ProductAndServiceAxis': {
                'label': 'Products and Services [Axis]',
                'terseLabel': 'Products and Services'
            },
            'us-gaap_ProductsAndServicesDomain': {
                'label': 'Products and Services [Domain]',
                'terseLabel': 'Products and Services'
            },
            'us-gaap_ProductMember': {
                'label': 'Product [Member]',
                'terseLabel': 'Product'
            },
            'us-gaap_ServiceMember': {
                'label': 'Service [Member]',
                'terseLabel': 'Service'
            }
        }

    def create_test_data():
        """Create test data mimicking real SEC filing structure"""
        data = {
            'Revenue': {
                'concept': 'us-gaap_Revenue',
                'level': 0,
                'has_dimensions': True,
                'abstract': False,
                'node_type': 'MainItem',
                'units': 'USD',
                'decimals': '-6',
                'Dec 31, 2023': '1000000000'
            },
            # Geographic breakdown
            'Revenue (Domestic Operations)': {
                'concept': 'us-gaap_Revenue',
                'level': 1,
                'has_dimensions': False,
                'abstract': False,
                'node_type': 'Detail',
                'units': 'USD',
                'decimals': '-6',
                'Dec 31, 2023': '600000000',
                'dimensions': {
                    'us-gaap_GeographicAreasAxis': 'us-gaap_DomesticOperationsMember'
                }
            },
            'Revenue (Foreign Operations)': {
                'concept': 'us-gaap_Revenue',
                'level': 1,
                'has_dimensions': False,
                'abstract': False,
                'node_type': 'Detail',
                'units': 'USD',
                'decimals': '-6',
                'Dec 31, 2023': '400000000',
                'dimensions': {
                    'us-gaap_GeographicAreasAxis': 'us-gaap_ForeignOperationsMember'
                }
            },
            # Product breakdown
            'Revenue (Product)': {
                'concept': 'us-gaap_Revenue',
                'level': 1,
                'has_dimensions': False,
                'abstract': False,
                'node_type': 'Detail',
                'units': 'USD',
                'decimals': '-6',
                'Dec 31, 2023': '700000000',
                'dimensions': {
                    'us-gaap_ProductAndServiceAxis': 'us-gaap_ProductMember'
                }
            },
            'Revenue (Service)': {
                'concept': 'us-gaap_Revenue',
                'level': 1,
                'has_dimensions': False,
                'abstract': False,
                'node_type': 'Detail',
                'units': 'USD',
                'decimals': '-6',
                'Dec 31, 2023': '300000000',
                'dimensions': {
                    'us-gaap_ProductAndServiceAxis': 'us-gaap_ServiceMember'
                }
            }
        }
        df = pd.DataFrame.from_dict(data, orient='index')

        # Create a minimal StatementDefinition with labels
        definition = StatementDefinition(
            role='http://www.example.com/role/ConsolidatedStatementsOfIncome',
            label='Consolidated Statements of Income'
        )
        definition.labels = create_test_labels()

        return Statement(
            name='ConsolidatedStatementsOfIncome',
            entity='Example Corp',
            df=df,
            definition=definition
        )

    # Create test statement
    statement = create_test_data()

    # Test 1: Get base items
    base_items = statement.get_base_items()
    assert len(base_items) == 1
    assert 'Revenue' in base_items.index
    assert base_items.loc['Revenue', 'concept'] == 'us-gaap_Revenue'

    # Test 2: Get dimensional items for concept
    dim_items = statement.get_dimensional_items(concept='us-gaap_Revenue')
    assert len(dim_items) == 4  # Should get all dimensional breakdowns

    # Test 3: Get dimensional items by geography
    geo_items = statement.filter_by_dimension(axis='us-gaap_GeographicAreasAxis')
    assert len(geo_items) == 3  # Base item + 2 geographic breakdowns

    # Test 4: Get dimensional items by product
    product_items = statement.filter_by_dimension(
        axis='us-gaap_ProductAndServiceAxis',
        member='us-gaap_ProductMember'
    )
    assert len(product_items) == 2  # Base item + product breakdown

    # Test 5: Get dimensional structure
    structure = statement.get_dimensional_structure()
    assert 'us-gaap_Revenue' in structure
    assert len(structure['us-gaap_Revenue']['dimensions']) == 4

    # Test 6: Verify dimensional values
    domestic_rev = statement.data.loc['Revenue (Domestic Operations)', 'Dec 31, 2023']
    foreign_rev = statement.data.loc['Revenue (Foreign Operations)', 'Dec 31, 2023']
    assert float(domestic_rev) + float(foreign_rev) == float(statement.data.loc['Revenue', 'Dec 31, 2023'])

    # Test 7: Print structure
    print("\nDimensional Structure:")
    statement.print_dimensional_structure()

    # Test 8: Rich display
    print("\nStatement Display:")
    print(statement)


def test_correct_labels_selected(aapl_xbrl):
    bs = aapl_xbrl.statements['CONSOLIDATEDBALANCESHEETS']
    assert 'Cash and cash equivalents'  in bs.data.index

def test_formatting_of_value_with_decimals_INF(aapl_xbrl):
    se = aapl_xbrl.statements['CONSOLIDATEDSTATEMENTSOFSHAREHOLDERSEQUITY']
    se_repr = repr(se)
    assert 'Dividends and dividend equivalents' in se_repr