"""
Issue Reproduction Template: Entity Facts Issues
For issues related to Company.facts, entity lookup, financial data access

Replace the placeholders below with actual values from the issue report:
- ISSUE_NUMBER: GitHub issue number
- REPORTER_USERNAME: GitHub username who reported the issue
- COMPANY_TICKER: Company ticker symbol (e.g., AAPL)
- COMPANY_CIK: Company CIK if specified
- EXPECTED_BEHAVIOR: What should happen
- ACTUAL_BEHAVIOR: What actually happens
- ERROR_MESSAGE: Specific error message if any
"""

import traceback

from rich.console import Console

from edgar import Company, get_entity, set_identity

# Set proper identity (CRITICAL for SEC API access)
set_identity("Research Team research@edgartools-investigation.com")

console = Console()

def reproduce_entity_facts_issue():
    """
    Issue #ISSUE_NUMBER: Entity Facts Reproduction

    Reporter: REPORTER_USERNAME
    Category: entity-facts

    Expected: EXPECTED_BEHAVIOR
    Actual: ACTUAL_BEHAVIOR
    Error: ERROR_MESSAGE
    """

    console.print("[bold blue]Issue #ISSUE_NUMBER: Entity Facts Reproduction[/bold blue]")
    console.print("Reporter: REPORTER_USERNAME")

    # Test case details
    ticker = "COMPANY_TICKER"
    cik = "COMPANY_CIK"  # Optional
    console.print(f"Testing company: {ticker}")

    try:
        # Step 1: Get the company object
        console.print("\n[cyan]Step 1: Loading company...[/cyan]")

        if cik and cik != "COMPANY_CIK":  # Check if CIK was provided
            company = get_entity(cik)
        else:
            company = Company(ticker)

        console.print(f"✅ Company loaded: {company.name} (CIK: {company.cik})")

        # Step 2: Access facts
        console.print("\n[cyan]Step 2: Loading facts...[/cyan]")
        facts = company.facts
        console.print(f"✅ Facts loaded: {type(facts)}")

        # Step 3: Test basic facts properties
        console.print("\n[cyan]Step 3: Testing facts properties...[/cyan]")

        if hasattr(facts, 'cik'):
            console.print(f"  CIK: {facts.cik}")

        if hasattr(facts, 'entity_name'):
            console.print(f"  Entity Name: {facts.entity_name}")

        # Step 4: Test statement access
        console.print("\n[cyan]Step 4: Testing statement access...[/cyan]")

        statements_to_test = [
            ('income_statement', 'Income Statement'),
            ('balance_sheet', 'Balance Sheet'),
            ('cash_flow_statement', 'Cash Flow Statement')
        ]

        statement_results = {}

        for stmt_method, stmt_name in statements_to_test:
            try:
                console.print(f"  Testing {stmt_name}...")

                # Test without parameters
                stmt = getattr(facts, stmt_method)()
                console.print(f"    ✅ {stmt_name} loaded")

                # Test with parameters
                stmt_annual = getattr(facts, stmt_method)(annual=True, periods=1)
                console.print(f"    ✅ {stmt_name} (annual) loaded")

                # Test dataframe conversion
                df = stmt.to_dataframe()
                console.print(f"    ✅ DataFrame conversion: {df.shape}")

                statement_results[stmt_method] = {
                    'success': True,
                    'shape': df.shape
                }

            except Exception as e:
                console.print(f"    ❌ {stmt_name} failed: {str(e)}")
                statement_results[stmt_method] = {
                    'success': False,
                    'error': str(e)
                }

        # Step 5: Test specific functionality mentioned in issue
        console.print("\n[cyan]Step 5: Testing reported issue...[/cyan]")

        # Add specific tests based on the issue
        # Common entity facts issues:

        # Test fact lookup
        try:
            # Look for common facts
            revenue_facts = facts.get_fact('Revenue')
            console.print("  ✅ Revenue facts accessible")
        except Exception as e:
            console.print(f"  ❌ Revenue facts failed: {str(e)}")

        # Test period selection
        try:
            income = facts.income_statement(annual=True, periods=3)
            console.print("  ✅ Multi-period selection works")
        except Exception as e:
            console.print(f"  ❌ Multi-period selection failed: {str(e)}")

        console.print("\n[green]✅ Entity facts access completed successfully[/green]")

        return {
            'success': True,
            'issue_reproduced': False,
            'company_name': company.name,
            'cik': company.cik,
            'statement_results': statement_results
        }

    except Exception as e:
        console.print(f"\n[red]❌ Entity facts access failed: {str(e)}[/red]")
        console.print(f"[red]Traceback: {traceback.format_exc()}[/red]")

        # Check if this matches the reported error
        error_str = str(e).lower()
        reported_error = "ERROR_MESSAGE".lower()

        if reported_error in error_str and reported_error != "error_message":
            console.print("\n[yellow]🎯 Error matches reported issue![/yellow]")
            issue_reproduced = True
        else:
            console.print("\n[blue]ℹ️  Different error than reported[/blue]")
            issue_reproduced = False

        return {
            'success': False,
            'issue_reproduced': issue_reproduced,
            'error': str(e),
            'error_type': type(e).__name__
        }

def test_multiple_companies():
    """Test with multiple companies to see if issue is specific to one company"""
    console.print("\n[bold blue]Testing Multiple Companies[/bold blue]")

    test_companies = [
        "COMPANY_TICKER",  # Original company from issue
        "AAPL",           # Known working company
        "MSFT",           # Another test case
    ]

    results = {}

    for ticker in test_companies:
        console.print(f"\n[cyan]Testing: {ticker}[/cyan]")

        try:
            company = Company(ticker)
            facts = company.facts

            # Test basic access
            income = facts.income_statement()
            console.print(f"  ✅ {ticker}: Facts accessible")

            results[ticker] = {'success': True}

        except Exception as e:
            console.print(f"  ❌ {ticker}: {str(e)}")
            results[ticker] = {'success': False, 'error': str(e)}

    return results

def test_facts_caching():
    """Test facts caching behavior if issue relates to cache"""
    console.print("\n[bold blue]Testing Facts Caching[/bold blue]")

    ticker = "COMPANY_TICKER"

    try:
        # First load
        console.print("First facts load...")
        company1 = Company(ticker)
        facts1 = company1.facts
        console.print("✅ First load completed")

        # Second load (should use cache)
        console.print("Second facts load...")
        company2 = Company(ticker)
        facts2 = company2.facts
        console.print("✅ Second load completed")

        # Compare
        if facts1 is facts2:
            console.print("✅ Same object - caching working")
        else:
            console.print("⚠️  Different objects - caching behavior unclear")

    except Exception as e:
        console.print(f"❌ Caching test failed: {str(e)}")

def test_specific_financial_concepts():
    """Test access to specific financial concepts mentioned in issue"""
    console.print("\n[bold blue]Testing Specific Financial Concepts[/bold blue]")

    ticker = "COMPANY_TICKER"

    try:
        company = Company(ticker)
        facts = company.facts

        # Add specific concepts mentioned in the issue
        concepts_to_test = [
            # "Revenue",
            # "NetIncome",
            # "Assets",
            # Add concepts from the issue
        ]

        for concept in concepts_to_test:
            try:
                fact_data = facts.get_fact(concept)
                console.print(f"  ✅ {concept}: Available")
            except Exception as e:
                console.print(f"  ❌ {concept}: {str(e)}")

    except Exception as e:
        console.print(f"❌ Concept testing failed: {str(e)}")

if __name__ == "__main__":
    # Main reproduction
    result = reproduce_entity_facts_issue()

    # Additional testing (uncomment as needed)
    # test_multiple_companies()
    # test_facts_caching()
    # test_specific_financial_concepts()

    # Summary
    if result.get('issue_reproduced'):
        print("\n✅ Issue #ISSUE_NUMBER reproduced successfully")
        print(f"Error: {result.get('error', 'Unknown')}")
    elif result.get('success'):
        print("\n❓ Issue #ISSUE_NUMBER could not be reproduced - Entity facts worked correctly")
    else:
        print("\n❌ Entity facts failed with different error than reported")
