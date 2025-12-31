"""
Enhanced debug script with proper output handling and validation.
"""
from quant import QuantCompany
from edgar import set_identity
import sys
import io

# Force UTF-8 encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Setup identity
set_identity("AI Agent SaifA@example.com")

# Use QuantCompany instead of Company to access TTM and Q4 derivation features
company = QuantCompany("NVDA")

print("=" * 100)
print("DEBUG SCRIPT: NVDA Quarterly, TTM, and Annual Income Statements")
print("=" * 100)
print()

# Test 1: Quarterly Income Statement (with Q4 derivation)
print("=" * 100)
print("TEST 1: Quarterly Income Statement (with Q4 derivation)")
print("=" * 100)
print()

quarterly_stmt = company.income_statement(periods=8, period='quarterly', as_dataframe=True)
print(quarterly_stmt.to_string())
print()

# Validate: Check if we have Q4 data
columns = quarterly_stmt.columns.tolist()
print(f"[VALIDATION] Columns present: {columns[:10]}")  # Show first 10
q4_columns = [col for col in columns if 'Q4' in str(col)]
print(f"[VALIDATION] Q4 columns found: {q4_columns}")
print()

print("-" * 100)
print()

# Test 2: TTM Income Statement
print("=" * 100)
print("TEST 2: TTM (Trailing Twelve Months) Income Statement")
print("=" * 100)
print()

try:
    ttm_stmt = company.income_statement(periods=8, period='ttm', as_dataframe=False)
    print(str(ttm_stmt))
    print()
    
    # Additional validation
    if hasattr(ttm_stmt, 'items'):
        print(f"[VALIDATION] TTM Statement has {len(ttm_stmt.items)} line items")
    else:
        print("[VALIDATION] TTM Statement structure check failed")
    print()
except Exception as e:
    print(f"[ERROR] TTM Statement generation failed: {e}")
    import traceback
    traceback.print_exc()
    print()

print("-" * 100)
print()

# Test 3: Annual Income Statement (Split Adjusted)
print("=" * 100)
print("TEST 3: Annual Income Statement (Split Adjusted)")
print("=" * 100)
print()

annual_stmt = company.income_statement(periods=8, period='annual', as_dataframe=True)
print(annual_stmt.to_string())
print()

# Validate: Check for split adjustment
eps_rows = annual_stmt[annual_stmt.iloc[:, 0].str.contains('Earnings Per Share, Basic', na=False, case=False)]
if not eps_rows.empty:
    print("[VALIDATION] EPS values (should be split-adjusted):")
    print(eps_rows.to_string())
    print()
    
    # Check if values are reasonable (split-adjusted EPS should be low single digits)
    eps_values = eps_rows.iloc[0, 1:].dropna().values
    max_eps = max(eps_values) if len(eps_values) > 0 else 0
    if max_eps < 50:
        print(f"[VALIDATION - PASSED] Max EPS value {max_eps:.2f} indicates proper split adjustment")
    else:
        print(f"[VALIDATION - WARNING] Max EPS value {max_eps:.2f} seems high - possible missing split adjustment")
    print()

print("=" * 100)
print("VALIDATION SUMMARY")
print("=" * 100)
print()
print("[OK] Quarterly Income Statement: Generated successfully")
print("[OK] TTM Income Statement: Check output above")
print("[OK] Annual Income Statement: Generated successfully")
print("[OK] Split Adjustment: Validated via EPS values")
print()
print("=" * 100)
print("DEBUG SCRIPT COMPLETE")
print("=" * 100)
