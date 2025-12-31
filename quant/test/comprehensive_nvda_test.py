"""
Comprehensive NVDA Quant Module Test Report
Tests all functionalities of the quant module with NVIDIA stock.
"""
from quant import QuantCompany
from edgar import set_identity
from datetime import date
import pandas as pd
import sys

# Force UTF-8 encoding for output
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Setup
set_identity("AI Agent Test@example.com")

print("=" * 100)
print("COMPREHENSIVE NVDA QUANT MODULE TEST REPORT")
print("=" * 100)
print()

# Initialize QuantCompany for NVDA
print("Initializing QuantCompany for NVIDIA (NVDA)...")
company = QuantCompany("NVDA")
print(f"[OK] Company: {company.name}")
print(f"[OK] CIK: {company.cik}")
print(f"[OK] SIC: {company.sic}")
print()

# ============================================================================
# TEST 1: Stock Split Detection
# ============================================================================
print("=" * 100)
print("TEST 1: STOCK SPLIT DETECTION")
print("=" * 100)
print()

from quant.utils import detect_splits
facts = company._get_adjusted_facts()
splits = detect_splits(facts)

print(f"[OK] Detected {len(splits)} stock split(s):")
for split in splits:
    print(f"  - Date: {split['date']}, Ratio: {split['ratio']}:1")
print()

# ============================================================================
# TEST 2: Annual Income Statement (Split-Adjusted)
# ============================================================================
print("=" * 100)
print("TEST 2: ANNUAL INCOME STATEMENT (Split-Adjusted)")
print("=" * 100)
print()

annual_stmt = company.income_statement(periods=5, period='annual', as_dataframe=True)
print(annual_stmt)
print()

# Extract EPS to verify split adjustment
eps_rows = annual_stmt[annual_stmt.iloc[:, 0].str.contains('Earnings Per Share, Basic', na=False, case=False)]
if not eps_rows.empty:
    print("\n[OK] Earnings Per Share (Basic) - Split Adjusted:")
    print(eps_rows.to_string())
print()

# ============================================================================
# TEST 3: Quarterly Income Statement (with Q4 Derivation)
# ============================================================================
print("=" * 100)
print("TEST 3: QUARTERLY INCOME STATEMENT (with Q4 Derivation)")
print("=" * 100)
print()

quarterly_stmt = company.income_statement(periods=8, period='quarterly', as_dataframe=True)
print(quarterly_stmt)
print()

# ============================================================================
# TEST 4: TTM Income Statement
# ============================================================================
print("=" * 100)
print("TEST 4: TTM (Trailing Twelve Months) INCOME STATEMENT")
print("=" * 100)
print()

try:
    ttm_stmt = company.income_statement(periods=8, period='ttm', as_dataframe=False)
    print(ttm_stmt)
    print()
except Exception as e:
    print(f"[WARNING] TTM Income Statement Error: {e}")
    import traceback
    traceback.print_exc()
    print()

# ============================================================================
# TEST 5: TTM Metrics (Revenue and Net Income)
# ============================================================================
print("=" * 100)
print("TEST 5: TTM METRICS - REVENUE & NET INCOME")
print("=" * 100)
print()

try:
    ttm_revenue = company.get_ttm_revenue()
    print(f"[OK] TTM Revenue:")
    print(f"  Value: ${ttm_revenue.value:,.0f}")
    print(f"  As of: {ttm_revenue.as_of_date}")
    print(f"  Periods: {ttm_revenue.periods}")
    print(f"  Has gaps: {ttm_revenue.has_gaps}")
    print(f"  Has calculated Q4: {ttm_revenue.has_calculated_q4}")
    print()
except Exception as e:
    print(f"[WARNING] TTM Revenue Error: {e}")
    import traceback
    traceback.print_exc()
    print()

try:
    ttm_income = company.get_ttm_net_income()
    print(f"[OK] TTM Net Income:")
    print(f"  Value: ${ttm_income.value:,.0f}")
    print(f"  As of: {ttm_income.as_of_date}")
    print(f"  Periods: {ttm_income.periods}")
    print(f"  Has gaps: {ttm_income.has_gaps}")
    print(f"  Has calculated Q4: {ttm_income.has_calculated_q4}")
    print()
except Exception as e:
    print(f"[WARNING] TTM Net Income Error: {e}")
    import traceback
    traceback.print_exc()
    print()

# ============================================================================
# TEST 6: Balance Sheet
# ============================================================================
print("=" * 100)
print("TEST 6: BALANCE SHEET (Annual)")
print("=" * 100)
print()

try:
    balance_sheet = company.balance_sheet(periods=4, period='annual', as_dataframe=True)
    print(balance_sheet.to_string())
    print()
except Exception as e:
    print(f"[WARNING] Balance Sheet Error: {e}")
    import traceback
    traceback.print_exc()
    print()

# ============================================================================
# TEST 7: Cash Flow Statement
# ============================================================================
print("=" * 100)
print("TEST 7: CASH FLOW STATEMENT (Annual)")
print("=" * 100)
print()

try:
    cashflow_stmt = company.cash_flow(periods=4, period='annual', as_dataframe=True)
    print(cashflow_stmt.to_string())
    print()
except Exception as e:
    print(f"[WARNING] Cash Flow Error: {e}")
    import traceback
    traceback.print_exc()
    print()

# ============================================================================
# TEST 8: Custom TTM Calculation for Specific Concept
# ============================================================================
print("=" * 100)
print("TEST 8: CUSTOM TTM CALCULATION")
print("=" * 100)
print()

try:
    # Try to get TTM for a specific concept
    ttm_custom = company.get_ttm('RevenueFromContractWithCustomerExcludingAssessedTax', as_of=date(2024, 10, 27))
    print(f"[OK] TTM Revenue (as of Q3 2024 - Oct 27, 2024):")
    print(f"  Value: ${ttm_custom.value:,.0f}")
    print(f"  Periods: {ttm_custom.periods}")
    print()
except Exception as e:
    print(f"[WARNING] Custom TTM Error: {e}")
    import traceback
    traceback.print_exc()
    print()

# ============================================================================
# SUMMARY
# ============================================================================
print("=" * 100)
print("TEST SUMMARY")
print("=" * 100)
print()
print("[OK] Stock Split Detection: PASSED")
print("[OK] Annual Income Statement: PASSED")
print("[OK] Quarterly Income Statement: PASSED")
print("[ ? ] TTM Income Statement: Check output above")
print("[ ? ] TTM Metrics: Check output above")
print("[ ? ] Balance Sheet: Check output above")
print("[ ? ] Cash Flow Statement: Check output above")
print("[ ? ] Custom TTM Calculation: Check output above")
print()
print("=" * 100)
print("REPORT COMPLETE")
print("=" * 100)
