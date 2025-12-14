"""
Debug find_statement for issue #518
"""

from edgar import Company

# CORT 2018
company = Company("CORT")
filings = company.get_filings(form="10-K")
filing = [f for f in filings if '2019-0' in str(f.filing_date)][0]

print(f"Filing: {filing.accession_no}\n")
xbrl = filing.xbrl()

# Debug find_statement
print("=" * 80)
print("find_statement('IncomeStatement') Debug")
print("=" * 80)

matching_statements, found_role, actual_statement_type = xbrl.find_statement('IncomeStatement')

print(f"\nmatching_statements: {len(matching_statements)} statements")
for i, stmt in enumerate(matching_statements):
    print(f"\n  Statement {i+1}:")
    print(f"    Type: {stmt.get('type')}")
    print(f"    Name: {stmt.get('name')}")
    print(f"    Role: {stmt.get('role')[:80]}..." if len(stmt.get('role', '')) > 80 else f"    Role: {stmt.get('role')}")

print(f"\nfound_role: {found_role}")
print(f"actual_statement_type: {actual_statement_type}")

# Check if found_role is in presentation_trees
if found_role:
    in_pres_trees = found_role in xbrl.presentation_trees
    print(f"found_role in presentation_trees: {in_pres_trees}")

# Now check get_statement
print("\n" + "=" * 80)
print("get_statement('IncomeStatement') Debug")
print("=" * 80)

statement_data = xbrl.get_statement('IncomeStatement')
print(f"\nReturned {len(statement_data)} line items")

if len(statement_data) > 0:
    print("\nFirst 10 concepts:")
    for i, item in enumerate(statement_data[:10]):
        print(f"  {i+1}. {item.get('concept', 'N/A')} - {item.get('label', 'N/A')}")

# Check what statements ARE available
print("\n" + "=" * 80)
print("Available Statements")
print("=" * 80)

all_statements = xbrl.get_all_statements()
financial_statements = [s for s in all_statements if s.get('category') == 'statement']

print(f"\nFinancial Statements: {len(financial_statements)}")
for stmt in financial_statements:
    print(f"\n  Name: {stmt.get('name')}")
    print(f"  Type: {stmt.get('type')}")
    print(f"  Role: {stmt.get('role')[:60]}..." if len(stmt.get('role', '')) > 60 else f"  Role: {stmt.get('role')}")
