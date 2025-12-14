"""Debug document_period_end_date extraction issue for Netflix 2011 10-K."""
from edgar import Company

print("=" * 80)
print("Testing document_period_end_date extraction - Netflix 2011 10-K")
print("=" * 80)

company = Company("NFLX")
filing = company.get_filings(form="10-K", accession_number="0001065280-13-000008").latest()

print(f"\nFiling: {filing.form} filed {filing.filing_date}")
print(f"Accession: {filing.accession_number}")

xbrl = filing.xbrl()

print("\nXBRL entity_info keys related to period/date:")
for key, value in xbrl.entity_info.items():
    if any(term in key.lower() for term in ['period', 'date', 'year']):
        print(f"  {key:30s}: {value}")

print("\nKey values:")
print(f"  xbrl.period_of_report: {xbrl.period_of_report}")
print(f"  document_period_end_date: {xbrl.entity_info.get('document_period_end_date')}")
print(f"  fiscal_year: {xbrl.entity_info.get('fiscal_year')}")
print(f"  fiscal_period: {xbrl.entity_info.get('fiscal_period')}")

# Check if DocumentPeriodEndDate exists in raw XBRL
print("\n" + "=" * 80)
print("Searching raw XBRL for DocumentPeriodEndDate...")
print("=" * 80)

import re

xbrl_xml = filing.xml()

# Search for various forms of DocumentPeriodEndDate
patterns = [
    r'<[^>]*DocumentPeriodEndDate[^>]*>([^<]+)</[^>]*DocumentPeriodEndDate[^>]*>',
    r'DocumentPeriodEndDate.*?(\d{4}-\d{2}-\d{2})',
    r'dei:DocumentPeriodEndDate.*?(\d{4}-\d{2}-\d{2})',
]

for pattern in patterns:
    matches = re.findall(pattern, xbrl_xml, re.DOTALL | re.IGNORECASE)
    if matches:
        print(f"  ✓ Found with pattern '{pattern[:50]}...': {matches[:3]}")

# Also search for the actual value we expect
if '2011-12-31' in xbrl_xml:
    print("\n  ✓ Date '2011-12-31' exists in XBRL")
    # Find context around it
    idx = xbrl_xml.find('2011-12-31')
    context = xbrl_xml[max(0, idx-200):idx+100]
    print(f"  Context: ...{context}...")
else:
    print("\n  ✗ Date '2011-12-31' NOT found in XBRL")

print("\n" + "=" * 80)
print("Expected vs Actual:")
print("=" * 80)
print("  Expected period_of_report: 2011-12-31")
print(f"  Actual period_of_report:   {xbrl.period_of_report}")
print(f"  Status: {'✓ PASS' if xbrl.period_of_report == '2011-12-31' else '✗ FAIL'}")
