"""Extract the facts and footnotes extract_nonaccrual reads, verbatim from live SEC XBRL (GH #1959).

Usage, from the repo root:  hatch run python tests/fixtures/bdc/nonaccrual_1959/extract.py ACCESSION PERIOD OUT.json
"""
import json
import sys

from edgar import find
from edgar.bdc.nonaccrual import _NONACCRUAL_RE

KEEP = ('fact_id', 'concept', 'numeric_value', 'period_instant', 'period_start', 'period_end')
SCHEDULE = ('us-gaap:InvestmentOwnedAtFairValue', 'us-gaap:InvestmentOwnedAtCost')


def row(fact):
    return {k: v for k, v in fact.items() if (k in KEEP or (k.startswith('dim_') and v)) and v is not None}


accession, period, out = sys.argv[1:4]
xbrl = find(accession).xbrl()
facts = xbrl.facts.get_facts()
footnotes = [fn for fn in xbrl.footnotes.values() if _NONACCRUAL_RE.search(fn.text.lower())]
linked = {fid for fn in footnotes for fid in fn.related_fact_ids}
kept = [row(f) for f in facts
        if f.get('fact_id') in linked
        or (f.get('concept') in SCHEDULE and f.get('period_instant') == period)
        or 'nonaccrual' in (f.get('concept') or '').lower()]
ids = {f.get('fact_id') for f in kept}
json.dump({
    'accession': accession,
    'period': period,
    'footnotes': [{'id': fid, 'text': fn.text, 'lang': getattr(fn, 'lang', 'en-US'),
                   'related_fact_ids': [i for i in fn.related_fact_ids if i in ids]}
                  for fid, fn in xbrl.footnotes.items() if fn in footnotes],
    'facts': kept,
}, open(out, 'w'), indent=0, default=str)
print(out, len(kept), 'facts', len(footnotes), 'footnotes')  # noqa: T201
