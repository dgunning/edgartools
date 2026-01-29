"""
Minimal test to reproduce CIK type issue on GitHub Actions.
This test will pass locally but may fail on GitHub if the parquet transformation fails.
"""
import sys
import pyarrow as pa
from edgar.reference.tickers import get_company_tickers, _get_company_tickers_raw

def test_cik_types():
    """Test that CIKs are int64, not strings."""
    print(f"Python version: {sys.version}")

    # Clear any cached data
    _get_company_tickers_raw.cache_clear()

    # Test DataFrame
    print("\n=== Testing DataFrame ===")
    df = get_company_tickers(as_dataframe=True)
    print(f"CIK dtype: {df['cik'].dtype}")
    print(f"Sample CIK: {df['cik'].iloc[0]} (type: {type(df['cik'].iloc[0]).__name__})")

    if df['cik'].dtype != 'int64':
        print(f"❌ FAILED: Expected int64, got {df['cik'].dtype}")
        print(f"First 5 CIKs: {df['cik'].head().tolist()}")
        sys.exit(1)

    # Test PyArrow conversion (this is where GitHub fails)
    print("\n=== Testing PyArrow Conversion ===")
    try:
        table = get_company_tickers(as_dataframe=False)
        print(f"PyArrow CIK type: {table.schema.field('cik').type}")

        if table.schema.field('cik').type != pa.int64():
            print(f"❌ FAILED: Expected int64, got {table.schema.field('cik').type}")
            sys.exit(1)

        print("✅ All tests passed!")

    except pa.lib.ArrowInvalid as e:
        print(f"❌ FAILED: PyArrow conversion error: {e}")
        print(f"This is the error happening on GitHub Actions!")
        print(f"DataFrame CIK dtype was: {df['cik'].dtype}")
        sys.exit(1)

if __name__ == "__main__":
    test_cik_types()
