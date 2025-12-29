"""
Debug: Check if derived EPS period_key matches selected periods.
"""
from datetime import date
from edgar.entity.enhanced_statement import calculate_fiscal_year_for_label, detect_fiscal_year_end
from edgar.entity.ttm import TTMCalculator
from edgar.entity.models import FinancialFact

# Create sample facts to simulate the issue
ni_fy = FinancialFact(
    concept='us-gaap:NetIncomeLoss', taxonomy='us-gaap', label='Net Income',
    value=1000, numeric_value=1000, unit='USD',
    fiscal_year=2024, fiscal_period='FY', period_type='duration',
    period_start=date(2024, 1, 1), period_end=date(2024, 12, 31)
)
ni_ytd9 = FinancialFact(
    concept='us-gaap:NetIncomeLoss', taxonomy='us-gaap', label='Net Income',
    value=700, numeric_value=700, unit='USD',
    fiscal_year=2024, fiscal_period='Q3', period_type='duration',
    period_start=date(2024, 1, 1), period_end=date(2024, 9, 30)
)
shares_fy = FinancialFact(
    concept='us-gaap:WeightedAverageNumberOfSharesOutstandingBasic', taxonomy='us-gaap', label='Shares',
    value=100, numeric_value=100, unit='shares',
    fiscal_year=2024, fiscal_period='FY', period_type='duration',
    period_start=date(2024, 1, 1), period_end=date(2024, 12, 31)
)

print("Deriving Q4 EPS...")
calc = TTMCalculator([ni_fy, ni_ytd9])
derived_eps = calc.derive_eps_for_quarter(
    net_income_facts=[ni_fy, ni_ytd9],
    shares_facts=[shares_fy]
)

print(f"Derived {len(derived_eps)} EPS facts")
for eps in derived_eps:
    print(f"  concept: {eps.concept}")
    print(f"  fiscal_year: {eps.fiscal_year}")
    print(f"  fiscal_period: {eps.fiscal_period}")
    print(f"  period_end: {eps.period_end}")
    print(f"  numeric_value: {eps.numeric_value}")
    
    # Check what the period_key and label would be
    correct_fiscal_year = calculate_fiscal_year_for_label(eps.period_end, 12)
    period_key = (correct_fiscal_year, eps.fiscal_period, eps.period_end)
    period_label = f"{eps.fiscal_period} {correct_fiscal_year}"
    print(f"  period_key: {period_key}")
    print(f"  period_label: {period_label}")
