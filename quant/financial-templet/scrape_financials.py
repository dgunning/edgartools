import pandas as pd
import os
from edgar import set_identity
from quant import QuantCompany

# Configuration
TICKERS = ["AAPL", "BAC", "NVDA"]
TARGET_DIR = r"C:\edgartools_git\quant\financial-templet"

if not os.path.exists(TARGET_DIR):
    os.makedirs(TARGET_DIR)

# Set identity for EDGAR access
set_identity("Emad emad@example.com")

def main():
    for ticker in TICKERS:
        print(f"Processing {ticker}...")
        try:
            company = QuantCompany(ticker)
            print(f"  Identified as: {company.name} (CIK: {company.cik})")
            
            output_path = os.path.join(TARGET_DIR, f"{ticker}_Financials.xlsx")
            
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # 1. Income Statement
                print("  Fetching Income Statement...")
                income = company.income_statement(period='annual', periods=5)
                if income:
                    df_income = income.to_dataframe()
                    df_income.to_excel(writer, sheet_name="Income", index=True)
                else:
                    print("  WARNING: No Income Statement found.")

                # 2. Balance Sheet
                print("  Fetching Balance Sheet...")
                balance = company.balance_sheet(period='annual', periods=5)
                if balance:
                    df_balance = balance.to_dataframe()
                    df_balance.to_excel(writer, sheet_name="Balance_Sheet", index=True)
                else:
                    print("  WARNING: No Balance Sheet found.")

                # 3. Cash Flow
                print("  Fetching Cash Flow Statement...")
                cash_flow = company.cash_flow(period='annual', periods=5)
                if cash_flow:
                    df_cash = cash_flow.to_dataframe()
                    df_cash.to_excel(writer, sheet_name="Cash_Flow", index=True)
                else:
                    print("  WARNING: No Cash Flow Statement found.")
            
            print(f"Saved {ticker}_Financials.xlsx")
            
        except Exception as e:
            print(f"Failed to process {ticker}: {e}")

if __name__ == "__main__":
    main()
