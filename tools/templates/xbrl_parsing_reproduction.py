"""
Issue Reproduction Template: XBRL Parsing Issues
For issues related to XBRL data extraction, element mapping, context errors

Replace the placeholders below with actual values from the issue report:
- ISSUE_NUMBER: GitHub issue number
- REPORTER_USERNAME: GitHub username who reported the issue
- ACCESSION_NUMBER: Filing accession number that shows the problem
- EXPECTED_BEHAVIOR: What should happen
- ACTUAL_BEHAVIOR: What actually happens
- ERROR_MESSAGE: Specific error message if any
"""

import traceback

from rich.console import Console

from edgar import get_by_accession_number, set_identity

# Set proper identity (CRITICAL for SEC API access)
set_identity("Research Team research@edgartools-investigation.com")

console = Console()

def reproduce_xbrl_parsing_issue():
    """
    Issue #ISSUE_NUMBER: XBRL Parsing Reproduction

    Reporter: REPORTER_USERNAME
    Category: xbrl-parsing

    Expected: EXPECTED_BEHAVIOR
    Actual: ACTUAL_BEHAVIOR
    Error: ERROR_MESSAGE
    """

    console.print("[bold blue]Issue #ISSUE_NUMBER: XBRL Parsing Reproduction[/bold blue]")
    console.print("Reporter: REPORTER_USERNAME")

    # Test case details
    accession = "ACCESSION_NUMBER"
    console.print(f"Testing accession: {accession}")

    try:
        # Step 1: Get the filing
        console.print("\n[cyan]Step 1: Loading filing...[/cyan]")
        filing = get_by_accession_number(accession)
        console.print(f"✅ Filing loaded: {filing.form} - {filing.company} - {filing.filing_date}")

        # Step 2: Load XBRL
        console.print("\n[cyan]Step 2: Loading XBRL...[/cyan]")
        xbrl = filing.xbrl()
        console.print(f"✅ XBRL loaded: {type(xbrl)}")

        # Step 3: Check basic XBRL properties
        console.print("\n[cyan]Step 3: Checking XBRL structure...[/cyan]")

        if hasattr(xbrl, 'entity_name'):
            console.print(f"  Entity: {xbrl.entity_name}")

        if hasattr(xbrl, 'reporting_periods'):
            console.print(f"  Reporting periods: {len(xbrl.reporting_periods)}")

        if hasattr(xbrl, 'facts'):
            console.print(f"  Facts count: {len(xbrl.facts)}")

        if hasattr(xbrl, 'contexts'):
            console.print(f"  Contexts count: {len(xbrl.contexts)}")

        # Step 4: Test specific functionality mentioned in issue
        console.print("\n[cyan]Step 4: Testing reported functionality...[/cyan]")

        # Add specific tests based on the issue
        # Examples:

        # Test statement access
        try:
            if hasattr(xbrl, 'statements'):
                statements = xbrl.statements
                console.print("  ✅ Statements object accessible")

                # Test each statement type
                for stmt_name in ['cashflow_statement', 'income_statement', 'balance_sheet']:
                    try:
                        stmt = getattr(statements, stmt_name)()
                        console.print(f"  ✅ {stmt_name} accessible")

                        # Test dataframe conversion
                        df = stmt.to_dataframe()
                        console.print(f"    DataFrame shape: {df.shape}")

                    except Exception as e:
                        console.print(f"  ❌ {stmt_name} failed: {str(e)}")

        except Exception as e:
            console.print(f"  ❌ Statements access failed: {str(e)}")

        # Test facts access
        try:
            facts = xbrl.facts
            console.print(f"  ✅ Facts accessible: {len(facts)} facts")

            # Test facts query
            query_result = facts.query()
            console.print("  ✅ Facts query accessible")

        except Exception as e:
            console.print(f"  ❌ Facts access failed: {str(e)}")

        console.print("\n[green]✅ XBRL parsing completed successfully[/green]")

        return {
            'success': True,
            'issue_reproduced': False,
            'form': filing.form,
            'company': filing.company,
            'has_xbrl': True
        }

    except Exception as e:
        console.print(f"\n[red]❌ XBRL parsing failed: {str(e)}[/red]")
        console.print(f"[red]Traceback: {traceback.format_exc()}[/red]")

        # Check if this matches the reported error
        error_str = str(e).lower()
        reported_error = "ERROR_MESSAGE".lower()

        if reported_error in error_str:
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

def test_element_mapping():
    """Test specific element mapping if issue relates to concept mapping"""
    console.print("\n[bold blue]Testing Element Mapping[/bold blue]")

    accession = "ACCESSION_NUMBER"

    try:
        filing = get_by_accession_number(accession)
        xbrl = filing.xbrl()

        # Check element catalog
        if hasattr(xbrl, 'element_catalog'):
            catalog = xbrl.element_catalog
            console.print(f"Element catalog size: {len(catalog)}")

            # Look for specific elements mentioned in the issue
            # Add specific element names from the issue report
            test_elements = [
                # "Revenue",
                # "NetIncome",
                # Add elements mentioned in the issue
            ]

            for element in test_elements:
                if element in catalog:
                    console.print(f"  ✅ Found element: {element}")
                else:
                    console.print(f"  ❌ Missing element: {element}")

    except Exception as e:
        console.print(f"❌ Element mapping test failed: {str(e)}")

def test_context_handling():
    """Test context handling if issue relates to periods or dimensions"""
    console.print("\n[bold blue]Testing Context Handling[/bold blue]")

    accession = "ACCESSION_NUMBER"

    try:
        filing = get_by_accession_number(accession)
        xbrl = filing.xbrl()

        if hasattr(xbrl, 'contexts'):
            contexts = xbrl.contexts
            console.print(f"Total contexts: {len(contexts)}")

            # Analyze context types
            instant_contexts = []
            duration_contexts = []

            for context_id, context in contexts.items():
                context_data = context.model_dump() if hasattr(context, 'model_dump') else {}
                period = context_data.get('period', {})

                if period.get('type') == 'instant':
                    instant_contexts.append(context_id)
                elif period.get('type') == 'duration':
                    duration_contexts.append(context_id)

            console.print(f"  Instant contexts: {len(instant_contexts)}")
            console.print(f"  Duration contexts: {len(duration_contexts)}")

    except Exception as e:
        console.print(f"❌ Context handling test failed: {str(e)}")

def compare_with_working_filing():
    """Compare with a filing that works correctly"""
    console.print("\n[bold blue]Comparing with Working Filing[/bold blue]")

    problematic = "ACCESSION_NUMBER"
    working = "0000320193-25-000073"  # Known working Apple filing

    console.print(f"Problematic: {problematic}")
    console.print(f"Working: {working}")

    try:
        # Test both filings
        for label, accession in [("Problematic", problematic), ("Working", working)]:
            console.print(f"\n[cyan]Testing {label}: {accession}[/cyan]")

            filing = get_by_accession_number(accession)
            xbrl = filing.xbrl()

            # Basic metrics
            facts_count = len(xbrl.facts) if hasattr(xbrl, 'facts') else 0
            contexts_count = len(xbrl.contexts) if hasattr(xbrl, 'contexts') else 0

            console.print(f"  Facts: {facts_count}")
            console.print(f"  Contexts: {contexts_count}")

    except Exception as e:
        console.print(f"❌ Comparison failed: {str(e)}")

if __name__ == "__main__":
    # Main reproduction
    result = reproduce_xbrl_parsing_issue()

    # Additional testing (uncomment as needed)
    # test_element_mapping()
    # test_context_handling()
    # compare_with_working_filing()

    # Summary
    if result.get('issue_reproduced'):
        print("\n✅ Issue #ISSUE_NUMBER reproduced successfully")
        print(f"Error: {result.get('error', 'Unknown')}")
    elif result.get('success'):
        print("\n❓ Issue #ISSUE_NUMBER could not be reproduced - XBRL parsing worked correctly")
    else:
        print("\n❌ XBRL parsing failed with different error than reported")
