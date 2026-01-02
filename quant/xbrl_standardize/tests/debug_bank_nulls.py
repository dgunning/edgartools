#!/usr/bin/env python3
"""Debug why certain fields are null for banks."""

from edgar import Company

def check_bank_concepts(ticker):
    """Check what concepts are available for a bank."""
    print(f"\n{'='*70}")
    print(f"Analyzing {ticker}")
    print(f"{'='*70}")

    company = Company(ticker)
    financials = company.get_financials()
    income_stmt = financials.income_statement()

    # Get statement as dataframe
    df = income_stmt.to_dataframe(presentation=True, include_dimensions=False)

    print(f"\nTotal concepts in income statement: {len(df)}")
    print(f"\nSearching for null field concepts...")

    # Fields that are null
    null_fields = {
        'costOfGoodsSold': ['CostOfRevenue', 'CostOfGoodsAndServicesSold', 'CostOfGoodsSold'],
        'grossIncome': ['GrossProfit', 'GrossMargin'],
        'researchDevelopment': ['ResearchAndDevelopmentExpense'],
        'operatingIncome': ['OperatingIncomeLoss'],
        'depreciationAndAmortization': ['DepreciationDepletionAndAmortization', 'DepreciationAndAmortization'],
        'otherIncomeExpense': ['OtherNonoperatingIncomeExpense', 'NonoperatingIncomeExpense']
    }

    for field, concept_variants in null_fields.items():
        print(f"\n{field}:")
        found = False
        for variant in concept_variants:
            matches = df[df['concept'].str.contains(variant, case=False, na=False)]
            if len(matches) > 0:
                print(f"  ✓ FOUND {variant}:")
                for _, row in matches.iterrows():
                    label = row.get('label', '')
                    concept = row.get('concept', '')
                    # Get value from first date column
                    date_cols = [c for c in df.columns if isinstance(c, str) and '-' in c]
                    if date_cols:
                        value = row.get(date_cols[0])
                        print(f"    {concept}: {value:,.0f} - {label}")
                found = True

        if not found:
            print(f"  ✗ NOT FOUND - Checking similar concepts...")
            # Show what IS there (first 5 concepts)
            print(f"    Available expense/income concepts:")
            expense_concepts = df[df['concept'].str.contains('Expense|Income|Loss', case=False, na=False)]
            for idx, (_, row) in enumerate(expense_concepts.head(10).iterrows()):
                print(f"      - {row['concept']}")
                if idx >= 4:
                    print(f"      ... and {len(expense_concepts)-5} more")
                    break

# Test both banks
for ticker in ['BAC', 'JPM']:
    check_bank_concepts(ticker)
