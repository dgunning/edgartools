"""
Test script to explore PEO compensation data in TSLA proxy statement (DEF 14A)

This script demonstrates:
1. How to access executive compensation data from proxy statements
2. The structure of PEO (Principal Executive Officer) compensation
3. Why certain values may be missing (e.g., Musk receives $0 salary)
"""
import pandas as pd
from edgar import Company

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 200)
pd.set_option('display.float_format', lambda x: '{:,.0f}'.format(x) if pd.notna(x) else '-')

# Get TSLA company and latest proxy statement
tsla = Company("TSLA")
print(f"Company: {tsla.name}")
print(f"CIK: {tsla.cik}")
print()

# Get the latest DEF 14A filing
filings = tsla.get_filings(form="DEF 14A")
print(f"Found {len(filings)} DEF 14A filings")
filing = filings[0]
print(f"Latest filing: {filing.filing_date}")
print(f"Accession: {filing.accession_number}")
print()

# Get the proxy object
proxy = filing.obj()
print(f"Proxy object type: {type(proxy).__name__}")
print()

# Check executive compensation
print("=" * 60)
print("EXECUTIVE COMPENSATION")
print("=" * 60)

if hasattr(proxy, 'executive_compensation'):
    exec_comp = proxy.executive_compensation
    print(f"Executive Compensation type: {type(exec_comp)}")
    print(f"\nColumns: {list(exec_comp.columns)}")
    print(f"\nFull DataFrame:")
    print(exec_comp.to_string())

    # Check PEO specific columns
    print("\n\nPEO COMPENSATION DETAILS:")
    if 'peo_total_comp' in exec_comp.columns:
        print(f"\nPEO Total Compensation by Year:")
        for idx, row in exec_comp.iterrows():
            year = row.get('fiscal_year_end', 'N/A')
            peo_total = row.get('peo_total_comp', None)
            peo_paid = row.get('peo_actually_paid_comp', None)
            peo_total_str = f"${peo_total:,.0f}" if pd.notna(peo_total) else "-"
            peo_paid_str = f"${peo_paid:,.0f}" if pd.notna(peo_paid) else "-"
            print(f"  {year}: Total={peo_total_str}, Actually Paid={peo_paid_str}")
else:
    print("No executive_compensation attribute found")

# Check pay vs performance
print()
print("=" * 60)
print("PAY VS PERFORMANCE")
print("=" * 60)

if hasattr(proxy, 'pay_vs_performance'):
    pvp = proxy.pay_vs_performance
    print(f"Pay vs Performance type: {type(pvp)}")
    print(f"\nColumns: {list(pvp.columns)}")
    print(f"\nFull DataFrame:")
    print(pvp.to_string())

    # Check for PEO data in columns
    print("\n\nPAY VS PERFORMANCE - PEO Details:")
    if 'peo_actually_paid_comp' in pvp.columns:
        for idx, row in pvp.iterrows():
            year = row.get('fiscal_year_end', 'N/A')
            peo_paid = row.get('peo_actually_paid_comp', None)
            tsr = row.get('total_shareholder_return', None)
            net_income = row.get('net_income', None)
            peo_paid_str = f"${peo_paid:,.0f}" if pd.notna(peo_paid) else "-"
            tsr_str = f"{tsr:.1%}" if pd.notna(tsr) else "-"
            ni_str = f"${net_income:,.0f}" if pd.notna(net_income) else "-"
            print(f"  {year}: PEO Actually Paid={peo_paid_str}, TSR={tsr_str}, Net Income={ni_str}")
else:
    print("No pay_vs_performance attribute found")

# Check raw XBRL data to understand the source values
print()
print("=" * 60)
print("RAW XBRL DATA - PEO CONCEPTS")
print("=" * 60)

xbrl = filing.xbrl()
if xbrl:
    # Get PEO-related concepts
    concepts = xbrl.facts.get_unique_concepts()
    peo_concepts = [c for c in concepts if 'peo' in c.lower()]
    print(f"PEO-related XBRL concepts: {peo_concepts}")
    print()

    # Get raw values for each PEO concept
    for concept_name in ['PeoTotalCompAmt', 'PeoActuallyPaidCompAmt']:
        results = xbrl.facts.search_facts(concept_name)
        if len(results) > 0:
            print(f"\n{concept_name}:")
            # Get unique period/value combinations
            unique_data = results[['value', 'period_end']].drop_duplicates()
            for _, row in unique_data.iterrows():
                val = row['value']
                period = row['period_end']
                # Show empty values explicitly
                if val == '' or val is None or (isinstance(val, float) and pd.isna(val)):
                    val_str = '(empty/missing)'
                else:
                    val_str = f"${float(val):,.0f}" if val else '(empty)'
                print(f"  {period}: {val_str}")
else:
    print("No XBRL data available")

# Summary
print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)

print("\nKey findings for TSLA proxy statement:")
if hasattr(proxy, 'executive_compensation'):
    exec_comp = proxy.executive_compensation
    if 'peo_total_comp' in exec_comp.columns:
        latest = exec_comp.iloc[-1]  # Most recent year
        peo_total = latest.get('peo_total_comp')
        peo_paid = latest.get('peo_actually_paid_comp')
        neo_total = latest.get('neo_avg_total_comp')
        neo_paid = latest.get('neo_avg_actually_paid_comp')

        na_msg = 'N/A (shows as "-" in proxy)'
        peo_total_str = f"${peo_total:,.0f}" if pd.notna(peo_total) else na_msg
        peo_paid_str = f"${peo_paid:,.0f}" if pd.notna(peo_paid) else na_msg

        print(f"  Latest Year: {latest.get('fiscal_year_end')}")
        print(f"  PEO Total Comp (Summary Comp Table): {peo_total_str}")
        print(f"  PEO Actually Paid Comp: {peo_paid_str}")
        if pd.notna(neo_total):
            print(f"  NEO Average Total Comp: ${neo_total:,.0f}")
        if pd.notna(neo_paid):
            print(f"  NEO Average Actually Paid: ${neo_paid:,.0f}")

print()
print("EXPLANATION:")
print("  - PEO Total Comp shows '-' because Elon Musk receives $0 salary/cash compensation")
print("  - PEO Actually Paid for 2024 is missing from the XBRL data in the filing")
print("  - Historical data (2020-2023) shows equity-based 'Actually Paid' values")
print("  - NEO (Named Executive Officer) averages ARE available for all years")
