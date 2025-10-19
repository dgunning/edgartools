"""
Test if XBRL instance values are consistent across companies.

Research Question: Does SEC store expense values consistently positive
across companies, or do companies use different conventions?

If YES (consistent): Implement Option A (match SEC, stop using weights for display)
If NO (inconsistent): Implement Option C (hybrid with validation)
If EDGE CASES: Implement Option B (keep current static lists)
"""

import pandas as pd
import pytest
from edgar import Company
from edgar.xbrl.parsers.concepts import CONSISTENT_POSITIVE_CONCEPTS

# Test across 20-30 companies, multiple industries
TEST_COMPANIES = [
    # Tech
    'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'NVDA', 'TSLA',
    # Finance
    'JPM', 'BAC', 'GS', 'MS',
    # Consumer
    'WMT', 'HD', 'NKE', 'SBUX',
    # Industrial
    'BA', 'CAT', 'GE', 'MMM',
    # Healthcare
    'JNJ', 'PFE', 'UNH', 'CVS',
    # Other
    'XOM', 'CVX', 'PG', 'KO'
]

# Essential expense concepts from static lists
EXPENSE_CONCEPTS = [
    'ResearchAndDevelopmentExpense',
    'SellingGeneralAndAdministrativeExpense',
    'CostOfRevenue',
    'IncomeTaxExpenseBenefit',
    'PaymentsOfDividends',
    'PaymentsForRepurchaseOfCommonStock'
]


def test_instance_values_consistency():
    """Test if instance values are positive across companies."""
    results = []

    print("\n" + "="*80)
    print("XBRL INSTANCE VALUE CONSISTENCY TEST")
    print("="*80)
    print(f"Testing {len(TEST_COMPANIES)} companies across {len(EXPENSE_CONCEPTS)} expense concepts")
    print()

    for ticker in TEST_COMPANIES:
        try:
            print(f"Processing {ticker}...", end=" ")
            company = Company(ticker)
            filing = company.get_filings(form="10-K").latest(1)
            if not filing:
                print("❌ No 10-K filing found")
                continue

            xbrl = filing.xbrl()

            for concept in EXPENSE_CONCEPTS:
                # Get facts for this concept
                facts = xbrl.facts.query().by_concept(concept).to_dataframe()

                if facts.empty:
                    continue

                for _, fact in facts.iterrows():
                    # Check raw instance value BEFORE any processing
                    instance_value = fact['numeric_value']

                    results.append({
                        'company': ticker,
                        'concept': concept,
                        'period_end': fact['period_end'],
                        'instance_value': instance_value,
                        'is_positive': instance_value > 0,
                        'filing_accession': filing.accession_number
                    })

            print("✅")

        except Exception as e:
            print(f"❌ Error: {e}")
            continue

    df = pd.DataFrame(results)

    # Analyze consistency
    print("\n" + "="*80)
    print("INSTANCE VALUE CONSISTENCY ANALYSIS")
    print("="*80)

    overall_stats = {
        'total_facts': 0,
        'positive_facts': 0,
        'negative_facts': 0,
        'concepts_fully_consistent': 0,
        'concepts_mostly_consistent': 0,
        'concepts_inconsistent': 0
    }

    for concept in EXPENSE_CONCEPTS:
        concept_data = df[df['concept'] == concept]
        if concept_data.empty:
            continue

        positive_count = (concept_data['is_positive']).sum()
        negative_count = len(concept_data) - positive_count
        consistency = (positive_count / len(concept_data)) * 100

        overall_stats['total_facts'] += len(concept_data)
        overall_stats['positive_facts'] += positive_count
        overall_stats['negative_facts'] += negative_count

        print(f"\n{concept}:")
        print(f"  Total facts: {len(concept_data)}")
        print(f"  Positive: {positive_count} ({consistency:.1f}%)")
        print(f"  Negative: {negative_count}")

        if negative_count > 0:
            print(f"  ⚠️  NEGATIVE INSTANCES FOUND:")
            negatives = concept_data[~concept_data['is_positive']]
            for _, row in negatives.iterrows():
                print(f"    - {row['company']}: {row['instance_value']:,.0f} (period: {row['period_end']})")

        # Store for decision making
        if consistency == 100.0:
            print(f"  ✅ FULLY CONSISTENT - SEC data already normalized")
            overall_stats['concepts_fully_consistent'] += 1
        elif consistency >= 95.0:
            print(f"  ⚠️  MOSTLY CONSISTENT - Few edge cases exist")
            overall_stats['concepts_mostly_consistent'] += 1
        else:
            print(f"  ❌ INCONSISTENT - Companies use different conventions")
            overall_stats['concepts_inconsistent'] += 1

    # Overall summary
    print("\n" + "="*80)
    print("OVERALL SUMMARY")
    print("="*80)
    print(f"Total facts analyzed: {overall_stats['total_facts']}")
    print(f"Positive facts: {overall_stats['positive_facts']} ({overall_stats['positive_facts']/overall_stats['total_facts']*100:.1f}%)")
    print(f"Negative facts: {overall_stats['negative_facts']} ({overall_stats['negative_facts']/overall_stats['total_facts']*100:.1f}%)")
    print()
    print(f"Concepts fully consistent (100%): {overall_stats['concepts_fully_consistent']}")
    print(f"Concepts mostly consistent (95-99%): {overall_stats['concepts_mostly_consistent']}")
    print(f"Concepts inconsistent (<95%): {overall_stats['concepts_inconsistent']}")
    print()

    # Decision recommendation
    overall_consistency = (overall_stats['positive_facts'] / overall_stats['total_facts']) * 100

    print("DECISION RECOMMENDATION:")
    print("="*80)
    if overall_consistency == 100.0:
        print("✅ Option A: Match SEC Exactly")
        print("   - 100% of instance values are positive")
        print("   - Source data is fully consistent")
        print("   - Stop applying calculation weights for display")
        print("   - Simplify to match SEC CompanyFacts API approach")
    elif overall_consistency >= 95.0:
        print("⚠️  Option C: Hybrid with Validation")
        print(f"   - {overall_consistency:.1f}% of instance values are positive")
        print("   - Mostly consistent with few edge cases")
        print("   - Use raw values + validation for edge cases")
        print("   - Provide defensive mode if needed")
    else:
        print("❌ Option B: Keep Static Lists")
        print(f"   - {overall_consistency:.1f}% of instance values are positive")
        print("   - Source data varies significantly")
        print("   - Maintain static list normalization")
        print("   - Add balance/weight columns for transparency")

    print("="*80)

    return df


def compare_with_sec_api(ticker, concept):
    """Compare EdgarTools values with SEC CompanyFacts API."""
    import requests

    print(f"\nComparing {ticker} {concept} with SEC CompanyFacts API...")

    # Get from EdgarTools
    company = Company(ticker)
    filing = company.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()
    edgar_facts = xbrl.facts.query().by_concept(concept).to_dataframe()

    if edgar_facts.empty:
        print(f"  No facts found for {concept}")
        return None

    # Get from SEC API
    cik = company.cik
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{concept}.json"
    response = requests.get(url, headers={'User-Agent': 'EdgarTools Test'})

    if response.status_code != 200:
        print(f"  ⚠️  SEC API unavailable (status {response.status_code})")
        return None

    sec_data = response.json()

    # Compare values
    matches = []
    for _, edgar_row in edgar_facts.iterrows():
        period_end = edgar_row['period_end']
        edgar_value = edgar_row['numeric_value']

        # Find matching SEC value
        sec_facts = [
            f for f in sec_data.get('units', {}).get('USD', [])
            if f.get('end') == period_end and f.get('form') == '10-K'
        ]

        if sec_facts:
            sec_value = sec_facts[0]['val']
            match = edgar_value == sec_value
            matches.append({
                'period': period_end,
                'edgar': edgar_value,
                'sec': sec_value,
                'match': match
            })

    if matches:
        df = pd.DataFrame(matches)
        print(f"  Compared {len(matches)} periods:")
        print(f"    Exact matches: {df['match'].sum()}")
        print(f"    Mismatches: {(~df['match']).sum()}")

        if (~df['match']).any():
            print("  ⚠️  Mismatches found:")
            mismatches = df[~df['match']]
            for _, row in mismatches.iterrows():
                print(f"    {row['period']}: EdgarTools={row['edgar']:,.0f}, SEC={row['sec']:,.0f}")

        return df

    return None


if __name__ == "__main__":
    # Run consistency test
    df = test_instance_values_consistency()

    # Optional: Compare specific companies with SEC API
    print("\n" + "="*80)
    print("SEC API ALIGNMENT VERIFICATION")
    print("="*80)

    test_cases = [
        ('AAPL', 'ResearchAndDevelopmentExpense'),
        ('MSFT', 'ResearchAndDevelopmentExpense'),
        ('AAPL', 'PaymentsOfDividends')
    ]

    for ticker, concept in test_cases:
        try:
            compare_with_sec_api(ticker, concept)
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
