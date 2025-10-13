"""
Reproduction script for Issue #412: How to get accurate and complete data from companies?

This script investigates reported issues:
1. AAPL 2020: Shows ~65 billion in revenue (quarterly) instead of annual
2. AAPL historical: Data stops being reported for years before 2020
3. TSLA 2019-2022: Revenue data is missing entirely

Expected behavior:
- Annual revenue should be properly aggregated/displayed for annual filings
- Historical data should be available for reasonable time periods
- Revenue data should be consistently available for major companies
"""

import sys
import os

# Add the project root to Python path for testing
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..'))
sys.path.insert(0, project_root)

import edgar
from edgar import Company
import pandas as pd
from datetime import datetime, date

def investigate_aapl_revenue():
    """Investigate AAPL revenue data issues for 2020 and historical data."""
    print("=" * 60)
    print("INVESTIGATING AAPL REVENUE DATA")
    print("=" * 60)
    
    try:
        
        # Use CIK directly to avoid ticker lookup issues
        aapl = Company("320193")  # AAPL CIK
        print(f"Company: {aapl.name} ({aapl.cik})")
        
        # Get recent 10-K filings to analyze annual revenue
        print("\n--- Getting 10-K filings ---")
        filings_10k = aapl.get_filings(form="10-K", amendments=False).head(5)
        print(f"Found {len(filings_10k)} recent 10-K filings:")
        
        for filing in filings_10k:
            print(f"  {filing.accession_number}: {filing.filing_date} - {filing.form}")
        
        # Focus on 2020 filing (fiscal year end Sep 2020)
        print("\n--- Analyzing 2020 10-K filing ---")
        filing_2020 = None
        for filing in filings_10k:
            if filing.filing_date.year == 2020:
                filing_2020 = filing
                break
        
        if not filing_2020:
            print("No 2020 10-K filing found")
            return None
            
        print(f"Found 2020 filing: {filing_2020.accession_number} dated {filing_2020.filing_date}")
        
        # Get XBRL data and examine revenue
        xbrl = filing_2020.xbrl()
        if not xbrl:
            print("No XBRL data available for 2020 filing")
            return None
            
        statements = xbrl.statements
        income_statement = statements.income_statement()
        
        if not income_statement:
            print("Income statement is None!")
            return None
            
        # Convert to dataframe for analysis
        income_df = income_statement.to_dataframe()
        print(f"\nIncome statement dataframe shape: {income_df.shape}")
        print(f"Column names: {list(income_df.columns)}")
        
        if income_df.empty:
            print("Income statement dataframe is empty!")
            return None
            
        # Look for main revenue line first
        main_revenue_row = income_df[income_df['concept'] == 'us-gaap_Revenues']
        if not main_revenue_row.empty:
            print(f"\nMain Revenue row found:")
            print(main_revenue_row.to_string())
        else:
            # Look for other main revenue concepts
            contract_revenue = income_df[income_df['concept'] == 'us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax']
            if not contract_revenue.empty:
                print(f"\nContract Revenue row found:")
                print(contract_revenue.head(1).to_string())
            
        # Look for revenue concepts
        revenue_concepts = income_df[
            income_df['concept'].str.contains('Revenue|Sales|Net.*Sales', case=False, na=False)
        ]
        
        print(f"\nRevenue-related concepts found ({len(revenue_concepts)}):")
        
        # Show sample with all columns to understand structure
        if len(revenue_concepts) > 0:
            print(f"\nSample revenue concept row structure:")
            sample_row = revenue_concepts.iloc[0]
            for col in income_df.columns:
                print(f"  {col}: {sample_row.get(col, 'N/A')}")
        
        # Display top revenue concepts more concisely
        print(f"\nTop 5 revenue concepts with actual values:")
        for _, row in revenue_concepts.head(5).iterrows():
            concept = row['concept']
            label = row.get('label', 'N/A')
            
            # Find numeric columns (these contain the actual values)
            numeric_values = {}
            for col in income_df.columns:
                if pd.api.types.is_numeric_dtype(income_df[col]) and pd.notna(row[col]):
                    # Format large numbers nicely
                    val = row[col]
                    if val > 1000000000:  # Billions
                        formatted_val = f"${val/1000000000:.2f}B"
                    elif val > 1000000:  # Millions
                        formatted_val = f"${val/1000000:.2f}M"
                    else:
                        formatted_val = f"${val:,.0f}"
                    numeric_values[col] = formatted_val
            
            if numeric_values:
                value_str = ", ".join([f"{col}: {val}" for col, val in numeric_values.items()])
                print(f"  {concept}: {label}")
                print(f"    Values: {value_str}")
            else:
                print(f"  {concept}: {label} = No numeric values found")
        
        # Try to get current period data
        print("\n--- Analyzing current period data ---")
        try:
            current_period = xbrl.current_period
            current_income = current_period.income_statement()
            
            if current_income is not None:
                current_income_df = current_income.to_dataframe()
                print(f"Current period income statement shape: {current_income_df.shape}")
                
                if not current_income_df.empty:
                    current_revenue = current_income_df[
                        current_income_df['concept'].str.contains('Revenue|Sales|Net.*Sales', case=False, na=False)
                    ]
                    print(f"Current period revenue concepts ({len(current_revenue)}):")
                    for _, row in current_revenue.iterrows():
                        concept = row['concept']
                        label = row.get('label', 'N/A')
                        value = row.get('value', 'N/A')
                        print(f"  {concept}: {label} = {value}")
            else:
                print("Current period income statement is None")
        except Exception as e:
            print(f"Error getting current period data: {e}")
        
        # Check company facts API for revenue data
        print("\n--- Checking Company Facts API ---")
        try:
            company_facts = aapl.get_facts()
            if company_facts and 'facts' in company_facts:
                us_gaap = company_facts['facts'].get('us-gaap', {})
                revenue_facts = {k: v for k, v in us_gaap.items() if 'revenue' in k.lower() or 'sales' in k.lower()}
                print(f"Revenue facts available: {list(revenue_facts.keys())}")
                
                # Look at specific revenue concept
                if 'Revenues' in us_gaap:
                    revenues = us_gaap['Revenues']
                    print(f"Revenues fact has {len(revenues.get('units', {}).get('USD', []))} USD entries")
                    
                    # Show recent annual data
                    usd_data = revenues.get('units', {}).get('USD', [])
                    annual_data = [entry for entry in usd_data if entry.get('form') == '10-K']
                    annual_data.sort(key=lambda x: x.get('end', ''), reverse=True)
                    
                    print("Recent annual revenue data:")
                    for entry in annual_data[:5]:
                        end_date = entry.get('end', 'N/A')
                        value = entry.get('val', 'N/A')
                        form = entry.get('form', 'N/A')
                        print(f"  {end_date} ({form}): ${value:,}" if isinstance(value, (int, float)) else f"  {end_date} ({form}): {value}")
                        
        except Exception as e:
            print(f"Error getting company facts: {e}")
        
        return filing_2020
        
    except Exception as e:
        print(f"Error investigating AAPL: {e}")
        import traceback
        traceback.print_exc()
        return None

def investigate_tsla_revenue():
    """Investigate TSLA revenue data issues for 2019-2022."""
    print("\n" + "=" * 60)
    print("INVESTIGATING TSLA REVENUE DATA")
    print("=" * 60)
    
    try:
        # Use CIK directly to avoid ticker lookup issues
        tsla = Company("1318605")  # TSLA CIK
        print(f"Company: {tsla.name} ({tsla.cik})")
        
        # Get 10-K filings from 2019-2023 period
        print("\n--- Getting 10-K filings for 2019-2023 ---")
        filings_10k = tsla.get_filings(form="10-K", amendments=False).head(10)
        
        relevant_filings = []
        for filing in filings_10k:
            if 2019 <= filing.filing_date.year <= 2023:
                relevant_filings.append(filing)
        
        print(f"Found {len(relevant_filings)} 10-K filings in 2019-2023:")
        for filing in relevant_filings:
            print(f"  {filing.accession_number}: {filing.filing_date} - {filing.form}")
        
        # Analyze each filing for revenue data
        for filing in relevant_filings[:3]:  # Check first 3 filings
            print(f"\n--- Analyzing {filing.filing_date.year} filing ---")
            
            try:
                xbrl = filing.xbrl()
                if not xbrl:
                    print(f"No XBRL data for {filing.filing_date}")
                    continue
                    
                statements = xbrl.statements
                income_statement = statements.income_statement()
                
                if not income_statement:
                    print("Income statement is None!")
                    continue
                    
                income_df = income_statement.to_dataframe()
                print(f"Income statement dataframe shape: {income_df.shape}")
                print(f"Column names: {list(income_df.columns)}")
                
                if income_df.empty:
                    print("Income statement dataframe is empty!")
                    continue
                
                # Look for main revenue lines
                main_revenue = income_df[income_df['concept'] == 'us-gaap_Revenues']
                if not main_revenue.empty:
                    print(f"Main Revenue row found:")
                    print(main_revenue.head(1).to_string())
                    
                # Look for revenue concepts
                revenue_concepts = income_df[
                    income_df['concept'].str.contains('Revenue|Sales|Net.*Sales', case=False, na=False)
                ]
                
                print(f"Top 3 revenue concepts with values:")
                for _, row in revenue_concepts.head(3).iterrows():
                    concept = row['concept']
                    label = row.get('label', 'N/A')
                    
                    # Find numeric columns
                    numeric_values = {}
                    for col in income_df.columns:
                        if pd.api.types.is_numeric_dtype(income_df[col]) and pd.notna(row[col]):
                            val = row[col]
                            if val > 1000000000:  # Billions
                                formatted_val = f"${val/1000000000:.2f}B"
                            elif val > 1000000:  # Millions
                                formatted_val = f"${val/1000000:.2f}M"
                            else:
                                formatted_val = f"${val:,.0f}"
                            numeric_values[col] = formatted_val
                    
                    if numeric_values:
                        value_str = ", ".join([f"{col}: {val}" for col, val in numeric_values.items()])
                        print(f"  {concept}: {label}")
                        print(f"    Values: {value_str}")
                    else:
                        print(f"  {concept}: {label} = No numeric values found")
                    
            except Exception as e:
                print(f"Error analyzing {filing.filing_date.year} filing: {e}")
        
        # Check company facts API
        print("\n--- Checking TSLA Company Facts API ---")
        try:
            company_facts = tsla.get_facts()
            if company_facts and 'facts' in company_facts:
                us_gaap = company_facts['facts'].get('us-gaap', {})
                revenue_facts = {k: v for k, v in us_gaap.items() if 'revenue' in k.lower() or 'sales' in k.lower()}
                print(f"Revenue facts available: {list(revenue_facts.keys())}")
                
                # Look for the most common revenue concepts
                for concept_name in ['Revenues', 'Revenue', 'SalesRevenueNet', 'RevenueFromContractWithCustomerExcludingAssessedTax']:
                    if concept_name in us_gaap:
                        concept_data = us_gaap[concept_name]
                        usd_data = concept_data.get('units', {}).get('USD', [])
                        annual_data = [entry for entry in usd_data if entry.get('form') == '10-K']
                        annual_data.sort(key=lambda x: x.get('end', ''), reverse=True)
                        
                        print(f"\n{concept_name} annual data:")
                        for entry in annual_data[:6]:
                            end_date = entry.get('end', 'N/A')
                            value = entry.get('val', 'N/A')
                            form = entry.get('form', 'N/A')
                            year = end_date[:4] if end_date != 'N/A' else 'N/A'
                            print(f"  {year} {end_date} ({form}): ${value:,}" if isinstance(value, (int, float)) else f"  {year} {end_date} ({form}): {value}")
                        break
                        
        except Exception as e:
            print(f"Error getting TSLA company facts: {e}")
            
    except Exception as e:
        print(f"Error investigating TSLA: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Run the investigation of revenue data issues."""
    print("Issue #412 Reproduction: Revenue Data Accuracy Investigation")
    print("=" * 70)
    
    # Investigate both companies
    aapl_result = investigate_aapl_revenue()
    investigate_tsla_revenue()
    
    print("\n" + "=" * 70)
    print("INVESTIGATION SUMMARY")
    print("=" * 70)
    print("This script investigated the reported revenue data issues.")
    print("Check the output above to understand the data retrieval patterns.")
    print("=" * 70)

if __name__ == "__main__":
    main()