
import sys
import os
import pandas as pd

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.getcwd()))

from edgar import Company, set_identity
from edgar.xbrl import XBRL

def main():
    set_identity("Test User test@example.com")
    company = Company("BAC")
    filing = company.latest("10-Q")
    xbrl = XBRL.from_filing(filing)
    
    income_stmt = xbrl.statements.income_statement()
    
    # We want to find the 'Three Months Ended' period
    # Usually this has a duration of ~90 days
    three_month_period = None
    for period in xbrl.reporting_periods:
        if 'duration' in period['key']:
            start = pd.to_datetime(period['start_date'])
            end = pd.to_datetime(period['end_date'])
            days = (end - start).days
            if 80 <= days <= 100 and end.month == 9 and end.year == 2025:
                three_month_period = period['key']
                break
    
    if not three_month_period:
        # Fallback to the first quarterly one found
        for period in xbrl.reporting_periods:
            if 'duration' in period['key']:
                start = pd.to_datetime(period['start_date'])
                end = pd.to_datetime(period['end_date'])
                if 80 <= (end - start).days <= 100:
                    three_month_period = period['key']
                    break

    print(f"Target Period: {three_month_period}")
    
    # Render with the specific period
    df = income_stmt.to_dataframe(period_filter=three_month_period, standard=True)
    
    comparison = {
        "revenue": None,
        "costOfRevenue": None,
        "grossProfit": None,
        "operatingIncome": None,
        "netIncome": None,
        "eps": None,
        "epsDiluted": None
    }
    
    for _, row in df.iterrows():
        label = row['label']
        if label in comparison:
            # Get the first numeric-looking column
            val = None
            for col in df.columns:
                if "-" in str(col) or three_month_period in str(col):
                    val = row[col]
                    break
            comparison[label] = val

    print("\n--- Head to Head Comparison (BAC Q3 2025) ---")
    print(f"{'Concept':25} | {'Local (Standardized)':>20} | {'FMP API (Fetched)':>20}")
    print("-" * 75)
    
    fmp_data = {
        "revenue": 48221000000,
        "costOfRevenue": 21428000000,
        "grossProfit": 26793000000,
        "operatingIncome": 9456000000,
        "netIncome": 8469000000,
        "eps": 1.08,
        "epsDiluted": 1.06
    }
    
    for concept, fmp_val in fmp_data.items():
        local_val = comparison.get(concept, "N/A")
        print(f"{concept:25} | {str(local_val):>20} | {str(fmp_val):>20}")

if __name__ == "__main__":
    main()
