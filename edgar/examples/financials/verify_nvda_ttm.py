
import sys
import os
import pandas as pd

# Add repo root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..")))

from edgar import Company, set_identity

set_identity("Verification Agent demo@example.com")

def verify_nvda():
    print("Fetching NVDA data...")
    company = Company("NVDA")
    
    print("\n--- Rolling TTM Income Statement (Last 4 Periods) ---")
    stmt = company.income_statement(periods=4, period='ttm')
    print(stmt)
    
    print("\n--- Data Alignment Check ---")
    df = stmt.to_dataframe()
    
    # Check if Revenue and Net Income have values in the same columns
    # Find Revenue row
    rev_row = df[df['label'].str.contains('Total Revenue', case=False)]
    if rev_row.empty:
        print("ERROR: Total Revenue not found")
        return
        
    # Find Net Income row
    inc_row = df[df['label'].str.contains('Net Income', case=False) & df['is_total']]
    if inc_row.empty:
        print("ERROR: Net Income not found")
        return
        
    # Get value columns
    metadata_cols = ['label', 'depth', 'is_abstract', 'is_total', 'section', 'confidence']
    periods = [c for c in df.columns if c not in metadata_cols]
    
    print(f"Periods found: {periods}")
    
    for p in periods:
        rev_val = rev_row.iloc[0][p]
        inc_val = inc_row.iloc[0][p]
        
        has_rev = pd.notnull(rev_val)
        has_inc = pd.notnull(inc_val)
        
        status = "OK" if (has_rev and has_inc) else "MISMATCH/GAP"
        print(f"  {p}: Revenue={has_rev}, NetIncome={has_inc} -> {status}")
        if has_rev:
            print(f"      Rev Value: ${rev_val/1e9:.2f}B")

if __name__ == "__main__":
    verify_nvda()
