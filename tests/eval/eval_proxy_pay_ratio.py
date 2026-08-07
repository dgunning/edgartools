#!/usr/bin/env python3
"""
Eval harness for CEO pay ratio extractor.

Runs against 20 real DEF 14A filings and reports extraction success rates.
Scores: OK = all 3 fields extracted, PARTIAL = at least ratio, FAIL = nothing.

Usage:
    python tests/eval/eval_proxy_pay_ratio.py
    python tests/eval/eval_proxy_pay_ratio.py --company AAPL
    python tests/eval/eval_proxy_pay_ratio.py --verbose
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
    """Evaluate pay ratio extraction for a single company."""
    try:
        company = Company(ticker)
        filing = company.get_filings(form='DEF 14A')[0]
        proxy = ProxyStatement.from_filing(filing)
        result = proxy.ceo_pay_ratio

        if result is None:
            return {'ticker': ticker, 'name': name, 'status': 'FAIL', 'detail': 'no section'}

        filled = sum(1 for v in [result.ceo_compensation, result.median_employee_compensation, result.ratio] if v is not None)

        if filled == 3:
            status = 'OK'
        elif filled > 0:
            status = 'PARTIAL'
        else:
            status = 'FAIL'

        out = {
            'ticker': ticker,
            'name': name,
            'status': status,
            'ceo': result.ceo_compensation,
            'median': result.median_employee_compensation,
            'ratio': result.ratio,
        }

        if verbose and result.ceo_compensation and result.median_employee_compensation and result.ratio:
            computed = result.ceo_compensation / result.median_employee_compensation
            out['computed_ratio'] = round(computed)
            out['ratio_match'] = abs(computed - result.ratio) / result.ratio < 0.1

        return out
    except Exception as e:
        return {'ticker': ticker, 'name': name, 'status': 'ERR', 'detail': str(e)}


def main():
    parser = argparse.ArgumentParser(description='Eval CEO pay ratio extractor')
    parser.add_argument('--company', type=str, help='Single ticker to test')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args()

    if args.company:
        companies = [c for c in COMPANIES if c['ticker'] == args.company.upper()]
        if not companies:
            companies = [{'ticker': args.company.upper(), 'name': args.company, 'category': 'custom'}]
    else:
        companies = COMPANIES

    print(f'Evaluating CEO pay ratio extraction on {len(companies)} companies')
    print('=' * 80)

    results = []
    for c in companies:
        result = evaluate_company(c['ticker'], c['name'], verbose=args.verbose)
        results.append(result)

        status = result['status']
        ticker = result['ticker']
        name = result['name']
        ceo = f"${result['ceo']:,}" if result.get('ceo') else '-'
        med = f"${result['median']:,}" if result.get('median') else '-'
        rat = f"{result['ratio']}:1" if result.get('ratio') else '-'
        extra = ''
        if args.verbose and 'computed_ratio' in result:
            match = 'match' if result['ratio_match'] else 'MISMATCH'
            extra = f'  (computed {result["computed_ratio"]}:1 — {match})'
        print(f'{status:7s} {ticker:5s} {name:20s} CEO={ceo:>15s}  median={med:>10s}  ratio={rat}{extra}')

        time.sleep(0.15)

    # Scorecard
    print()
    print('=' * 80)
    ok = sum(1 for r in results if r['status'] == 'OK')
    partial = sum(1 for r in results if r['status'] == 'PARTIAL')
    fail = sum(1 for r in results if r['status'] in ('FAIL', 'ERR'))
    has_ratio = sum(1 for r in results if r.get('ratio'))
    total = len(results)
    print(f'Scorecard: {ok}/{total} OK ({ok / total * 100:.0f}%)')
    print(f'  OK:      {ok} (all 3 fields)')
    print(f'  PARTIAL: {partial} (at least 1 field)')
    print(f'  FAIL:    {fail}')
    print(f'  Ratio found: {has_ratio}/{total} ({has_ratio / total * 100:.0f}%)')

    return 0 if ok / total >= 0.60 else 1


if __name__ == '__main__':
    sys.exit(main())
