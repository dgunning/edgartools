"""
Deep Dive Investigation: JPM ShortTermDebt

Find all debt-related concepts and values to identify the missing $11.58B.
"""

from edgar import Company, set_identity, use_local_storage
import yfinance as yf
import pandas as pd

set_identity("Dev Gunning developer-gunning@gmail.com")
use_local_storage(True)

print("="*80)
print("JPM SHORT-TERM DEBT DEEP DIVE")
print("="*80)

# Get JPM data
company = Company('JPM')
filing = list(company.get_filings(form='10-K'))[0]
xbrl = filing.xbrl()
stock = yf.Ticker('JPM')

# Get yfinance reference
yf_value = None
if 'Current Debt' in stock.balance_sheet.index:
    yf_value = stock.balance_sheet.loc['Current Debt'].iloc[0]

print(f"\n🎯 TARGET: yfinance 'Current Debt' = ${yf_value/1e9:.2f}B")
print(f"📊 XBRL ShortTermBorrowings = $52.89B")
print(f"❓ GAP = $11.58B (18.0%)")

# Get ALL facts as DataFrame
print(f"\n" + "="*80)
print("STEP 1: GET ALL CONCEPTS FROM XBRL FACTS")
print("="*80)

# Use the facts query interface properly
all_facts_df = xbrl.facts.query().to_dataframe()

print(f"Total facts in XBRL: {len(all_facts_df)}")
print(f"Unique concepts: {all_facts_df['concept'].nunique()}")

# Get all unique concepts
all_concepts = all_facts_df['concept'].unique()

# Filter for debt/borrow related concepts
debt_concepts = [c for c in all_concepts if 'debt' in c.lower() or 'borrow' in c.lower()]

print(f"\n📋 Found {len(debt_concepts)} debt/borrow-related concepts:")
for concept in sorted(debt_concepts)[:20]:
    print(f"  - {concept}")

# STEP 2: Check each debt concept for current period values
print(f"\n" + "="*80)
print("STEP 2: EXTRACT VALUES FOR DEBT CONCEPTS")
print("="*80)

# Get the most recent period key
if len(all_facts_df) > 0 and 'period_key' in all_facts_df.columns:
    # Get instant periods (for balance sheet items)
    instant_periods = all_facts_df[all_facts_df['period_key'].str.startswith('instant_')]
    if len(instant_periods) > 0:
        latest_period = instant_periods['period_key'].max()
        print(f"\n🗓️  Latest instant period: {latest_period}")

        debt_values = {}

        for concept in debt_concepts:
            # Get facts for this concept in the latest period
            concept_facts = all_facts_df[
                (all_facts_df['concept'] == concept) &
                (all_facts_df['period_key'] == latest_period)
            ]

            # Filter for non-dimensioned (total) values
            if 'full_dimension_label' in concept_facts.columns:
                total_facts = concept_facts[concept_facts['full_dimension_label'].isna()]
            else:
                total_facts = concept_facts

            # Get numeric values
            if len(total_facts) > 0 and 'numeric_value' in total_facts.columns:
                numeric_facts = total_facts[total_facts['numeric_value'].notna()]

                if len(numeric_facts) > 0:
                    # Get the value (should be one row for non-dimensioned)
                    value = numeric_facts.iloc[0]['numeric_value']
                    debt_values[concept] = value

                    val_b = value / 1e9
                    gap_b = 11.58

                    # Check if this could fill the gap
                    if abs(val_b - gap_b) < 3:  # Within $3B of gap
                        print(f"  ⭐ {concept}: ${val_b:.2f}B (could fill ${gap_b:.2f}B gap!)")
                    elif val_b > 5:  # Show significant values
                        print(f"  💰 {concept}: ${val_b:.2f}B")
                    elif val_b > 1:  # Show smaller values
                        print(f"  - {concept}: ${val_b:.2f}B")

# STEP 3: Look for "Current" debt concepts specifically
print(f"\n" + "="*80)
print("STEP 3: CHECK 'CURRENT' DEBT CONCEPTS")
print("="*80)

current_debt_concepts = [c for c in all_concepts if 'current' in c.lower() and ('debt' in c.lower() or 'borrow' in c.lower())]
print(f"\n📋 Found {len(current_debt_concepts)} 'current' debt concepts:")

for concept in sorted(current_debt_concepts):
    print(f"  - {concept}")

    # Get value
    concept_facts = all_facts_df[
        (all_facts_df['concept'] == concept) &
        (all_facts_df['period_key'] == latest_period)
    ]

    if 'full_dimension_label' in concept_facts.columns:
        total_facts = concept_facts[concept_facts['full_dimension_label'].isna()]
    else:
        total_facts = concept_facts

    if len(total_facts) > 0 and 'numeric_value' in total_facts.columns:
        numeric_facts = total_facts[total_facts['numeric_value'].notna()]

        if len(numeric_facts) > 0:
            value = numeric_facts.iloc[0]['numeric_value']
            print(f"    Value: ${value/1e9:.2f}B")

# STEP 4: Check for LongTermDebtCurrent specifically
print(f"\n" + "="*80)
print("STEP 4: CHECK FOR LongTermDebtCurrent (MISSING COMPONENT?)")
print("="*80)

longtermdebtcurrent_concepts = [c for c in all_concepts if 'longtermdebtcurrent' in c.lower()]
print(f"\nSearching for LongTermDebtCurrent variations...")
print(f"Found {len(longtermdebtcurrent_concepts)} matches:")

if longtermdebtcurrent_concepts:
    for concept in longtermdebtcurrent_concepts:
        print(f"  ✓ {concept}")

        # Get value
        concept_facts = all_facts_df[
            (all_facts_df['concept'] == concept) &
            (all_facts_df['period_key'] == latest_period)
        ]

        if 'full_dimension_label' in concept_facts.columns:
            total_facts = concept_facts[concept_facts['full_dimension_label'].isna()]
        else:
            total_facts = concept_facts

        if len(total_facts) > 0 and 'numeric_value' in total_facts.columns:
            numeric_facts = total_facts[total_facts['numeric_value'].notna()]

            if len(numeric_facts) > 0:
                value = numeric_facts.iloc[0]['numeric_value']
                print(f"    Value: ${value/1e9:.2f}B")
else:
    print("  ❌ LongTermDebtCurrent NOT FOUND in XBRL")
    print("  This is the likely reason for the gap!")

# STEP 5: Summary and recommendations
print(f"\n" + "="*80)
print("SUMMARY & RECOMMENDATIONS")
print("="*80)

print(f"\n📊 What we know:")
print(f"  - yfinance 'Current Debt': ${yf_value/1e9:.2f}B")
print(f"  - XBRL ShortTermBorrowings: $52.89B")
print(f"  - Gap: $11.58B (18.0%)")

print(f"\n💡 Likely causes:")
print(f"  1. LongTermDebtCurrent not available in JPM's XBRL")
print(f"  2. yfinance includes additional components we don't have")
print(f"  3. JPM uses custom concepts not in our composite definition")

print(f"\n🔧 Next steps:")
print(f"  1. Check if LongTermDebtCurrent exists under different name")
print(f"  2. Review JPM's 10-K for current portion of long-term debt")
print(f"  3. Consider if ShortTermDebt composite needs JPM-specific config")

print("\n" + "="*80)
