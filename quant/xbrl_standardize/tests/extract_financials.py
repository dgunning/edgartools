import requests
import json
import time
import os

# Configuration
TICKERS = ["AAPL", "NVDA", "TSLA", "BA", "OXY", "BAC", "SHOP", "JPM", "RKLB", "BFLY", "URI", "SNAP", "META", "ASTS", "BULL"]
BASE_URL = "https://api.nasdaq.com/api/company/{}/financials?frequency=1"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.nasdaq.com/'
}
OUTPUT_DIR = "."  # Current directory

def fetch_financials(ticker):
    url = BASE_URL.format(ticker)
    print(f"Fetching data for {ticker}...")
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def process_table(table_data):
    if not table_data:
        return None
    
    # Structure:
    # "headers": {"value1": "Period Ending:", "value2": "Date1", ...}
    # "rows": [{"value1": "Item Name", "value2": "Data1", ...}, ...]
    
    headers = table_data.get('headers', {})
    rows = table_data.get('rows', [])
    
    if not headers or not rows:
        return None

    # We want the first data column, which is usually value2 (value1 is the label column)
    target_col_key = "value2"
    date_label = headers.get(target_col_key, "Unknown Date")
    
    extracted_data = {}
    extracted_data["Period Ending"] = date_label
    
    for row in rows:
        item_name = row.get("value1", "")
        item_value = row.get(target_col_key, "")
        if item_name:
             extracted_data[item_name] = item_value
             
    return extracted_data

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    for ticker in TICKERS:
        data = fetch_financials(ticker)
        
        if data and 'data' in data and data['data']:
            api_data = data['data']
            
            # The keys in the API response corresponding to the requested tables
            tables_map = {
                "Income Statement": "incomeStatementTable",
                "Balance Sheet": "balanceSheetTable",
                "Cash Flow": "cashFlowTable",
                "Financial Ratios": "financialRatiosTable"
            }
            
            ticker_output = {}
            has_data = False
            
            for nice_name, api_key in tables_map.items():
                if api_key in api_data:
                    processed_table = process_table(api_data[api_key])
                    if processed_table:
                        ticker_output[nice_name] = processed_table
                        has_data = True
            
            if has_data:
                filename = f"{ticker}_financials.json"
                filepath = os.path.join(OUTPUT_DIR, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(ticker_output, f, indent=4)
                print(f"Saved {filepath}")
            else:
                print(f"No valid financial data found for {ticker}")
        else:
            print(f"Failed to parse data for {ticker}")
            
        time.sleep(1) # Be polite

if __name__ == "__main__":
    main()
