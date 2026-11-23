"""
Crash sweep: run the library's user entry points on a sample of last week's filings.

Every week SEC publishes thousands of filings the library has never seen. This
script draws a seeded, stratified sample of them and runs what a user would run
on each one -- ``attachments``, ``text()``, ``markdown()``, ``obj()`` and its
rendering, ``xbrl()`` and the three primary statements -- each stage on its own,
so one failure does not hide the next. The oracle is the weakest one there is
(it does not raise), which is why it finds bugs no fixture-based test can: the
input is new.

Failures are grouped by signature (exception type, stage and the innermost
``edgar/`` frame; see ``scripts/scheduled_issues.py``). With ``--repo`` each new
signature becomes one GitHub issue labelled ``sweep:crash``, and the run's
scorecard is a comment on one rolling issue. Network and SEC errors, and filings
that exceed ``--timeout``, are counted in the scorecard and never filed.

The sample
----------
Filings from ``--days`` days ending yesterday, from the SEC quarterly form
indexes. Strata are the form families in ``FAMILIES`` plus ``other`` (every form
not named, amendments included); ``--size`` is shared equally across strata that
have filings, and each stratum draws uniformly without replacement with its own
generator seeded from ``--seed`` and the stratum's name. The default seed is the
window's last day as YYYYMMDD, so a rerun of the same week draws the same filings.

Usage::

    python scripts/crash_sweep.py --days 7 --size 60 --out crash-run --dry-run
    python scripts/crash_sweep.py --days 7 --size 60 --out crash-run --repo dgunning/edgartools

Needs EDGAR_IDENTITY. Filings run one at a time inside the library's SEC throttle.
"""
from __future__ import annotations

import argparse
import csv
import io
import random
import signal
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scheduled_issues as si  # noqa: E402

JOB = 'crash'
LABEL = 'sweep:crash'
LABEL_DESCRIPTION = 'Found by the scheduled crash sweep over new filings'
SCORECARD_TITLE = 'Crash sweep scorecard (weekly)'

FAMILIES: Dict[str, Tuple[str, ...]] = {
    '10-K': ('10-K',),
    '10-Q': ('10-Q',),
    '8-K': ('8-K',),
    'foreign': ('20-F', '40-F', '6-K'),
    'ownership': ('3', '4', '5'),
    '13F': ('13F-HR',),
    'schedule-13': ('SCHEDULE 13D', 'SCHEDULE 13G', 'SC 13D', 'SC 13G'),
    'proxy': ('DEF 14A',),
    'registration': ('S-1', 'S-3', 'S-4', 'F-1', 'F-3'),
    'prospectus': ('424B2', '424B3', '424B4', '424B5'),
    'funds': ('497K', 'NPORT-P', 'N-CEN', 'N-MFP3', 'N-CSR'),
    'offerings': ('D', 'C', '1-A'),
}
OTHER = 'other'
DEFAULT_TIMEOUT = 180
STATEMENTS = ('income_statement', 'balance_sheet', 'cash_flow_statement')
STAGE_NAMES = ('attachments', 'text', 'markdown', 'obj', 'obj_render', 'xbrl', 'statements')


def family_of(form: str) -> str:
    for name, forms in FAMILIES.items():
        if form in forms:
            return name
    return OTHER


def quarters(start: date, end: date) -> List[Tuple[int, int]]:
    out, y, q = [], start.year, (start.month - 1) // 3 + 1
    while (y, q) <= (end.year, (end.month - 1) // 3 + 1):
        out.append((y, q))
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


def load_population(start: date, end: date) -> List[Dict[str, Any]]:
    """Every filing from ``start`` to ``end`` in the SEC quarterly indexes."""
    from edgar import get_filings
    rows = []
    for y, q in quarters(start, end):
        filings = get_filings(y, q)
        if filings is None:
            continue
        cols = ['form', 'company', 'cik', 'filing_date', 'accession_number']
        for r in filings.data.select(cols).to_pylist():
            if start <= r['filing_date'] <= end:
                rows.append(r)
    return rows


def draw_sample(population: Sequence[Dict[str, Any]], size: int, seed: int) -> List[Dict[str, Any]]:
    """Stratified draw: ``size`` shared equally by the families that have filings."""
    strata: Dict[str, List[Dict[str, Any]]] = {}
    for r in sorted(population, key=lambda r: r['accession_number']):
        strata.setdefault(family_of(r['form']), []).append(r)
    names = sorted(strata)
    if not names or size < 1:
        return []
    base, extra = divmod(size, len(names))
    sample = []
    for i, name in enumerate(names):
        want = base + (1 if i < extra else 0)
        rng = random.Random(f"{seed}:{name}")
        pool = strata[name]
        for r in rng.sample(pool, min(want, len(pool))):
            sample.append({**r, 'family': name})
    return sample


# ---------------------------------------------------------------------------
# Running one filing
# ---------------------------------------------------------------------------

@dataclass
class StageResult:
    stage: str
    outcome: str            # 'ok', 'none', 'error', 'skipped'
    error_type: str = ''
    error_message: str = ''
    traceback: str = ''
    seconds: float = 0.0


@dataclass
class FilingResult:
    row: Dict[str, Any]
    stages: List[StageResult] = field(default_factory=list)
    timed_out: bool = False
    seconds: float = 0.0


class _SweepTimeout(Exception):
    pass


def _on_alarm(*_args):
    raise _SweepTimeout('the filing took longer than --timeout')


def _render(obj: Any) -> str:
    from rich.console import Console
    console = Console(file=io.StringIO(), width=120, record=False)
    console.print(obj)
    return console.file.getvalue()


def stages_for(filing) -> List[Tuple[str, Callable[[Dict[str, Any]], Any]]]:
    """The entry points run on every filing, in order. Each gets a dict for passing results along."""
    def obj(state):
        state['obj'] = filing.obj()
        return state['obj']

    def obj_render(state):
        if state.get('obj') is None:
            raise _Skip
        return _render(state['obj'])

    def xbrl(state):
        state['xbrl'] = filing.xbrl()
        return state['xbrl']

    def statements(state):
        x = state.get('xbrl')
        if x is None:
            raise _Skip
        for name in STATEMENTS:
            st = getattr(x.statements, name)()
            if st is not None:
                st.to_dataframe()
                _render(st)
        return True

    return [
        ('attachments', lambda s: len(filing.attachments)),
        ('text', lambda s: filing.text()),
        ('markdown', lambda s: filing.markdown()),
        ('obj', obj),
        ('obj_render', obj_render),
        ('xbrl', xbrl),
        ('statements', statements),
    ]


class _Skip(Exception):
    """A stage that does not apply to this filing (no object, no XBRL)."""


def run_filing(row: Dict[str, Any], timeout: int = DEFAULT_TIMEOUT,
               stages: Optional[Callable] = None) -> FilingResult:
    from edgar import Filing
    result = FilingResult(row)
    t0 = time.time()
    filing = Filing(form=row['form'], filing_date=str(row['filing_date']), company=row['company'],
                    cik=int(row['cik']), accession_no=row['accession_number'])
    state: Dict[str, Any] = {}
    use_alarm = hasattr(signal, 'SIGALRM')
    if use_alarm:
        signal.signal(signal.SIGALRM, _on_alarm)
        signal.alarm(timeout)
    try:
        for name, fn in (stages or stages_for)(filing):
            s0 = time.time()
            try:
                value = fn(state)
                outcome = 'none' if value is None else 'ok'
                result.stages.append(StageResult(name, outcome, seconds=round(time.time() - s0, 2)))
            except _Skip:
                result.stages.append(StageResult(name, 'skipped'))
            except _SweepTimeout:
                raise
            except Exception as e:  # the sweep records every failure; it never stops on one
                result.stages.append(StageResult(
                    name, 'error', type(e).__name__, ' '.join(str(e).split())[:300],
                    ' || '.join(traceback.format_exc().strip().splitlines()),
                    round(time.time() - s0, 2)))
    except _SweepTimeout:
        result.timed_out = True
    finally:
        if use_alarm:
            signal.alarm(0)
    result.seconds = round(time.time() - t0, 2)
    return result


def failures_of(results: Sequence[FilingResult]) -> List[si.Failure]:
    return [si.Failure(r.row['accession_number'], r.row['form'], r.row['company'], s.stage,
                       s.error_type, s.error_message, s.traceback)
            for r in results for s in r.stages if s.outcome == 'error']


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

RESULT_FIELDS = ['accession_number', 'form', 'family', 'company', 'cik', 'filing_date', 'stage', 'outcome',
                 'error_type', 'error_message', 'seconds', 'traceback']


def write_results(results: Sequence[FilingResult], out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / 'results.csv'
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        w.writeheader()
        for r in results:
            base = {k: r.row.get(k, '') for k in ('accession_number', 'form', 'family', 'company', 'cik',
                                                     'filing_date')}
            if r.timed_out:
                w.writerow({**base, 'stage': '(filing)', 'outcome': 'timeout', 'seconds': r.seconds})
            for s in r.stages:
                w.writerow({**base, 'stage': s.stage, 'outcome': s.outcome, 'error_type': s.error_type,
                            'error_message': s.error_message, 'seconds': s.seconds, 'traceback': s.traceback})
    return path


def scorecard(results: Sequence[FilingResult], *, start: date, end: date, seed: int, population: int,
              provenance: str) -> str:
    stage_names = list(STAGE_NAMES)
    families = sorted({r.row['family'] for r in results})
    lines = [
        f"## Crash sweep {start} to {end}",
        '',
        f"{len(results)} filings drawn from {population:,} (seed {seed}); {provenance}.",
        '',
        '| Family | Filings | With a failure | ' + ' | '.join(stage_names) + ' |',
        '|---|---|---|' + '---|' * len(stage_names),
    ]
    for fam in families:
        rs = [r for r in results if r.row['family'] == fam]
        failing = sum(1 for r in rs if any(s.outcome == 'error' and not si.is_transient(s.error_type)
                                           for s in r.stages))
        cells = []
        for name in stage_names:
            errs = sum(1 for r in rs for s in r.stages
                       if s.stage == name and s.outcome == 'error' and not si.is_transient(s.error_type))
            cells.append(str(errs) if errs else '·')
        lines.append(f"| {fam} | {len(rs)} | {failing} | " + ' | '.join(cells) + ' |')
    transient = sum(1 for r in results for s in r.stages if s.outcome == 'error' and si.is_transient(s.error_type))
    harness = sorted({f"{s.stage}: {s.error_type}" for r in results for s in r.stages
                      if s.outcome == 'error' and not si.is_transient(s.error_type) and not si.edgar_frame(s.traceback)})
    timeouts = [r for r in results if r.timed_out]
    obj_none = sorted({r.row['form'] for r in results for s in r.stages if s.stage == 'obj' and s.outcome == 'none'})
    lines += ['', f"- Network/SEC errors (not filed): {transient}",
              f"- Errors raised outside edgar/, a sweep bug (not filed): {', '.join(harness) or 'none'}",
              f"- Filings over the time limit (not filed): {len(timeouts)}"
              + (': ' + ', '.join(f"{r.row['accession_number']} ({r.row['form']})" for r in timeouts[:5])
                 if timeouts else ''),
              f"- Forms where `obj()` returned None: {', '.join(obj_none) or 'none'}"]
    slow = sorted(results, key=lambda r: -r.seconds)[:5]
    if slow:
        lines.append('- Slowest: ' + ', '.join(f"{r.row['accession_number']} {r.row['form']} {r.seconds}s"
                                               for r in slow))
    return '\n'.join(lines)


def provenance() -> str:
    import subprocess

    from edgar.__about__ import __version__
    try:
        commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True,
                                check=True).stdout.strip()
    except Exception:
        commit = 'unknown'
    return f"edgartools {__version__} at {commit}"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument('--days', type=int, default=7, help='filing window length, ending yesterday (default 7)')
    p.add_argument('--end', type=date.fromisoformat, help='last filing date (default yesterday)')
    p.add_argument('--size', type=int, default=60, help='filings to draw (default 60)')
    p.add_argument('--seed', type=int, help='random seed (default: the window end as YYYYMMDD)')
    p.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT, help='seconds per filing (default %(default)s)')
    p.add_argument('--out', type=Path, required=True, help='output directory for results.csv and scorecard.md')
    p.add_argument('--repo', help='file issues in this GitHub repo, e.g. dgunning/edgartools')
    p.add_argument('--dry-run', action='store_true', help='print the issues that would be filed')
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    end = args.end or date.today() - timedelta(days=1)
    start = end - timedelta(days=args.days - 1)
    seed = args.seed if args.seed is not None else int(end.strftime('%Y%m%d'))
    population = load_population(start, end)
    sample = draw_sample(population, args.size, seed)
    print(f"sample: {len(sample)} of {len(population)} filings {start}..{end} (seed {seed})", flush=True)
    results = []
    for i, row in enumerate(sample, 1):
        r = run_filing(row, timeout=args.timeout)
        results.append(r)
        errs = [f"{s.stage}:{s.error_type}" for s in r.stages if s.outcome == 'error']
        print(f"[{i}/{len(sample)}] {row['accession_number']} {row['form']} "
              f"{'TIMEOUT ' if r.timed_out else ''}{' '.join(errs) or 'ok'} {r.seconds}s", flush=True)
    write_results(results, args.out)
    card = scorecard(results, start=start, end=end, seed=seed, population=len(population), provenance=provenance())
    (args.out / 'scorecard.md').write_text(card)
    signatures = si.group_failures(JOB, failures_of(results))
    if args.repo or args.dry_run:
        si.publish(args.repo, job=JOB, label=LABEL, label_description=LABEL_DESCRIPTION,
                   scorecard_title=SCORECARD_TITLE, scorecard_md=card, signatures=signatures,
                   run_label=f"{start} to {end}, seed {seed}", dry_run=args.dry_run)
    else:
        print(card)
    return 0


if __name__ == '__main__':
    sys.exit(main())
