#!/usr/bin/env python3
"""
Test for Issue #438 Facts API revenue deduplication fix.

This test verifies that NVDA's income statement shows comprehensive revenue
data across all periods, combining explicit revenue concepts with calculated
revenue (GrossProfit + CostOfRevenue) when needed.

Expected Result:
NVDA should show "Total Revenue" with values for ALL periods (FY 2025 to FY 2020),
not just the older periods where explicit revenue concepts exist.
"""

import sys
import subprocess

def test_revenue_fix():
    """Test the revenue deduplication fix in a completely fresh Python process."""
    
    # Run the test in a subprocess to avoid any import/caching issues
    code = '''
import sys
sys.path.insert(0, "/Users/dwight/PycharmProjects/edgartools")

from edgar import Company

# Test NVDA income statement
print("Testing NVDA income statement revenue fix...")
c = Company("NVDA")
income_statement = c.income_statement(periods=6)

# Find Total Revenue item
total_revenue_item = None
for item in income_statement:
    if "Total Revenue" in item.label:
        total_revenue_item = item
        break

if not total_revenue_item:
    print("ERROR: No Total Revenue item found")
    sys.exit(1)

print(f"Found: {total_revenue_item.label}")
print(f"Concept: {total_revenue_item.concept}")

# Check values for each period
all_periods_have_values = True
for period, value in total_revenue_item.values.items():
    if value is not None:
        print(f"  {period}: ${value:,.0f}")
    else:
        print(f"  {period}: None")
        all_periods_have_values = False

if all_periods_have_values:
    print("\\nSUCCESS: All periods have revenue values!")
    print("Revenue deduplication fix is working correctly.")
else:
    print("\\nFAILED: Some periods still missing revenue values.")
    print("Revenue deduplication fix needs more work.")
    
print(f"\\nAll periods have values: {all_periods_have_values}")
'''
    
    # Run in subprocess
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
            
        return "SUCCESS: All periods have revenue values!" in result.stdout
        
    except subprocess.TimeoutExpired:
        print("ERROR: Test timed out")
        return False
    except Exception as e:
        print(f"ERROR: Failed to run test: {e}")
        return False

if __name__ == "__main__":
    print("Issue #438 Facts API Revenue Deduplication Fix Test")
    print("=" * 60)
    
    success = test_revenue_fix()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ PASSED: Revenue deduplication fix is working!")
    else:
        print("❌ FAILED: Revenue deduplication fix needs more work")
        
    print("=" * 60)