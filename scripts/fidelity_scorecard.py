"""
As-filed fidelity scorecard: the facts check and the statement check over a random sample of filings.

For a seeded, stratified random sample of 10-K, 10-Q, 20-F and 40-F filings,
this script runs both checks against the SEC's own rendering of each filing
(the ``R*.htm`` statement pages):

- the facts check, ``filing.viewer.compare(xbrl)``, taken from the statement check's ``.facts``
  (which runs it once)
  (``edgar.xbrl.viewer_validation``): does each numeric cell of the statement
  pages have the XBRL fact the library parsed, with the same value?
- the statement check, ``filing.viewer.compare_statements(xbrl)``
  (``edgar.xbrl.statement_fidelity``): do the statements a user gets
  (``Statement.to_dataframe()`` and the rendered table) show those cells, in
  the page's rows, with the page's value and sign?

and writes every outcome plus a scorecard. The scorecard's numbers all come
from the run; the definitions of the rates are the modules' own and are quoted
from their docstrings, and the limits are read from the module docstrings and
the SEC viewer guide at run time.

Usage::

    python scripts/fidelity_scorecard.py --seed 20261114 --size 120 \\
        --start 2020-01-01 --end 2026-09-30 --out scorecard-run
    python scripts/fidelity_scorecard.py --seed 7 --size 10 --end 2026-09-30 \\
        --exclude seen.txt --out small-run

Needs EDGAR_IDENTITY. Filings are processed one at a time; the library's own
throttle keeps requests within SEC limits.

The sample
----------
``draw_sample`` reads the SEC quarterly form indexes for every quarter from
``--start`` to ``--end`` and keeps original filings (no amendments) of the four
forms filed in that window. The population is sorted by accession number, so
the draw does not depend on the order of the index files.

- Strata are form x era. Eras are split at the ``--era-split`` years (default
  2024: 2020-2023 and 2024 onward). ``--size`` filings are allocated to the
  strata by ``FORM_WEIGHTS`` (shared equally by the eras), largest remainder
  first; a stratum with no filings gets none. Within a stratum filings are
  drawn uniformly without replacement, each stratum with its own generator
  seeded from ``--seed`` and the stratum's name.
- Industry is the SIC group of the filer (``sic_group``): bank, insurer, reit,
  utility, fund_like, commercial, or unknown when the SIC code cannot be
  looked up. Groups are thin in a random draw, so after it a top-up draws
  further filings uniformly from the whole population until each group in
  ``MIN_GROUP_SHARE`` has at least ``ceil(share x size)`` filings, or
  ``TOPUP_MAX_LOOKUPS`` filers have been looked up. Top-up filings are flagged
  (``topup=1``) and are added to ``--size``; the scorecard counts them apart.
- ``--exclude`` names a file of accession numbers and/or CIKs (one per line,
  ``#`` starts a comment) never to draw, for a sample that is fresh relative
  to earlier ones.

What is reproducible
--------------------
The same ``--seed``, ``--size``, ``--start``, ``--end``, ``--era-split`` and
``--exclude`` draw the same sample, provided the quarter holding ``--end`` has
ended (the index of a past quarter does not change) and every SIC lookup
succeeds (a failed lookup puts a filer in ``unknown``, which can change the
top-up). What can still change between runs of the same sample:

- the SEC can re-render a filing's ``R*.htm`` pages or ``MetaLinks.json``;
- the library version and commit, both recorded in the scorecard;
- network failures, recorded per filing as errors after one retry;
- a filer's SIC code, if the SEC reclassifies it before a later draw.

Outputs (in ``--out``)
----------------------
- ``sample.csv``: the drawn filings with their stratum, SIC group, top-up flag and seed.
- ``cells.csv``: every cell of the facts check (``ComparisonResults.to_dataframe()``) with its accession.
- ``outcomes.csv``: every outcome of the statement check
  (``StatementFidelityResults.to_dataframe()``) with its accession and the facts check's status for the cell.
- ``pages.csv``: each statement page and the library statement it was compared with.
- ``filings.csv``: one row per filing: outcome, error type and message, seconds, and both checks' summary.
- ``scorecard.md`` and ``scorecard.json``: the sample definition, the facts check, the statement check
  per surface, the limits, the library version and the git commit.

A filing whose check raises is recorded with the exception's type and message
and the run goes on. Pooled rates are the modules' definitions applied to the
counts summed over the compared filings.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import signal
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

FORMS = ('10-K', '10-Q', '20-F', '40-F')

#: Relative share of ``--size`` per form, before the split across eras. 10-Q
#: outnumbers 10-K about three to one in the indexes; weighting them alike keeps
#: annual statements, which carry more pages, as visible as quarterly ones.
FORM_WEIGHTS = {'10-K': 20, '10-Q': 22, '20-F': 2, '40-F': 1}

DEFAULT_START = date(2020, 1, 1)   # MetaLinks.json, which the viewer reads, is in every filing from here
DEFAULT_ERA_SPLITS = (2024,)

#: Minimum share of ``--size`` for each thin SIC group; the top-up fills them.
MIN_GROUP_SHARE = {'bank': 0.025, 'insurer': 0.025, 'reit': 0.02, 'utility': 0.02, 'fund_like': 0.02}
#: Most filers the top-up looks up (one SEC request each) before it stops.
TOPUP_MAX_LOOKUPS = 300

DEFAULT_TIMEOUT = 480   # seconds per attempt
RETRY_PAUSE = 5         # seconds before the one retry

SAMPLE_FIELDS = ['accession_number', 'form', 'cik', 'company', 'co_registrant_ciks', 'filing_date', 'era',
                 'stratum', 'sic', 'group', 'topup', 'seed']

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / 'docs' / 'guides' / 'sec-viewer-guide.md'


class ScorecardError(ValueError):
    """Bad input to the scorecard: dates, exclusions or options."""


# --------------------------------------------------------------------------------------------
# Sample
# --------------------------------------------------------------------------------------------

def sic_group(sic: Any) -> str:
    """The industry group of a SIC code ('' or None when it is not known)."""
    s = str(sic or '').strip()
    if not s:
        return 'unknown'
    if s.startswith('60'):
        return 'bank'
    if s.startswith('63'):
        return 'insurer'
    if s == '6798':
        return 'reit'
    if s.startswith('49'):
        return 'utility'
    if s in ('6221', '6726', '6799') or s.startswith('67'):
        return 'fund_like'
    return 'commercial'


def eras_for(start: date, end: date, splits: Sequence[int]) -> List[Tuple[str, date, date]]:
    """The eras between ``start`` and ``end``: (label, first day, last day), split at the given years."""
    bounds = [start] + [date(y, 1, 1) for y in sorted(set(splits)) if start < date(y, 1, 1) <= end]
    eras = []
    for i, lo in enumerate(bounds):
        hi = date(bounds[i + 1].year - 1, 12, 31) if i + 1 < len(bounds) else end
        label = f"{lo.year}-{hi.year}" if lo.year != hi.year else str(lo.year)
        eras.append((label, lo, hi))
    return eras


def era_of(filed: date, eras: Sequence[Tuple[str, date, date]]) -> Optional[str]:
    for label, lo, hi in eras:
        if lo <= filed <= hi:
            return label
    return None


def read_exclusions(path: Optional[Path]) -> Tuple[set, set]:
    """Accession numbers and CIKs (as int) listed in ``path``; raises ScorecardError on a line that is neither."""
    accessions, ciks = set(), set()
    if path is None:
        return accessions, ciks
    path = Path(path)
    if not path.exists():
        raise ScorecardError(f"--exclude file {path} does not exist")
    for n, line in enumerate(path.read_text().splitlines(), 1):
        item = line.split('#', 1)[0].strip().split(',')[0].strip()
        if not item or item.lower() in ('accession_number', 'accession', 'cik'):
            continue
        if re.fullmatch(r'\d{10}-\d{2}-\d{6}', item):
            accessions.add(item)
        elif re.fullmatch(r'\d{18}', item):
            accessions.add(f"{item[:10]}-{item[10:12]}-{item[12:]}")
        elif re.fullmatch(r'\d{1,10}', item):
            ciks.add(int(item))
        else:
            raise ScorecardError(f"{path}:{n}: {item!r} is neither an accession number "
                                 f"(0000320193-24-000123) nor a CIK")
    return accessions, ciks


def quarters(start: date, end: date) -> List[Tuple[int, int]]:
    out, y, q = [], start.year, (start.month - 1) // 3 + 1
    while (y, q) <= (end.year, (end.month - 1) // 3 + 1):
        out.append((y, q))
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


def load_population(start: date, end: date, forms: Sequence[str] = FORMS) -> List[Dict[str, Any]]:
    """Original filings of ``forms`` filed from ``start`` to ``end``, from the SEC quarterly indexes."""
    import pyarrow as pa
    import pyarrow.compute as pc

    from edgar import get_filings
    rows = []
    for y, q in quarters(start, end):
        filings = get_filings(y, q, amendments=False)
        if filings is None:
            continue
        t = filings.data
        t = t.filter(pc.is_in(t['form'], value_set=pa.array(list(forms))))
        for r in t.select(['form', 'company', 'cik', 'filing_date', 'accession_number']).to_pylist():
            if start <= r['filing_date'] <= end:
                rows.append(r)
    return rows


def allocate(size: int, weights: Dict[str, float]) -> Dict[str, int]:
    """Split ``size`` across strata in proportion to ``weights``, largest remainder first (ties by stratum order)."""
    weights = {k: w for k, w in weights.items() if w > 0}
    total = sum(weights.values())
    if size <= 0 or not total:
        return {k: 0 for k in weights}
    exact = {k: size * w / total for k, w in weights.items()}
    out = {k: math.floor(v) for k, v in exact.items()}
    order = sorted(weights, key=lambda k: (-(exact[k] - out[k]), list(weights).index(k)))
    for k in order[:size - sum(out.values())]:
        out[k] += 1
    return out


@dataclass
class Sample:
    rows: List[Dict[str, Any]]
    seed: int
    size: int
    start: date
    end: date
    eras: List[Tuple[str, date, date]]
    population: Dict[str, int]
    planned: Dict[str, int]
    group_minimums: Dict[str, int]
    topup_lookups: int
    sic_lookup_failures: int = 0
    excluded_accessions: int = 0
    excluded_ciks: int = 0

    def definition(self) -> Dict[str, Any]:
        rows = self.rows
        return {
            'seed': self.seed, 'size': self.size, 'start': self.start.isoformat(), 'end': self.end.isoformat(),
            'forms': list(FORMS), 'form_weights': FORM_WEIGHTS,
            'eras': [{'era': e, 'from': lo.isoformat(), 'to': hi.isoformat()} for e, lo, hi in self.eras],
            'population_by_stratum': self.population, 'planned_by_stratum': self.planned,
            'drawn_by_stratum': dict(Counter(r['stratum'] for r in rows if not r['topup'])),
            'group_minimums': self.group_minimums, 'topup_lookups': self.topup_lookups,
            'sic_lookup_failures': self.sic_lookup_failures,
            'drawn_by_group': dict(Counter(r['group'] for r in rows)),
            'topup_by_group': dict(Counter(r['group'] for r in rows if r['topup'])),
            'random': sum(1 for r in rows if not r['topup']), 'topup': sum(1 for r in rows if r['topup']),
            'filings_drawn': len(rows),
            'excluded_accessions': self.excluded_accessions, 'excluded_ciks': self.excluded_ciks,
        }


def draw_sample(seed: int, size: int, start: date, end: date, *,
                exclude_accessions: Iterable[str] = (), exclude_ciks: Iterable[int] = (),
                era_splits: Sequence[int] = DEFAULT_ERA_SPLITS,
                population: Optional[List[Dict[str, Any]]] = None,
                sic_lookup: Optional[Callable[[int], str]] = None) -> Sample:
    """
    Draw the seeded stratified sample (see the module docstring).

    Args:
        seed: random seed; each stratum and the top-up get their own generator derived from it
        size: filings in the random draw; the top-up adds to it
        start, end: filing-date window, inclusive
        exclude_accessions, exclude_ciks: never drawn
        era_splits: years at which a new era starts
        population: the filings to draw from (dicts with form, company, cik, filing_date,
            accession_number); read from the SEC indexes when None
        sic_lookup: cik -> SIC code; ``Company(cik).sic`` when None

    Returns:
        Sample, its rows in a seeded shuffled order
    """
    if size < 1:
        raise ScorecardError(f"--size must be at least 1, not {size}")
    if start > end:
        raise ScorecardError(f"--start {start} is after --end {end}")
    if end >= date.today():
        raise ScorecardError(f"--end {end} is not in the past; a sample needs a closed filing window")
    eras = eras_for(start, end, era_splits)
    if population is None:
        population = load_population(start, end)
    if sic_lookup is None:
        sic_lookup = _company_sic
    ex_acc, ex_cik = set(exclude_accessions), {int(c) for c in exclude_ciks}
    sics: Dict[int, str] = {}
    sic_failures: List[int] = []

    def sic(cik: int) -> str:
        if cik not in sics:
            try:
                sics[cik] = str(sic_lookup(cik) or '')
            except Exception:  # a failed lookup puts the filer in 'unknown'; counted in the scorecard
                sics[cik] = ''
                sic_failures.append(cik)
        return sics[cik]

    # The index lists a filing once per co-registrant. Keep one row per accession, under its lowest CIK,
    # and sort by accession, so the draw does not depend on the order the population was read in.
    by_accession: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in population:
        by_accession[r['accession_number']].append(r)
    filings = []
    for accession in sorted(by_accession):
        listed = sorted(by_accession[accession], key=lambda r: int(r['cik']))
        ciks = sorted({int(r['cik']) for r in listed})
        filings.append(dict(listed[0], co_registrant_ciks=';'.join(str(c) for c in ciks[1:])))
    strata: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in filings:
        era = era_of(r['filing_date'], eras)
        if era is None or r['form'] not in FORMS:
            continue
        if r['accession_number'] in ex_acc or int(r['cik']) in ex_cik or any(
                int(c) in ex_cik for c in filter(None, r['co_registrant_ciks'].split(';'))):
            continue
        strata[f"{r['form']} {era}"].append(r)
    names = [f"{form} {era}" for form in FORMS for era, _lo, _hi in eras]
    weights = {s: (FORM_WEIGHTS[s.split(' ')[0]] / len(eras) if strata.get(s) else 0) for s in names}
    planned = allocate(size, weights)

    rows: List[Dict[str, Any]] = []
    taken = set()
    for name in names:
        pool, n = strata.get(name, []), planned.get(name, 0)
        if not n:
            continue
        rng = random.Random(f"{seed}:{name}")
        for r in rng.sample(pool, min(n, len(pool))):
            rows.append(dict(r, era=name.split(' ', 1)[1], stratum=name, topup=0))
            taken.add(r['accession_number'])
    for r in rows:
        r['sic'] = sic(int(r['cik']))
        r['group'] = sic_group(r['sic'])

    minimums = {g: math.ceil(share * size) for g, share in MIN_GROUP_SHARE.items()}
    have = Counter(r['group'] for r in rows)
    everyone = [r for name in names for r in strata.get(name, [])]
    everyone.sort(key=lambda r: r['accession_number'])
    rng = random.Random(f"{seed}:topup")
    lookups = 0
    for i in rng.sample(range(len(everyone)), len(everyone)) if everyone else ():
        if all(have[g] >= m for g, m in minimums.items()) or lookups >= TOPUP_MAX_LOOKUPS:
            break
        r = everyone[i]
        if r['accession_number'] in taken:
            continue
        cik = int(r['cik'])
        if cik not in sics:
            lookups += 1
        g = sic_group(sic(cik))
        if g in minimums and have[g] < minimums[g]:
            era = era_of(r['filing_date'], eras)
            rows.append(dict(r, era=era, stratum=f"{r['form']} {era}", topup=1, sic=sics[cik], group=g))
            taken.add(r['accession_number'])
            have[g] += 1

    random.Random(f"{seed}:order").shuffle(rows)
    for r in rows:
        r['seed'] = seed
        r['filing_date'] = r['filing_date'].isoformat() if isinstance(r['filing_date'], date) else r['filing_date']
    population_counts = {s: len(strata.get(s, [])) for s in names}
    return Sample(rows=rows, seed=seed, size=size, start=start, end=end, eras=eras,
                  population=population_counts, planned={s: planned.get(s, 0) for s in names},
                  group_minimums=minimums, topup_lookups=lookups, sic_lookup_failures=len(sic_failures),
                  excluded_accessions=len(ex_acc), excluded_ciks=len(ex_cik))


def _company_sic(cik: int) -> str:
    from edgar import Company
    return str(Company(int(cik)).sic or '')


def write_sample(sample: Sample, out: Path) -> Path:
    path = Path(out) / 'sample.csv'
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=SAMPLE_FIELDS, extrasaction='ignore')
        w.writeheader()
        w.writerows(sample.rows)
    return path


# --------------------------------------------------------------------------------------------
# Runs
# --------------------------------------------------------------------------------------------

@dataclass
class FilingRun:
    """One filing's run: its sample row, how the run ended, and both checks' results when they ran."""
    row: Dict[str, Any]
    #: 'ok', 'no_viewer', 'no_xbrl' or 'error'
    outcome: str
    has_viewer: Optional[bool] = None
    facts: Any = None          # ComparisonResults
    statements: Any = None     # StatementFidelityResults
    error_type: str = ''
    error_message: str = ''
    error_stage: str = ''
    traceback: str = ''
    attempts: int = 1
    seconds: float = 0.0


class _FilingTimeoutError(Exception):
    pass


def _on_alarm(*_args):
    raise _FilingTimeoutError('the filing took longer than --timeout')


def _transient(e: BaseException) -> bool:
    """A network or SEC hiccup worth one retry; a library error is not retried."""
    from edgar.exceptions import TransportError
    if isinstance(e, (TransportError, OSError)):
        return True
    try:
        import httpx
        if isinstance(e, httpx.HTTPError):
            return True
    except ImportError:
        pass
    return any(k in type(e).__name__ for k in ('SECHTML', 'HTTP', 'Connect', 'RemoteProtocol', 'ReadTimeout'))


def _record_error(run: FilingRun, e: BaseException, stage: str) -> None:
    run.outcome = 'error'
    run.error_type = type(e).__name__
    run.error_message = ' '.join(str(e).split())[:300]
    run.error_stage = stage
    run.traceback = ' || '.join(traceback.format_exc().strip().splitlines()[-8:])[:1200]


def run_filing(row: Dict[str, Any], timeout: int = DEFAULT_TIMEOUT) -> FilingRun:
    """Run both checks on one filing, retrying once on a network error; never raises (but KeyboardInterrupt).

    The facts check comes from the statement check's ``.facts``: ``compare_statements()`` runs it once.
    The retry pause is outside the alarm's handlers, and a timeout that fires while a failure is being
    recorded is caught too, so no exception leaves this function.
    """
    from edgar import find
    t0 = time.time()
    run = FilingRun(row=row, outcome='error')
    use_alarm = bool(timeout) and hasattr(signal, 'SIGALRM')
    for attempt in (1, 2):
        run = FilingRun(row=row, outcome='error', attempts=attempt)
        stage, retry = 'find', False
        try:
            if use_alarm:
                signal.signal(signal.SIGALRM, _on_alarm)
                signal.alarm(int(timeout))
            try:
                filing = find(row['accession_number'])
                if filing is None:
                    raise LookupError(f"find({row['accession_number']!r}) returned None")
                stage = 'viewer'
                viewer = filing.viewer
                run.has_viewer = viewer is not None
                if viewer is None:
                    run.outcome = 'no_viewer'
                else:
                    stage = 'xbrl'
                    xbrl = filing.xbrl()
                    if xbrl is None:
                        run.outcome = 'no_xbrl'
                    else:
                        stage = 'statement check'
                        run.statements = viewer.compare_statements(xbrl)
                        run.facts = run.statements.facts
                        run.outcome = 'ok'
            except KeyboardInterrupt:
                raise
            except BaseException as e:  # noqa: BLE001 - every failure is recorded, none stops the run
                _record_error(run, e, stage)
                retry = attempt == 1 and _transient(e)
            finally:
                if use_alarm:
                    signal.alarm(0)
        except _FilingTimeoutError as e:  # the alarm fired while a failure was being recorded
            _record_error(run, e, stage)
            retry = False
        if not retry:
            break
        time.sleep(RETRY_PAUSE)
    run.seconds = round(time.time() - t0, 1)
    return run


# --------------------------------------------------------------------------------------------
# Writer
# --------------------------------------------------------------------------------------------

def _rate(num: int, den: int) -> Optional[float]:
    return num / den if den else None


def _pct(x: Optional[float]) -> str:
    return '-' if x is None else f"{100 * x:.2f}%"


def _cell(v: Any) -> Any:
    if isinstance(v, dict):
        return json.dumps(v, sort_keys=True)
    if isinstance(v, float) and math.isnan(v):
        return ''
    return v


_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def reason_pattern(reason: Optional[str]) -> str:
    """A facts-check reason with its quoted values and numbers replaced, so reasons group by kind."""
    if not reason:
        return '(no reason given)'
    return _NUMBER.sub('<n>', _QUOTED.sub('<v>', reason))


def _docstring_section(doc: str, title: str) -> List[str]:
    """The text of a reST section (title underlined with '-') of ``doc``, as one string per bullet or paragraph."""
    lines = (doc or '').splitlines()
    for i in range(len(lines) - 1):
        if lines[i].strip() == title and set(lines[i + 1].strip()) == {'-'}:
            body = []
            for line in lines[i + 2:]:
                if line.strip() and set(line.strip()) == {'-'} and body:
                    body.pop()  # the next section's title
                    break
                body.append(line)
            return _bullets(body)
    return []


def _bullets(lines: List[str]) -> List[str]:
    items, cur = [], []
    for line in lines + ['']:
        s = line.strip()
        if s.startswith('- ') or not s:
            if cur:
                items.append(' '.join(cur))
            cur = [s[2:]] if s.startswith('- ') else []
        else:
            cur.append(s)
    return items


def _guide_section_bullets(path: Path, heading: str) -> List[str]:
    """The bullets of the guide section titled ``heading`` (a markdown ### heading)."""
    if not path.exists():
        return []
    lines, out, inside = path.read_text().splitlines(), [], False
    for line in lines:
        if line.startswith('#'):
            if inside:
                break
            inside = line.lstrip('#').strip() == heading
            continue
        if inside and line.startswith('- '):
            out.append(line[2:].strip())
    return out


def collect_limits(guide: Path = GUIDE) -> List[Dict[str, str]]:
    """The documented limits of both checks: the module docstring's Limits section and the guide's lists."""
    from edgar.xbrl import statement_fidelity
    limits = [{'source': 'edgar/xbrl/statement_fidelity.py, Limits', 'text': t}
              for t in _docstring_section(statement_fidelity.__doc__, 'Limits')]
    for heading in ('What the comparison does not check', 'Compare the statements edgartools builds'):
        limits += [{'source': f'{_relative(guide)}, "{heading}"', 'text': t}
                   for t in _guide_section_bullets(guide, heading)]
    return limits


def headline_definitions() -> List[str]:
    from edgar.xbrl import statement_fidelity
    return _docstring_section(statement_fidelity.__doc__, 'Headline')


def _relative(p: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def library_provenance() -> Dict[str, Any]:
    """The library version, where it was imported from, and the git commit of its checkout."""
    import edgar
    from edgar.__about__ import __version__
    src = Path(edgar.__file__).resolve().parent
    info = {'version': __version__, 'imported_from': str(src), 'commit': None, 'uncommitted_files': None}
    try:
        top = subprocess.run(['git', '-C', str(src), 'rev-parse', '--show-toplevel'], capture_output=True,
                             text=True, check=True).stdout.strip()
        info['commit'] = subprocess.run(['git', '-C', top, 'rev-parse', 'HEAD'], capture_output=True, text=True,
                                        check=True).stdout.strip()
        status = subprocess.run(['git', '-C', top, 'status', '--porcelain', '--', 'edgar'], capture_output=True,
                                text=True, check=True).stdout.splitlines()
        info['uncommitted_files'] = [s[3:] for s in status]
    except (OSError, subprocess.CalledProcessError):
        pass  # not a git checkout (an installed package): the version is what identifies it
    return info


CELL_EXTRA = ['accession']
OUTCOME_EXTRA = ['accession', 'fact_status']
PAGE_FIELDS = ['accession', 'page', 'role', 'access', 'compared', 'cells', 'reason']


class ScorecardWriter:
    """
    Streams each filing's outcomes to CSV as it is added and keeps the pooled counts for the scorecard.

    ``add(run)`` appends to cells.csv, outcomes.csv, pages.csv and filings.csv; ``finish()`` writes
    scorecard.json and scorecard.md and returns the scorecard dict.
    """

    def __init__(self, out: Path, sample_definition: Dict[str, Any], *,
                 provenance: Optional[Dict[str, Any]] = None, limits: Optional[List[Dict[str, str]]] = None,
                 definitions: Optional[List[str]] = None):
        from edgar.xbrl.statement_fidelity import KINDS, SURFACES
        self.kinds, self.surfaces = KINDS, SURFACES
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.sample = sample_definition
        self.provenance = provenance if provenance is not None else library_provenance()
        self.limits = limits if limits is not None else collect_limits()
        self.definitions = definitions if definitions is not None else headline_definitions()
        self.started = time.time()
        self.runs: List[Dict[str, Any]] = []
        self.facts = Counter()
        self.not_comparable = Counter()
        self.missing = Counter()
        self.surface = {s: Counter() for s in SURFACES}
        self.families = {s: Counter() for s in SURFACES}
        self.kind_outcomes = {s: Counter() for s in SURFACES}
        self.kind_filings = {s: Counter() for s in SURFACES}
        self.facts_cols: Optional[List[str]] = None
        self.outcome_cols: Optional[List[str]] = None
        self._filings_fields = self._filing_fields()
        for name, fields in (('filings.csv', self._filings_fields), ('pages.csv', PAGE_FIELDS)):
            with open(self.out / name, 'w', newline='') as f:
                csv.writer(f).writerow(fields)
        for name in ('cells.csv', 'outcomes.csv'):
            (self.out / name).unlink(missing_ok=True)

    def _filing_fields(self) -> List[str]:
        fields = ['accession_number', 'form', 'era', 'group', 'topup', 'cik', 'company', 'outcome', 'has_viewer',
                  'error_type', 'error_message', 'error_stage', 'attempts', 'seconds',
                  'facts_cells', 'facts_matched', 'facts_mismatched', 'facts_missing', 'facts_not_comparable',
                  'facts_match_rate', 'facts_coverage', 'unread_statements',
                  'pages', 'pages_compared']
        for s in self.surfaces:
            fields += [f'{s}_compared_cells', f'{s}_cell_matched', f'{s}_value_rate', f'{s}_coverage',
                       f'{s}_disagreement', f'{s}_presentation', f'{s}_not_comparable']
        return fields + ['traceback']

    def _append(self, name: str, df, cols_attr: str):
        cols = getattr(self, cols_attr)
        if cols is None:
            cols = list(df.columns)
            setattr(self, cols_attr, cols)
        df = df.reindex(columns=cols)
        for c in df.columns:
            if df[c].dtype == object:
                df[c] = df[c].map(_cell)
        path = self.out / name
        df.to_csv(path, mode='a', header=not path.exists(), index=False)

    def add(self, run: FilingRun) -> None:
        r = run.row
        acc = r['accession_number']
        rec = {k: r.get(k, '') for k in ('accession_number', 'form', 'era', 'group', 'topup', 'cik', 'company')}
        rec.update(outcome=run.outcome, has_viewer=run.has_viewer, error_type=run.error_type,
                   error_message=run.error_message, error_stage=run.error_stage, attempts=run.attempts,
                   seconds=run.seconds, traceback=run.traceback)
        facts, st = run.facts, run.statements
        if facts is not None:
            rec.update(facts_cells=facts.total, facts_matched=facts.matched, facts_mismatched=facts.mismatched,
                       facts_missing=facts.missing, facts_not_comparable=facts.not_comparable,
                       facts_match_rate=round(facts.match_rate, 6), facts_coverage=round(facts.coverage, 6),
                       unread_statements=len(facts.unread_statements))
            self.facts.update(filings=1, cells=facts.total, matched=facts.matched, mismatched=facts.mismatched,
                              missing=facts.missing, not_comparable=facts.not_comparable,
                              unread_statements=len(facts.unread_statements))
            for c in facts.results:
                if c.status == 'not_comparable':
                    self.not_comparable[reason_pattern(c.reason)] += 1
                elif c.status == 'missing':
                    self.missing[reason_pattern(c.reason)] += 1
            df = facts.to_dataframe()
            if len(df):
                df.insert(0, 'accession', acc)
                self._append('cells.csv', df, 'facts_cols')
        if st is not None:
            rec.update(pages=len(st.pages), pages_compared=sum(1 for p in st.pages if p.compared))
            self.surface_filings = getattr(self, 'surface_filings', 0) + 1
            for s in self.surfaces:
                compared = st.compared_cells(s)
                matched = len(st.of_kind('cell_matched', s))
                fam = st.family_counts(s)
                rec.update({f'{s}_compared_cells': compared, f'{s}_cell_matched': matched,
                            f'{s}_value_rate': round(st.value_rate(s), 6), f'{s}_coverage': round(st.coverage(s), 6),
                            f'{s}_disagreement': fam.get('disagreement', 0),
                            f'{s}_presentation': fam.get('presentation', 0),
                            f'{s}_not_comparable': fam.get('not_comparable', 0)})
                self.surface[s].update(compared_cells=compared, cell_matched=matched, facts_cells=st.facts.total)
                self.families[s].update(fam)
                kinds = Counter(o.kind for o in st.results if o.surface in (s, ''))
                self.kind_outcomes[s].update(kinds)
                self.kind_filings[s].update(kinds.keys())
            df = st.to_dataframe()
            if len(df):
                df.insert(0, 'accession', acc)
                df.insert(1, 'fact_status', [o.fact.status if o.fact is not None else None for o in st.results])
                self._append('outcomes.csv', df, 'outcome_cols')
            with open(self.out / 'pages.csv', 'a', newline='') as f:
                w = csv.writer(f)
                for p in st.pages:
                    w.writerow([acc, p.page, p.role, p.access, p.compared, p.cells, p.reason])
        with open(self.out / 'filings.csv', 'a', newline='') as f:
            csv.DictWriter(f, fieldnames=self._filings_fields, extrasaction='ignore').writerow(rec)
        self.runs.append({'outcome': run.outcome, 'has_viewer': run.has_viewer, 'seconds': run.seconds,
                          'error_type': run.error_type, 'error_stage': run.error_stage,
                          'topup': int(r.get('topup') or 0)})

    # ------------------------------------------------------------------------------------------

    def scorecard(self) -> Dict[str, Any]:
        runs = self.runs
        outcomes = Counter(x['outcome'] for x in runs)
        seconds = sorted(x['seconds'] for x in runs)
        f = self.facts
        compared_facts = f['matched'] + f['mismatched']
        statement = {}
        for s in self.surfaces:
            c = self.surface[s]
            statement[s] = {
                'compared_cells': c['compared_cells'], 'cell_matched': c['cell_matched'],
                'facts_cells': c['facts_cells'],
                'value_rate': _rate(c['cell_matched'], c['compared_cells']),
                'coverage': _rate(c['compared_cells'], c['facts_cells']),
                'families': {fam: self.families[s].get(fam, 0)
                             for fam in ('disagreement', 'presentation', 'not_comparable', 'matched')},
                'kinds': [{'kind': k, 'family': fam, 'level': lvl, 'outcomes': self.kind_outcomes[s].get(k, 0),
                           'filings': self.kind_filings[s].get(k, 0)} for k, (fam, lvl, _t) in self.kinds.items()],
            }
        return {
            'generated': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'library': self.provenance,
            'sample': dict(self.sample, run={
                'filings': len(runs),
                'with_viewer': sum(1 for x in runs if x['has_viewer']),
                'compared': outcomes.get('ok', 0),
                'no_viewer': outcomes.get('no_viewer', 0),
                'no_xbrl': outcomes.get('no_xbrl', 0),
                'errors': outcomes.get('error', 0),
                'errors_by_type': dict(Counter(f"{x['error_type']} ({x['error_stage']})"
                                               for x in runs if x['outcome'] == 'error')),
                'compared_topup': sum(1 for x in runs if x['outcome'] == 'ok' and x['topup']),
            }),
            'run_time': {
                'seconds_total': round(time.time() - self.started, 1),
                'seconds_per_filing_mean': round(sum(seconds) / len(seconds), 1) if seconds else None,
                'seconds_per_filing_median': seconds[len(seconds) // 2] if seconds else None,
                'seconds_per_filing_max': seconds[-1] if seconds else None,
            },
            'facts_check': {
                'filings': f['filings'], 'cells': f['cells'], 'matched': f['matched'], 'mismatched': f['mismatched'],
                'missing': f['missing'], 'not_comparable': f['not_comparable'],
                'unread_statements': f['unread_statements'],
                'match_rate': _rate(f['matched'], compared_facts), 'coverage': _rate(compared_facts, f['cells']),
                'missing_by_reason': dict(self.missing.most_common()),
                'not_comparable_by_reason': dict(self.not_comparable.most_common()),
            },
            'statement_check': {'filings': getattr(self, 'surface_filings', 0), 'surfaces': statement,
                                'definitions': self.definitions},
            'limits': self.limits,
        }

    def finish(self) -> Dict[str, Any]:
        card = self.scorecard()
        (self.out / 'scorecard.json').write_text(json.dumps(card, indent=2, default=str))
        (self.out / 'scorecard.md').write_text(render_markdown(card))
        return card


def _table(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> List[str]:
    out = ['| ' + ' | '.join(header) + ' |', '|' + '|'.join('---' for _ in header) + '|']
    out += ['| ' + ' | '.join(str(c).replace('|', '\\|') for c in row) + ' |' for row in rows]
    return out


def render_markdown(card: Dict[str, Any]) -> str:
    s, lib, fc, sc = card['sample'], card['library'], card['facts_check'], card['statement_check']
    run, rt = s['run'], card['run_time']
    md = ['# As-filed fidelity scorecard', '']
    commit = lib.get('commit') or 'not a git checkout'
    dirty = lib.get('uncommitted_files')
    md += [f"edgartools {lib['version']}, commit `{commit}`"
           + (f", with {len(dirty)} uncommitted file(s) under edgar/" if dirty else '')
           + f". Generated {card['generated']}.", '']
    md += ['## Sample', '']
    md += [f"Seed {s['seed']}; original 10-K, 10-Q, 20-F and 40-F filings filed {s['start']} to {s['end']}; "
           f"{s['random']} drawn at random by form and era plus {s['topup']} top-up filing(s) for thin SIC groups "
           f"({s['filings_drawn']} in all). "
           f"Excluded: {s['excluded_accessions']} accession(s), {s['excluded_ciks']} CIK(s). "
           f"SIC lookups that failed (filer counted as unknown): {s.get('sic_lookup_failures', 0)}.", '']
    md += _table(['Stratum', 'Population', 'Planned', 'Drawn'],
                 [(k, s['population_by_stratum'][k], s['planned_by_stratum'][k], s['drawn_by_stratum'].get(k, 0))
                  for k in s['population_by_stratum']])
    md += ['']
    groups = sorted(set(s['drawn_by_group']) | set(s['group_minimums']))
    md += _table(['SIC group', 'Minimum', 'Drawn', 'Of which top-up'],
                 [(g, s['group_minimums'].get(g, '-'), s['drawn_by_group'].get(g, 0), s['topup_by_group'].get(g, 0))
                  for g in groups])
    md += ['']
    md += _table(['Filings drawn', 'With viewer', 'Compared', 'No viewer', 'No XBRL', 'Errors'],
                 [(run['filings'], run['with_viewer'], run['compared'], run['no_viewer'], run['no_xbrl'],
                   run['errors'])])
    if run['errors_by_type']:
        md += ['', 'Errors by type (stage): ' + '; '.join(f"{k}: {v}" for k, v in run['errors_by_type'].items())
               + '. Messages are in filings.csv.']
    md += ['', f"Run time: {rt['seconds_total']} s in all; per filing mean {rt['seconds_per_filing_mean']} s, "
               f"median {rt['seconds_per_filing_median']} s, max {rt['seconds_per_filing_max']} s.", '']

    md += ['## Facts check (`viewer.compare`)', '',
           'Each numeric cell of the statement pages against the XBRL fact it shows, pooled over '
           f"{fc['filings']} compared filing(s); filings with an error, no viewer or no XBRL are not in it. Match rate is matched over matched plus mismatched; coverage is matched "
           'plus mismatched over all cells.', '']
    md += _table(['Cells', 'Matched', 'Mismatched', 'Missing', 'Not comparable', 'Match rate', 'Coverage'],
                 [(fc['cells'], fc['matched'], fc['mismatched'], fc['missing'], fc['not_comparable'],
                   _pct(fc['match_rate']), _pct(fc['coverage']))])
    if fc['unread_statements']:
        md += ['', f"{fc['unread_statements']} statement page(s) could not be read and are not in the cells."]
    for title, key in (('Not comparable by reason', 'not_comparable_by_reason'), ('Missing by reason', 'missing_by_reason')):
        if fc[key]:
            md += ['', f"{title} (quoted values and numbers shown as <v> and <n>):", '']
            md += _table(['Cells', 'Reason'], [(n, reason) for reason, n in fc[key].items()])

    outside = run['filings'] - run['compared']
    md += ['', '## Statement check (`viewer.compare_statements`)', '',
           f"The library's statements against the same pages, pooled over {sc['filings']} filing(s). "
           f"The {outside} filing(s) with an error, no viewer or no XBRL are outside both checks' rates "
           f"(errors {run['errors']}, no viewer {run['no_viewer']}, no XBRL {run['no_xbrl']}). "
           'Definitions, from the `edgar.xbrl.statement_fidelity` docstring:', '']
    md += [d if d.endswith(':') else f"- {d}" for d in sc['definitions']]
    md += ['']
    surfaces = sc['surfaces']
    md += _table(['Surface', 'Compared cells', 'Cell matched', 'Value rate', 'Page cells', 'Coverage',
                  'Disagreement', 'Presentation', 'Not comparable', 'Matched outcomes'],
                 [(name, v['compared_cells'], v['cell_matched'], _pct(v['value_rate']), v['facts_cells'],
                   _pct(v['coverage']), v['families']['disagreement'], v['families']['presentation'],
                   v['families']['not_comparable'], v['families']['matched']) for name, v in surfaces.items()])
    md += ['', 'Outcomes by kind; each surface counts the outcomes not tied to a surface too. '
               '"Filings" is the number of filings the kind appears in.', '']
    names = list(surfaces)
    header = ['Kind', 'Family', 'Level'] + [f"{n} {c}" for n in names for c in ('outcomes', 'filings')]
    by_kind = {n: {k['kind']: k for k in surfaces[n]['kinds']} for n in names}
    first = surfaces[names[0]]['kinds'] if names else []
    md += _table(header, [[k['kind'], k['family'], k['level']]
                          + [x for n in names for x in (by_kind[n][k['kind']]['outcomes'],
                                                        by_kind[n][k['kind']]['filings'])]
                          for k in first])
    md += ['', '## Limits', '', 'As documented; the scorecard measures nothing beyond them.', '']
    md += [f"- {lim['text']} ({lim['source']})" for lim in card['limits']]
    md += ['']
    return '\n'.join(md)


# --------------------------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------------------------

def _date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{s!r} is not a date (YYYY-MM-DD)") from None


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0].strip(),
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--seed', type=int, required=True, help='random seed for the draw')
    p.add_argument('--size', type=int, required=True, help='filings in the random draw (the top-up adds to it)')
    p.add_argument('--start', type=_date, default=DEFAULT_START, help=f'first filing date (default {DEFAULT_START})')
    p.add_argument('--end', type=_date, required=True, help='last filing date, in the past')
    p.add_argument('--era-split', type=int, nargs='*', default=list(DEFAULT_ERA_SPLITS),
                   help='years at which a new era starts (default %(default)s)')
    p.add_argument('--exclude', type=Path, help='file of accession numbers and/or CIKs never to draw')
    p.add_argument('--out', type=Path, required=True, help='output directory')
    p.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT, help='seconds per filing attempt (default %(default)s)')
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        ex_acc, ex_cik = read_exclusions(args.exclude)
        sample = draw_sample(args.seed, args.size, args.start, args.end, exclude_accessions=ex_acc,
                             exclude_ciks=ex_cik, era_splits=args.era_split)
    except ScorecardError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    write_sample(sample, args.out)
    print(f"sample: {len(sample.rows)} filings ({sum(1 for r in sample.rows if r['topup'])} top-up) "
          f"-> {args.out / 'sample.csv'}", flush=True)
    writer = ScorecardWriter(args.out, sample.definition())
    for i, row in enumerate(sample.rows, 1):
        run = run_filing(row, timeout=args.timeout)
        writer.add(run)
        st = run.statements
        rates = '' if st is None else ' '.join(f"{s}={_pct(st.value_rate(s))}" for s in ('dataframe', 'rendered'))
        print(f"[{i}/{len(sample.rows)}] {row['accession_number']} {row['form']} {run.outcome}"
              f"{' ' + run.error_type if run.error_type else ''} {rates} {run.seconds}s", flush=True)
    writer.finish()
    print(f"scorecard -> {args.out / 'scorecard.md'}", flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
