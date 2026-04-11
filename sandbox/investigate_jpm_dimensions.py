"""
Investigate JPM's Dimensional Reporting

Check if ShortTermBorrowings and other debt concepts use dimensions.
"""

from edgar import Company, set_identity, use_local_storage
import yfinance as yf
import pandas as pd

set_identity("Dev Gunning developer-gunning@gmail.com")
use_local_storage(True)

print("="*80)
print("JPM DIMENSIONAL DEBT ANALYSIS")
print("="*80)

# Get JPM data
company = Company('JPM')
filing = list(company.get_filings(form='10-K'))[0]
xbrl = filing.xbrl()
stock = yf.Ticker('JPM')

# Get yfinance reference
yf_value = stock.balance_sheet.loc['Current Debt'].iloc[0] if 'Current Debt' in stock.balance_sheet.index else None

print(f"\n🎯 TARGET: ${yf_value/1e9:.2f}B (yfinance 'Current Debt')")
print(f"📊 CURRENT: $52.89B (XBRL ShortTermBorrowings, non-dimensioned)")
print(f"❓ GAP: $11.58B")

# Get all ShortTermBorrowings facts (INCLUDING dimensions)
print(f"\n" + "="*80)
print("SHORTTERMBORROWINGS - ALL FACTS (with dimensions)")
print("="*80)

all_facts = xbrl.facts.query().to_dataframe()

# Filter for ShortTermBorrowings
stb_facts = all_facts[all_facts['concept'].str.contains('ShortTermBorrowings', case=False, na=False)]

print(f"\nFound {len(stb_facts)} ShortTermBorrowings facts")

if len(stb_facts) > 0:
    # Group by period
    for period in stb_facts['period_key'].unique()[:3]:  # Show top 3 periods
        period_facts = stb_facts[stb_facts['period_key'] == period]

        print(f"\n📅 Period: {period}")
        print(f"   Total facts: {len(period_facts)}")

        # Show dimensioned vs non-dimensioned
        if 'full_dimension_label' in period_facts.columns:
            non_dim = period_facts[period_facts['full_dimension_label'].isna()]
            dim = period_facts[period_facts['full_dimension_label'].notna()]

            print(f"   Non-dimensioned: {len(non_dim)}")
            print(f"   Dimensioned: {len(dim)}")

            # Show non-dimensioned values
            if len(non_dim) > 0:
                for idx, row in non_dim.iterrows():
                    value = row.get('numeric_value', None)
                    if value:
                        print(f"     Total: ${value/1e9:.2f}B")

            # Show dimensioned values
            if len(dim) > 0:
                print(f"\n   Dimensional breakdown:")
                for idx, row in dim.iterrows():
                    dimension = row['full_dimension_label']
                    value = row.get('numeric_value', None)
                    if value:
                        print(f"     - {dimension}: ${value/1e9:.2f}B")

# Check CommercialPaper (we know it has dimensions)
print(f"\n" + "="*80)
print("COMMERCIALPAPER - ALL FACTS (with dimensions)")
print("="*80)

cp_facts = all_facts[all_facts['concept'].str.contains('CommercialPaper', case=False, na=False)]

print(f"\nFound {len(cp_facts)} CommercialPaper facts")

# Focus on instant_2024-12-31
cp_2024 = cp_facts[cp_facts['period_key'] == 'instant_2024-12-31']

if len(cp_2024) > 0:
    print(f"\n📅 Period: instant_2024-12-31")

    # Show dimensioned breakdown
    if 'full_dimension_label' in cp_2024.columns:
        dim_facts = cp_2024[cp_2024['full_dimension_label'].notna()]

        if len(dim_facts) > 0:
            print(f"\n   Dimensional values:")
            total_cp = 0
            for idx, row in dim_facts.iterrows():
                concept = row['concept']
                dimension = row['full_dimension_label']
                value = row.get('numeric_value', None)

                if value:
                    print(f"     - {concept}")
                    print(f"       {dimension}: ${value/1e9:.2f}B")

                    # Only sum us-gaap:CommercialPaper (not eliminated items)
                    if 'us-gaap:CommercialPaper' in concept and 'Eliminated' not in concept:
                        total_cp += value

            print(f"\n   💡 Total CommercialPaper (non-eliminated): ${total_cp/1e9:.2f}B")

# Check for LongTermDebt with "current" dimension
print(f"\n" + "="*80)
print("LONGTERMDEBT - CHECK FOR 'CURRENT' DIMENSIONS")
print("="*80)

ltd_facts = all_facts[all_facts['concept'].str.contains('LongTermDebt', case=False, na=False)]

print(f"\nFound {len(ltd_facts)} LongTermDebt facts")

# Filter for facts with "current" in dimension label
if 'full_dimension_label' in ltd_facts.columns:
    current_dim = ltd_facts[
        ltd_facts['full_dimension_label'].notna() &
        ltd_facts['full_dimension_label'].str.contains('current', case=False, na=False)
    ]

    print(f"Facts with 'current' in dimension: {len(current_dim)}")

    if len(current_dim) > 0:
        print(f"\n📋 Long-term debt with 'current' dimension:")
        for idx, row in current_dim.iterrows():
            concept = row['concept']
            period = row['period_key']
            dimension = row['full_dimension_label']
            value = row.get('numeric_value', None)

            if value and period == 'instant_2024-12-31':
                print(f"\n  ⭐ {concept}")
                print(f"     Period: {period}")
                print(f"     Dimension: {dimension}")
                print(f"     Value: ${value/1e9:.2f}B")

                # Check if this could be the missing piece
                if abs(value/1e9 - 11.58) < 3:
                    print(f"     🎯 THIS COULD BE THE MISSING $11.58B!")

# Summary
print(f"\n" + "="*80)
print("SUMMARY")
print("="*80)

print(f"\n💡 Key findings:")
print(f"  1. JPM uses dimensional reporting extensively")
print(f"  2. CommercialPaper has $21.80B in dimensions (consolidated VIEs)")
print(f"  3. ShortTermBorrowings might have dimensional values too")
print(f"  4. Current implementation filters OUT dimensioned values")

print(f"\n🔧 Potential solutions:")
print(f"  1. Include dimensional values in composite calculation")
print(f"  2. Look for 'current portion' in dimensions")
print(f"  3. Check if CommercialPaper dimensions should be included")

print("\n" + "="*80)
