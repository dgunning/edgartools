"""Debug AAPL LongTermDebt and ShortTermDebt issues."""

from edgar import Company, set_identity, use_local_storage
import yfinance as yf

set_identity("Dev Gunning developer-gunning@gmail.com")
use_local_storage(True)

company = Company('AAPL')
filing = list(company.get_filings(form='10-K'))[0]
xbrl = filing.xbrl()
stock = yf.Ticker('AAPL')

print("="*80)
print("AAPL DEBT INVESTIGATION")
print("="*80)

# LongTermDebt
print("\n1. LONG-TERM DEBT")
print("-"*80)

yf_ltd = stock.balance_sheet.loc['Long Term Debt'].iloc[0] if 'Long Term Debt' in stock.balance_sheet.index else None
print(f"yfinance: ${yf_ltd/1e9:.2f}B")

# Check what our current mapping gets
facts = xbrl.facts
ltd_df = facts.get_facts_by_concept('LongTermDebt')

# Filter for exact match
expected = ['us-gaap:LongTermDebt', 'us-gaap_LongTermDebt', 'LongTermDebt']
ltd_exact = ltd_df[ltd_df['concept'].isin(expected)]
ltd_no_dim = ltd_exact[ltd_exact['full_dimension_label'].isna()]
ltd_numeric = ltd_no_dim[ltd_no_dim['numeric_value'].notna()]
latest = ltd_numeric.sort_values('period_key', ascending=False).iloc[0] if len(ltd_numeric) > 0 else None

if latest is not None:
    print(f"Current mapping (LongTermDebt): ${latest['numeric_value']/1e9:.2f}B")
    print(f"  Concept: {latest['concept']}")
    print(f"  Label: {latest.get('label', 'N/A')}")

# Check LongTermDebtNoncurrent
print("\nChecking LongTermDebtNoncurrent...")
ltdn_df = facts.get_facts_by_concept('LongTermDebtNoncurrent')
expected_ltdn = ['us-gaap:LongTermDebtNoncurrent', 'us-gaap_LongTermDebtNoncurrent', 'LongTermDebtNoncurrent']
ltdn_exact = ltdn_df[ltdn_df['concept'].isin(expected_ltdn)]
if 'full_dimension_label' in ltdn_exact.columns:
    ltdn_no_dim = ltdn_exact[ltdn_exact['full_dimension_label'].isna()]
else:
    ltdn_no_dim = ltdn_exact
ltdn_numeric = ltdn_no_dim[ltdn_no_dim['numeric_value'].notna()]
latest_ltdn = ltdn_numeric.sort_values('period_key', ascending=False).iloc[0] if len(ltdn_numeric) > 0 else None

if latest_ltdn is not None:
    print(f"LongTermDebtNoncurrent: ${latest_ltdn['numeric_value']/1e9:.2f}B")
    print(f"  Concept: {latest_ltdn['concept']}")
    print(f"  Label: {latest_ltdn.get('label', 'N/A')}")
    variance = abs(latest_ltdn['numeric_value'] - yf_ltd) / yf_ltd * 100
    print(f"  Variance: {variance:.1f}%")

# ShortTermDebt
print("\n2. SHORT-TERM DEBT")
print("-"*80)

yf_std = stock.balance_sheet.loc['Current Debt'].iloc[0] if 'Current Debt' in stock.balance_sheet.index else None
print(f"yfinance: ${yf_std/1e9:.2f}B")

# Check different concepts for short-term debt
short_debt_concepts = [
    'ShortTermBorrowings',
    'DebtCurrent',
    'LongTermDebtCurrent',
    'CommercialPaper',
    'ShortTermDebtAndCapitalLeaseObligationsCurrent'
]

print("\nChecking various short-term debt concepts:")
for concept in short_debt_concepts:
    df = facts.get_facts_by_concept(concept)
    if df is not None and len(df) > 0:
        expected = [f'us-gaap:{concept}', f'us-gaap_{concept}', concept]
        exact = df[df['concept'].isin(expected)]
        if 'full_dimension_label' in exact.columns:
            no_dim = exact[exact['full_dimension_label'].isna()]
        else:
            no_dim = exact
        numeric = no_dim[no_dim['numeric_value'].notna()]
        if len(numeric) > 0:
            latest = numeric.sort_values('period_key', ascending=False).iloc[0]
            val = latest['numeric_value'] / 1e9
            variance = abs(latest['numeric_value'] - yf_std) / yf_std * 100 if yf_std else 0
            match = "✓" if variance <= 15 else "✗"
            print(f"  {match} {concept}: ${val:.2f}B (variance: {variance:.1f}%)")
            print(f"      Label: {latest.get('label', 'N/A')}")

# Check if we need to sum multiple concepts
print("\nChecking if yfinance sums multiple components:")
ltd_current = None
if len(ltd_numeric) > 0:
    # Check LongTermDebtCurrent
    ltdc_df = facts.get_facts_by_concept('LongTermDebtCurrent')
    expected_ltdc = ['us-gaap:LongTermDebtCurrent', 'us-gaap_LongTermDebtCurrent', 'LongTermDebtCurrent']
    ltdc_exact = ltdc_df[ltdc_df['concept'].isin(expected_ltdc)]
    if 'full_dimension_label' in ltdc_exact.columns:
        ltdc_no_dim = ltdc_exact[ltdc_exact['full_dimension_label'].isna()]
    else:
        ltdc_no_dim = ltdc_exact
    ltdc_numeric = ltdc_no_dim[ltdc_no_dim['numeric_value'].notna()]
    if len(ltdc_numeric) > 0:
        ltd_current = ltdc_numeric.sort_values('period_key', ascending=False).iloc[0]
        print(f"  LongTermDebtCurrent: ${ltd_current['numeric_value']/1e9:.2f}B")

if latest is not None and ltd_current is not None:
    total_std = ltd_current['numeric_value']
    variance_std = abs(total_std - yf_std) / yf_std * 100 if yf_std else 0
    print(f"\nIf yfinance 'Current Debt' = LongTermDebtCurrent:")
    print(f"  LongTermDebtCurrent: ${total_std/1e9:.2f}B (variance: {variance_std:.1f}%)")

    total_ltd = latest['numeric_value'] + ltd_current['numeric_value']
    variance_ltd = abs(latest['numeric_value'] - yf_ltd) / yf_ltd * 100 if yf_ltd else 0
    print(f"\nIf yfinance 'Long Term Debt' = LongTermDebt (no current portion):")
    print(f"  LongTermDebt: ${latest['numeric_value']/1e9:.2f}B (variance: {variance_ltd:.1f}%)")
    print(f"  LongTermDebt + LongTermDebtCurrent: ${total_ltd/1e9:.2f}B")

print("\n" + "="*80)
