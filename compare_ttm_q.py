from edgar import set_identity, Company
import pandas as pd

set_identity('Test User test@example.com')

facts = Company('MSFT').facts

print("="*60)
print("Comparing TTM vs Quarterly Values")
print("="*60)

# Get both statements
q_stmt = facts.income_statement(period='quarterly', periods=8)
ttm_stmt = facts.income_statement(period='ttm', periods=8)

# Extract DataFrames
df_q = q_stmt.to_dataframe()
df_ttm = ttm_stmt.to_dataframe()

# Find common concepts to compare
concepts = ['RevenueFromContractWithCustomerExcludingAssessedTax', 'GrossProfit', 'OperatingIncomeLoss', 'NetIncomeLoss']
# Map to labels usually found in DF
concept_labels = {
    'RevenueFromContractWithCustomerExcludingAssessedTax': 'Total Revenue',
    'GrossProfit': 'Gross Profit',
    'OperatingIncomeLoss': 'Operating Income (Loss)',
    'NetIncomeLoss': 'Net Income (Loss) Attributable to Parent'
}

print("\nValue Comparison (Billions):")
print(f"{'Metric':<25} | {'Period':<15} | {'Quarterly':<12} | {'TTM':<12} | {'Ratio (TTM/Q)':<12}")
print("-" * 85)

# Compare most recent overlapping period (e.g. Q1 2026)
# Note: TTM Q1 2026 should be approx 4x Quarterly Q1 2026 if business is stable
cols_q = [c for c in df_q.columns if '2025' in c or '2026' in c]
cols_ttm = [c for c in df_ttm.columns if '2025' in c or '2026' in c]

# Pick a few key periods to compare
test_periods = ['Q1 2026', 'Q4 2025', 'Q3 2025']

for concept, label in concept_labels.items():
    row_q = df_q[df_q.iloc[:, 0].str.contains(label, na=False, regex=False)]
    row_ttm = df_ttm[df_ttm.iloc[:, 0].str.contains(label, na=False, regex=False)]
    
    if not row_q.empty and not row_ttm.empty:
        for period in test_periods:
            col_q = period  # e.g. "Q1 2026"
            col_ttm = f"{period} TTM" # e.g. "Q1 2026 TTM"
            
            val_q = row_q[col_q].values[0] if col_q in row_q.columns else None
            val_ttm = row_ttm[col_ttm].values[0] if col_ttm in row_ttm.columns else None
            
            if val_q is not None and val_ttm is not None and not pd.isna(val_q) and not pd.isna(val_ttm):
                # Format
                q_fmt = f"${val_q/1e9:.1f}B"
                ttm_fmt = f"${val_ttm/1e9:.1f}B"
                ratio = f"{val_ttm/val_q:.1f}x"
                print(f"{label:<25} | {period:<15} | {q_fmt:<12} | {ttm_fmt:<12} | {ratio:<12}")
                
print("\n" + "="*60)
print("Raw Data Sample:")
print("\nQuarterly:")
print(df_q.head(3))
print("\nTTM:")
print(df_ttm.head(3))
