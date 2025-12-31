from quant import QuantCompany
from edgar import set_identity

# Setup identity
set_identity("AI Agent SaifA@example.com")

# Use QuantCompany instead of Company to access TTM and Q4 derivation features
company = QuantCompany("TSLA")

print("--- Testing Quarterly Income Statement (with Q4 derivation) ---")
# QuantCompany.income_statement handles the custom logic
fact = company.income_statement(periods=8, period='quarterly', as_dataframe=False)
print(fact)

print('\n' + '-' * 50 + '\n')

print("--- Testing TTM Income Statement ---")
fact = company.income_statement(periods=8, period='ttm', as_dataframe=False)
print(fact)

print('\n' + '-' * 50 + '\n')

print("--- Testing Annual Income Statement (Split Adjusted) ---")
fact = company.income_statement(periods=8, period='annual', as_dataframe=False)
print(fact)
