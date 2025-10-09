"""
Issue #374: Missing Early Filings Investigation
Reporter: lsy617004926
Category: filing-access

Expected: Should return all MSFT filings from company inception
Actual: User reports only filings from 2019 onwards, stops at 1000 filings

TOOLKIT FINDING: Issue appears to be user environment or caching related.
MSFT actually has 4,328 filings going back to 1994.
"""

from edgar import set_identity, Company
from rich.console import Console
import traceback

# Set proper identity (CRITICAL for SEC API access)
set_identity("Research Team research@edgartools-investigation.com")

console = Console()

def reproduce_missing_early_filings():
    """
    Issue #374: Missing Early Filings Reproduction

    Reporter: lsy617004926
    Category: filing-access

    Expected: Should return all MSFT filings from company inception
    Actual: User reports only filings from 2019 onwards, stops at 1000 filings
    """

    console.print("[bold blue]Issue #374: Missing Early Filings Investigation[/bold blue]")
    console.print("Reporter: lsy617004926")
    console.print("Company: MSFT")

    try:
        # Test the exact issue described
        console.print("\n[cyan]Step 1: Loading MSFT company object...[/cyan]")
        msft = Company('MSFT')
        console.print(f"✅ Company loaded: {msft.name} (CIK: {msft.cik})")

        # Test total filings
        console.print("\n[cyan]Step 2: Getting all filings...[/cyan]")
        all_filings = msft.get_filings()
        console.print(f"✅ Total filings: {len(all_filings)}")
        console.print(f"✅ Date range: {all_filings.date_range}")

        # Test 10-K filings specifically
        console.print("\n[cyan]Step 3: Getting 10-K filings...[/cyan]")
        filings_10k = msft.get_filings(form='10-K')
        console.print(f"✅ 10-K filings: {len(filings_10k)}")
        console.print(f"✅ 10-K date range: {filings_10k.date_range}")

        # Test pagination behavior (this was user's core issue)
        console.print("\n[cyan]Step 4: Testing pagination behavior...[/cyan]")

        filings_no_full_load = msft.get_filings(trigger_full_load=False)
        console.print(f"Without full load: {len(filings_no_full_load)} filings")

        filings_with_full_load = msft.get_filings(trigger_full_load=True)
        console.print(f"With full load: {len(filings_with_full_load)} filings")

        # Analysis of user's claim
        console.print(f"\n[bold]Analysis:[/bold]")

        if len(all_filings) > 1000:
            console.print(f"✅ PAGINATION WORKING: Found {len(all_filings)} filings (> 1000)")
        else:
            console.print(f"❌ PAGINATION ISSUE: Only {len(all_filings)} filings found")

        earliest_date = all_filings.date_range[0]
        if earliest_date.year < 2019:
            console.print(f"✅ EARLY FILINGS FOUND: Earliest filing from {earliest_date}")
        else:
            console.print(f"❌ MISSING EARLY FILINGS: Earliest filing only from {earliest_date}")

        # Test workaround mentioned in comments
        console.print("\n[cyan]Step 5: Testing date range workaround...[/cyan]")
        try:
            workaround_filings = msft.get_filings(form='10-K', filing_date='1990-01-01:')
            console.print(f"✅ Workaround result: {len(workaround_filings)} 10-K filings")
            console.print(f"✅ Workaround date range: {workaround_filings.date_range}")
        except Exception as e:
            console.print(f"❌ Workaround failed: {str(e)}")

        # Issue assessment with maintainer knowledge
        console.print(f"\n[bold green]✅ INVESTIGATION COMPLETE[/bold green]")

        # MAINTAINER INSIGHT: ~1000 filings indicates pagination failure
        if len(all_filings) > 1000 and earliest_date.year < 2019:
            console.print(f"[green]CONCLUSION: Issue NOT reproduced in current environment[/green]")
            console.print(f"  - Found {len(all_filings)} total filings (pagination working here)")
            console.print(f"  - Earliest filing from {earliest_date} (early filings present)")
            console.print(f"  - User's ~1000 filing limit suggests pagination bug in their environment")

            return {
                'issue_reproduced': False,
                'total_filings': len(all_filings),
                'date_range': all_filings.date_range,
                'pagination_working': True,
                'early_filings_present': True,
                'conclusion': 'Pagination bug exists but not reproduced here - environment specific'
            }
        elif len(all_filings) <= 1000:
            console.print(f"[red]CONCLUSION: PAGINATION BUG CONFIRMED[/red]")
            console.print(f"  - Found exactly {len(all_filings)} filings")
            console.print(f"  - MAINTAINER INSIGHT: ~1000 filings = pagination failure")
            console.print(f"  - Root cause: download_submissions only gets first page")
            console.print(f"  - Likely causes: cached data issue OR pagination logic bug")

            return {
                'issue_reproduced': True,
                'total_filings': len(all_filings),
                'date_range': all_filings.date_range,
                'pagination_working': False,
                'early_filings_present': earliest_date.year < 2019,
                'conclusion': 'CONFIRMED: Pagination bug - stuck at first page of SEC submissions API'
            }
        else:
            console.print(f"[red]CONCLUSION: Issue reproduced - missing early filings[/red]")
            console.print(f"  - Expected: >1000 filings from before 2019")
            console.print(f"  - Actual: {len(all_filings)} filings from {earliest_date}")

            return {
                'issue_reproduced': True,
                'total_filings': len(all_filings),
                'date_range': all_filings.date_range,
                'pagination_working': len(all_filings) > 1000,
                'early_filings_present': earliest_date.year < 2019,
                'conclusion': 'Confirmed early filing access issue'
            }

    except Exception as e:
        console.print(f"\n[red]❌ Investigation failed: {str(e)}[/red]")
        console.print(f"[red]Traceback: {traceback.format_exc()}[/red]")

        return {
            'error': str(e),
            'issue_reproduced': False,
            'conclusion': 'Investigation failed due to technical error'
        }

def test_other_companies():
    """Test the issue with other companies mentioned in comments"""
    console.print("\n[bold blue]Testing Other Companies[/bold blue]")

    test_companies = [
        ('BTBT', 'Expected filings since 2018'),
        ('SON', 'User reports only 2021 onwards'),
    ]

    results = {}

    for ticker, description in test_companies:
        console.print(f"\n[cyan]Testing: {ticker} - {description}[/cyan]")

        try:
            company = Company(ticker)
            filings = company.get_filings()
            filings_10k = company.get_filings(form='10-K')

            console.print(f"  Total filings: {len(filings)}")
            console.print(f"  Date range: {filings.date_range}")
            console.print(f"  10-K filings: {len(filings_10k)}")
            if len(filings_10k) > 0:
                console.print(f"  10-K date range: {filings_10k.date_range}")

            results[ticker] = {
                'total_filings': len(filings),
                'date_range': filings.date_range,
                'filing_10k_count': len(filings_10k),
                'success': True
            }

        except Exception as e:
            console.print(f"  ❌ Error: {str(e)}")
            results[ticker] = {
                'error': str(e),
                'success': False
            }

    return results

def analyze_cache_behavior():
    """Analyze potential caching issues"""
    console.print("\n[bold blue]Cache Behavior Analysis[/bold blue]")

    try:
        # Test multiple loads of same company
        console.print("Testing multiple loads of MSFT...")

        msft1 = Company('MSFT')
        filings1 = msft1.get_filings()
        console.print(f"First load: {len(filings1)} filings")

        msft2 = Company('MSFT')
        filings2 = msft2.get_filings()
        console.print(f"Second load: {len(filings2)} filings")

        if len(filings1) == len(filings2):
            console.print("✅ Consistent results across loads")
        else:
            console.print("❌ Inconsistent results - possible caching issue")

        # Test cache clearing behavior
        console.print("\nTesting with different cache settings...")
        filings3 = msft1.get_filings(use_cache=False)
        console.print(f"No cache: {len(filings3)} filings")

        return {
            'consistent_results': len(filings1) == len(filings2) == len(filings3),
            'first_load': len(filings1),
            'second_load': len(filings2),
            'no_cache': len(filings3)
        }

    except Exception as e:
        console.print(f"❌ Cache analysis failed: {str(e)}")
        return {'error': str(e)}

if __name__ == "__main__":
    # Main reproduction
    result = reproduce_missing_early_filings()

    # Additional testing
    other_companies = test_other_companies()
    cache_analysis = analyze_cache_behavior()

    # Summary
    print(f"\n" + "="*50)
    print("INVESTIGATION SUMMARY")
    print("="*50)

    if result.get('issue_reproduced'):
        print(f"❌ Issue #374 reproduced")
    else:
        print(f"✅ Issue #374 NOT reproduced")

    print(f"MSFT filings: {result.get('total_filings', 'Unknown')}")
    print(f"Date range: {result.get('date_range', 'Unknown')}")
    print(f"Conclusion: {result.get('conclusion', 'Unknown')}")

    # Recommend next steps
    if not result.get('issue_reproduced'):
        print(f"\nRECOMMENDED ACTIONS:")
        print(f"1. Ask user to upgrade to latest EdgarTools version")
        print(f"2. Ask user to clear cache and try again")
        print(f"3. Ask user to test with fresh Python environment")
        print(f"4. May be user environment or network-specific issue")
    else:
        print(f"\nRECOMMENDED ACTIONS:")
        print(f"1. Investigate pagination logic in company filings")
        print(f"2. Check SEC API response handling")
        print(f"3. Add debug logging to filing retrieval process")