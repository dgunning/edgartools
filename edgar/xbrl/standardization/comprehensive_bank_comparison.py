
import sys
import os
import requests
import pandas as pd
from edgar import Company, set_identity
from edgar.xbrl import XBRL

# Configuration
API_KEY = "5RyKeLfm0OSUCluSNA03rT8HumQCCpKp"
TICKERS = ["JPM", "WFC", "C", "GS", "MS"]
# TICKERS = ["JPM"] # Test first

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.getcwd()))

def fetch_fmp_data(ticker):
    url = f"https://financialmodelingprep.com/stable/income-statement?symbol={ticker}&limit=1&apikey={API_KEY}&period=quarter"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        if data:
            return data[0]
    return None

def get_local_data(ticker, target_date):
    company = Company(ticker)
    # Get 10-Q closest to or containing target_date
    filings = company.get_filings(form="10-Q")
    if not filings:
        return None, None
    
    # Just take the latest for now
    filing = filings[0]
    xbrl = XBRL.from_filing(filing)
    if not xbrl:
        return None, None
    
    income_stmt = xbrl.statements.income_statement()
    
    # Find the period
    period_key = None
    for p in xbrl.reporting_periods:
        if 'duration' in p['key']:
            if p['end_date'] == target_date:
                period_key = p['key']
                break
    
    if not period_key:
        # Try to find any 3-month period ending in target_date month
        for p in xbrl.reporting_periods:
            if 'duration' in p['key']:
                end = pd.to_datetime(p['end_date'])
                start = pd.to_datetime(p['start_date'])
                if (end - start).days < 100 and end.strftime('%Y-%m') == target_date[:7]:
                    period_key = p['key']
                    break
                    
    if not period_key:
        return None, None
        
    df = income_stmt.to_dataframe(period_filter=period_key, standard=True)
    
    print(f"DEBUG: Data for {ticker}:\n{df[['concept', 'label']].to_string()}")
    
    result = {}
    for _, row in df.iterrows():
        label = row['label']
        # Find numeric column
        val = None
        for col in df.columns:
            if "-" in str(col) or period_key in str(col):
                val = row[col]
                break
        result[label] = val
        
    return result, filing.accession_no

def main():
    set_identity("Test User test@example.com")
    
    results = []
    
    for ticker in TICKERS:
        print(f"Comparing {ticker}...")
        fmp = fetch_fmp_data(ticker)
        if not fmp:
            print(f"Failed to fetch FMP data for {ticker}")
            continue
            
        target_date = fmp['date']
        print(f"FMP Date: {target_date}")
        
        local, acc_no = get_local_data(ticker, target_date)
        if not local:
            print(f"Failed to get local data for {ticker} at {target_date}")
            continue
            
        metrics = ["revenue", "costOfRevenue", "grossProfit", "operatingIncome", "netIncome", "eps", "epsDiluted"]
        
        row = {"ticker": ticker, "period": target_date}
        for m in metrics:
            row[f"{m}_fmp"] = fmp.get(m)
            row[f"{m}_local"] = local.get(m)
            
        results.append(row)
        
    df_results = pd.DataFrame(results)
    print("\n--- Summary Comparison Table ---")
    
    # Print a condensed view
    for _, r in df_results.iterrows():
        print(f"\n{r['ticker']} ({r['period']})")
        print(f"{ 'Metric':20} | {'Local':>15} | {'FMP':>15} | {'Match'}")
        print("-" * 60)
        for m in ["revenue", "netIncome", "eps"]:
            l_v = r[f'{m}_local']
            f_v = r[f'{m}_fmp']
            match = "YES" if str(l_v) == str(f_v) else "NO"
            print(f"{m:20} | {str(l_v):>15} | {str(f_v):>15} | {match}")

if __name__ == "__main__":
    main()
