from edgar import Company

print("="*60)
print("VERIFYING TTM & QUARTERLY FIXES")
print("="*60)
print("Fetching MSFT data...")

try:
    facts = Company("MSFT").facts
    
    # 1. Quarterly Check
    print("\n1. QUARTERLY MODE")
    print("   Looking for: Q4 columns (e.g. Q4 2025, Q4 2024)")
    q_st = facts.income_statement(period='quarterly', periods=8)
    print(q_st)
    
    # 2. TTM Check
    print("\n2. TTM MODE")
    print("   Looking for: Populated data (non-empty columns)")
    ttm_st = facts.income_statement(period='ttm', periods=8)
    print(ttm_st)
    
    print("\n" + "="*60)
    print("✅ TEST COMPLETE")
    print("If you see Q4 columns above and data in TTM tables, the fix is working.")
    print("="*60)

except Exception as e:
    print(f"\n❌ Error encountered: {e}")
