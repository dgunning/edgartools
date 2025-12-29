"""
Test Q4 EPS calculation using derive_eps_for_quarter method.
"""
from edgar import Company, set_identity
from edgar.entity.ttm import TTMCalculator

set_identity("AI Agent SaifA@example.com")

print("=" * 60)
print("Q4 EPS CALCULATION TEST (NVDA)")
print("=" * 60)

company = Company("NVDA")
facts = company.facts

# Get required facts for EPS calculation - use precise concept names
print("\n1. Finding Net Income facts...")
ni_concepts = ['us-gaap:NetIncomeLoss', 'us-gaap:ProfitLoss', 'us-gaap:NetIncome']
ni_facts = [f for f in facts if f.concept in ni_concepts]
print(f"   Found {len(ni_facts)} Net Income facts")

# Show sample FY values
fy_ni = [f for f in ni_facts if f.fiscal_period == 'FY'][-3:]
for f in fy_ni:
    print(f"   FY{f.fiscal_year}: ${f.numeric_value/1e9:.2f}B")

print("\n2. Finding Weighted Average Shares facts...")
shares_concepts = ['us-gaap:WeightedAverageNumberOfSharesOutstandingBasic']
shares_facts = [f for f in facts if f.concept in shares_concepts]
print(f"   Found {len(shares_facts)} Shares facts")

# Show sample FY values
fy_shares = [f for f in shares_facts if f.fiscal_period == 'FY'][-3:]
for f in fy_shares:
    print(f"   FY{f.fiscal_year}: {f.numeric_value/1e9:.2f}B shares")

print("\n3. Calculating Q4 EPS...")
calc = TTMCalculator(ni_facts)
derived_eps = calc.derive_eps_for_quarter(
    net_income_facts=ni_facts,
    shares_facts=shares_facts
)

print(f"\n   Derived {len(derived_eps)} Q4 EPS values:")
if len(derived_eps) == 0:
    print("   (No Q4 EPS derived - check Net Income / Shares data)")
else:
    for eps in derived_eps[-5:]:  # Show last 5
        print(f"   * FY{eps.fiscal_year} Q4 EPS = ${eps.numeric_value:.4f}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
