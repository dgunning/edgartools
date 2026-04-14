#!/usr/bin/env python3
"""
Eval harness for proxy voting proposals extractor.

Runs against 20 real DEF 14A filings (large-cap, mid-cap, small-cap)
and reports extraction success rates. This is the primary quality gate
for the proposals extractor.

Usage:
    python tests/eval/eval_proxy_proposals.py
    python tests/eval/eval_proxy_proposals.py --company AAPL
    python tests/eval/eval_proxy_proposals.py --verbose

Based on the edgartools-workers eval harness (scripts/eval-proxy-extractors.ts).
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
    """Evaluate proposals extraction for a single company."""
    try:
        company = Company(ticker)
        filing = company.get_filings(form='DEF 14A')[0]
        proxy = ProxyStatement.from_filing(filing)
        proposals = proxy.voting_proposals
        with_rec = sum(1 for p in proposals if p.board_recommendation)

        if len(proposals) >= 2:
            status = 'OK'
        elif proposals:
            status = 'LOW'
        else:
            status = 'FAIL'

        if verbose:
            for p in proposals:
                rec = p.board_recommendation or '-'
                print(f'       {p.number}. {p.description[:55]:55s} [{p.proposal_type:20s}] {rec}')

        return {
            'ticker': ticker,
            'name': name,
            'status': status,
            'count': len(proposals),
            'with_rec': with_rec,
            'filing_date': str(filing.filing_date),
        }
    except Exception as e:
        return {
            'ticker': ticker,
            'name': name,
            'status': 'ERR',
            'count': 0,
            'with_rec': 0,
            'error': str(e),
        }


def main():
    parser = argparse.ArgumentParser(description='Eval proxy proposals extractor')
    parser.add_argument('--company', type=str, help='Single ticker to test')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show proposal details')
    args = parser.parse_args()

    if args.company:
        companies = [c for c in COMPANIES if c['ticker'] == args.company.upper()]
        if not companies:
            companies = [{'ticker': args.company.upper(), 'name': args.company, 'category': 'custom'}]
    else:
        companies = COMPANIES

    print(f'Evaluating voting proposals extraction on {len(companies)} companies')
    print('=' * 80)

    results = []
    for c in companies:
        result = evaluate_company(c['ticker'], c['name'], verbose=args.verbose)
        results.append(result)

        status = result['status']
        ticker = result['ticker']
        name = result['name']
        count = result['count']
        with_rec = result['with_rec']
        print(f'{status:4s} {ticker:5s} {name:20s} {count:2d} proposals ({with_rec} with rec)')

        time.sleep(0.15)

    # Scorecard
    print()
    print('=' * 80)
    ok = sum(1 for r in results if r['status'] == 'OK')
    low = sum(1 for r in results if r['status'] == 'LOW')
    fail = sum(1 for r in results if r['status'] in ('FAIL', 'ERR'))
    total = len(results)
    print(f'Scorecard: {ok}/{total} OK ({ok / total * 100:.0f}%)')
    print(f'  OK:   {ok} (2+ proposals found)')
    print(f'  LOW:  {low} (1 proposal found)')
    print(f'  FAIL: {fail} (0 proposals or error)')

    # By category
    categories = {}
    for r in results:
        cat = next((c['category'] for c in COMPANIES if c['ticker'] == r['ticker']), 'custom')
        categories.setdefault(cat, []).append(r)

    print()
    for cat, cat_results in categories.items():
        cat_ok = sum(1 for r in cat_results if r['status'] == 'OK')
        print(f'  {cat}: {cat_ok}/{len(cat_results)} OK')

    return 0 if ok / total >= 0.80 else 1


if __name__ == '__main__':
    sys.exit(main())
