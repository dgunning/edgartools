
import pandas as pd
import os

CIK_FILE = "CIK_CODES.csv"
OUTPUT_FILE = "test_list.csv"

def main():
    if not os.path.exists(CIK_FILE):
        # Check parent dir if not in current
        CIK_FILE_ALT = os.path.join("..", "CIK_CODES.csv")
        if os.path.exists(CIK_FILE_ALT):
            df = pd.read_csv(CIK_FILE_ALT)
        else:
            print(f"Error: {CIK_FILE} not found.")
            return
    else:
        df = pd.read_csv(CIK_FILE)
    
    print(f"Loaded {len(df)} tickers.")
    
    # Filter for NYSE and NASDAQ if needed (user previously mentioned them)
    # df = df[df['exchange'].isin(['NYSE', 'NASDAQ'])]
    
    # Group by sector and take first 50
    test_list = df.groupby('sector').head(50)
    
    # Save to CSV
    test_list.to_csv(OUTPUT_FILE, index=False)
    
    print(f"Saved {len(test_list)} tickers to {OUTPUT_FILE}")
    print("\nTickers per sector:")
    print(test_list.groupby('sector').size())

if __name__ == "__main__":
    main()
