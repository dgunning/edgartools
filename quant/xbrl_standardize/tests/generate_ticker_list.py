
import pandas as pd
import time
import os
import requests
from edgar import Company, set_identity
from typing import Dict, List, Optional

# Set identity for SEC API
set_identity("User user@example.com")

CIK_FILE = os.path.join("..", "CIK_CODES.csv")
OUTPUT_FILE = "tickers_by_industry.csv"

def fetch_sic_code(cik: str) -> Optional[str]:
    """Fetches SIC code for a CIK using edgar library."""
    try:
        # Rate limiting: SEC allows 10 requests per second
        time.sleep(0.11) 
        company = Company(int(cik)) # Use CIK directly for speed
        if company and hasattr(company, 'sic'):
            return str(company.sic)
    except Exception:
        pass
    return None

def main():
    if not os.path.exists(CIK_FILE):
        print(f"Error: {CIK_FILE} not found.")
        return

    print(f"Loading {CIK_FILE}...")
    df = pd.read_csv(CIK_FILE)
    
    # Filter for NYSE and NASDAQ
    df = df[df['exchange'].isin(['NYSE', 'NASDAQ'])]
    print(f"Filtered to {len(df)} NYSE/NASDAQ tickers.")

    # We want 50 per SIC industry.
    # Since we don't have SIC codes in the CSV, we must fetch them.
    # To be efficient, we'll iterate and keep track of counts per SIC.
    
    output_rows = []
    sic_counts = {}
    limit_per_industry = 50
    
    print(f"Processing tickers to find up to {limit_per_industry} per SIC code...")
    
    # Optional: shuffle to get a more diverse sample if needed
    # df = df.sample(frac=1).reset_index(drop=True)

    processed_count = 0
    start_time = time.time()

    for _, row in df.iterrows():
        ticker = row['symbol']
        cik = row['cik']
        sector = row['sector']
        nasdaq_industry = row['industry']
        
        # Check if we already have 50 for this Nasdaq industry as a heuristic 
        # (usually Nasdaq industry aligns with SIC)
        # But we must be precise about SIC if requested.
        
        sic = fetch_sic_code(cik)
        processed_count += 1
        
        if not sic:
            continue
            
        if sic not in sic_counts:
            sic_counts[sic] = 0
            
        if sic_counts[sic] < limit_per_industry:
            output_rows.append({
                'ticker': ticker,
                'sector': sector,
                'industry': nasdaq_industry,
                'SIC code': sic
            })
            sic_counts[sic] += 1
            
            if len(output_rows) % 10 == 0:
                elapsed = time.time() - start_time
                print(f"Collected {len(output_rows)} tickers... (Processed {processed_count}/{len(df)}, {elapsed:.1f}s)")
        
        # If we have enough industries covered, we can stop? 
        # The user didn't specify a total limit, just 50 per industry.
        # Let's try to get a good amount.
        if len(output_rows) >= 2500: # 50 industries * 50 tickers
            break

    # Save to CSV
    final_df = pd.DataFrame(output_rows)
    final_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nFinalized: Saved {len(final_df)} tickers to {OUTPUT_FILE}")
    print(f"Found {len(sic_counts)} distinct SIC codes.")

if __name__ == "__main__":
    main()
