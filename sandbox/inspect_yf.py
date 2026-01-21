
import yfinance as yf
from datetime import datetime

t = yf.Ticker("JPM")
print("--- QUARTERLY FINANCIALS ---")
print(t.quarterly_financials.head())
print("\n--- QUARTERLY BALANCE SHEET ---")
print(t.quarterly_balance_sheet.head())
print("\n--- QUARTERLY CASHFLOW ---")
print(t.quarterly_cashflow.head())

print("\n--- DATES ---")
for col in t.quarterly_financials.columns:
    print(f"Col: {col} TYPE: {type(col)}")
