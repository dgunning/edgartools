"""List Henry Schein 10-K filings."""
from edgar import Company

company = Company("1000228")  # HENRY SCHEIN INC
filings = company.get_filings(form="10-K")

print("=" * 80)
print("Henry Schein 10-K Filings")
print("=" * 80)

for i, filing in enumerate(filings[:10], 1):
    print(f"\n{i}. Filing Date: {filing.filing_date}")
    print(f"   Accession: {filing.accession_number}")
    print(f"   Period: {filing.period_of_report}")
    print(f"   Form: {filing.form}")
