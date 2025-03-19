"""
Test module for the XBRL class.

This module demonstrates how to use the XBRL class to parse XBRL files and
extract information from them.
"""

import datetime
from pathlib import Path

import pytest
from rich import print
from rich.console import Console

from edgar import *
from edgar.xbrl2.statements import Statements, Statement
from edgar.xbrl2.xbrl import XBRL


@pytest.fixture
def aapl_xbrl():
    data_dir = Path("data/xbrl/datafiles/aapl")

    # Parse the directory
    return XBRL.parse_directory(data_dir)

def test_dei_info(aapl_xbrl:XBRL):
    assert aapl_xbrl.entity_info.get('entity_name') == 'Apple Inc.'
    assert aapl_xbrl.entity_info.get('identifier') == '320193'
    assert aapl_xbrl.entity_info.get('reporting_end_date') == datetime.date(2023, 10, 20)
    assert aapl_xbrl.entity_info.get('fiscal_year') == 2023
    assert aapl_xbrl.entity_info.get('fiscal_period') == 'FY'

def test_get_coverpage(aapl_xbrl:XBRL):
    print()
    #print(aapl_xbrl)
    cover_page = aapl_xbrl.render_statement('BalanceSheet')
    print(cover_page)
    #print(aapl_xbrl.get_all_statements())

def test_xbrl_statements(aapl_xbrl:XBRL):
    print()
    statements = Statements(aapl_xbrl)
    assert statements

def test_render_balance_sheet_using_short_name_or_standard_name(aapl_xbrl:XBRL):
    print()
    # Standard Name
    statement = aapl_xbrl.render_statement('BalanceSheet')
    print(statement)

    # Short Name
    statement = aapl_xbrl.render_statement('CONSOLIDATEDBALANCESHEETS')
    print(statement)


def test_filtering_of_mostly_empty_columns(aapl_xbrl:XBRL):
    print()
    # Standard Name
    statement = aapl_xbrl.render_statement('BalanceSheet')
    print(statement)

def test_render_cashflow_statement():
    f = Filing(company='Apple Inc.', cik=320193,
               form='10-K', filing_date='2024-11-01', accession_no='0000320193-24-000123')
    xbrl = XBRL.from_filing(f)
    cash_flow = xbrl.render_statement("CashFlowStatement")
    print(cash_flow)


def test_find_facts_for_concept(aapl_xbrl:XBRL):
    print()
    concept = 'us-gaap_CashAndCashEquivalentsAtCarryingValue'
    facts = aapl_xbrl._find_facts_for_element(concept)
    print(f"Facts for concept '{concept}': {len(facts)}")
    print(facts)


def test_find_balance_sheet_facts():
    'us-gaap_Assets'
    f = Filing(company='Apple Inc.', cik=320193,
               form='10-K', filing_date='2024-11-01', accession_no='0000320193-24-000123')
    xbrl = XBRL.from_filing(f)
    facts = xbrl._find_facts_for_element('us-gaap_Assets')
    print(facts)
    balance_sheet = xbrl.render_statement('BalanceSheet')
    print(balance_sheet)


def test_period_views_for_balance_sheet(aapl_xbrl:XBRL):
    print()
    # Get period views for balance sheet
    balance_sheet_views = aapl_xbrl.get_period_views('BalanceSheet')
    print("[bold]Balance Sheet Period Views:[/bold]")
    for view in balance_sheet_views:
        print(f"- {view['name']}: {view['description']}")
        print(f"  Keys: {view['period_keys']}")
    


def test_period_views_for_income_statement(aapl_xbrl:XBRL):
    # Get period views for income statement
    income_statement_views = aapl_xbrl.get_period_views('IncomeStatement')
    print("\n[bold]Income Statement Period Views:[/bold]")
    for view in income_statement_views:
        print(f"- {view['name']}: {view['description']}")
        print(f"  Keys: {view['period_keys']}")

def test_to_pandas(aapl_xbrl:XBRL):
    print()
    print("[bold]Converting XBRL to pandas DataFrames:[/bold]")
    
    # Convert to pandas DataFrames
    dataframes = aapl_xbrl.to_pandas()
    
    # Display available DataFrames
    print(f"Available DataFrames: {list(dataframes.keys())}")
    
    # Show sample of facts DataFrame
    if 'facts' in dataframes:
        print("\n[bold]Facts DataFrame Sample:[/bold]")
        facts_df = dataframes['facts']
        print(f"Shape: {facts_df.shape}")
        print(facts_df.head(3))
    
    # Convert specific statement to DataFrame
    balance_sheet_df = aapl_xbrl.to_pandas('BalanceSheet')
    if 'statement' in balance_sheet_df:
        print("\n[bold]Balance Sheet DataFrame Sample:[/bold]")
        statement_df = balance_sheet_df['statement']
        print(f"Shape: {statement_df.shape}")
        print(statement_df.head(3))



def test_get_entity_info(aapl_xbrl):
    entity_info = aapl_xbrl.entity_info
    print()
    print(entity_info)
    assert entity_info.get('annual_report')
    assert not entity_info.get('quarterly_report')


def test_parse_directory():
    """Test parsing a directory of XBRL files."""
    # Get the path to the test files
    data_dir = Path("data/xbrl/datafiles/aapl")
    
    # Parse the directory
    xbrl = XBRL.parse_directory(data_dir)
    print()
    # Print information about the parsed XBRL
    console = Console()
    console.print(xbrl)
    
    # Get all available statements
    statements = xbrl.get_all_statements()
    console.print("[bold]Available Statements:[/bold]")
    for stmt in statements:
        console.print(f"- [{stmt['type'] or 'Other'}] {stmt['definition']}")
    
    # Debug information to understand the element name / ID issue
    console.print("\n[bold]Debug: Element Catalog vs Facts[/bold]")
    # Get first 5 facts
    fact_keys = list(xbrl.facts.keys())[:5]
    for key in fact_keys:
        fact = xbrl.facts[key]
        console.print(f"Fact: element_id={fact.element_id}, context={fact.context_ref}, value={fact.value}")
    
    # Get first 5 elements from catalog
    element_keys = list(xbrl.element_catalog.keys())[:5]
    for key in element_keys:
        elem = xbrl.element_catalog[key]
        console.print(f"Element: id={key}, name={elem.name}")
    
    # Get first 5 nodes from first presentation tree
    if xbrl.presentation_trees:
        first_tree = next(iter(xbrl.presentation_trees.values()))
        node_keys = list(first_tree.all_nodes.keys())[:5]
        for key in node_keys:
            node = first_tree.all_nodes[key]
            console.print(f"Node: id={key}, element_name={node.element_name}, label={node.standard_label}")
    
    # Demonstrate new statement rendering feature
    console.print("\n[bold]Rendering Balance Sheet:[/bold]")
    balance_sheet = xbrl.render_statement("BalanceSheet")
    console.print(balance_sheet)
    
    # Debug: Print sample statement data to see what's happening
    statement_data = xbrl.get_statement("BalanceSheet")
    console.print("\n[bold]Debug: Sample Statement Data[/bold]")
    for i, item in enumerate(statement_data[:5]):
        console.print(f"Item {i}: concept={item['concept']}, all_names={item.get('all_names')}, has_values={item.get('has_values')}")
        if item.get('values'):
            console.print(f"   Values: {item['values']}")
    
    # If available, show stats on line items with values vs. without
    has_values_count = len([item for item in statement_data if item.get('has_values')])
    console.print(f"\nItems with values: {has_values_count} / {len(statement_data)} ({has_values_count/len(statement_data)*100:.1f}%)")
    
    console.print("\n[bold]Rendering Income Statement:[/bold]")
    income_statement = xbrl.render_statement("IncomeStatement")
    console.print(income_statement)
    
    console.print("\n[bold]Rendering Cash Flow Statement:[/bold]")
    cash_flow = xbrl.render_statement("CashFlowStatement")
    console.print(cash_flow)
    
    # Get a specific statement data and display sample line items
    if statements:
        # Find a balance sheet statement if available
        balance_sheet_role = next(
            (stmt['role'] for stmt in statements 
             if stmt['type'] == 'BalanceSheet'),
            statements[0]['role']  # Fallback to first statement if no balance sheet
        )
        
        # Get the statement data
        statement_data = xbrl.get_statement(balance_sheet_role)
        
        console.print(f"\n[bold]Sample line items from {statements[0]['definition']}:[/bold]")
        for i, item in enumerate(statement_data[:10]):  # Show first 10 items
            is_abstract = "[abstract]" if item['is_abstract'] else ""
            # Remove [Abstract] from label if present
            label = item['label'].replace(' [Abstract]', '')
            console.print(f"- {'  ' * item['level']}{label} {is_abstract}")
            # Show values if any
            if item['values'] and not item['is_abstract']:
                for period, value in item['values'].items():
                    console.print(f"  {'  ' * item['level']}{period}: {value}")
        
        # Convert to pandas DataFrame
        dfs = xbrl.to_pandas(balance_sheet_role)
        console.print("\n[bold]Facts DataFrame Sample:[/bold]")
        console.print(dfs['facts'].head(5))
        
        if 'statement' in dfs:
            console.print("\n[bold]Statement DataFrame Sample:[/bold]")
            console.print(dfs['statement'].head(5))


def test_period_views_for_AAPL():
    c = Company("AAPL")
    filing = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2024-11-01', accession_no='0000320193-24-000123')
    filing = c.latest("10-K")
    print(str(filing))
    xbrl = XBRL.from_filing(filing)

    period_filter ="Three-Year Comparison"

    revenue_facts = xbrl._find_facts_for_element('us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax',
                                                 period_filter)
    print(revenue_facts)

    statement_data = xbrl.get_statement("IncomeStatement")
    values = [
        item['values'] for item in statement_data if item['has_values']
    ]
    print(values)
    statement = xbrl.render_statement("IncomeStatement",period_view="Three-Year Comparison")
    print(statement)


def test_period_views_for_INTC():
    filing = Filing(company='INTEL CORP', cik=50863, form='10-K', filing_date='2025-01-31',accession_no='0000050863-25-000009')
    xbrl = XBRL.from_filing(filing)
    print(xbrl.get_period_views("IncomeStatement"))

    period_filter = "Three Recent Quarters"

    revenue_facts = xbrl._find_facts_for_element('us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax')
    #print(revenue_facts)

    statement = xbrl.render_statement("IncomeStatement", period_view="Three Recent Quarters")
    print(statement)



if __name__ == "__main__":
    test_parse_directory()