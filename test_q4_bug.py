"""
Test script to reproduce Q4 missing bug.
"""
from edgar import Company
import sys

# Ensure UTF-8 encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 100)
print("Testing Q4 Bug with NVDA")
print("=" * 100)

company = Company("NVDA")

# Test 1: periods=6 (reported to miss Q4)
print("\n1. TEST: period='quarterly', periods=6")
print("-" * 100)
stmt1 = company.income_statement(period='quarterly', periods=6)
print(f"Periods returned: {stmt1.periods}")
print(f"Number of periods: {len(stmt1.periods)}")

# Check which quarters are present
quarters = stmt1.periods
for q in quarters:
    if 'Q1' in q:
        print(f"  ✓ Q1 found: {q}")
    if 'Q2' in q:
        print(f"  ✓ Q2 found: {q}")
    if 'Q3' in q:
        print(f"  ✓ Q3 found: {q}")
    if 'Q4' in q:
        print(f"  ✓ Q4 found: {q}")

# Count Q4s
q4_count = sum(1 for q in quarters if 'Q4' in q)
print(f"\nQ4 count: {q4_count}")
if q4_count == 0:
    print("❌ BUG CONFIRMED: Q4 is missing!")

# Test 2: periods='any text' (reported to work correctly)
print("\n\n2. TEST: period='quarterly', periods='invalid'")
print("-" * 100)
try:
    # This should cause an error but user says it works
    stmt2 = company.income_statement(period='quarterly', periods='invalid')
    print(f"Periods returned: {stmt2.periods}")
    print(f"Number of periods: {len(stmt2.periods)}")

    quarters2 = stmt2.periods
    for q in quarters2:
        if 'Q1' in q:
            print(f"  ✓ Q1 found: {q}")
        if 'Q2' in q:
            print(f"  ✓ Q2 found: {q}")
        if 'Q3' in q:
            print(f"  ✓ Q3 found: {q}")
        if 'Q4' in q:
            print(f"  ✓ Q4 found: {q}")

    q4_count2 = sum(1 for q in quarters2 if 'Q4' in q)
    print(f"\nQ4 count: {q4_count2}")
    if q4_count2 > 0:
        print("✓ Q4 is present with 'invalid' parameter!")
except Exception as e:
    print(f"Error (expected): {e}")

# Test 3: Different period counts
print("\n\n3. TEST: Different period counts")
print("-" * 100)
for p in [4, 5, 6, 7, 8]:
    stmt = company.income_statement(period='quarterly', periods=p)
    q4_count = sum(1 for q in stmt.periods if 'Q4' in q)
    print(f"periods={p}: {stmt.periods} -> Q4 count: {q4_count}")

print("\n" + "=" * 100)
