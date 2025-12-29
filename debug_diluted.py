"""
Debug: Check if Diluted shares are being found.
"""
from edgar import Company, set_identity

set_identity("AI Agent SaifA@example.com")

company = Company("NVDA")
facts = company.facts

# Check shares data
print("Checking shares data...")

basic = [f for f in facts if f.concept == 'us-gaap:WeightedAverageNumberOfSharesOutstandingBasic']
diluted = [f for f in facts if f.concept == 'us-gaap:WeightedAverageNumberOfSharesOutstandingDiluted']

print(f"\nBasic Shares: {len(basic)} facts")
fy_basic = [f for f in basic if f.fiscal_period == 'FY'][-3:]
for f in fy_basic:
    print(f"  FY{f.fiscal_year}: {f.numeric_value/1e9:.2f}B")

print(f"\nDiluted Shares: {len(diluted)} facts")
fy_diluted = [f for f in diluted if f.fiscal_period == 'FY'][-3:]
for f in fy_diluted:
    print(f"  FY{f.fiscal_year}: {f.numeric_value/1e9:.2f}B")

# Test derive_eps_for_quarter with diluted
from edgar.entity.ttm import TTMCalculator

ni_concepts = ['us-gaap:NetIncomeLoss', 'us-gaap:ProfitLoss', 'us-gaap:NetIncome']
ni_facts = [f for f in facts if f.concept in ni_concepts]

print("\nTesting Diluted EPS derivation...")
calc = TTMCalculator(ni_facts)
derived_diluted = calc.derive_eps_for_quarter(
    net_income_facts=ni_facts,
    shares_facts=diluted,
    eps_concept='us-gaap:EarningsPerShareDiluted'
)
print(f"Derived {len(derived_diluted)} Diluted EPS facts")
for eps in derived_diluted[-3:]:
    print(f"  FY{eps.fiscal_year} Q4: ${eps.numeric_value:.4f}")
