#!/usr/bin/env python3
"""Debug AAPL revenue extraction to find the period mismatch."""

from edgar import Company

# Get Apple's latest 10-K
company = Company("AAPL")
filings = company.get_filings(form='10-K')
filing = None
for f in filings:
    filing = f
    break

print(f"Filing: {filing.form} filed {filing.filing_date}")

# Get XBRL
xbrl = filing.xbrl()

# Get ALL revenue facts with period information
# Try specific revenue concepts
revenue_concepts = [
    "us-gaap:Revenues",
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues"
]

print("\nSearching for revenue concepts:")
for concept in revenue_concepts:
    facts_df = xbrl.facts.query().by_concept(concept, exact=True).to_dataframe()
    if facts_df is not None and len(facts_df) > 0:
        print(f"\n  Found {len(facts_df)} facts for concept: {concept}")

        for _, row in facts_df.iterrows():
            value = row['value']
            period_key = row.get('period_key', 'unknown')

            # Handle both numeric and string values
            try:
                print(f"    Value: {float(value):,.0f} | Period: {period_key}")
            except (ValueError, TypeError):
                print(f"    Value: {value} | Period: {period_key}")

# Check what is.py extracts
print("\n" + "="*60)
print("Checking is.py extraction:")
print("="*60)

try:
    from quant.xbrl_standardize.map.is_module import extract_income_statement

    result = extract_income_statement(xbrl)
    if result and 'revenue' in result:
        print(f"is.py revenue: {result['revenue']:,.0f}")
except Exception as e:
    print(f"Could not test is.py: {e}")
