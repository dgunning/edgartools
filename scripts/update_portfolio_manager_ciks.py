#!/usr/bin/env python3
"""
Script to update the portfolio manager database with CIKs extracted from recent 13F-HR filings.

This script:
1. Extracts CIKs from recent 13F-HR filings 
2. Maps them to companies in our portfolio manager database
3. Updates the database with the correct CIKs and company names from SEC filings

Usage:
    python scripts/update_portfolio_manager_ciks.py
"""

import json
from pathlib import Path


import edgar


def get_recent_filing_ciks():
    """Extract CIKs and company names from recent 13F-HR filings."""
    print("Fetching recent 13F-HR filings...")
    filings = edgar.get_filings(form='13F-HR', filing_date='2025-07-01:2025-09-30')
    df = filings.data.to_pandas()
    cik_company_pairs = df[['cik', 'company']].drop_duplicates()
    print(f"Found {len(cik_company_pairs)} unique CIK-company pairs")
    return cik_company_pairs


def create_cik_mappings(filing_data):
    """Create mappings from our database keys to CIKs found in filings."""

    # Manually verified mappings from recent filings
    mappings = {
        'millennium_management': {'cik': 1273087, 'filing_name': 'MILLENNIUM MANAGEMENT LLC'},
        'bridgewater': {'cik': 1350694, 'filing_name': 'Bridgewater Associates, LP'}, 
        'citadel': {'cik': 1423053, 'filing_name': 'CITADEL ADVISORS LLC'},
        'arrowstreet': {'cik': 1164508, 'filing_name': 'ARROWSTREET CAPITAL, LIMITED PARTNERSHIP'},
        'man_group': {'cik': 1637460, 'filing_name': 'Man Group plc'},
        'vanguard_group': {'cik': 102909, 'filing_name': 'VANGUARD GROUP INC'},
        'fidelity': {'cik': 315066, 'filing_name': 'FMR LLC'},  # Fidelity's main investment entity
        'state_street': {'cik': 93751, 'filing_name': 'STATE STREET CORP'},
        'goldman_sachs': {'cik': 886982, 'filing_name': 'GOLDMAN SACHS GROUP INC'},
        'troweprice': {'cik': 1113169, 'filing_name': 'T Rowe Price Group, Inc.'},
        'wellington': {'cik': 1014739, 'filing_name': 'Wellington Management Group LLP'},
        'renaissance': {'cik': 1037389, 'filing_name': 'RENAISSANCE TECHNOLOGIES LLC'},
        'deshaw': {'cik': 1283808, 'filing_name': 'D E SHAW & CO INC'},
        'point72': {'cik': 1603466, 'filing_name': 'Point72 Asset Management, L.P.'},
        'baupost': {'cik': 1061768, 'filing_name': 'BAUPOST GROUP LLC/MA'},
        'aqr': {'cik': 1167557, 'filing_name': 'AQR CAPITAL MANAGEMENT LLC'},
        'two_sigma': {'cik': 1478735, 'filing_name': 'TWO SIGMA ADVISERS, LP'},  # Main Two Sigma entity
        'elliott': {'cik': 1791786, 'filing_name': 'Elliott Investment Management L.P.'},
        'pershing_square': {'cik': 1336528, 'filing_name': 'Pershing Square Capital Management, L.P.'},
        'icahn': {'cik': 921669, 'filing_name': 'ICAHN CARL C'},
        'capital_group': {'cik': 1063001, 'filing_name': 'CAPITAL RESEARCH & MANAGEMENT CO'},
        'invesco': {'cik': 914208, 'filing_name': 'INVESCO LTD.'},
        'tiger_global': {'cik': 1167483, 'filing_name': 'TIGER GLOBAL MANAGEMENT LLC'},
        'coatue': {'cik': 1135730, 'filing_name': 'COATUE MANAGEMENT LLC'},
    }

    # Verify mappings exist in filing data
    verified_mappings = {}
    for key, data in mappings.items():
        cik = data['cik']
        matches = filing_data[filing_data['cik'] == cik]
        if len(matches) > 0:
            verified_mappings[key] = {
                'cik': cik,
                'filing_name': matches.iloc[0]['company']
            }
            print(f"✅ {key}: CIK {cik} verified")
        else:
            print(f"❌ {key}: CIK {cik} not found in recent filings")

    return verified_mappings


def update_portfolio_manager_database(cik_mappings):
    """Update the portfolio manager database with CIKs."""

    db_path = Path(__file__).parent.parent / 'edgar' / 'reference' / 'data' / 'portfolio_managers.json'

    # Load current database
    with open(db_path, 'r', encoding='utf-8') as f:
        db = json.load(f)

    # Update companies with CIKs
    updated_count = 0
    for db_key, company_data in db['managers'].items():
        if db_key in cik_mappings:
            mapping = cik_mappings[db_key]

            # Add CIK
            company_data['cik'] = mapping['cik']

            # Update company name to match SEC filing name for consistency
            original_name = company_data['company_name']
            filing_name = mapping['filing_name']

            if original_name.lower() != filing_name.lower():
                print(f"Updating name: '{original_name}' -> '{filing_name}'")
                company_data['company_name'] = filing_name

            updated_count += 1
            print(f"Updated {db_key}: CIK {mapping['cik']}")

    # Update metadata
    db['metadata']['last_updated'] = '2025-01-09'
    db['metadata']['version'] = '2025.01.09'
    companies_with_ciks = sum(1 for data in db['managers'].values() if 'cik' in data)

    print(f"\nUpdated {updated_count} companies with CIKs")
    print(f"Total companies with CIKs: {companies_with_ciks} / {len(db['managers'])}")

    # Save updated database
    with open(db_path, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

    print(f"Database saved to {db_path}")


def main():
    """Main function to update portfolio manager database with CIKs."""
    print("=== Updating Portfolio Manager Database with CIKs ===\n")

    # Get CIKs from recent filings
    filing_data = get_recent_filing_ciks()

    # Create mappings
    cik_mappings = create_cik_mappings(filing_data)

    # Update database
    update_portfolio_manager_database(cik_mappings)

    print("\n=== Update Complete ===")


if __name__ == '__main__':
    main()
