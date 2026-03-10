"""
Profile 424B prospectus parsing to identify performance bottlenecks.

Breaks down time spent in each phase (excluding lifecycle which is known
to be dominated by SEC API calls for related_filings).

Phases measured:
  1. filing.html()          — network download + SGML extraction
  2. filing.parse()         — HTML → Document tree (standalone)
  3. cover page extraction  — regex over cover text (calls parse() internally)
  4. offering classification— regex cascade (calls parse() internally)
  5. table classification   — iterate Document tables (calls parse() internally)
  6. deal properties        — computed from tables
  7. selling_stockholders   — table extraction
  8. full end-to-end pass   — from_filing + deal + selling_stockholders

Usage:
    python scripts/profile_424b.py [--n 10]
"""

import time
import statistics
import argparse


def profile_single_filing(filing):
    """Profile a single filing, returning timing breakdown."""
    from edgar.documents import HTMLParser, ParserConfig
    from edgar.core import is_probably_html
    from edgar.offerings.prospectus import Prospectus424B
    from edgar.offerings._424b_cover import extract_cover_page_fields
    from edgar.offerings._424b_classifier import classify_offering_type
    from edgar.offerings._424b_tables import classify_tables_in_document

    timings = {}

    # Phase 1: HTML download (network + SGML)
    t0 = time.perf_counter()
    html_content = filing.html()
    timings['html_download'] = time.perf_counter() - t0

    if not html_content or not is_probably_html(html_content):
        return None

    html_size_kb = len(html_content) / 1024

    # Phase 2: HTML parse (standalone, measures raw parsing cost)
    t0 = time.perf_counter()
    parser = HTMLParser(ParserConfig(form=filing.form))
    doc = parser.parse(html_content)
    timings['html_parse'] = time.perf_counter() - t0

    # Phase 3: Cover page extraction (calls filing.parse() internally)
    t0 = time.perf_counter()
    cover_fields = extract_cover_page_fields(filing)
    timings['cover_extract'] = time.perf_counter() - t0

    # Phase 4: Offering type classification (calls filing.parse() internally)
    t0 = time.perf_counter()
    classification = classify_offering_type(filing)
    timings['classify'] = time.perf_counter() - t0

    # Phase 5: Table classification (on already-parsed doc)
    t0 = time.perf_counter()
    table_map = classify_tables_in_document(doc) if doc else {}
    timings['table_classify'] = time.perf_counter() - t0

    num_tables = len(doc.tables) if doc and hasattr(doc, 'tables') else 0
    num_classified = sum(len(v) for v in table_map.values())

    # Phase 6: from_filing (cover + classify combined — 2x parse() internally)
    t0 = time.perf_counter()
    prospectus = Prospectus424B.from_filing(filing)
    timings['from_filing'] = time.perf_counter() - t0

    # Phase 7: Deal (triggers _classified_tables → another parse())
    t0 = time.perf_counter()
    deal = prospectus.deal
    _ = deal.price, deal.shares, deal.gross_proceeds, deal.lead_bookrunner
    _ = deal.fee_per_share, deal.total_fees, deal.discount_rate
    _ = deal.dilution_per_share, deal.shares_before, deal.shares_after
    timings['deal'] = time.perf_counter() - t0

    # Phase 8: Selling stockholders (uses cached _classified_tables)
    t0 = time.perf_counter()
    ss = prospectus.selling_stockholders
    timings['selling_stockholders'] = time.perf_counter() - t0

    # Phase 9: Underwriting (uses cached _classified_tables)
    t0 = time.perf_counter()
    uw = prospectus.underwriting
    timings['underwriting'] = time.perf_counter() - t0

    # Phase 10: Lifecycle (SEC API calls for related filings)
    t0 = time.perf_counter()
    lc = prospectus.lifecycle
    timings['lifecycle'] = time.perf_counter() - t0

    # Full end-to-end (fresh object, no prior caching)
    t0 = time.perf_counter()
    p2 = Prospectus424B.from_filing(filing)
    d2 = p2.deal
    _ = d2.price, d2.shares, d2.gross_proceeds, d2.lead_bookrunner
    _ = d2.fee_per_share, d2.total_fees, d2.discount_rate
    _ = d2.dilution_per_share, d2.shares_before, d2.shares_after
    _ = p2.selling_stockholders
    _ = p2.underwriting
    timings['full_no_lifecycle'] = time.perf_counter() - t0

    timings['html_size_kb'] = html_size_kb
    timings['num_tables'] = num_tables
    timings['num_classified'] = num_classified
    timings['file_number'] = prospectus.cover_page.registration_number or 'N/A'

    return timings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=10, help='Number of filings to profile')
    args = ap.parse_args()

    from edgar import get_filings

    print(f"Fetching {args.n} recent 424B filings...")
    filings = get_filings(form=['424B1', '424B2', '424B3', '424B4', '424B5']).sample(args.n)

    all_timings = []
    for i, filing in enumerate(filings):
        print(f"\n[{i+1}/{args.n}] {filing.company} — {filing.form} ({filing.accession_no})")
        try:
            t = profile_single_filing(filing)
            if t is None:
                print("  SKIP (no HTML)")
                continue
            all_timings.append(t)

            print(f"  HTML: {t['html_size_kb']:.0f} KB, {t['num_tables']} raw tables, "
                  f"{t['num_classified']} classified, file# {t['file_number']}")
            print(f"  html_download:       {t['html_download']:7.3f}s")
            print(f"  html_parse:          {t['html_parse']:7.3f}s")
            print(f"  cover_extract:       {t['cover_extract']:7.3f}s  (parses HTML)")
            print(f"  classify:            {t['classify']:7.3f}s  (parses HTML)")
            print(f"  table_classify:      {t['table_classify']:7.3f}s  (on pre-parsed doc)")
            print(f"  from_filing:         {t['from_filing']:7.3f}s  (cover+classify)")
            print(f"  deal:                {t['deal']:7.3f}s  (tables+compute)")
            print(f"  selling_stockholders:{t['selling_stockholders']:7.3f}s")
            print(f"  underwriting:        {t['underwriting']:7.3f}s")
            print(f"  lifecycle:           {t['lifecycle']:7.3f}s  (Company + file_number filter)")
            print(f"  ---")
            print(f"  full_no_lifecycle:   {t['full_no_lifecycle']:7.3f}s  (end-to-end)")
        except Exception as e:
            print(f"  ERROR: {e}")

    if not all_timings:
        print("\nNo successful profiles.")
        return

    print("\n" + "=" * 70)
    print(f"SUMMARY ({len(all_timings)} filings)")
    print("=" * 70)

    phases = ['html_download', 'html_parse', 'cover_extract', 'classify',
              'table_classify', 'from_filing', 'deal',
              'selling_stockholders', 'underwriting', 'lifecycle',
              'full_no_lifecycle']

    for phase in phases:
        vals = [t[phase] for t in all_timings]
        avg = statistics.mean(vals)
        med = statistics.median(vals)
        mx = max(vals)
        print(f"  {phase:24s}  avg={avg:.3f}s  med={med:.3f}s  max={mx:.3f}s")

    html_sizes = [t['html_size_kb'] for t in all_timings]
    print(f"\n  HTML size:     avg={statistics.mean(html_sizes):.0f} KB  max={max(html_sizes):.0f} KB")
    table_counts = [t['num_tables'] for t in all_timings]
    print(f"  Raw tables:    avg={statistics.mean(table_counts):.0f}     max={max(table_counts)}")

    # Breakdown: what fraction of full_no_lifecycle is each phase?
    print(f"\n  Phase breakdown (% of full_no_lifecycle avg):")
    full_avg = statistics.mean([t['full_no_lifecycle'] for t in all_timings])
    for phase in ['html_download', 'html_parse', 'cover_extract', 'classify',
                  'table_classify', 'deal', 'selling_stockholders', 'underwriting']:
        pavg = statistics.mean([t[phase] for t in all_timings])
        pct = (pavg / full_avg * 100) if full_avg > 0 else 0
        bar = '#' * int(pct / 2)
        print(f"    {phase:24s}  {pavg:.3f}s  {pct:5.1f}%  {bar}")

    # Estimate parse() caching savings
    parse_cost = statistics.mean([t['html_parse'] for t in all_timings])
    print(f"\n  html_parse() avg cost: {parse_cost:.3f}s")
    print(f"  cover_extract + classify each re-parse internally")
    print(f"  deal triggers _classified_tables which re-parses")
    print(f"  Caching parse() would save ~{parse_cost * 3:.3f}s "
          f"({parse_cost * 3 / full_avg * 100:.0f}% of total)" if full_avg > 0 else "")


if __name__ == '__main__':
    main()
