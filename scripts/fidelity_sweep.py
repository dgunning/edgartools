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
  scorecard's worst-filings table, not filed one by one.

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


def failures_from(filings_csv: Path) -> List[si.Failure]:
    """Every filing whose check raised, from the scorecard's filings.csv."""
    if not filings_csv.exists():
        return []
    with open(filings_csv, newline='') as f:
        return [si.Failure(r['accession_number'], r['form'], r['company'], r.get('error_stage') or 'check',
                           r['error_type'], r['error_message'], r.get('traceback', ''))
                for r in csv.DictReader(f) if r.get('outcome') == 'error']


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
    card = (args.out / 'scorecard.md').read_text()
    signatures = si.group_failures(JOB, failures_from(args.out / 'filings.csv'))
    if args.repo or args.dry_run:
        si.publish(args.repo, job=JOB, label=LABEL, label_description=LABEL_DESCRIPTION,
                   scorecard_title=SCORECARD_TITLE, scorecard_md=card, signatures=signatures,
                   run_label=f"{start} to {end}, seed {seed}", dry_run=args.dry_run)
    return 0


if __name__ == '__main__':
    sys.exit(main())
