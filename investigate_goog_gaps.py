#!/usr/bin/env python3
"""
Investigate GOOG concepts to identify gaps relative to other MAG7 companies.
"""
import pandas as pd
from edgar import Company, set_identity

set_identity("Dev Gunning developer-gunning@gmail.com")

# Define tickers to compare
tickers = ['GOOG', 'AAPL']  # Compare GOOG to AAPL as a reference

# Concept we are looking for (stripped)
TARGET_CONCEPTS = [
    'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet', 
    'Revenues', 'Revenue', 'TotalRevenues', 'NetSales'
]

for ticker in tickers:
    company = Company(ticker)
    facts = company.get_facts()
    df = facts.to_dataframe(include_metadata=True)
    
    # Strip namespace
    df['concept_stripped'] = df['concept'].apply(lambda x: x.split(':')[-1] if ':' in x else x)
    
    # Filter for revenue-like concepts
    mask = df['concept_stripped'].isin(TARGET_CONCEPTS)
    revenue_df = df[mask]
    
    print(f"\n========== {ticker} ==========")
    print(f"Total revenue facts found: {len(revenue_df)}")
    
    if not revenue_df.empty:
        print(f"Year range: {revenue_df['fiscal_year'].min()} - {revenue_df['fiscal_year'].max()}")
        print("Unique concepts used:")
        print(revenue_df['concept'].unique())
    else:
        print("No revenue facts found with target concepts!")
        # Let's find what they DO use
        possible = df[df['concept_stripped'].str.contains('revenue|sales', case=False, na=False)]
        print(f"Possible alternatives ({len(possible['concept_stripped'].unique())} unique):")
        for c in possible['concept_stripped'].unique()[:10]:
            print(f"  - {c}")
