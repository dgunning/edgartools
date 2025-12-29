# Debug TTM Q4/FY issue
from edgar import set_identity, Company
from edgar.entity.ttm import TTMCalculator

set_identity('Test User test@example.com')

facts = Company('MSFT').facts

# Get revenue facts directly  
revenue_concepts = [
    'RevenueFromContractWithCustomerExcludingAssessedTax',
    'Revenues',
    'Revenue',
]

for concept in revenue_concepts:
    try:
        concept_facts = facts.query().by_concept(f'us-gaap:{concept}').execute()
        if concept_facts:
            print(f"\n{'='*60}")
            print(f"Testing concept: {concept}")
            print(f"Found {len(concept_facts)} facts")
            print('='*60)
            
            calculator = TTMCalculator(concept_facts)
            
            # Get quarterized facts
            quarterly = calculator._quarterize_facts()
            
            print(f"\nQuarterized facts ({len(quarterly)} quarters):")
            for q in sorted(quarterly, key=lambda x: x.period_end, reverse=True)[:12]:
                print(f"  {q.fiscal_period} {q.fiscal_year}: period_end={q.period_end}, value=${q.numeric_value/1e9:.1f}B")
                if hasattr(q, 'calculation_context') and q.calculation_context:
                    print(f"    ^^^ DERIVED: {q.calculation_context}")
            
            # Now calculate TTM trend
            print("\n\nTTM Trend:")
            trend = calculator.calculate_ttm_trend(periods=8)
            print(trend[['as_of_quarter', 'fiscal_year', 'fiscal_period', 'ttm_value', 'as_of_date']])
            break
    except Exception as e:
        print(f"Error with {concept}: {e}")
        continue
