import pandas as pd
import os

TARGET_DIR = r"C:\edgartools_git\quant\financial-templet"
FILES = ["AAPL_Financials.xlsx", "BAC_Financials.xlsx", "NVDA_Financials.xlsx"]

def verify():
    for f in FILES:
        path = os.path.join(TARGET_DIR, f)
        if not os.path.exists(path):
            print(f"MISSING: {f}")
            continue
        
        print(f"Checking {f}...")
        try:
            xl = pd.ExcelFile(path)
            print(f"  Sheets: {xl.sheet_names}")
            for sheet in xl.sheet_names:
                df = xl.parse(sheet)
                print(f"    {sheet}: {len(df)} rows, {len(df.columns)} cols")
                # Sample check structure
                if not df.empty and "Item" in df.columns[0]:
                     print(f"      First item: {df.iloc[0,0]}")
        except Exception as e:
            print(f"  ERROR reading {f}: {e}")

if __name__ == "__main__":
    verify()
