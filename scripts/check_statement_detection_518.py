"""
Check if income statements are being detected in XBRL
"""

from edgar import Company

print("=" * 80)
print("Statement Detection Analysis for Issue #518")
print("=" * 80)

# CORT 2018
print("\n" + "=" * 80)
print("CORT 2018")
print("=" * 80)

company = Company("CORT")
filings = company.get_filings(form="10-K")
filing = [f for f in filings if '2019-0' in str(f.filing_date)][0]

print(f"Filing: {filing.accession_no}")
xbrl = filing.xbrl()

print("\n--- xbrl.statements Inspection ---")
print(f"Type: {type(xbrl.statements)}")
print(f"Dir: {[x for x in dir(xbrl.statements) if not x.startswith('_')]}")

print("\n--- Individual Statement Check ---")
print(f"balance_sheet: {xbrl.statements.balance_sheet}")
print(f"income_statement: {xbrl.statements.income_statement}")
print(f"cashflow_statement: {xbrl.statements.cashflow_statement}")
print(f"comprehensive_income: {xbrl.statements.comprehensive_income}")
print(f"statement_of_equity: {xbrl.statements.statement_of_equity}")

# Check raw statements list
print("\n--- Raw Statements List ---")
if hasattr(xbrl.statements, 'statements'):
    statements = xbrl.statements.statements
    print(f"Number of statements: {len(statements)}")
    for i, stmt in enumerate(statements):
        print(f"\n Statement {i+1}:")
        print(f"  Type: {type(stmt)}")
        print(f"  Name: {stmt.name if hasattr(stmt, 'name') else 'N/A'}")
        print(f"  Category: {stmt.category if hasattr(stmt, 'category') else 'N/A'}")
        if hasattr(stmt, 'to_dataframe'):
            df = stmt.to_dataframe()
            print(f"  Rows: {len(df)}")
            if len(df) > 0 and 'concept' in df.columns:
                print(f"  First 5 concepts: {df['concept'].head().tolist()}")

# Check statement categories
print("\n--- Statement Categories ---")
if hasattr(xbrl.statements, 'get_statements_by_category'):
    categories = ['IncomeStatement', 'StatementOfIncome', 'OperationsStatement']
    for cat in categories:
        try:
            stmts = xbrl.statements.get_statements_by_category(cat)
            print(f"{cat}: {len(stmts) if stmts else 0} statements")
        except:
            print(f"{cat}: Error retrieving")

print("\n\n" + "=" * 80)
print("AMZN Q3 2025")
print("=" * 80)

company = Company("AMZN")
filing = company.get_filings(form="10-Q").latest()

print(f"Filing: {filing.accession_no}")
xbrl = filing.xbrl()

print("\n--- xbrl.statements Inspection ---")
print(f"Type: {type(xbrl.statements)}")

print("\n--- Individual Statement Check ---")
print(f"balance_sheet: {xbrl.statements.balance_sheet}")
print(f"income_statement: {xbrl.statements.income_statement}")
print(f"cashflow_statement: {xbrl.statements.cashflow_statement}")
print(f"comprehensive_income: {xbrl.statements.comprehensive_income}")

# Check raw statements list
print("\n--- Raw Statements List ---")
if hasattr(xbrl.statements, 'statements'):
    statements = xbrl.statements.statements
    print(f"Number of statements: {len(statements)}")
    for i, stmt in enumerate(statements):
        print(f"\nStatement {i+1}:")
        print(f"  Type: {type(stmt)}")
        print(f"  Name: {stmt.name if hasattr(stmt, 'name') else 'N/A'}")
        print(f"  Category: {stmt.category if hasattr(stmt, 'category') else 'N/A'}")
        if hasattr(stmt, 'to_dataframe'):
            df = stmt.to_dataframe()
            print(f"  Rows: {len(df)}")
            if len(df) > 0 and 'concept' in df.columns:
                concepts = df['concept'].head(10).tolist()
                print(f"  First concepts: {concepts}")

print("\n" + "=" * 80)
