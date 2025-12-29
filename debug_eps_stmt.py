"""
Debug: Check if Q4 EPS is being added to the income statement.
"""
from edgar import Company, set_identity

set_identity("AI Agent SaifA@example.com")

company = Company("msft")
facts = company.facts

# Get quarterly income statement
print("Getting quarterly income statement...")
stmt = facts.income_statement(periods=8, period='quarterly', as_dataframe=False)

# Check periods
print(f"\nPeriods in statement: {stmt.periods}")

# Search for EPS items
print("\nSearching for EPS in statement items...")
for item in stmt:
    if 'EPS' in item.label.upper() or 'EARNINGS PER SHARE' in item.label.upper():
        print(f"\n  Found: {item.label}")
        print(f"  Concept: {item.concept}")
        print(f"  Values: {item.values}")


# Get quarterly income statement
print("Getting annual income statement...")
stmt = facts.income_statement(periods=8, period='annual', as_dataframe=False)