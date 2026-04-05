from edgar import Company, set_identity
import pandas as pd
pd.set_option('display.max_rows', 100)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

set_identity('Test test@test.com')

def explore(ticker):
    print(f"\n{'='*50}\nExploring {ticker} OCF\n{'='*50}")
    c = Company(ticker)
    # Get latest 10-Q
    filing = c.get_filings(form='10-Q').latest(1)
    print(f"Filing: {filing.form} {filing.filing_date} (Accession: {filing.accession_no})")
    
    xbrl = filing.xbrl()
    concept = 'NetCashProvidedByUsedInOperatingActivities'
    
    facts = xbrl.facts.get_facts_by_concept(f'us-gaap:{concept}')
    if facts is None or facts.empty:
        print("No OCF facts found.")
        return

    # Filter columns safely
    available_cols = facts.columns.tolist()
    desired_cols = ['period_key', 'numeric_value', 'value', 'units', 'dimension_label', 'segment_label']
    cols = [c for c in desired_cols if c in available_cols]
        
    print(facts[cols].head(50))

explore('JPM')
explore('GOOG')
