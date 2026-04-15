#!/usr/bin/env python3
"""
Eval harness for director compensation table extractor.

Usage:
    python tests/eval/eval_proxy_director_comp.py
    python tests/eval/eval_proxy_director_comp.py --company AAPL
    python tests/eval/eval_proxy_director_comp.py --verbose
"""

import argparse
import sys
import time

from edgar import Company
from edgar.proxy import ProxyStatement


COMPANIES = [
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
    {'ticker': 'ETSY', 'name': 'Etsy Inc.', 'category': 'mid-cap'},
    {'ticker': 'CBRL', 'name': 'Cracker Barrel', 'category': 'mid-cap'},
    {'ticker': 'CAKE', 'name': 'Cheesecake Factory', 'category': 'mid-cap'},
    {'ticker': 'FIVE', 'name': 'Five Below', 'category': 'mid-cap'},
    {'ticker': 'ROKU', 'name': 'Roku Inc.', 'category': 'mid-cap'},
    {'ticker': 'DIN', 'name': 'Dine Brands', 'category': 'small-cap'},
    {'ticker': 'PBPB', 'name': 'Potbelly Corp.', 'category': 'small-cap'},
    {'ticker': 'BJRI', 'name': "BJ's Restaurants", 'category': 'small-cap'},
    {'ticker': 'SHAK', 'name': 'Shake Shack', 'category': 'small-cap'},
    {'ticker': 'CATO', 'name': 'Cato Corp.', 'category': 'small-cap'},
]


def evaluate_company(ticker: str, name: str, verbose: bool = False):
    try:
        company = Company(ticker)
        filing = company.get_filings(form='DEF 14A')[0]
        proxy = ProxyStatement.from_filing(filing)
        df = proxy.director_compensation_table

        if df.empty:
            return {'ticker': ticker, 'name': name, 'status': 'FAIL', 'detail': 'empty'}

        directors = len(df)
        has_fees = df['fees_earned'].notna().any()
        has_total = df['total'].notna().any()

        if directors >= 3 and (has_fees or has_total):
            status = 'OK'
        elif directors >= 1:
            status = 'PARTIAL'
        else:
            status = 'FAIL'

        result = {
            'ticker': ticker, 'name': name, 'status': status,
            'directors': directors, 'has_fees': has_fees, 'has_total': has_total,
        }

        if verbose:
            for _, row in df.iterrows():
                total = f"${row['total']:,.0f}" if row.get('total') else '-'
                fees = f"${row['fees_earned']:,.0f}" if row.get('fees_earned') else '-'
                print(f"       {row['name']:30s} fees={fees:>10s}  total={total:>10s}")

        return result
    except Exception as e:
        return {'ticker': ticker, 'name': name, 'status': 'ERR', 'detail': str(e)}


def main():
    parser = argparse.ArgumentParser(description='Eval director compensation extractor')
    parser.add_argument('--company', type=str)
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args()

    if args.company:
        companies = [c for c in COMPANIES if c['ticker'] == args.company.upper()]
        if not companies:
            companies = [{'ticker': args.company.upper(), 'name': args.company, 'category': 'custom'}]
    else:
        companies = COMPANIES

    print(f'Evaluating director compensation extraction on {len(companies)} companies')
    print('=' * 80)

    results = []
    for c in companies:
        result = evaluate_company(c['ticker'], c['name'], verbose=args.verbose)
        results.append(result)

        status = result['status']
        ticker = result['ticker']
        name = result['name']
        if result.get('directors'):
            print(f'{status:7s} {ticker:5s} {name:20s} {result["directors"]:2d} directors')
        else:
            print(f'{status:7s} {ticker:5s} {name:20s} {result.get("detail", "")}')

        time.sleep(0.2)

    print()
    print('=' * 80)
    ok = sum(1 for r in results if r['status'] == 'OK')
    partial = sum(1 for r in results if r['status'] == 'PARTIAL')
    fail = sum(1 for r in results if r['status'] in ('FAIL', 'ERR'))
    total = len(results)
    print(f'Scorecard: {ok}/{total} OK ({ok / total * 100:.0f}%)')
    print(f'  OK:      {ok} (3+ directors with data)')
    print(f'  PARTIAL: {partial}')
    print(f'  FAIL:    {fail}')

    return 0 if ok / total >= 0.35 else 1


if __name__ == '__main__':
    sys.exit(main())
