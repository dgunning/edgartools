
import sys
import os
import requests
import pandas as pd
import json
from edgar import Company, set_identity
from edgar.xbrl import XBRL
import edgar.xbrl.standardization as standardization

# Configuration
API_KEY = "5RyKeLfm0OSUCluSNA03rT8HumQCCpKp"
TICKERS = ["JPM", "WFC", "C", "GS", "MS"]

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.getcwd()))

# --- Debug: Print Master_Unified_Schema.json content ---
SCHEMA_PATH = "xbrl/standardization/Master_Unified_Schema.json"
try:
    with open(SCHEMA_PATH, 'r') as f:
        schema_content = json.load(f)
    print("DEBUG: Master_Unified_Schema.json content snippet (Cash Flow core):")
    for tag, label in schema_content.get('cash_flow', {}).get('core', {}).items():
        if "cash" in label.lower() or "change" in label.lower() or "capital" in label.lower():
            print(f"  {tag}: {label}")
except Exception as e:
    print(f"DEBUG: Failed to load Master_Unified_Schema.json: {e}")
# --- End Debug ---

def fetch_fmp_cf_data(ticker):
    url = f"https://financialmodelingprep.com/stable/cash-flow-statement?symbol={ticker}&limit=1&apikey={API_KEY}&period=quarter"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        if data:
            return data[0]
    return None

def get_local_cf_data(ticker, target_date):
    company = Company(ticker)
    filings = company.get_filings(form="10-Q")
    if not filings:
        return None, None
    
    filing = filings[0]
    xbrl = XBRL.from_filing(filing)
    if not xbrl:
        return None, None
    
    cashflow_stmt = xbrl.statements.cashflow_statement()
    
    period_key = None
    for p in xbrl.reporting_periods:
        if 'duration' in p['key']:
            if p['end_date'] == target_date:
                period_key = p['key']
                break
    
    if not period_key:
        for p in xbrl.reporting_periods:
            if 'duration' in p['key']:
                end = pd.to_datetime(p['end_date'])
                start = pd.to_datetime(p['start_date'])
                if (end - start).days < 100 and end.strftime('%Y-%m') == target_date[:7]:
                    period_key = p['key']
                    break
                    
    if not period_key:
        return None, None
        
    # Get raw data from the statement
    raw_statement_data = cashflow_stmt.get_raw_data(period_filter=period_key)
    
    # Initialize mapper (same as in rendering.py)
    mapper = standardization.ConceptMapper(standardization.initialize_default_mappings())
    
    # Determine sector from SIC code in entity_info if available
    sector = None
    entity_info = xbrl.entity_info # XBRL object has entity_info
    if entity_info:
        sic = entity_info.get('sic')
        if sic:
            try:
                sic_int = int(sic)
                if 6000 <= sic_int <= 6299: sector = "FINANCIAL_SERVICES"
                elif 6300 <= sic_int <= 6411: sector = "INSURANCE"
                elif sic_int == 6798: sector = "REIT"
                elif sic_int in [1311, 1381, 1382, 1389, 2911]: sector = "ENERGY"
            except: pass

    # Manually apply standardization and collect results
    standardized_data = []
    for item in raw_statement_data:
        concept = item.get('concept', '')
        original_label = item.get('label', '')

        if item.get('is_abstract') or item.get('is_dimension'):
            standardized_data.append(item)
            continue
            
        context = {
            "statement_type": "CashFlowStatement",
            "sector": sector,
            "level": item.get('level', 0)
        }
        
        
        mapped_label = mapper.map_concept(concept, original_label, context)
        
        # Debug print here
        print(f"DEBUG_MAPPER: Ticker={ticker}, Concept={concept}, OriginalLabel='{original_label}', MappedLabel='{mapped_label}'")
        
        # Update label in item if mapped
        if mapped_label:
            item['label'] = mapped_label
        standardized_data.append(item)
            
    # Now build a DataFrame from the standardized data manually
    # Simplified version, assuming all items are dicts and have 'label' and 'concept'
    df_rows = []
    for item in standardized_data:
        row = {
            'concept': item.get('concept', ''),
            'label': item.get('label', ''), # This will now be the mapped label if found
        }
        # Get the value for the specific period_key
        values = item.get('values', {})
        val = values.get(period_key) # period_key is defined outside this loop
        row[period_key] = val
        df_rows.append(row)
        
    df = pd.DataFrame(df_rows)
    print(f"DEBUG: Final standardized DF for {ticker} CF:\n{df.to_string()}")
    
    result = {}
    for _, row in df.iterrows():
        label = row['label']
        # Find numeric column
        val = row.get(period_key)
        result[label] = val
        
    return result, filing.accession_no

def main():
    set_identity("Test User test@example.com")
    
    results = []
    
    fmp_data_all = {
        "C": {"netCashProvidedByOperatingActivities": 1100000000, "netCashProvidedByInvestingActivities": -6363000000, "netCashProvidedByFinancingActivities": 0, "netChangeInCash": 0, "capitalExpenditure": 0, "date": "2025-09-30"},
        "JPM": {"netCashProvidedByOperatingActivities": -45214000000, "netCashProvidedByInvestingActivities": -21311000000, "netCashProvidedByFinancingActivities": -47773000000, "netChangeInCash": -116891000000, "capitalExpenditure": 0, "date": "2025-09-30"},
        "WFC": {"netCashProvidedByOperatingActivities": -869000000, "netCashProvidedByInvestingActivities": -82865000000, "netCashProvidedByFinancingActivities": 63117000000, "netChangeInCash": -20617000000, "capitalExpenditure": 0, "date": "2025-09-30"},
        "MS": {"netCashProvidedByOperatingActivities": -3332000000, "netCashProvidedByInvestingActivities": -10676000000, "netCashProvidedByFinancingActivities": 9076000000, "netChangeInCash": -5396000000, "capitalExpenditure": -713000000, "date": "2025-09-30"},
        "GS": {"netCashProvidedByOperatingActivities": 2680000000, "netCashProvidedByInvestingActivities": -5113000000, "netCashProvidedByFinancingActivities": 19781000000, "netChangeInCash": 16610000000, "capitalExpenditure": -558000000, "date": "2025-09-30"}
    }
    
    metrics = ["netCashProvidedByOperatingActivities", "netCashProvidedByInvestingActivities", "netCashProvidedByFinancingActivities", "netChangeInCash", "capitalExpenditure"]
    
    for ticker in TICKERS:
        print(f"Comparing Cash Flow for {ticker}...")
        fmp = fmp_data_all.get(ticker)
        if not fmp:
            print(f"FMP data not available for {ticker}")
            continue
            
        target_date = fmp['date']
        
        local, acc_no = get_local_cf_data(ticker, target_date)
        if not local:
            print(f"Failed to get local CF data for {ticker} at {target_date}")
            continue
            
        row = {"ticker": ticker, "period": target_date}
        for m in metrics:
            row[f"{m}_fmp"] = fmp.get(m)
            row[f"{m}_local"] = local.get(m)
            
        results.append(row)
        
    df_results = pd.DataFrame(results)
        
    print("\n--- Cash Flow Summary Comparison Table ---")
        
    
        
    for _, r in df_results.iterrows():
        
        print(f"\n{r['ticker']} ({r['period']})")
        
        print(f"{'Metric':40} | {'Local':>20} | {'FMP':>20} | {'Match'}")
        
        print("-" * 100)
        
        for m in metrics:
        
            l_v = r[f'{m}_local']
        
            f_v = r[f'{m}_fmp']
        
            
        
            # FMP often reports 0 for capitalExpenditure for banks, where it's actually just not a separate line item but included in investing
        
            # Let's consider 0 and None a match for now for capitalExpenditure
            match = "YES" if str(l_v) == str(f_v) or (m == 'capitalExpenditure' and ((l_v == 0 and f_v is None) or (l_v is None and f_v == 0))) else "NO"
            print(f"{m:40} | {str(l_v):>20} | {str(f_v):>20} | {match}")

if __name__ == "__main__":
    main()
