from edgar import set_identity, Company

set_identity('Test User test@example.com')

facts = Company('MSFT').facts

# Valid period parameter values based on entity_facts.py:
# - 'annual': Annual periods (fiscal year data)
# - 'quarterly': Quarterly periods
# - 'ttm': Trailing Twelve Months

period_values = ['annual', 'quarterly', 'ttm']

for period in period_values:
    print(f"\n{'='*80}")
    print(f"Testing period='{period}' with periods=4")
    print('='*80)
    try:
        result = facts.income_statement(periods=4, period=period, as_dataframe=False)
        print(result)
        print(f"\n--- Type: {type(result).__name__} ---")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

# Also test with different 'periods' count for TTM
print(f"\n{'='*80}")
print(f"Testing period='ttm' with periods=8")
print('='*80)
try:
    result = facts.income_statement(periods=8, period='ttm', as_dataframe=False)
    print(result)
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
