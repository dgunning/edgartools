from edgar import *
from edgar.entity import EntityFacts
import pandas as pd



def check_facts_availability(ticker:str):
    c = Company(ticker)
    print(f"{'='*60}")
    print(f"INVESTIGATING {ticker} FACTS AVAILABILITY")
    print(f"{'='*60}")
    
    # Show income statement to see what data appears
    print(f"\n📊 INCOME STATEMENT (Annual):")
    try:
        income_statement = c.income_statement(annual=True)
        print(income_statement)
    except Exception as e:
        print(f"❌ Income statement error: {e}")

    # Show balance sheet to see what data appears  
    print(f"\n📊 BALANCE SHEET (Annual):")
    try:
        balance_sheet = c.balance_sheet(annual=True)
        print(balance_sheet)
    except Exception as e:
        print(f"❌ Balance sheet error: {e}")
        
    # Now investigate using facts query for missing data
    print(f"\n🔍 FACTS INVESTIGATION:")
    facts:EntityFacts = c.get_facts()
    print(f"Total facts loaded: {len(facts):,}")
    
    # Test 1: Check for Revenue in problematic years 2019-2022
    print(f"\n1. Revenue facts 2019-2022:")
    try:
        revenue_2019_2022 = facts.query().date_range(start="2019-01-01", end="2022-12-31").by_label("Revenue")
        print(f"   Revenue 2019-2022: {revenue_2019_2022}")
    except Exception as e:
        print(f"   Revenue query error: {e}")
        
    # Test 2: Check what data exists in those years at all
    print(f"\n2. Any facts available 2019-2022:")
    try:
        any_facts_2019_2022 = facts.query().date_range(start="2019-01-01", end="2022-12-31")
        print(f"   Any facts 2019-2022: {any_facts_2019_2022}")
    except Exception as e:
        print(f"   Any facts query error: {e}")
        
    # Test 3: Check year by year
    print(f"\n3. Data availability by year:")
    for year in [2019, 2020, 2021, 2022, 2023, 2024]:
        try:
            year_facts = facts.query().date_range(start=f"{year}-01-01", end=f"{year}-12-31")
            print(f"   {year}: {year_facts}")
        except Exception as e:
            print(f"   {year}: Error - {e}")
    
    # Test 4: Try different revenue concept searches for 2019-2022
    print(f"\n4. Revenue concept searches 2019-2022:")
    revenue_searches = ["Revenue", "Revenues", "Contract Revenue"]
    for search in revenue_searches:
        try:
            concept_facts = facts.query().date_range(start="2019-01-01", end="2022-12-31").by_label(search)
            print(f"   '{search}': {concept_facts}")
        except Exception as e:
            print(f"   '{search}': Error - {e}")
            
    # Test 5: Get specific data for missing years to see structure
    print(f"\n5. Detailed analysis of missing years data:")
    missing_years = [2019, 2020]
    for year in missing_years:
        print(f"\n   --- {year} Detailed Analysis ---")
        try:
            year_facts = facts.query().date_range(start=f"{year}-01-01", end=f"{year}-12-31").to_dataframe()
            if year_facts is not None and not year_facts.empty:
                print(f"   {year} facts shape: {year_facts.shape}")
                
                # Look for revenue data specifically
                revenue_data = year_facts[year_facts['label'].str.contains('Revenue', case=False, na=False)]
                if not revenue_data.empty:
                    print(f"   {year} revenue facts: {len(revenue_data)}")
                    print(f"   Sample revenue data:")
                    sample_revenue = revenue_data[['concept', 'label', 'value', 'period_start', 'period_end']].head(3)
                    print(sample_revenue.to_string())
                else:
                    print(f"   No revenue facts found for {year}")
                    
                # Look for balance sheet items
                balance_items = year_facts[year_facts['label'].str.contains('Assets|Cash|Liability', case=False, na=False)]
                if not balance_items.empty:
                    print(f"   {year} balance sheet items: {len(balance_items)}")
                    print(f"   Sample balance sheet data:")
                    sample_balance = balance_items[['concept', 'label', 'value', 'period_start', 'period_end']].head(3)
                    print(sample_balance.to_string())
                    
                # Check period types (annual vs quarterly)
                print(f"   {year} period analysis:")
                if 'period_start' in year_facts.columns and 'period_end' in year_facts.columns:
                    # Calculate period lengths
                    year_facts['period_days'] = (pd.to_datetime(year_facts['period_end']) - pd.to_datetime(year_facts['period_start'])).dt.days
                    period_lengths = year_facts['period_days'].value_counts().sort_index()
                    print(f"   Period lengths: {period_lengths.to_dict()}")
                    
                    # Show annual periods (300+ days)
                    annual_data = year_facts[year_facts['period_days'] >= 300]
                    print(f"   Annual periods ({year}): {len(annual_data)} facts")
                    if len(annual_data) > 0:
                        annual_concepts = annual_data['concept'].value_counts().head(5)
                        print(f"   Top annual concepts: {annual_concepts.to_dict()}")
                        
            else:
                print(f"   No dataframe data for {year}")
        except Exception as e:
            print(f"   Error analyzing {year}: {e}")
            
    # Test 6: Compare with working years (2021-2022) structure
    print(f"\n6. Compare with working years structure:")
    working_years = [2021, 2022]  # These show up in statements
    for year in working_years:
        try:
            year_facts = facts.query().date_range(start=f"{year}-01-01", end=f"{year}-12-31").to_dataframe()
            if year_facts is not None and not year_facts.empty:
                print(f"   {year} (working): {year_facts.shape[0]} facts")
                
                # Check annual periods structure
                if 'period_start' in year_facts.columns and 'period_end' in year_facts.columns:
                    year_facts['period_days'] = (pd.to_datetime(year_facts['period_end']) - pd.to_datetime(year_facts['period_start'])).dt.days
                    annual_data = year_facts[year_facts['period_days'] >= 300]
                    print(f"   {year} annual facts: {len(annual_data)}")
                    
                    if len(annual_data) > 0:
                        # Check for key statement concepts
                        revenue_annual = annual_data[annual_data['label'].str.contains('Revenue', case=False, na=False)]
                        assets_annual = annual_data[annual_data['label'].str.contains('Assets', case=False, na=False)]
                        print(f"   {year} annual revenue concepts: {len(revenue_annual)}")
                        print(f"   {year} annual assets concepts: {len(assets_annual)}")
        except Exception as e:
            print(f"   Error analyzing working year {year}: {e}")


def check_tsla_specific_issue():
    """Investigate TSLA specifically for Issue #412."""
    print(f"\n{'='*60}")
    print(f"TSLA SPECIFIC ISSUE #412 INVESTIGATION") 
    print(f"{'='*60}")
    
    check_facts_availability("TSLA")
    
    print(f"\n{'='*60}")
    print(f"COMPARISON WITH AAPL (Known Working)")
    print(f"{'='*60}")
    
    check_facts_availability("AAPL")


if __name__ == '__main__':
    check_tsla_specific_issue()