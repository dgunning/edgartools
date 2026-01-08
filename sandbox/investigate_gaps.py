"""
Deep Investigation of Concept Mapping Gaps

Investigates why TotalAssets, LongTermDebt, and ShortTermDebt
are failing validation using the systematic methodology.
"""

from edgar import Company, set_identity, use_local_storage
import yfinance as yf
import pandas as pd

set_identity("Dev Gunning developer-gunning@gmail.com")
use_local_storage(True)


def investigate_metric(ticker: str, metric: str):
    """Investigate a single metric for a company."""
    print(f"\n{'='*70}")
    print(f"INVESTIGATING: {metric} for {ticker}")
    print(f"{'='*70}")

    # Get XBRL and facts
    company = Company(ticker)
    filing = list(company.get_filings(form='10-K'))[0]
    xbrl = filing.xbrl()
    facts_df = company.get_facts().to_dataframe()

    # Get yfinance reference
    stock = yf.Ticker(ticker)
    if metric == 'TotalAssets':
        yf_value = stock.balance_sheet.loc['Total Assets'].iloc[0] if 'Total Assets' in stock.balance_sheet.index else None
    elif metric == 'LongTermDebt':
        yf_value = stock.balance_sheet.loc['Long Term Debt'].iloc[0] if 'Long Term Debt' in stock.balance_sheet.index else None
    elif metric == 'ShortTermDebt':
        yf_value = stock.balance_sheet.loc['Current Debt'].iloc[0] if 'Current Debt' in stock.balance_sheet.index else None
    else:
        yf_value = None

    print(f"\nyfinance Reference Value: ${yf_value/1e9:.2f}B" if yf_value else "No yfinance data")

    # Step 1: Examine Calculation Tree Structure
    print(f"\nSTEP 1: CALCULATION TREE STRUCTURE")
    print("-" * 70)

    # Search for related concepts in calc trees
    related_concepts = set()
    for role, tree in xbrl.calculation_trees.items():
        for node_id in tree.all_nodes.keys():
            if metric.lower() in node_id.lower() or \
               (metric == 'TotalAssets' and 'asset' in node_id.lower()) or \
               (metric == 'LongTermDebt' and 'debt' in node_id.lower() and 'long' in node_id.lower()) or \
               (metric == 'ShortTermDebt' and 'debt' in node_id.lower() and ('short' in node_id.lower() or 'current' in node_id.lower())):
                related_concepts.add(node_id)

    if related_concepts:
        print(f"Found {len(related_concepts)} related concepts in calculation trees:")
        for concept in sorted(related_concepts)[:10]:  # Show top 10
            print(f"  - {concept}")
    else:
        print("No related concepts found in calculation trees")

    # Step 2: Compare XBRL Facts vs yfinance Values
    print(f"\nSTEP 2: XBRL FACTS ANALYSIS")
    print("-" * 70)

    # Search facts for related concepts
    if metric == 'TotalAssets':
        search_patterns = ['asset']
    elif metric == 'LongTermDebt':
        search_patterns = ['debt', 'borrowing', 'note']
    elif metric == 'ShortTermDebt':
        search_patterns = ['debt', 'borrowing', 'note']
    else:
        search_patterns = [metric.lower()]

    fact_values = []
    for pattern in search_patterns:
        related_facts = facts_df[facts_df['concept'].str.contains(pattern, case=False, na=False)]

        # Get unique concepts with their values
        for concept_name in related_facts['concept'].unique():
            concept_facts = related_facts[related_facts['concept'] == concept_name]
            # Filter for non-dimensioned values
            if 'full_dimension_label' in concept_facts.columns:
                total_facts = concept_facts[concept_facts['full_dimension_label'].isna()]
            else:
                total_facts = concept_facts

            # Get numeric values
            numeric = total_facts[total_facts['numeric_value'].notna()]
            if len(numeric) > 0:
                latest_value = float(numeric.iloc[-1]['numeric_value'])
                fact_values.append({
                    'concept': concept_name,
                    'value': latest_value,
                    'value_billions': latest_value / 1e9,
                    'dimension_count': len(concept_facts)
                })

    # Sort by value (descending) and show top matches
    fact_values_df = pd.DataFrame(fact_values).drop_duplicates('concept')
    if len(fact_values_df) > 0:
        fact_values_df = fact_values_df.sort_values('value', ascending=False)

        print(f"Top XBRL concept candidates (by value):")
        for _, row in fact_values_df.head(15).iterrows():
            variance = abs(row['value'] - yf_value) / abs(yf_value) * 100 if yf_value else 0
            match = "✓" if variance <= 15 else "✗"
            print(f"  {match} {row['concept']}: ${row['value_billions']:.2f}B (variance: {variance:.1f}%)")
    else:
        print("No numeric fact values found")

    # Step 3: Identify Root Cause Category
    print(f"\nSTEP 3: ROOT CAUSE ANALYSIS")
    print("-" * 70)

    if yf_value and len(fact_values_df) > 0:
        top_match = fact_values_df.iloc[0]
        variance_pct = abs(top_match['value'] - yf_value) / abs(yf_value) * 100

        if top_match['value'] < yf_value * 0.1:
            category = "CONSOLIDATION ISSUE"
            explanation = f"XBRL value ({top_match['value_billions']:.2f}B) is much smaller than yfinance ({yf_value/1e9:.2f}B). Likely extracting parent-only instead of consolidated entity."
        elif variance_pct > 30:
            category = "DEFINITION DIFFERENCE"
            explanation = f"XBRL concept may have different definition than yfinance. Variance: {variance_pct:.1f}%"
        elif variance_pct > 15:
            category = "COMPOSITE MISMATCH"
            explanation = f"May need to sum multiple XBRL concepts to match yfinance definition. Variance: {variance_pct:.1f}%"
        else:
            category = "TIMING DIFFERENCE"
            explanation = f"Small variance ({variance_pct:.1f}%) suggests timing or rounding difference."

        print(f"Category: {category}")
        print(f"Explanation: {explanation}")

        # Check if multiple concepts sum to yfinance value
        print(f"\nChecking if sum of concepts matches yfinance...")
        if len(fact_values_df) >= 2:
            # Try summing top 2, 3, 4 concepts
            for n in [2, 3, 4]:
                if len(fact_values_df) >= n:
                    sum_value = fact_values_df.head(n)['value'].sum()
                    sum_variance = abs(sum_value - yf_value) / abs(yf_value) * 100
                    if sum_variance <= 15:
                        print(f"  ✓ Sum of top {n} concepts = ${sum_value/1e9:.2f}B (variance: {sum_variance:.1f}%)")
                        print(f"    Concepts: {list(fact_values_df.head(n)['concept'])}")
                    else:
                        print(f"  ✗ Sum of top {n} concepts = ${sum_value/1e9:.2f}B (variance: {sum_variance:.1f}%)")
    else:
        print("Cannot determine root cause - missing data")

    # Step 4: Suggest Fix
    print(f"\nSTEP 4: SUGGESTED FIX")
    print("-" * 70)

    if yf_value and len(fact_values_df) > 0:
        top_match = fact_values_df.iloc[0]
        variance_pct = abs(top_match['value'] - yf_value) / abs(yf_value) * 100

        if top_match['value'] < yf_value * 0.1:
            print("Fix Type: Update _extract_xbrl_value() to prefer consolidated")
            print("Location: edgar/xbrl/standardization/reference_validator.py line ~250")
            print("\nRecommended Change:")
            print("""
# Filter for consolidated (no dimension) OR specific consolidated dimensions
if 'full_dimension_label' in df.columns:
    # Prefer rows with no dimensions (consolidated)
    consolidated = df[df['full_dimension_label'].isna()]
    if len(consolidated) > 0:
        df = consolidated
    else:
        # If no non-dimensioned rows, look for explicitly consolidated
        # (This handles cases where 'Consolidated' is a dimension value)
        # For now, just use all rows and take the largest value
        pass
""")
        elif variance_pct <= 15:
            print(f"Fix Type: Accept this mapping (variance within tolerance)")
            print(f"Recommended: Update variance threshold or accept {top_match['concept']}")
        else:
            print("Fix Type: Composite metric or definition review needed")
            print(f"Recommended: Investigate sum of concepts or yfinance definition")
    else:
        print("Cannot suggest fix - need more investigation")


# Main investigation
if __name__ == "__main__":
    metrics_to_investigate = [
        ('AAPL', 'TotalAssets'),
        ('AAPL', 'LongTermDebt'),
        ('AAPL', 'ShortTermDebt'),
        ('GOOG', 'TotalAssets'),
        ('GOOG', 'LongTermDebt'),
        ('AMZN', 'TotalAssets'),
        ('AMZN', 'LongTermDebt'),
    ]

    for ticker, metric in metrics_to_investigate:
        try:
            investigate_metric(ticker, metric)
        except Exception as e:
            print(f"\nError investigating {metric} for {ticker}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*70}")
    print("INVESTIGATION COMPLETE")
    print(f"{'='*70}")
