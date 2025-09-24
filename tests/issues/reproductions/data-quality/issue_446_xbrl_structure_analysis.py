#!/usr/bin/env python3
"""
XBRL structure analysis for 20-F vs 10-K forms

This script compares the XBRL structure and content between 20-F and 10-K filings
to identify why 20-F statements are showing empty values.

Created: 2025-09-23
Related to Issue #446
"""

from edgar import Company, set_identity, get_filings
import traceback
import json


def analyze_xbrl_structure(filing, company_name, form_type):
    """Analyze the XBRL structure of a filing."""
    print(f"\n{'='*60}")
    print(f"ANALYZING {form_type} XBRL STRUCTURE - {company_name}")
    print(f"Filing: {filing.accession_number} from {filing.filing_date}")
    print(f"{'='*60}")

    try:
        xbrl = filing.xbrl()

        # Basic XBRL info
        print(f"\n1. BASIC XBRL INFO:")
        print(f"   Parser class: {type(xbrl).__name__}")
        print(f"   Has statements: {hasattr(xbrl, 'statements')}")

        if hasattr(xbrl, 'facts') and xbrl.facts:
            print(f"   Total facts: {len(xbrl.facts)}")
            # Show sample facts using FactsView methods
            try:
                sample_df = xbrl.facts.query().limit(10).to_dataframe()
                if len(sample_df) > 0:
                    sample_concepts = sample_df['concept'].unique()[:10]
                    print(f"   Sample concepts: {list(sample_concepts)}")
                else:
                    print(f"   No facts in dataframe")
            except Exception as e:
                print(f"   Error getting sample facts: {e}")
        else:
            print(f"   No facts found or facts is empty")

        if hasattr(xbrl, 'statements'):
            statements = xbrl.statements
            print(f"\n2. STATEMENTS OBJECT:")
            print(f"   Statements class: {type(statements).__name__}")
            print(f"   Available methods: {[m for m in dir(statements) if not m.startswith('_')]}")

            # Test each statement type
            statement_types = ['balance_sheet', 'income_statement', 'cashflow_statement']
            for stmt_type in statement_types:
                print(f"\n3. {stmt_type.upper()} ANALYSIS:")
                try:
                    stmt_method = getattr(statements, stmt_type)
                    stmt = stmt_method()

                    print(f"   Statement object: {type(stmt)}")
                    print(f"   Statement is None: {stmt is None}")

                    if stmt is not None:
                        print(f"   Has data attribute: {hasattr(stmt, 'data')}")
                        if hasattr(stmt, 'data'):
                            print(f"   Data type: {type(stmt.data)}")
                            print(f"   Data length: {len(stmt.data) if stmt.data else 'None/Empty'}")

                            # Show sample data if available
                            if stmt.data and len(stmt.data) > 0:
                                print(f"   Sample first row: {stmt.data[0] if len(stmt.data) > 0 else 'None'}")
                            else:
                                print(f"   No data rows found")

                        # Check for other attributes
                        attrs = [attr for attr in dir(stmt) if not attr.startswith('_') and attr != 'data']
                        if attrs:
                            print(f"   Other attributes: {attrs[:5]}...")  # Show first 5
                    else:
                        print(f"   Statement returned None")

                except Exception as e:
                    print(f"   Error getting {stmt_type}: {e}")
                    traceback.print_exc()

        # Look at raw XBRL structure
        print(f"\n4. RAW XBRL INVESTIGATION:")
        try:
            # Try to access raw facts differently
            if hasattr(xbrl, '_facts'):
                print(f"   Has _facts: {len(xbrl._facts) if xbrl._facts else 'None'}")

            if hasattr(xbrl, 'concept_map'):
                print(f"   Has concept_map: {len(xbrl.concept_map) if xbrl.concept_map else 'None'}")

            if hasattr(xbrl, 'taxonomy'):
                print(f"   Has taxonomy: {xbrl.taxonomy}")

            # Check for financial statement elements
            if hasattr(xbrl, 'facts') and xbrl.facts:
                financial_concepts = [
                    'Revenue', 'Revenues', 'SalesRevenueNet', 'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'Assets', 'AssetsCurrent', 'TotalAssets',
                    'CashAndCashEquivalents', 'CashAndCashEquivalentsAtCarryingValue'
                ]

                found_concepts = []
                for concept in financial_concepts:
                    try:
                        facts_df = xbrl.facts.query().by_concept(concept).to_dataframe()
                        if len(facts_df) > 0:
                            found_concepts.append(concept)
                    except Exception:
                        pass

                print(f"   Found standard financial concepts: {found_concepts}")

                # Look for any revenue-like concepts
                try:
                    all_facts_df = xbrl.facts.query().to_dataframe()
                    if len(all_facts_df) > 0:
                        all_concepts = all_facts_df['concept'].unique()
                        revenue_like = [c for c in all_concepts if 'revenue' in c.lower() or 'sales' in c.lower()]
                        print(f"   Revenue-like concepts: {revenue_like[:5]}")
                    else:
                        print(f"   No concepts found in facts dataframe")
                except Exception as e:
                    print(f"   Error searching for revenue concepts: {e}")

        except Exception as e:
            print(f"   Error in raw XBRL investigation: {e}")

        return {
            'has_statements': hasattr(xbrl, 'statements'),
            'facts_count': len(xbrl.facts) if hasattr(xbrl, 'facts') and xbrl.facts else 0,
            'statement_results': {}
        }

    except Exception as e:
        print(f"   XBRL analysis failed: {e}")
        traceback.print_exc()
        return {'error': str(e)}


def compare_20f_vs_10k():
    """Compare 20-F and 10-K XBRL structures."""

    print("COMPARING 20-F vs 10-K XBRL STRUCTURES")
    print("="*80)

    # Test with BioNTech (confirmed 20-F filer)
    bntx_cik = '0001776985'

    try:
        company = Company(bntx_cik)
        print(f"Analyzing company: {company.name} (CIK: {bntx_cik})")

        # Get latest 20-F
        filings_20f = company.get_filings(form="20-F", amendments=False)
        if filings_20f:
            latest_20f = filings_20f.latest()
            print(f"Found 20-F filing: {latest_20f.accession_number}")

            # Analyze 20-F structure
            result_20f = analyze_xbrl_structure(latest_20f, company.name, "20-F")
        else:
            print("No 20-F filings found")
            result_20f = None

        # Compare with a known good 10-K company for reference
        print(f"\n{'='*80}")
        print("REFERENCE: Analyzing 10-K from a US company (AAPL)")
        print(f"{'='*80}")

        try:
            aapl = Company('AAPL')
            filings_10k = aapl.get_filings(form="10-K", amendments=False)
            if filings_10k:
                latest_10k = filings_10k.latest()
                print(f"Found 10-K filing: {latest_10k.accession_number}")

                # Analyze 10-K structure for comparison
                result_10k = analyze_xbrl_structure(latest_10k, aapl.name, "10-K")
            else:
                print("No 10-K filings found for AAPL")
                result_10k = None

        except Exception as e:
            print(f"Error analyzing AAPL 10-K: {e}")
            result_10k = None

        # Summary comparison
        print(f"\n{'='*80}")
        print("COMPARISON SUMMARY")
        print(f"{'='*80}")

        if result_20f and result_10k:
            print(f"20-F (BioNTech):")
            print(f"  Has statements: {result_20f.get('has_statements', False)}")
            print(f"  Facts count: {result_20f.get('facts_count', 0)}")

            print(f"\n10-K (Apple):")
            print(f"  Has statements: {result_10k.get('has_statements', False)}")
            print(f"  Facts count: {result_10k.get('facts_count', 0)}")

            print(f"\nKey Differences Identified:")
            if result_20f.get('facts_count', 0) < result_10k.get('facts_count', 0):
                print(f"  - 20-F has significantly fewer facts ({result_20f.get('facts_count', 0)} vs {result_10k.get('facts_count', 0)})")

        return {'20f': result_20f, '10k': result_10k}

    except Exception as e:
        print(f"Comparison failed: {e}")
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Set proper identity for SEC API
    set_identity("Edgar Research Team research@edgartools.ai")

    print("XBRL Structure Analysis for Issue #446")
    print("="*80)

    results = compare_20f_vs_10k()

    if results:
        print(f"\n{'='*80}")
        print("ANALYSIS COMPLETE - Key findings to investigate:")
        print("1. Check if 20-F uses different taxonomy or concept names")
        print("2. Verify if statement building logic handles international concepts")
        print("3. Look for differences in fact structure or units")
        print("4. Check if XBRL parser handles 20-F form differently")
        print(f"{'='*80}")