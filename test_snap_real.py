import sys
from pathlib import Path

sys.path.insert(0, "../")

from edgar import Company
from edgar.llm import extract_markdown

print("=" * 70)
print("SETUP: Getting SNAP 10-K filing")
print("=" * 70)

snap = Company("SNAP")

# Depending on the library behavior, you may need one of these:
filings = snap.get_filings(form="10-K")

# Option A (if latest() returns a single filing):
filing = filings.latest()

# Option B (if latest(1) returns a list-like):
# filing = filings.latest(1)[0]

print(f"Filing: {filing.form} for {filing.company}")
print(f"Date: {filing.filing_date}\n")

print("=" * 70)
print("EXAMPLE 1: Basic Usage (all defaults)")
print("=" * 70)

# Extract Item 1 (change to "7" if you actually want Item 7)
markdown = extract_markdown(filing, statement=["IncomeStatement", "BalanceSheet"], show_dimension=False)

print(f"\nResult: {len(markdown)} characters")
print("First 200 characters:")
print(markdown[:200])
print("...")

# --- Save output ---
output_dir = Path.cwd() / "test_outputs"   # works in scripts + notebooks
output_dir.mkdir(exist_ok=True)

filename = "SNAP_10K_Item1.md"
filepath = output_dir / filename

with open(filepath, "w", encoding="utf-8") as f:
    f.write(markdown)

print(f"\nSaved to: {filepath}")
