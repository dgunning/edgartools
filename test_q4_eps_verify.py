"""
Verify Q4 EPS is in the statement data.
"""
from edgar import Company, set_identity

set_identity("AI Agent SaifA@example.com")

company = Company("NVDA")
facts = company.facts

# Get quarterly income statement
print("Getting quarterly income statement (4 periods)...")
stmt = facts.income_statement(periods=4, period='quarterly', as_dataframe=False)

print(f"\nPeriods: {stmt.periods}")

# Search for EPS
eps_item = stmt.find_item(label="Earnings Per Share, Basic")
if eps_item:
    print(f"\nEPS Basic found:")
    print(f"  Concept: {eps_item.concept}")
    print(f"  Values by period:")
    for period in stmt.periods:
        val = eps_item.values.get(period)
        print(f"    {period}: {val}")
else:
    print("\nEPS Basic NOT found in statement")

# Also check Diluted
eps_diluted = stmt.find_item(label="Earnings Per Share, Diluted")
if eps_diluted:
    print(f"\nEPS Diluted found:")
    for period in stmt.periods:
        val = eps_diluted.values.get(period)
        print(f"    {period}: {val}")
