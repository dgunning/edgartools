"""
Weekly as-filed fidelity sweep: the fidelity scorecard on last week's filings, published to GitHub.

``scripts/fidelity_scorecard.py`` compares what the library parses and renders
against the SEC's own rendering of each filing (the ``R*.htm`` statement pages).
It was run by hand on historical samples. This wrapper runs it on the 10-K,
10-Q, 20-F and 40-F filings of the last ``--days`` days, so every week checks
filings the library has never seen, and then:

- comments the run's ``scorecard.md`` on one rolling issue labelled
  ``sweep:fidelity`` (read the per-filing spread there, not only the pooled
  rate: one large filing can move the pooled rate by several points);
- files one issue per new failure signature among the filings whose check raised
  (see ``scripts/scheduled_issues.py``). Value mismatches are listed in the
  scorecard's worst-filings table, not filed one by one;
- checks that each balance sheet balances, ``validate(level='fundamental')``. A
  statement can match the SEC page and still not balance when the library picked
  the wrong totals or the validator misses an equity component (GH #2055).
  Invalid results are grouped by shape (which check ran, and any temporary,
  redeemable or partners' equity on the sheet), one issue per shape; a validator
  that raises is filed like any other exception.

The window is ``--days`` days ending yesterday and the seed is the window's last
day as YYYYMMDD, so a rerun of the same week draws the same filings.

Usage::

    python scripts/fidelity_sweep.py --days 7 --size 30 --out fidelity-run --dry-run
    python scripts/fidelity_sweep.py --days 7 --size 30 --out fidelity-run --repo dgunning/edgartools

Needs EDGAR_IDENTITY.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fidelity_scorecard  # noqa: E402
import scheduled_issues as si  # noqa: E402

JOB = 'fidelity'
LABEL = 'sweep:fidelity'
LABEL_DESCRIPTION = 'Found by the scheduled as-filed fidelity sweep over new filings'
SCORECARD_TITLE = 'As-filed fidelity scorecard (weekly)'

csv.field_size_limit(sys.maxsize)   # filings.csv carries whole tracebacks


VALIDATE_STAGE = 'balance sheet validate'
INVALID = 'Balance sheet does not balance'


def _rows(filings_csv: Path) -> List[dict]:
    if not filings_csv.exists():
        return []
    with open(filings_csv, newline='') as f:
        return list(csv.DictReader(f))


def failures_from(filings_csv: Path) -> List[si.Failure]:
    """Every filing whose check or balance-sheet validation raised, from the scorecard's filings.csv."""
    out = []
    for r in _rows(filings_csv):
        if r.get('outcome') == 'error':
            out.append(si.Failure(r['accession_number'], r['form'], r['company'], r.get('error_stage') or 'check',
                                  r['error_type'], r['error_message'], r.get('traceback', '')))
        if r.get('bs_validation') == 'error':
            error_type = (r.get('bs_validation_message') or 'Exception').split(':', 1)[0]
            out.append(si.Failure(r['accession_number'], r['form'], r['company'], VALIDATE_STAGE, error_type,
                                  r.get('bs_validation_message', ''), r.get('bs_validation_traceback', '')))
    return out


def invalid_findings(filings_csv: Path) -> List[tuple]:
    """``(shape, Failure)`` for every balance sheet whose validation is invalid."""
    return [(r.get('bs_validation_shape') or 'unknown',
             si.Failure(r['accession_number'], r['form'], r['company'], VALIDATE_STAGE, INVALID,
                        r.get('bs_validation_message', '')))
            for r in _rows(filings_csv) if r.get('bs_validation') == 'invalid']


def validation_summary(filings_csv: Path) -> str:
    """The scorecard section for balance-sheet validation: counts by status, then each invalid filing."""
    rows = [r for r in _rows(filings_csv) if r.get('bs_validation')]
    counts = Counter(r['bs_validation'] for r in rows)
    lines = ['## Balance-sheet validation (`validate(level="fundamental")`)', '',
             '| Status | Filings |', '|---|---|']
    lines += [f"| {k} | {counts[k]} |" for k in ('valid', 'invalid', 'inconclusive', 'no_balance_sheet', 'error')
              if counts[k]]
    invalid = [r for r in rows if r['bs_validation'] == 'invalid']
    if invalid:
        lines += ['', '| Filing | Form | Company | Shape | Message |', '|---|---|---|---|---|']
        lines += [f"| {r['accession_number']} | {r['form']} | {si._md(r['company'])[:50]} | "
                  f"`{r.get('bs_validation_shape', '')}` | {si._md(r.get('bs_validation_message', ''))[:160]} |"
                  for r in invalid]
    return '\n'.join(lines)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument('--days', type=int, default=7, help='filing window length, ending yesterday (default 7)')
    p.add_argument('--end', type=date.fromisoformat, help='last filing date (default yesterday)')
    p.add_argument('--size', type=int, default=30, help='filings in the random draw (default 30)')
    p.add_argument('--seed', type=int, help='random seed (default: the window end as YYYYMMDD)')
    p.add_argument('--timeout', type=int, default=fidelity_scorecard.DEFAULT_TIMEOUT,
                   help='seconds per filing attempt (default %(default)s)')
    p.add_argument('--out', type=Path, required=True, help='output directory for the scorecard files')
    p.add_argument('--repo', help='file issues in this GitHub repo, e.g. dgunning/edgartools')
    p.add_argument('--dry-run', action='store_true', help='print the issues that would be filed')
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    end = args.end or date.today() - timedelta(days=1)
    start = end - timedelta(days=args.days - 1)
    seed = args.seed if args.seed is not None else int(end.strftime('%Y%m%d'))
    code = fidelity_scorecard.main(['--seed', str(seed), '--size', str(args.size), '--start', start.isoformat(),
                                    '--end', end.isoformat(), '--out', str(args.out),
                                    '--timeout', str(args.timeout)])
    if code != 0:
        return code
    filings_csv = args.out / 'filings.csv'
    card = (args.out / 'scorecard.md').read_text() + '\n\n' + validation_summary(filings_csv)
    (args.out / 'scorecard.md').write_text(card)
    signatures = (si.group_failures(JOB, failures_from(filings_csv))
                  + si.group_findings(JOB, INVALID, VALIDATE_STAGE, invalid_findings(filings_csv)))
    if args.repo or args.dry_run:
        si.publish(args.repo, job=JOB, label=LABEL, label_description=LABEL_DESCRIPTION,
                   scorecard_title=SCORECARD_TITLE, scorecard_md=card, signatures=signatures,
                   run_label=f"{start} to {end}, seed {seed}", dry_run=args.dry_run)
    return 0


if __name__ == '__main__':
    sys.exit(main())
