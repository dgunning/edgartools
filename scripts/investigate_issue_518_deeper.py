"""
Deep investigation of GitHub Issue #518
Checking XBRL statement detection and rendering
"""

from edgar import Company

print("=" * 80)
print("Deep Investigation of GitHub Issue #518")
print("=" * 80)

# Test Case 1: CORT 2018
print("\n" + "=" * 80)
print("CORT 2018 - Detailed XBRL Investigation")
print("=" * 80)

company = Company("CORT")
filings = company.get_filings(form="10-K")

# Find 2018 filing
filing_2018 = None
for filing in filings:
    if '2019-0' in str(filing.filing_date):
        filing_2018 = filing
        break

if filing_2018:
    print(f"\nFiling: {filing_2018.accession_no}")
    xbrl = filing_2018.xbrl()

    # Check what statements are available
    print("\n--- Available Statements ---")
    if hasattr(xbrl, 'statements'):
        print(f"xbrl.statements type: {type(xbrl.statements)}")
        print("Available statement attributes:")
        for attr in dir(xbrl.statements):
            if not attr.startswith('_'):
                print(f"  - {attr}")

        # Check each statement type
        print("\n--- Statement Availability ---")
        if hasattr(xbrl.statements, 'income'):
            print(f"Income statement: {xbrl.statements.income is not None}")
            if xbrl.statements.income:
                print(f"  Type: {type(xbrl.statements.income)}")
                print(f"  Periods: {len(xbrl.statements.income)}")

        if hasattr(xbrl.statements, 'cash_flow'):
            print(f"Cash flow statement: {xbrl.statements.cash_flow is not None}")
            if xbrl.statements.cash_flow:
                print(f"  Type: {type(xbrl.statements.cash_flow)}")
                print(f"  Periods: {len(xbrl.statements.cash_flow)}")

        if hasattr(xbrl.statements, 'balance_sheet'):
            print(f"Balance sheet: {xbrl.statements.balance_sheet is not None}")

    # Get current period and check income statement
    print("\n--- Current Period Income Statement ---")
    current = xbrl.current_period
    print(f"Current period: {current}")

    # Try getting income statement different ways
    print("\n--- Different Income Statement Retrieval Methods ---")

    # Method 1: via current period
    is1 = current.income_statement(raw_concepts=True, as_statement=False)
    print("\n1. current.income_statement():")
    print(f"   Shape: {is1.shape if is1 is not None else 'None'}")
    if is1 is not None and not is1.empty:
        print(f"   First 5 concepts: {is1['concept'].head().tolist()}")

    # Method 2: via xbrl.statements
    if hasattr(xbrl.statements, 'income') and xbrl.statements.income:
        is2 = xbrl.statements.income
        print("\n2. xbrl.statements.income:")
        print(f"   Type: {type(is2)}")
        if hasattr(is2, 'to_dataframe'):
            df = is2.to_dataframe()
            print(f"   Shape: {df.shape}")
            print(f"   First 5 concepts: {df['concept'].head().tolist() if 'concept' in df.columns else 'No concept column'}")

    # Check presentation tree
    print("\n--- Presentation Tree Analysis ---")
    if hasattr(xbrl, 'presentation'):
        print(f"Presentation tree available: {xbrl.presentation is not None}")
        if xbrl.presentation:
            # Try to get income statement roles
            roles = xbrl.presentation.keys() if hasattr(xbrl.presentation, 'keys') else []
            print(f"Number of presentation roles: {len(roles)}")

            income_roles = [r for r in roles if 'income' in str(r).lower()]
            print(f"Income-related roles: {len(income_roles)}")
            if income_roles:
                print("First 3 income roles:")
                for role in income_roles[:3]:
                    print(f"  - {role}")

print("\n\n" + "=" * 80)
print("AMZN Q3 2025 - Detailed XBRL Investigation")
print("=" * 80)

company = Company("AMZN")
filing = company.get_filings(form="10-Q").latest()

print(f"\nFiling: {filing.accession_no}")
xbrl = filing.xbrl()

# Check what statements are available
print("\n--- Available Statements ---")
if hasattr(xbrl, 'statements'):
    print(f"xbrl.statements type: {type(xbrl.statements)}")

    # Check each statement type
    print("\n--- Statement Availability ---")
    if hasattr(xbrl.statements, 'income'):
        print(f"Income statement: {xbrl.statements.income is not None}")
        if xbrl.statements.income:
            print(f"  Type: {type(xbrl.statements.income)}")
            print(f"  Number of periods: {len(xbrl.statements.income)}")

# Get current period and check income statement
print("\n--- Current Period Income Statement ---")
current = xbrl.current_period
print(f"Current period: {current}")

# Try getting income statement
is_df = current.income_statement(raw_concepts=True, as_statement=False)
print(f"\ncurrent.income_statement() shape: {is_df.shape if is_df is not None else 'None'}")
if is_df is not None and not is_df.empty:
    print(f"Concepts: {is_df['concept'].tolist()}")

# Method 2: via xbrl.statements
if hasattr(xbrl.statements, 'income') and xbrl.statements.income:
    is2 = xbrl.statements.income
    print("\nxbrl.statements.income:")
    print(f"   Type: {type(is2)}")
    if hasattr(is2, 'to_dataframe'):
        df = is2.to_dataframe()
        print(f"   Shape: {df.shape}")
        print(f"   Columns: {df.columns.tolist()}")
        if 'concept' in df.columns:
            print(f"   Number of unique concepts: {df['concept'].nunique()}")
            print(f"   First 10 concepts: {df['concept'].head(10).tolist()}")

# Check presentation tree
print("\n--- Presentation Tree Analysis ---")
if hasattr(xbrl, 'presentation'):
    print(f"Presentation tree available: {xbrl.presentation is not None}")
    if xbrl.presentation:
        roles = xbrl.presentation.keys() if hasattr(xbrl.presentation, 'keys') else []
        print(f"Number of presentation roles: {len(roles)}")

        income_roles = [r for r in roles if 'income' in str(r).lower()]
        print(f"Income-related roles: {len(income_roles)}")
        if income_roles:
            print("First 3 income roles:")
            for role in income_roles[:3]:
                print(f"  - {role}")

print("\n" + "=" * 80)
print("Investigation Complete")
print("=" * 80)
