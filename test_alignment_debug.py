"""
Debug numeric alignment
"""
from edgar.llm_helpers import list_of_dicts_to_table

# Create sample data with numeric columns
data = [
    {"label": "", "col_1": "Q1 2024", "col_2": "Q2 2024"},  # Header row
    {"label": "Revenue", "col_1": "$100M", "col_2": "$120M"},
    {"label": "Net Income", "col_1": "$20M", "col_2": "$25M"},
]

print("Input data:")
for row in data:
    print(f"  {row}")

print("\nGenerating table...")
markdown = list_of_dicts_to_table(data)

print("\nGenerated markdown:")
print(markdown)

print("\nChecking for alignment:")
if "---:" in markdown:
    count = markdown.count("---:")
    print(f"[PASS] Found {count} right-aligned columns")
else:
    print("[FAIL] No right-aligned columns")

# Test with simpler data (just numbers)
print("\n" + "=" * 80)
print("Testing with pure numbers:")

data2 = [
    {"label": "Item", "2024": "2024", "2023": "2023"},  # Header
    {"label": "Revenue", "2024": "100", "2023": "90"},
    {"label": "Expenses", "2024": "40", "2023": "35"},
]

print("\nInput data:")
for row in data2:
    print(f"  {row}")

markdown2 = list_of_dicts_to_table(data2)
print("\nGenerated markdown:")
print(markdown2)

if "---:" in markdown2:
    count = markdown2.count("---:")
    print(f"[PASS] Found {count} right-aligned columns")
else:
    print("[FAIL] No right-aligned columns")
