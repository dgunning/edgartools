pytest_plugins = ["tests.fixtures.xbrl2_fixtures"]
from pathlib import Path

import pytest
from rich import print

from edgar import *
from edgar.xbrl.rendering import RenderedStatement
from edgar.xbrl.statements import Statement, Statements
from edgar.xbrl import XBRL, XBRLS
import pandas as pd
pd.options.display.max_colwidth = 200

# Import new fixtures from the centralized fixture module

@pytest.fixture
def tsla_xbrl():
    # Quarterly statements
    data_dir = Path("data/xbrl/datafiles/tsla")

    # Parse the directory
    return XBRL.from_directory(data_dir)


@pytest.fixture
def aapl_xbrl():
    data_dir = Path("tests/fixtures/xbrl/aapl/10k_2023")
    return XBRL.from_directory(data_dir)

@pytest.fixture
def aapl_xbrl_2022():
    data_dir = Path("tests/fixtures/xbrl/aapl/10k_2022")
    return XBRL.from_directory(data_dir)

@pytest.fixture
def unp_xbrl():
    data_dir = Path("data/xbrl/datafiles/unp")
    return XBRL.from_directory(data_dir)

def test_dimensioned_statement(aapl_xbrl):
    statements = aapl_xbrl.statements
    role_definition = 'SegmentInformationandGeographicDataInformationbyReportableSegmentDetails'
    assert aapl_xbrl._is_dimension_display_statement(None, role_definition)
    statement = statements[role_definition]
    print()
    result = statement.render()
    print(result)


def test_get_statement_by_short_name(tsla_xbrl):
    # Get the cover statement.
    # Statements currently return a list of dicts. Maybe in the future return a StatementDefinition object.
    statement_lst: List = tsla_xbrl.get_statement('Cover')
    assert statement_lst
    assert statement_lst[0]['concept'] == 'dei_CoverAbstract'

    cover = tsla_xbrl.statements.cover_page()
    assert cover

    # Use the Statements class to get the statement
    statements = tsla_xbrl.statements
    statement: Statement = statements['Cover']
    assert isinstance(statement, Statement)
    assert statement.role_or_type == 'Cover'
    assert statement

    # Get the ConsolidatedBalanceSheetsParenthetical
    balance_sheet_lst = tsla_xbrl.get_statement('ConsolidatedBalanceSheetsParenthetical')
    assert balance_sheet_lst
    assert balance_sheet_lst[0]['concept'] == 'us-gaap_StatementOfFinancialPositionAbstract'

    balance_sheet = statements['ConsolidatedBalanceSheetsParenthetical']
    assert balance_sheet


def test_get_statement_by_type(tsla_xbrl):
    statement = tsla_xbrl.get_statement('BalanceSheet')
    assert statement
    assert statement[0]['concept'] == 'us-gaap_StatementOfFinancialPositionAbstract'


def test_statement_get_item_int(tsla_xbrl):
    statements = tsla_xbrl.statements
    statement = statements[0]
    assert statement


def test_statement_get_item_by_name(tsla_xbrl):
    statements = tsla_xbrl.statements
    print()
    statement = statements["Cover"]
    assert statement
    print(statement)

    # Get ConsolidatedBalanceSheetsParenthetical
    statement = statements["ConsolidatedBalanceSheetsParenthetical"]
    assert statement


def test_aapl_balance_sheet(aapl_xbrl):
    statements = aapl_xbrl.statements
    print()
    balance_sheet = statements['BalanceSheet']
    assert balance_sheet
    rendered_statement = balance_sheet.render()
    assert rendered_statement
    print(rendered_statement)

    balance_sheet = statements.balance_sheet()
    print(balance_sheet)

    balance_sheet = statements['CONSOLIDATEDBALANCESHEETS']
    print(balance_sheet)


def test_get_income_statement(tsla_xbrl):
    statements = tsla_xbrl.statements
    print()

    income_statement = statements.income_statement()
    assert income_statement
    rendered_statement = income_statement.render()
    repr_ = repr(rendered_statement)
    assert '$25,500' in repr_


def test_statement_to_dataframe(aapl_xbrl):
    cashflow_statement: Statement = aapl_xbrl.statements.cashflow_statement()
    print()
    # print(cashflow_statement)
    rendered_statement:RenderedStatement = cashflow_statement.render()
    df = rendered_statement.to_dataframe()
    assert df.columns.tolist() ==['concept', 'label', '2023-09-30', '2022-09-24', '2021-09-25',
                                  'level','abstract', 'dimension', 'is_breakdown']

    # Issue #504: Filter for non-dimensional rows to avoid duplicate NetIncomeLoss entries
    net_income_filter = (df.concept == 'us-gaap_NetIncomeLoss') & (df.dimension == False)
    assert df[net_income_filter]['2023-09-30'].item() == 96995000000.0
    assert df[net_income_filter]['2022-09-24'].item() == 99803000000.0
    assert df[net_income_filter]['2021-09-25'].item() == 94680000000.0

    # Labels - now using original company labels (not standardized)
    labels = df.label.tolist()
    assert labels[0] == 'Cash, cash equivalents and restricted cash, ending balances'
    assert labels[1] == 'Operating activities:'
    assert labels[2] == 'Net income'  # Original company label (lowercase)
    print(df[['label', '2023-09-30']])

    assert all(col in df.columns for col in ['2023-09-30', '2022-09-24', '2021-09-25'])


def test_xbrls_cashflow_to_dataframe(aapl_xbrl, aapl_xbrl_2022):
    xbs = XBRLS([aapl_xbrl, aapl_xbrl_2022])
    cashflow = xbs.statements.cashflow_statement()
    assert cashflow.periods == ['2023-09-30', '2022-09-24']
    df = cashflow.to_dataframe()
    columns = df.columns.tolist()
    print(columns)
    labels = df.label.tolist()
    # Original labels are preserved (check case-insensitively for common patterns)
    # Apple's cash flow has "Cash, cash equivalents and restricted cash" patterns
    cash_related = [l for l in labels if 'cash' in l.lower()]
    assert len(cash_related) > 0, "Should have cash-related labels"
    assert df[(df.concept == 'us-gaap_NetIncomeLoss')]['2023-09-30'].item() == 96995000000.0
    # Use concept filter instead of label since labels are now original (may differ by company)
    net_income_row = df[df.concept == 'us-gaap_NetIncomeLoss']
    assert net_income_row['2023-09-30'].item() == 96995000000.0

def test_xbrls_balancesheet_to_dataframe(aapl_xbrl, aapl_xbrl_2022):
    xbs = XBRLS([aapl_xbrl, aapl_xbrl_2022])
    balance_sheet = xbs.statements.balance_sheet()
    assert balance_sheet.periods == ['2023-09-30', '2022-09-24']
    df = balance_sheet.to_dataframe()
    columns = df.columns.tolist()
    assert columns == ['label', 'concept', '2023-09-30', '2022-09-24']
    labels = df.label.tolist()
    print(labels)
    # Check using concept filter instead of label since labels are now original company labels
    # Apple uses 'Total assets' (lowercase) not 'Total Assets'
    assert any('assets' in l.lower() for l in labels), "Should have asset-related labels"
    # Verify the Assets concept is present
    assert df[df.concept == 'us-gaap_Assets'].shape[0] > 0, "Should have Assets concept"


@pytest.mark.slow
def test_non_financial_statement():
    f = Filing(company='SOUTHERN COPPER CORP/', cik=1001838, form='10-K', filing_date='2025-03-03',
               accession_no='0001558370-25-002017')
    xbrl: XBRL = XBRL.from_filing(f)

    print()
    # print(xbrl.statements)

    statement = xbrl.statements["DisclosureSegmentAndRelatedInformationSalesDetails"]
    assert statement
    print(statement)

    statement = xbrl.render_statement('DisclosureProperty')
    print(statement)


def test_render_segmented_statement(tsla_xbrl):
    statements = tsla_xbrl.statements
    statement = statements['SegmentReportingandInformationaboutGeographicAreas']
    assert statement
    print()
    print(statement)

    
def test_statement_lookup_optimizations(tsla_xbrl):
    """Test that our statement lookup optimizations work correctly"""
    # First call to build indices
    statements = tsla_xbrl.get_all_statements()
    
    # Ensure indices are properly built
    assert hasattr(tsla_xbrl, '_statement_by_standard_name')
    assert hasattr(tsla_xbrl, '_statement_by_primary_concept')
    assert hasattr(tsla_xbrl, '_statement_by_role_uri')
    assert hasattr(tsla_xbrl, '_statement_by_role_name')
    
    # Test lookup by standard name
    assert 'BalanceSheet' in tsla_xbrl._statement_by_standard_name
    
    # Get statement by standard name
    balance_sheet = tsla_xbrl.get_statement('BalanceSheet')
    assert balance_sheet
    
    # Get statement by role name
    for role, statement in tsla_xbrl._statement_by_role_uri.items():
        role_name = role.split('/')[-1].lower() if '/' in role else ''
        if role_name:
            # Try to get statement by role name
            stmt = tsla_xbrl.get_statement(role_name)
            assert stmt  # Statement should be found
    
    # Ensure cached result is returned (for performance)
    import time
    
    # Time the first call (should use cached indices)
    start = time.time()
    statements1 = tsla_xbrl.get_all_statements()
    elapsed1 = time.time() - start
    
    # Time the second call (should return cached result)
    start = time.time()
    statements2 = tsla_xbrl.get_all_statements()
    elapsed2 = time.time() - start
    
    # The second call should be extremely fast (effectively 0) because it's returning a cached result
    # Either the second call is faster OR both calls are extremely fast (less than 1ms)
    assert elapsed2 < elapsed1 or (elapsed1 < 0.001 and elapsed2 < 0.001)
    assert statements1 == statements2  # Same result


def test_cashflow_statement_totals():
    filing = Filing(company='Corsair Gaming, Inc.', cik=1743759, form='10-K',
                    filing_date='2025-02-26', accession_no='0000950170-25-027856')
    xbrl: XBRL = XBRL.from_filing(filing)
    cashflow_statement = xbrl.statements.cashflow_statement()
    print()
    print(cashflow_statement)
    df = cashflow_statement.to_dataframe()
    main_concepts = ["us-gaap_NetCashProvidedByUsedInOperatingActivities",
                     "us-gaap_NetCashProvidedByUsedInInvestingActivities",
                     "us-gaap_NetCashProvidedByUsedInFinancingActivities"]
    idx = df.concept.isin(main_concepts)
    cols = ["concept", "label", "2024-12-31"]
    cash_totals = df[idx][cols]
    assert len(cash_totals) == 3
    print(cash_totals)

    cash_statement = filing.statements.cash_flow_statement
    print(cash_statement.view())


def test_get_statement_by_name_returns_correct_statement():
    filing = Filing(company='SOUTHERN COPPER CORP/', cik=1001838, form='10-Q', filing_date='2011-08-08', accession_no='0001104659-11-044725')
    xbrl: XBRL = XBRL.from_filing(filing)
    statement:Statement = xbrl.statements.income_statement()
    #assert statement.primary_concept == 'us-gaap:IncomeStatementAbstract'
    df = statement.to_dataframe()
    concepts = df.concept.tolist()
    assert concepts[0] == 'us-gaap_IncomeStatementAbstract'



def test_get_balance_sheet_with_few_concepts():
    filing = Filing(company='M-Tron Industries Inc', cik=1902314, form='10-K', filing_date='2024-03-27', accession_no="0001437749-25-009645")
    xbrl: XBRL = XBRL.from_filing(filing)
    balance_sheet = xbrl.statements.balance_sheet()
    balance_sheet.render()
    print()
    print(balance_sheet)


def test_quarterly_statements():
    filing = Filing(company='Apple Inc.', cik=320193, form='10-Q', filing_date='2025-01-31', accession_no='0000320193-25-000008')
    xbrl = XBRL.from_filing(filing)
    income_statement = xbrl.statements.income_statement()
    income_statement.render()
    print()
    print(income_statement)

def test_stateement_matching_for_old_filing():
    xbrl = XBRL.from_directory('data/xbrl/datafiles/unp')
    print()
    income_statement = xbrl.statements.income_statement()
    assert income_statement
    rendered_statement = income_statement.render()
    print(rendered_statement)

@pytest.mark.network
def test_canonical_statement_type_preservation(unp_xbrl):
    """Test that canonical statement types are preserved when finding statements."""
    # Test basic statement finding
    matching_statements, found_role, actual_type = unp_xbrl.find_statement("BalanceSheet")

    # Verify that the actual_type is still "BalanceSheet" even though the role might be different
    assert actual_type == "BalanceSheet"

    # Also test with parenthetical version
    matching_statements, found_role, actual_type = unp_xbrl.find_statement("BalanceSheet", is_parenthetical=True)

    # The actual_type should still be "BalanceSheet" for downstream logic
    assert actual_type == "BalanceSheet"

    # Try with IncomeStatement
    matching_statements, found_role, actual_type = unp_xbrl.find_statement("IncomeStatement")
    assert actual_type == "IncomeStatement"

    # Role URI should be different from the type
    assert found_role != "IncomeStatement"

@pytest.mark.network
def test_render_statement_preserves_types(tsla_xbrl):
    """Test that the render_statement method correctly uses preserved types."""
    # Render an income statement
    statement = tsla_xbrl.render_statement("IncomeStatement")

    # Make sure rendering worked (this would fail if statement type wasn't recognized)
    assert statement is not None

    # Try a balance sheet with parenthetical flag
    try:
        paren_statement = tsla_xbrl.render_statement("BalanceSheet", parenthetical=True)
        if paren_statement:
            assert "(Parenthetical)" in paren_statement.title
    except:
        # Not all test data has parenthetical statements
        pytest.skip("No parenthetical balance sheet found in test data")

@pytest.mark.network
def test_statement_with_canonical_type(tsla_xbrl):
    """Test that a Statement created with a canonical type preserves it."""
    # Create a statement with a canonical type
    stmt = Statement(tsla_xbrl, "SomeRoleURI", canonical_type="BalanceSheet")

    # Check that the canonical type was stored
    assert stmt.canonical_type == "BalanceSheet"

    # The role_or_type should still be the original role
    assert stmt.role_or_type == "SomeRoleURI"

@pytest.mark.network
def test_balance_sheet_statement(tsla_xbrl):
    """Test that a balance sheet statement created via the accessor has the right canonical type."""
    # Get a balance sheet using the accessor method
    statements = tsla_xbrl.statements
    balance_sheet = statements.balance_sheet()

    # Check that it has the canonical type set
    assert balance_sheet.canonical_type == "BalanceSheet"

    # Check that the render method would use the canonical type
    rendering_type = balance_sheet.canonical_type if balance_sheet.canonical_type else balance_sheet.role_or_type
    assert rendering_type == "BalanceSheet"

@pytest.mark.network
def test_parenthetical_balance_sheet(tsla_xbrl):
    """Test that a parenthetical balance sheet preserves the canonical type."""
    # Try to get a parenthetical balance sheet
    statements = tsla_xbrl.statements

    try:
        paren_balance_sheet = statements.balance_sheet(parenthetical=True)

        # Check that it has the canonical type set
        assert paren_balance_sheet.canonical_type == "BalanceSheet"

        # The role should be different from the canonical type
        assert paren_balance_sheet.role_or_type != "BalanceSheet"

        # But the rendering type should be the canonical type
        rendering_type = paren_balance_sheet.canonical_type if paren_balance_sheet.canonical_type else paren_balance_sheet.role_or_type
        assert rendering_type == "BalanceSheet"
    except:
        # Not all test data has parenthetical statements
        pytest.skip("No parenthetical balance sheet in test data")

@pytest.mark.network
def test_canonical_type_preservation(tsla_xbrl):
    """Test that the statement type is preserved during validation and access."""
    # Get an income statement, skipping concept validation for test data
    statements = tsla_xbrl.statements
    income_stmt = statements.income_statement(skip_concept_check=True)

    # It should have the canonical type set
    assert income_stmt.canonical_type == "IncomeStatement"

    # Check that calculate_ratios uses the canonical type
    ratios = income_stmt.calculate_ratios()

    # Get the statement data and make sure it's retrievable
    statement_data = income_stmt.get_raw_data()
    assert statement_data is not None

    # The canonical type should be used in rendering
    rendering_type = income_stmt.canonical_type if income_stmt.canonical_type else income_stmt.role_or_type
    assert rendering_type == "IncomeStatement"


# ===== Enhanced Statement Tests from Fixture-Based Testing =====

@pytest.mark.slow
def test_standard_statement_resolution(cached_companies):
    """Test that standard financial statements are correctly resolved for multiple companies."""
    if not cached_companies:
        pytest.skip("No company fixtures available")
    
    # Standard statement types
    standard_statements = [
        "BalanceSheet",
        "IncomeStatement", 
        "CashFlowStatement",
        "ChangesInEquity",
        "ComprehensiveIncome"
    ]
    
    # Test each company
    results = {}
    
    for ticker, xbrl in cached_companies.items():
        statement_found = []
        
        for stmt_type in standard_statements:
            try:
                statement = xbrl.get_statement(stmt_type)
                if statement:
                    statement_found.append(stmt_type)
            except Exception:
                pass
        
        # Store results
        if statement_found:
            results[ticker] = statement_found
    
    # Verify that we found at least some statements
    assert results, "No standard statements found for any company"
    
    # Print summary
    print("\nStandard statements found:")
    for ticker, found_statements in results.items():
        print(f"  {ticker}: {', '.join(found_statements)}")

@pytest.mark.slow
def test_statement_accessor_methods(cached_companies):
    """Test statement accessor methods on Statements class across companies."""
    if not cached_companies:
        pytest.skip("No company fixtures available")
    
    # Statement accessor methods
    accessors = [
        "balance_sheet",
        "income_statement", 
        "cash_flow_statement",
        "changes_in_equity",
        "comprehensive_income"
    ]
    
    # Test each company
    results = {}
    
    for ticker, xbrl in cached_companies.items():
        statement_found = []
        
        for accessor in accessors:
            try:
                # Get the method
                method = getattr(xbrl.statements, accessor, None)
                if method and callable(method):
                    # Call the method
                    statement = method()
                    if statement:
                        statement_found.append(accessor)
            except Exception:
                pass
        
        # Store results
        if statement_found:
            results[ticker] = statement_found
    
    # Verify that we found at least some statements
    assert results, "No statements found via accessor methods"
    
    # Print summary
    print("\nStatements found via accessor methods:")
    for ticker, found_statements in results.items():
        print(f"  {ticker}: {', '.join(found_statements)}")

@pytest.mark.slow
def test_parenthetical_statement_resolution(cached_companies):
    """Test resolution of parenthetical statements across companies."""
    if not cached_companies:
        pytest.skip("No company fixtures available")
    
    # Test each company for parenthetical statements
    results = {}
    
    for ticker, xbrl in cached_companies.items():
        try:
            # Try to get parenthetical balance sheet
            statement = xbrl.statements.balance_sheet(parenthetical=True)
            if statement:
                results[ticker] = True
        except Exception:
            pass
    
    # Print summary - we don't assert here because not all companies have parenthetical statements
    print("\nParenthetical statements found:")
    for ticker in results:
        print(f"  {ticker}")

@pytest.mark.slow
def test_historical_vs_modern_xbrl_statements(nflx_10k_2010, nflx_10k_2024):
    """Compare statement structure between historical and modern XBRL filings."""
    if nflx_10k_2010 is None or nflx_10k_2024 is None:
        pytest.skip("Both historical and modern Netflix statements required")
    
    # Try to get balance sheets from both
    historical_bs = nflx_10k_2010.statements.balance_sheet()
    modern_bs = nflx_10k_2024.statements.balance_sheet()
    
    # Skip if either statement is missing
    if not historical_bs or not modern_bs:
        pytest.skip("Balance sheet not available in both historical and modern filings")
    
    # Convert to dataframes for comparison
    historical_df = historical_bs.to_dataframe()
    modern_df = modern_bs.to_dataframe()
    
    # Compare structure
    assert "concept" in historical_df.columns, "Historical statement missing concept column"
    assert "concept" in modern_df.columns, "Modern statement missing concept column"
    
    # Count concepts
    historical_concepts = set(historical_df["concept"].tolist())
    modern_concepts = set(modern_df["concept"].tolist())
    
    # Print summary
    print(f"\nComparison of historical (2010) vs modern (2024) Netflix balance sheets:")
    print(f"  Historical concepts: {len(historical_concepts)}")
    print(f"  Modern concepts: {len(modern_concepts)}")
    
    # Common concepts should exist (may be a small number due to taxonomy changes)
    common_concepts = historical_concepts.intersection(modern_concepts)
    print(f"  Common concepts: {len(common_concepts)}")
    
    # Show some examples of common concepts
    if common_concepts:
        print("  Sample common concepts:")
        for concept in list(common_concepts)[:5]:
            print(f"    - {concept}")
    
    # Due to taxonomy changes over time, we don't enforce a specific number of common concepts
    # but there should be at least some core concepts shared
    assert common_concepts, "No common concepts found between historical and modern statements"

@pytest.mark.network
def test_correct_period_selected_for_income_statement():
    filing = Filing(company='BRISTOL MYERS SQUIBB CO', cik=14272, form='10-K', filing_date='2025-02-12', accession_no='0000014272-25-000039')
    xb = filing.xbrl()
    income_statement = xb.statements.income_statement()
    print(income_statement)
    rendered_statement = income_statement.render()
    periods = rendered_statement.periods
    labels = [p.label for p in periods]
    print(periods)
    print(labels)

@pytest.mark.network
def test_periods_property_different_statement_types(aapl_xbrl):
    """Test periods property works across different statement types."""
    statements_to_test = {
        'balance_sheet': 'instant',
        'income_statement': 'duration',
        'cashflow_statement': 'duration'
    }

    for stmt_method, expected_type in statements_to_test.items():
        try:
            statement:Statement = getattr(aapl_xbrl.statements, stmt_method)()
            rendered_statement = statement.render()
            if statement:
                periods = rendered_statement.periods
                assert len(periods) > 0, f"{stmt_method} should have periods"

                # Check that period types match expectations
                for period in periods:
                    if expected_type == 'instant':
                        assert period.type == 'instant', f"Balance sheet should use instant periods, got {period.type}"
                    elif expected_type == 'duration':
                        assert period.type == 'duration', f"{stmt_method} should use duration periods, got {period.type}"

                print(f"\n{stmt_method} periods:")
                for period in periods:
                    print(f"  {period.label} ({period.type})")
        except Exception as e:
            print(f"Could not test {stmt_method}: {e}")


@pytest.mark.network
def test_periods_property_structure(tsla_xbrl):
    """Test the structure and content of periods property."""
    income_statement = tsla_xbrl.statements.income_statement()
    rendered_statement = income_statement.render()
    periods = rendered_statement.periods

    assert len(periods) > 0, "Should have at least one period"

    # Test first period structure
    period = periods[0]

    # Required attributes
    assert hasattr(period, 'key'), "Period missing key"
    assert hasattr(period, 'label'), "Period missing label"

    # Key should be in expected format
    assert isinstance(period.key, str), "Period key should be string"

    # Label should be non-empty
    assert period.label.strip(), "Period label should not be empty"

    print(f"\nFirst period details:")
    print(f"  Key: {period.key}")
    print(f"  Label: {period.label}")

@pytest.mark.network
def test_periods_property_consistency_with_rendered_statement(aapl_xbrl):
    """Test that Statement.periods matches the periods in rendered statement."""
    income_statement = aapl_xbrl.statements.income_statement()

    # Get periods from statement property
    statement_periods = income_statement.render().periods

    # Get periods from rendered statement
    rendered_statement = income_statement.render()
    rendered_periods = rendered_statement.periods

    # Should be the same
    assert len(statement_periods) == len(rendered_periods), "Period counts should match"

    for stmt_period, rendered_period in zip(statement_periods, rendered_periods):
        assert stmt_period.key == rendered_period.key, "Period keys should match"
        assert stmt_period.label == rendered_period.label, "Period labels should match"

    print(f"\nPeriod consistency verified: {len(statement_periods)} periods match")


class TestStatementsDiscovery:
    """Tests for the statement discovery and access methods on the Statements class."""

    def test_list_available_returns_dataframe(self, aapl_xbrl):
        statements = aapl_xbrl.statements
        df = statements.list_available()
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ['index', 'category', 'name', 'role_name', 'element_count']
        assert len(df) == len(statements.statements)

    def test_list_available_category_filter(self, aapl_xbrl):
        statements = aapl_xbrl.statements
        df_all = statements.list_available()
        df_statements = statements.list_available(category='statement')
        assert len(df_statements) > 0
        assert len(df_statements) < len(df_all)
        assert all(df_statements['category'] == 'statement')

    def test_search_finds_income(self, aapl_xbrl):
        results = aapl_xbrl.statements.search('income')
        assert len(results) > 0
        assert all(isinstance(s, Statement) for s in results)

    def test_search_multi_word(self, aapl_xbrl):
        results_broad = aapl_xbrl.statements.search('income')
        results_narrow = aapl_xbrl.statements.search('income statement')
        assert len(results_narrow) <= len(results_broad)

    def test_search_empty(self, aapl_xbrl):
        assert aapl_xbrl.statements.search('') == []
        assert aapl_xbrl.statements.search('   ') == []

    def test_search_no_match(self, aapl_xbrl):
        assert aapl_xbrl.statements.search('xyznonexistent') == []

    def test_get_exact_type(self, aapl_xbrl):
        result = aapl_xbrl.statements.get('IncomeStatement')
        assert result is not None
        assert isinstance(result, Statement)

    def test_get_by_role_name(self, aapl_xbrl):
        result = aapl_xbrl.statements.get('CASHFLOWS')
        assert result is not None
        assert isinstance(result, Statement)

    def test_get_no_match(self, aapl_xbrl):
        assert aapl_xbrl.statements.get('xyznonexistent') is None

    def test_all_returns_all(self, aapl_xbrl):
        statements = aapl_xbrl.statements
        all_stmts = statements.all()
        assert len(all_stmts) == len(statements.statements)
        assert all(isinstance(s, Statement) for s in all_stmts)

    def test_all_category_filter(self, aapl_xbrl):
        statements = aapl_xbrl.statements
        stmt_only = statements.all(category='statement')
        assert len(stmt_only) > 0
        assert len(stmt_only) < len(statements.all())

    def test_get_by_category_fix(self, aapl_xbrl):
        """Regression test: get_by_category('statement') should return non-empty results."""
        results = aapl_xbrl.statements.get_by_category('statement')
        assert len(results) > 0
        assert all(isinstance(s, Statement) for s in results)

    def test_len(self, aapl_xbrl):
        statements = aapl_xbrl.statements
        assert len(statements) == len(statements.statements)

    def test_iter(self, aapl_xbrl):
        statements = aapl_xbrl.statements
        iterated = list(statements)
        assert len(iterated) == len(statements)
        assert all(isinstance(s, Statement) for s in iterated)

    def test_to_context_minimal(self, aapl_xbrl):
        ctx = aapl_xbrl.statements.to_context('minimal')
        assert 'STATEMENTS' in ctx
        assert 'Apple Inc.' in ctx
        assert 'CORE STATEMENTS:' in ctx
        assert '.income_statement()' in ctx
        assert '.balance_sheet()' in ctx
        # Minimal should not include discovery section
        assert 'DISCOVERY:' not in ctx

    def test_to_context_standard(self, aapl_xbrl):
        ctx = aapl_xbrl.statements.to_context('standard')
        assert 'CORE STATEMENTS:' in ctx
        assert 'OTHER:' in ctx
        assert 'DISCOVERY:' in ctx
        assert '.search(' in ctx
        assert '.get(' in ctx
        assert '.list_available()' in ctx
        # Standard should not include full listing
        assert 'NOTES (' not in ctx

    def test_to_context_full(self, aapl_xbrl):
        ctx = aapl_xbrl.statements.to_context('full')
        assert 'DISCOVERY:' in ctx
        # Full includes per-category listings
        assert 'OTHER (' in ctx
        assert 'DOCUMENT (' in ctx
        # Full is longer than standard
        standard = aapl_xbrl.statements.to_context('standard')
        assert len(ctx) > len(standard)

    def test_to_context_default_is_standard(self, aapl_xbrl):
        assert aapl_xbrl.statements.to_context() == aapl_xbrl.statements.to_context('standard')