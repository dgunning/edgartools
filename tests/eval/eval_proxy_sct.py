#!/usr/bin/env python3
"""
Eval harness for Summary Compensation Table extractor.

Runs against 20 real DEF 14A filings and reports extraction success rates.
Scores: OK = 3+ executives with total comp, PARTIAL = some data, FAIL = empty.

Usage:
    python tests/eval/eval_proxy_sct.py
    python tests/eval/eval_proxy_sct.py --company AAPL
    python tests/eval/eval_proxy_sct.py --verbose
"""

import argparse
import sys
import time

from edgar import Company
from edgar.proxy import ProxyStatement


COMPANIES = [
    # Large-cap (diverse filing agents)
    {'ticker': 'AAPL', 'name': 'Apple Inc.', 'category': 'large-cap'},
    {'ticker': 'MSFT', 'name': 'Microsoft Corp.', 'category': 'large-cap'},
    {'ticker': 'JPM', 'name': 'JPMorgan Chase', 'category': 'large-cap'},
    {'ticker': 'AMZN', 'name': 'Amazon.com', 'category': 'large-cap'},
    {'ticker': 'GOOGL', 'name': 'Alphabet Inc.', 'category': 'large-cap'},
    {'ticker': 'META', 'name': 'Meta Platforms', 'category': 'large-cap'},
    {'ticker': 'JNJ', 'name': 'Johnson & Johnson', 'category': 'large-cap'},
    {'ticker': 'XOM', 'name': 'Exxon Mobil', 'category': 'large-cap'},
    {'ticker': 'PG', 'name': 'Procter & Gamble', 'category': 'large-cap'},
    {'ticker': 'KO', 'name': 'Coca-Cola Co.', 'category': 'large-cap'},
    # Mid-cap
    {'ticker': 'ETSY', 'name': 'Etsy Inc.', 'category': 'mid-cap'},
    {'ticker': 'CBRL', 'name': 'Cracker Barrel', 'category': 'mid-cap'},
    {'ticker': 'CAKE', 'name': 'Cheesecake Factory', 'category': 'mid-cap'},
    {'ticker': 'FIVE', 'name': 'Five Below', 'category': 'mid-cap'},
    {'ticker': 'ROKU', 'name': 'Roku Inc.', 'category': 'mid-cap'},
    # Small-cap
    {'ticker': 'DIN', 'name': 'Dine Brands', 'category': 'small-cap'},
    {'ticker': 'PBPB', 'name': 'Potbelly Corp.', 'category': 'small-cap'},
    {'ticker': 'BJRI', 'name': "BJ's Restaurants", 'category': 'small-cap'},
    {'ticker': 'SHAK', 'name': 'Shake Shack', 'category': 'small-cap'},
    {'ticker': 'CATO', 'name': 'Cato Corp.', 'category': 'small-cap'},
]


def evaluate_company(ticker: str, name: str, verbose: bool = False):
    """Evaluate SCT extraction for a single company."""
    try:
        company = Company(ticker)
        filing = company.get_filings(form='DEF 14A')[0]
        proxy = ProxyStatement.from_filing(filing)
        df = proxy.summary_compensation_table

        if df.empty:
            return {'ticker': ticker, 'name': name, 'status': 'FAIL', 'detail': 'empty'}

        execs = df['name'].nunique()
        years = df['year'].nunique()
        has_total = df['total'].notna().any()

        if execs >= 3 and years >= 1 and has_total:
            status = 'OK'
        elif execs >= 1:
            status = 'PARTIAL'
        else:
            status = 'FAIL'

        result = {
            'ticker': ticker, 'name': name, 'status': status,
            'execs': execs, 'years': years, 'rows': len(df),
            'has_total': has_total,
        }

        if verbose:
            latest = df['year'].max()
            for _, row in df[df['year'] == latest].iterrows():
                total = f"${row['total']:,.0f}" if row.get('total') else '-'
                print(f"       {row['name']:30s} {row.get('title',''):5s} {total:>15s}")

        return result
    except Exception as e:
        return {'ticker': ticker, 'name': name, 'status': 'ERR', 'detail': str(e)}


def main():
    parser = argparse.ArgumentParser(description='Eval Summary Compensation Table extractor')
    parser.add_argument('--company', type=str, help='Single ticker to test')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args()

    if args.company:
        companies = [c for c in COMPANIES if c['ticker'] == args.company.upper()]
        if not companies:
            companies = [{'ticker': args.company.upper(), 'name': args.company, 'category': 'custom'}]
    else:
        companies = COMPANIES

    print(f'Evaluating Summary Compensation Table extraction on {len(companies)} companies')
    print('=' * 80)

    results = []
    for c in companies:
        result = evaluate_company(c['ticker'], c['name'], verbose=args.verbose)
        results.append(result)

        status = result['status']
        ticker = result['ticker']
        name = result['name']
        if result.get('execs'):
            execs = result['execs']
            years = result['years']
            rows = result['rows']
            print(f'{status:7s} {ticker:5s} {name:20s} {execs} execs, {years} yrs, {rows:2d} rows')
        else:
            detail = result.get('detail', '')
            print(f'{status:7s} {ticker:5s} {name:20s} {detail}')

        time.sleep(0.2)

    # Scorecard
    print()
    print('=' * 80)
    ok = sum(1 for r in results if r['status'] == 'OK')
    partial = sum(1 for r in results if r['status'] == 'PARTIAL')
    fail = sum(1 for r in results if r['status'] in ('FAIL', 'ERR'))
    total = len(results)
    print(f'Scorecard: {ok}/{total} OK ({ok / total * 100:.0f}%)')
    print(f'  OK:      {ok} (3+ execs with total)')
    print(f'  PARTIAL: {partial}')
    print(f'  FAIL:    {fail}')

    return 0 if ok / total >= 0.50 else 1


if __name__ == '__main__':
    sys.exit(main())
