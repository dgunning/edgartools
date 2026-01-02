#!/usr/bin/env python3
"""Quick real company validation test - minimal companies per sector."""

from edgar import Company
from apply_mappings import extract_income_statement, detect_sector, validate_extraction

# Minimal test set - 1-2 companies per sector
TEST_COMPANIES = [
    ('AAPL', None, 'Tech'),
    ('BAC', 'banking', 'Banking'),
    ('PGR', 'insurance', 'Insurance'),
    ('NEE', 'utilities', 'Utilities'),
]

def test_company(ticker, sector, sector_name):
    """Test extraction for one company."""
    print(f"\n{'='*60}")
    print(f"Testing: {ticker} ({sector_name})")
    print(f"{'='*60}")

    try:
        # Get company and latest 10-K
        company = Company(ticker)
        filings_list = company.get_filings(form='10-K', amendments=False)

        if not filings_list or len(filings_list) == 0:
            print(f"  ✗ No 10-K filings found")
            return None

        # Get the first filing from the list
        filing = None
        for f in filings_list:
            filing = f
            break

        if not filing:
            print(f"  ✗ Could not access filing")
            return None

        print(f"  Filing: {filing.form} filed {filing.filing_date}")

        # Get XBRL
        xbrl = filing.xbrl()
        if not xbrl:
            print(f"  ✗ No XBRL data")
            return None

        print(f"  ✓ XBRL loaded")

        # CRITICAL: Use current_period.income_statement with dimensional filtering
        # This gets consolidated figures without segment breakdowns
        try:
            # Use EdgarTools API with dimensional filtering
            if hasattr(xbrl, 'current_period'):
                stmt_df = xbrl.current_period.income_statement(
                    as_statement=False,
                    include_dimensions=False
                )

                if stmt_df is not None and len(stmt_df) > 0:
                    print(f"  ✓ Using current_period.income_statement (dimensions filtered)")

                    # Get the period column (usually YYYY-MM-DD format)
                    # The dataframe should have 'concept' and a date column
                    date_cols = [c for c in stmt_df.columns if isinstance(c, str) and '-' in c and len(c) >= 10]

                    if not date_cols and 'value' in stmt_df.columns:
                        # Fallback: use 'value' column if no date columns
                        period_col = 'value'
                    elif date_cols:
                        period_col = date_cols[0]  # Most recent
                    else:
                        raise Exception("No value column found")

                    # Extract facts from this period
                    facts = {}
                    from apply_mappings import normalize_concept_name

                    for _, row in stmt_df.iterrows():
                        if 'concept' in row and period_col in row:
                            concept = row['concept']
                            value = row[period_col]
                            if value is not None and concept:
                                normalized = normalize_concept_name(concept)
                                facts[normalized] = value

                    print(f"  ✓ Extracted {len(facts)} facts from {period_col}")
                else:
                    raise Exception("No statement dataframe returned")
            else:
                raise Exception("No current_period API available")

        except Exception as e:
            # Fallback to filtered XBRL query (filter dimensional segments)
            print(f"  ⚠️  Fallback to XBRL query with dimension filter: {e}")

            try:
                # Use query API with dimensional filtering
                q = xbrl.facts.query()

                # Filter by statement type
                if hasattr(q, 'by_statement_type'):
                    q = q.by_statement_type('IncomeStatement')

                # Filter by period type (duration for income statement)
                if hasattr(q, 'by_period_type'):
                    q = q.by_period_type('duration')

                # CRITICAL: Filter out dimensional segments (consolidated only)
                if hasattr(q, 'by_dimension'):
                    q = q.by_dimension(None)  # None = no dimensions

                # Convert to dataframe
                facts_df = q.to_dataframe()

                if facts_df is None or len(facts_df) == 0:
                    print(f"  ✗ No facts extracted from filtered query")
                    return None

                print(f"  ✓ Extracted {len(facts_df)} facts (dimensions filtered)")

                # Get most recent period
                if 'period_end' in facts_df.columns:
                    facts_df = facts_df.copy()
                    facts_df['period_end'] = pd.to_datetime(facts_df['period_end'], errors='coerce')
                    latest_period = facts_df['period_end'].max()
                    facts_df = facts_df[facts_df['period_end'] == latest_period]
                    print(f"  ✓ Using period: {latest_period}")

                # Extract facts
                from apply_mappings import normalize_concept_name
                import pandas as pd

                facts = {}
                for _, row in facts_df.iterrows():
                    concept = row['concept']
                    value = row['value']
                    if value is not None and not pd.isna(value):
                        normalized_concept = normalize_concept_name(concept)
                        # Take largest absolute value if duplicate concepts
                        try:
                            val = float(value)
                            if normalized_concept not in facts or abs(val) > abs(facts[normalized_concept]):
                                facts[normalized_concept] = val
                        except (ValueError, TypeError):
                            pass

            except Exception as e2:
                print(f"  ✗ XBRL query fallback also failed: {e2}")
                return None

        # Apply mappings
        result = extract_income_statement(facts, sector=sector)
        validation = validate_extraction(result)

        print(f"\n  Results:")
        print(f"    Extracted: {result['fields_extracted']}/{result['fields_total']}")
        print(f"    Valid: {'✓' if validation['valid'] else '✗'}")
        print(f"    Rate: {validation['extraction_rate']:.1%}")

        # Show key fields
        for field in ['revenue', 'netIncome', 'operatingIncome']:
            if field in result['data']:
                value = result['data'][field]
                # Handle both numeric and string values
                try:
                    print(f"    {field}: {float(value):,.0f}")
                except (ValueError, TypeError):
                    print(f"    {field}: {value}")

        return {
            'ticker': ticker,
            'valid': validation['valid'],
            'rate': validation['extraction_rate'],
            'extracted': result['fields_extracted']
        }

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None

def main():
    print("\n" + "="*60)
    print("QUICK REAL COMPANY VALIDATION")
    print("="*60)

    results = []
    for ticker, sector, sector_name in TEST_COMPANIES:
        result = test_company(ticker, sector, sector_name)
        if result:
            results.append(result)

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    if results:
        valid_count = sum(1 for r in results if r['valid'])
        avg_rate = sum(r['rate'] for r in results) / len(results)

        print(f"\nTested: {len(results)} companies")
        print(f"Valid: {valid_count}/{len(results)}")
        print(f"Avg Rate: {avg_rate:.1%}")

        if valid_count == len(results) and avg_rate > 0.30:
            print("\n✅ VALIDATION PASSED")
        else:
            print("\n⚠️  Some tests below threshold")
    else:
        print("\n✗ No results collected")

if __name__ == '__main__':
    main()
