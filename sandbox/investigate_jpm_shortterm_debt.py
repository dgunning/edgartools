"""
Investigation: JPM ShortTermDebt Validation Failure

From E2E test:
- yfinance: $64.47B
- Static workflow: Mapped to us-gaap:CommercialPaper
- Validation: FAILED (marked as "no mapping")
- AI agent: All 5 candidates failed verification

Goal: Understand why validation failed and what the correct mapping should be.
"""

from edgar import Company, set_identity, use_local_storage
import yfinance as yf

set_identity("Dev Gunning developer-gunning@gmail.com")
use_local_storage(True)

print("="*80)
print("INVESTIGATING: JPM ShortTermDebt Validation Failure")
print("="*80)

# Get JPM data
company = Company('JPM')
filing = list(company.get_filings(form='10-K'))[0]
xbrl = filing.xbrl()
facts_df = company.get_facts().to_dataframe()
stock = yf.Ticker('JPM')

# Get yfinance reference
yf_value = None
if 'Current Debt' in stock.balance_sheet.index:
    yf_value = stock.balance_sheet.loc['Current Debt'].iloc[0]

print(f"\nyfinance 'Current Debt': ${yf_value/1e9:.2f}B" if yf_value else "No yfinance data")

# Step 1: Check what the static workflow mapped
print(f"\nSTEP 1: STATIC WORKFLOW MAPPING")
print("-"*80)

# From the test output, it mapped to CommercialPaper
# Let's check all ShortTermDebt composite components
composite_components = ['LongTermDebtCurrent', 'CommercialPaper', 'ShortTermBorrowings']

print("Checking ShortTermDebt composite components:")
for component in composite_components:
    try:
        facts = xbrl.facts
        df = facts.get_facts_by_concept(component)

        if df is not None and len(df) > 0:
            # Filter for exact concept match
            expected = [f'us-gaap:{component}', f'us-gaap_{component}', component]
            exact = df[df['concept'].isin(expected)]

            if len(exact) > 0:
                # Filter for non-dimensioned
                if 'full_dimension_label' in exact.columns:
                    no_dim = exact[exact['full_dimension_label'].isna()]
                else:
                    no_dim = exact

                # Get numeric values
                numeric = no_dim[no_dim['numeric_value'].notna()]

                if len(numeric) > 0:
                    latest = numeric.sort_values('period_key', ascending=False).iloc[0]
                    val = latest['numeric_value'] / 1e9
                    variance = abs(latest['numeric_value'] - yf_value) / yf_value * 100 if yf_value else 0
                    match = "✓" if variance <= 15 else "✗"
                    print(f"  {match} {component}: ${val:.2f}B (variance: {variance:.1f}%)")
                else:
                    print(f"  - {component}: Found but no numeric values")
            else:
                print(f"  - {component}: Not found (no exact match)")
        else:
            print(f"  - {component}: Not found in XBRL")
    except Exception as e:
        print(f"  - {component}: Error - {e}")

# Step 2: Check if composite sum matches
print(f"\nSTEP 2: COMPOSITE METRIC ANALYSIS")
print("-"*80)

component_values = {}
for component in composite_components:
    try:
        facts = xbrl.facts
        df = facts.get_facts_by_concept(component)

        if df is not None and len(df) > 0:
            expected = [f'us-gaap:{component}', f'us-gaap_{component}', component]
            exact = df[df['concept'].isin(expected)]

            if len(exact) > 0:
                if 'full_dimension_label' in exact.columns:
                    no_dim = exact[exact['full_dimension_label'].isna()]
                else:
                    no_dim = exact

                numeric = no_dim[no_dim['numeric_value'].notna()]

                if len(numeric) > 0:
                    latest = numeric.sort_values('period_key', ascending=False).iloc[0]
                    component_values[component] = latest['numeric_value']
    except Exception:
        pass

if component_values:
    total = sum(component_values.values())
    print(f"Component breakdown:")
    for component, value in component_values.items():
        print(f"  {component}: ${value/1e9:.2f}B")
    print(f"  TOTAL: ${total/1e9:.2f}B")

    if yf_value:
        variance = abs(total - yf_value) / yf_value * 100
        print(f"\nComposite vs yfinance:")
        print(f"  XBRL composite: ${total/1e9:.2f}B")
        print(f"  yfinance: ${yf_value/1e9:.2f}B")
        print(f"  Variance: {variance:.1f}%")
        print(f"  Match: {'✓' if variance <= 15 else '✗'}")
else:
    print("No composite components found")

# Step 3: Search for other short-term debt concepts
print(f"\nSTEP 3: OTHER SHORT-TERM DEBT CONCEPTS")
print("-"*80)

# Search for all debt-related concepts in balance sheet
debt_concepts = [
    'DebtCurrent',
    'ShortTermDebt',
    'ShorttermDebtFairValue',
    'DebtCurrentAndNoncurrent',
    'LongTermDebtAndCapitalLeaseObligationsCurrent',
]

print("Checking other debt concepts:")
for concept in debt_concepts:
    try:
        facts = xbrl.facts
        df = facts.get_facts_by_concept(concept)

        if df is not None and len(df) > 0:
            expected = [f'us-gaap:{concept}', f'us-gaap_{concept}', concept]
            exact = df[df['concept'].isin(expected)]

            if len(exact) > 0:
                if 'full_dimension_label' in exact.columns:
                    no_dim = exact[exact['full_dimension_label'].isna()]
                else:
                    no_dim = exact

                numeric = no_dim[no_dim['numeric_value'].notna()]

                if len(numeric) > 0:
                    latest = numeric.sort_values('period_key', ascending=False).iloc[0]
                    val = latest['numeric_value'] / 1e9
                    variance = abs(latest['numeric_value'] - yf_value) / yf_value * 100 if yf_value else 0
                    match = "✓" if variance <= 15 else "✗"
                    print(f"  {match} {concept}: ${val:.2f}B (variance: {variance:.1f}%)")
    except Exception:
        pass

# Step 4: Check what yfinance "Current Debt" might include
print(f"\nSTEP 4: ANALYZING THE GAP")
print("-"*80)

if component_values and yf_value:
    total = sum(component_values.values())
    gap = yf_value - total

    print(f"yfinance 'Current Debt': ${yf_value/1e9:.2f}B")
    print(f"XBRL ShortTermBorrowings: ${total/1e9:.2f}B")
    print(f"GAP: ${gap/1e9:.2f}B")
    print(f"\nWhat could the ${gap/1e9:.2f}B gap be?")

    # Check if there are other debt concepts in JPM's XBRL
    print("\nSearching for other potential debt components...")

    # Get all concepts from XBRL facts
    all_concepts = xbrl.facts._facts_df['concept'].unique() if hasattr(xbrl.facts, '_facts_df') else []

    # Filter for debt-related concepts
    debt_related = [c for c in all_concepts if 'debt' in c.lower() or 'borrow' in c.lower()]

    print(f"Found {len(debt_related)} debt-related concepts in XBRL")

    # Check each one for values
    for concept in sorted(debt_related)[:30]:
        try:
            concept_name = concept.replace('us-gaap:', '').replace('us-gaap_', '')
            df = xbrl.facts.get_facts_by_concept(concept_name)

            if df is not None and len(df) > 0:
                expected = [f'us-gaap:{concept_name}', f'us-gaap_{concept_name}', concept_name]
                exact = df[df['concept'].isin(expected)]

                if len(exact) > 0:
                    if 'full_dimension_label' in exact.columns:
                        no_dim = exact[exact['full_dimension_label'].isna()]
                    else:
                        no_dim = exact

                    numeric = no_dim[no_dim['numeric_value'].notna()]

                    if len(numeric) > 0:
                        latest = numeric.sort_values('period_key', ascending=False).iloc[0]
                        val = latest['numeric_value'] / 1e9

                        # Check if this value could be the missing piece
                        if abs(val - gap/1e9) < 5:  # Within $5B of the gap
                            print(f"  ⭐ {concept}: ${val:.2f}B (could fill ${gap/1e9:.2f}B gap)")
                        elif val > 5:  # Show significant debt values
                            print(f"  - {concept}: ${val:.2f}B")
        except Exception:
            pass

# Step 5: Root cause analysis
print(f"\nSTEP 5: ROOT CAUSE ANALYSIS")
print("-"*80)

if component_values:
    total = sum(component_values.values())
    if yf_value:
        variance = abs(total - yf_value) / yf_value * 100

        if variance <= 15:
            print("Category: WORKING CORRECTLY")
            print(f"Explanation: Composite metric matches yfinance (variance: {variance:.1f}%)")
        elif total < yf_value * 0.5:
            print("Category: MISSING COMPONENTS")
            print(f"Explanation: Composite sum (${total/1e9:.2f}B) is much less than yfinance (${yf_value/1e9:.2f}B)")
            print("Likely missing major debt components in the composite definition")
        else:
            print("Category: DEFINITION MISMATCH")
            print(f"Explanation: Composite sum (${total/1e9:.2f}B) differs from yfinance (${yf_value/1e9:.2f}B) by {variance:.1f}%")
            print("May need different component combination or additional concepts")

print("\n" + "="*80)
print("INVESTIGATION COMPLETE")
print("="*80)
