"""
Reproduction script for GitHub Issue #518
Missing Income Statement lines for CORT and AMZN

Issue: Income statement returning wrong data or incomplete data
- CORT 2018/2019: Returns Cash Flow Statement instead of Income Statement
- AMZN Q3 2025: Returns only NetIncome (missing other lines)
"""

from edgar import Company

print("=" * 80)
print("Reproducing GitHub Issue #518 - Missing Income Statement Lines")
print("=" * 80)

# Test Case 1: CORT 2018
print("\n" + "=" * 80)
print("Test Case 1: CORT 2018 10-K")
print("=" * 80)

try:
    company = Company("CORT")
    # Get 2018 10-K
    filings = company.get_filings(form="10-K")
    print(f"\nFound {len(filings)} 10-K filings for CORT")

    # Find 2018 filing
    filing_2018 = None
    for filing in filings:
        if '2018' in str(filing.filing_date) or '2019-0' in str(filing.filing_date):
            filing_2018 = filing
            break

    if filing_2018:
        print(f"\n2018 Filing: {filing_2018.accession_no}")
        print(f"Filing Date: {filing_2018.filing_date}")

        xbrl = filing_2018.xbrl()
        if xbrl:
            print("\nXBRL loaded successfully")
            print(f"Period of report: {xbrl.period_of_report}")

            # Get current period income statement
            current = xbrl.current_period
            if current:
                print(f"\nCurrent period: {current}")

                # Get income statement with raw concepts
                is_df = current.income_statement(raw_concepts=True, as_statement=False)

                if is_df is not None and not is_df.empty:
                    print(f"\nIncome Statement shape: {is_df.shape}")
                    print(f"Number of concepts: {len(is_df)}")
                    print("\nFirst 20 concepts:")
                    print(is_df['concept'].head(20).tolist())

                    # Check if these are cash flow concepts
                    cash_flow_keywords = ['CashFlow', 'Operating', 'Investing', 'Financing',
                                         'IncreaseDecrease', 'PaymentsTo', 'ProceedsFrom']
                    income_keywords = ['Revenue', 'Income', 'Expense', 'GrossProfit',
                                      'OperatingIncome', 'EarningsPerShare']

                    concepts_list = is_df['concept'].tolist()
                    cash_flow_count = sum(1 for c in concepts_list if any(k in str(c) for k in cash_flow_keywords))
                    income_count = sum(1 for c in concepts_list if any(k in str(c) for k in income_keywords))

                    print(f"\nConcepts with Cash Flow keywords: {cash_flow_count}")
                    print(f"Concepts with Income keywords: {income_count}")

                    if cash_flow_count > income_count:
                        print("\n⚠️  WARNING: More cash flow concepts than income concepts!")
                        print("This looks like the Cash Flow Statement, not Income Statement")
                else:
                    print("\n❌ Income statement is empty or None")
            else:
                print("\n❌ No current period found")
        else:
            print("\n❌ XBRL not available")
    else:
        print("\n❌ Could not find 2018 filing")

except Exception as e:
    print(f"\n❌ Error with CORT 2018: {e}")
    import traceback
    traceback.print_exc()

# Test Case 2: AMZN Q3 2025
print("\n\n" + "=" * 80)
print("Test Case 2: AMZN Q3 2025")
print("=" * 80)

try:
    company = Company("AMZN")
    # Get recent 10-Q
    filings = company.get_filings(form="10-Q")
    print(f"\nFound {len(filings)} 10-Q filings for AMZN")

    # Get the latest (should be Q3 2025)
    if len(filings) > 0:
        filing = filings[0]
        print(f"\nLatest 10-Q: {filing.accession_no}")
        print(f"Filing Date: {filing.filing_date}")

        xbrl = filing.xbrl()
        if xbrl:
            print("\nXBRL loaded successfully")
            print(f"Period of report: {xbrl.period_of_report}")

            # Get current period income statement
            current = xbrl.current_period
            if current:
                print(f"\nCurrent period: {current}")

                # Get income statement with raw concepts
                is_df = current.income_statement(raw_concepts=True, as_statement=False)

                if is_df is not None and not is_df.empty:
                    print(f"\nIncome Statement shape: {is_df.shape}")
                    print(f"Number of concepts: {len(is_df)}")
                    print(f"\nAll concepts ({len(is_df)} total):")
                    for idx, concept in enumerate(is_df['concept'].tolist(), 1):
                        print(f"  {idx}. {concept}")

                    if len(is_df) <= 3:
                        print("\n⚠️  WARNING: Only 1-3 lines in income statement!")
                        print("Expected dozens of lines for a company like Amazon")
                else:
                    print("\n❌ Income statement is empty or None")
            else:
                print("\n❌ No current period found")
        else:
            print("\n❌ XBRL not available")
    else:
        print("\n❌ No 10-Q filings found")

except Exception as e:
    print(f"\n❌ Error with AMZN Q3 2025: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("Reproduction Complete")
print("=" * 80)
