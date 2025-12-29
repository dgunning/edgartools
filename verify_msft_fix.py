from edgar import Company, set_identity
set_identity("Antigravity Agent <antigravity@example.com>")

print("="*60)
print("VERIFYING TTM & QUARTERLY FIXES")
print("="*60)
print("Fetching MSFT data...")

try:
    facts = Company("MSFT").facts
    
    # 1. Quarterly Check
    print("\n1. QUARTERLY MODE")
    q_st = facts.income_statement(period='quarterly', periods=8)
    print(q_st)
    
    # Check for Q4 in column names
    df_q = q_st.to_dataframe()
    cols = df_q.columns.tolist()
    print(f"\nQuarterly Columns Found: {cols}")
    q4_cols = [c for c in cols if 'Q4' in str(c)]
    
    if q4_cols:
        print(f"✅ FOUND Q4 COLUMNS: {q4_cols}")
        # Check if data is populated in Q4
        sample_val = df_q[q4_cols[0]].iloc[0] # Get first row (usually Revenue)
        print(f"   Sample Q4 Value (Row 0): {sample_val}")
        if sample_val and str(sample_val) != 'nan':
             print("   ✅ Q4 Data is Populated")
        else:
             print("   ❌ Q4 Data appears Empty/NaN")
    else:
        print("❌ NO Q4 COLUMNS FOUND")

    # 2. TTM Check
    print("\n2. TTM MODE")
    ttm_st = facts.income_statement(period='ttm', periods=8)
    print(ttm_st)
    
    # Check TTM columns
    df_ttm = ttm_st.to_dataframe()
    print(f"\nTTM Columns Found: {df_ttm.columns.tolist()}")
    if not df_ttm.empty:
         print("✅ TTM Table is Populated")
    else:
         print("❌ TTM Table is Empty")
    
    print("\n" + "="*60)
    print("✅ TEST COMPLETE")
    print("If you see Q4 columns above and data in TTM tables, the fix is working.")
    print("="*60)

except Exception as e:
    print(f"\n❌ Error encountered: {e}")
