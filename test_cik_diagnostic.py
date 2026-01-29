"""
Diagnostic test to understand what's happening with CIK types on GitHub Actions.
"""
from edgar.reference.tickers import load_company_tickers_from_package, _get_company_tickers_raw
from edgar.reference.data.common import read_parquet_from_package

def main():
    print("=== Diagnostic Test ===\n")

    # Test 1: Can we read the raw parquet file?
    print("1. Testing raw parquet read...")
    try:
        raw_df = read_parquet_from_package('company_tickers.parquet')
        print(f"   ✅ Raw parquet loaded")
        print(f"   Schema: {raw_df.dtypes.to_dict()}")
        print(f"   CIK dtype: {raw_df['cik'].dtype}")
        print(f"   Sample CIK: {raw_df['cik'].iloc[0]}")
    except Exception as e:
        print(f"   ❌ Failed to read parquet: {e}")
        return

    # Test 2: Does the transformation work?
    print("\n2. Testing transformation...")
    try:
        transformed_df = load_company_tickers_from_package()
        if transformed_df is None:
            print("   ❌ Transformation returned None!")
            return
        print(f"   ✅ Transformation successful")
        print(f"   Schema: {transformed_df.dtypes.to_dict()}")
        print(f"   CIK dtype: {transformed_df['cik'].dtype}")
        print(f"   Sample CIK: {transformed_df['cik'].iloc[0]}")
    except Exception as e:
        print(f"   ❌ Transformation failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test 3: Does the cached version work?
    print("\n3. Testing cached version...")
    _get_company_tickers_raw.cache_clear()
    final_df = _get_company_tickers_raw()
    print(f"   ✅ Got DataFrame from cache")
    print(f"   Schema: {final_df.dtypes.to_dict()}")
    print(f"   CIK dtype: {final_df['cik'].dtype}")
    print(f"   Sample CIK: {final_df['cik'].iloc[0]}")

    print("\n✅ All diagnostic tests passed!")

if __name__ == "__main__":
    main()
