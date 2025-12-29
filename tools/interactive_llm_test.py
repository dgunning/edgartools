import sys
from pathlib import Path

sys.path.insert(0, "../")

from edgar import Company
from edgar.llm import extract_markdown

print("=" * 70)
print("SETUP: Getting SNAP 10-K filing")
print("=" * 70)

snap = Company("SNAP")
filings = snap.get_filings(form="10-K")

# Depending on library behavior, choose one:
try:
    filing = filings.latest()          # common: returns a single filing
except TypeError:
    filing = filings.latest(1)[0]      # if latest(n) returns a list-like

print(f"Filing: {filing.form} for {filing.company}")
print(f"Date: {filing.filing_date}\n")

print("=" * 70)
print("EXAMPLE 1: Basic Usage (all defaults)")
print("=" * 70)

# Extract Item 1 (switch to "7" if needed)
markdown = extract_markdown(filing, item="8")

print(f"\nResult: {len(markdown)} characters")
print("First 200 characters:")
print(markdown[:200])
print("...")

# Save output relative to THIS script file
script_dir = Path(__file__).resolve().parent
output_dir = script_dir / "test_outputs"
output_dir.mkdir(exist_ok=True)

filename = "SNAP_10K_Item1.md"
filepath = output_dir / filename

with open(filepath, "w", encoding="utf-8") as f:
    f.write(markdown)

print(f"\nSaved to: {filepath}")
