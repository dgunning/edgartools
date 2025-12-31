"""
Test as_reported parameter to verify it skips split adjustments.
"""
from edgar import Company, set_identity
set_identity("Test agent@example.com")

print("Testing as_reported=True parameter\n")
print("=" * 80)

# Test with NVDA (has 10:1 split in 2024)
c = Company("NVDA")

print("\n1. NORMAL MODE (with split adjustments):")
print("-" * 80)
normal_stmt = c.facts.income_statement(periods=3, period='annual', as_dataframe=False)
print(str(normal_stmt).split('\n')[0])  # Header
for line in str(normal_stmt).split('\n'):
    if 'Earnings Per Share, Basic' in line:
        print(line)
        break

print("\n2. AS-REPORTED MODE (no adjustments):")
print("-" * 80)
reported_stmt = c.facts.income_statement(periods=3, period='annual', as_reported=True, as_dataframe=False)
print(str(reported_stmt).split('\n')[0])  # Header
for line in str(reported_stmt).split('\n'):
    if 'Earnings Per Share, Basic' in line:
        print(line)
        break

print("\n3. EXPECTED:")
print("-" * 80)
print("Normal mode: ~$1.19 for FY2023 (split-adjusted by 10x)")
print("As-reported: ~$11.93 for FY2023 (pre-split, as originally filed)")
print("\n" + "=" * 80)
