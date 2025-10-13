#!/usr/bin/env python3
"""
Root cause investigation for GitHub Issue #446: Missing values in 20-F filings

This script investigates why BioNTech 20-F statements return empty data despite
having facts available. Focus on IFRS vs US-GAAP taxonomy differences.

Created: 2025-09-23
Related to Issue #446
"""

from edgar import Company, set_identity
import traceback
import json


def investigate_statement_data_source(filing, company_name, form_type):
    """Deep dive into how statement data is constructed."""
    print(f"\n{'='*60}")
    print(f"ROOT CAUSE INVESTIGATION - {form_type} - {company_name}")
    print(f"Filing: {filing.accession_number} from {filing.filing_date}")
    print(f"{'='*60}")

    try:
        xbrl = filing.xbrl()
        statements = xbrl.statements

        # Focus on income statement
        print(f"\n1. INCOME STATEMENT DEEP DIVE:")

        try:
            income_stmt = statements.income_statement()
            print(f"   Statement object type: {type(income_stmt)}")
            print(f"   Statement is None: {income_stmt is None}")

            if income_stmt is not None:
                # Check various attributes and methods
                print(f"   Available attributes: {[attr for attr in dir(income_stmt) if not attr.startswith('_')]}")

                # Try to get raw data
                if hasattr(income_stmt, 'get_raw_data'):
                    try:
                        raw_data = income_stmt.get_raw_data()
                        print(f"   Raw data type: {type(raw_data)}")
                        print(f"   Raw data length: {len(raw_data) if raw_data else 'None/Empty'}")
                        if raw_data and len(raw_data) > 0:
                            print(f"   Sample raw data: {raw_data[:2]}")
                    except Exception as e:
                        print(f"   Error getting raw data: {e}")

                # Check if it has a data method or property
                if hasattr(income_stmt, 'data'):
                    data = income_stmt.data
                    print(f"   Statement.data type: {type(data)}")
                    print(f"   Statement.data length: {len(data) if data else 'None/Empty'}")

                # Try the standard Statement string representation (which shows the table)
                try:
                    stmt_str = str(income_stmt)
                    lines = stmt_str.split('\n')
                    print(f"   String representation has {len(lines)} lines")
                    if len(lines) > 5:
                        print(f"   First few lines:")
                        for line in lines[:5]:
                            print(f"     {line}")
                    else:
                        print(f"   Full output: {stmt_str[:200]}...")
                except Exception as e:
                    print(f"   Error getting string representation: {e}")

            else:
                print(f"   Income statement returned None")

        except Exception as e:
            print(f"   Error getting income statement: {e}")
            traceback.print_exc()

        # Investigate the underlying facts for income statement concepts
        print(f"\n2. INCOME STATEMENT FACTS INVESTIGATION:")

        # Check for IFRS concepts commonly used in income statements
        ifrs_income_concepts = [
            'ifrs-full:Revenue',
            'ifrs-full:RevenueFromContractsWithCustomers',
            'ifrs-full:ProfitLoss',
            'ifrs-full:ProfitLossFromOperatingActivities',
            'ifrs-full:OperatingIncome',
            'ifrs-full:ProfitLossAttributableToOwnersOfParent',
            'ifrs-full:BasicEarningsLossPerShare',
            'ifrs-full:DilutedEarningsLossPerShare'
        ]

        us_gaap_income_concepts = [
            'us-gaap:Revenue',
            'us-gaap:Revenues',
            'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
            'us-gaap:NetIncomeLoss',
            'us-gaap:OperatingIncomeLoss',
            'us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest'
        ]

        concepts_to_check = ifrs_income_concepts if form_type == "20-F" else us_gaap_income_concepts

        print(f"   Checking {len(concepts_to_check)} standard {('IFRS' if form_type == '20-F' else 'US-GAAP')} income concepts:")

        found_concepts = {}
        for concept in concepts_to_check:
            try:
                facts_df = xbrl.facts.query().by_concept(concept).to_dataframe()
                if len(facts_df) > 0:
                    found_concepts[concept] = len(facts_df)
                    print(f"     ✓ {concept}: {len(facts_df)} facts")

                    # Show sample values for the first concept found
                    if len(found_concepts) == 1:
                        print(f"       Sample values:")
                        for _, row in facts_df.head(3).iterrows():
                            print(f"         Period: {row.get('period_key', 'Unknown')}, Value: {row.get('value', 'None')}")
                else:
                    print(f"     ✗ {concept}: No facts")
            except Exception as e:
                print(f"     ✗ {concept}: Error - {e}")

        # Search for income-related concepts more broadly
        print(f"\n3. BROAD INCOME CONCEPT SEARCH:")
        try:
            all_facts_df = xbrl.facts.query().to_dataframe()
            if len(all_facts_df) > 0:
                all_concepts = all_facts_df['concept'].unique()

                # Look for concepts that might be income-related
                income_keywords = ['revenue', 'income', 'profit', 'loss', 'earnings', 'sales']
                income_related = []

                for concept in all_concepts:
                    concept_lower = concept.lower()
                    if any(keyword in concept_lower for keyword in income_keywords):
                        income_related.append(concept)

                print(f"   Found {len(income_related)} income-related concepts:")
                for concept in income_related[:10]:  # Show first 10
                    fact_count = len(all_facts_df[all_facts_df['concept'] == concept])
                    print(f"     {concept}: {fact_count} facts")

                if len(income_related) > 10:
                    print(f"     ... and {len(income_related) - 10} more")

        except Exception as e:
            print(f"   Error in broad concept search: {e}")

        # Check period information
        print(f"\n4. PERIOD ANALYSIS:")
        try:
            if hasattr(xbrl, 'reporting_periods'):
                periods = xbrl.reporting_periods
                print(f"   Available periods: {len(periods)}")
                for period in periods[:5]:  # Show first 5
                    period_key = period.get('key', 'Unknown')
                    period_label = period.get('label', 'Unknown')
                    print(f"     {period_label}: {period_key}")

                    # Check how many facts are in this period
                    try:
                        period_facts = xbrl.facts.query().by_period_key(period_key).to_dataframe()
                        print(f"       Facts in period: {len(period_facts)}")
                    except Exception as e:
                        print(f"       Error getting period facts: {e}")

        except Exception as e:
            print(f"   Error analyzing periods: {e}")

        return {'found_concepts': found_concepts}

    except Exception as e:
        print(f"   Investigation failed: {e}")
        traceback.print_exc()
        return {'error': str(e)}


def investigate_statement_building_logic():
    """Investigate how statements are built from facts."""

    print(f"\n{'='*80}")
    print("STATEMENT BUILDING LOGIC INVESTIGATION")
    print(f"{'='*80}")

    # Test with BioNTech 20-F (IFRS)
    print(f"\n1. BioNTech 20-F (IFRS taxonomy)")
    try:
        bntx = Company('0001776985')
        filing_20f = bntx.get_filings(form="20-F", amendments=False).latest()
        result_ifrs = investigate_statement_data_source(filing_20f, "BioNTech SE", "20-F")
    except Exception as e:
        print(f"Error investigating BioNTech: {e}")
        result_ifrs = None

    # Test with Apple 10-K (US-GAAP) for comparison
    print(f"\n2. Apple 10-K (US-GAAP taxonomy)")
    try:
        aapl = Company('AAPL')
        filing_10k = aapl.get_filings(form="10-K", amendments=False).latest()
        result_usgaap = investigate_statement_data_source(filing_10k, "Apple Inc.", "10-K")
    except Exception as e:
        print(f"Error investigating Apple: {e}")
        result_usgaap = None

    # Summary
    print(f"\n{'='*80}")
    print("ROOT CAUSE ANALYSIS SUMMARY")
    print(f"{'='*80}")

    if result_ifrs and result_usgaap:
        ifrs_concepts = result_ifrs.get('found_concepts', {})
        usgaap_concepts = result_usgaap.get('found_concepts', {})

        print(f"IFRS (20-F) concepts found: {len(ifrs_concepts)}")
        for concept, count in ifrs_concepts.items():
            print(f"  {concept}: {count} facts")

        print(f"\nUS-GAAP (10-K) concepts found: {len(usgaap_concepts)}")
        for concept, count in usgaap_concepts.items():
            print(f"  {concept}: {count} facts")

        print(f"\nHYPOTHESIS:")
        if len(ifrs_concepts) == 0:
            print("- 20-F uses IFRS taxonomy but statement builder looks for US-GAAP concepts")
            print("- Need to update statement mapping logic to handle IFRS concepts")
        elif len(ifrs_concepts) > 0 and len(usgaap_concepts) > 0:
            print("- Both taxonomies have data, issue may be in statement rendering logic")
        else:
            print("- Issue may be more complex, need further investigation")


if __name__ == "__main__":

    print("Root Cause Investigation for Issue #446")
    print("="*80)

    investigate_statement_building_logic()