from pathlib import Path
from rich import print
import pytest

from edgar.xbrl import XBRLData, Statement
from edgar.xbrl.dimensions import Dimensions


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


def test_print_statement_presentation_structure(aapl_xbrl):
    statement = aapl_xbrl.get_statement('RevenueNetSalesDisaggregatedbySignificantProductsandServicesDetails')
    statement.print_structure()


def test_statement_displays_with_correct_segments(aapl_xbrl:XBRLData):
    statement_definition = aapl_xbrl.get_statement_definition('RevenueNetSalesDisaggregatedbySignificantProductsandServicesDetails')
    assert len(statement_definition.line_items) == 6
    assert statement_definition.line_items[0].concept == 'us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax'
    assert statement_definition.line_items[0].label == 'Net sales'
    assert statement_definition.line_items[1].concept == 'aapl_IPhoneMember'
    assert statement_definition.line_items[1].label == 'iPhone'

    statement:Statement = aapl_xbrl.get_statement('RevenueNetSalesDisaggregatedbySignificantProductsandServicesDetails')
    statement_repr = repr(statement)
    assert all(label in statement_repr for label in ['Net sales', 'iPhone', 'iPad', 'Mac', 'Wearables', 'Services'])


def test_list_axes_for_statement_definition(aapl_xbrl:XBRLData):
    print()
    print(aapl_xbrl.statements)
    print(aapl_xbrl.statements[7])