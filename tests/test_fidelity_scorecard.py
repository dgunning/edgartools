"""Offline checks for scripts/fidelity_scorecard.py: the sampler and the scorecard writer.

The writer is fed a stubbed result set built from the library's own result classes
(``ComparisonResults``, ``StatementFidelityResults``), so every rate it prints is the
modules' definition applied to known counts. The sampler draws from a synthetic population.
"""
import csv
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest

from edgar.xbrl import viewer_validation as vv
from edgar.xbrl.statement_fidelity import (
    KINDS,
    StatementFidelityPage,
    StatementFidelityResult,
    StatementFidelityResults,
)

pytestmark = pytest.mark.fast

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "fidelity_scorecard.py"
_spec = importlib.util.spec_from_file_location("fidelity_scorecard", SCRIPT)
sc = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = sc   # dataclasses look their module up by name
_spec.loader.exec_module(sc)


def _cell(status, reason=None, concept='us-gaap:Revenues'):
    match = status == 'matched'
    return vv.ComparisonResult(concept_id=concept, label='Revenues', period='12 Months Ended Dec. 31, 2024',
                               viewer_value=100.0, xbrl_value=100.0 if status in ('matched', 'mismatched') else None,
                               difference=0.0, match=match, report='R2.htm', status=status, reason=reason)


def _outcome(kind, surface, fact=None):
    return StatementFidelityResult(kind=kind, page='INCOME', role='r', surface=surface, concept='us-gaap:Revenues',
                                   fact=fact)


def _ok_run(accession):
    """A filing with 6 page cells: 3 matched, 1 mismatched, 1 missing, 1 not comparable."""
    cells = [_cell('matched'), _cell('matched'), _cell('matched'), _cell('mismatched'),
             _cell('missing', 'no XBRL fact for this concept'),
             _cell('not_comparable', "value 'abc' cannot be read as a number")]
    facts = vv.ComparisonResults(results=cells)
    statements = StatementFidelityResults(facts=facts, pages=[
        StatementFidelityPage('INCOME', 'r', 'income_statement()', True, 6),
        StatementFidelityPage('EQUITY', 'e', 'statement_of_equity()', False, 0, 'equity layout')])
    statements.results = [
        _outcome('cell_matched', 'dataframe', cells[0]), _outcome('cell_matched', 'dataframe', cells[1]),
        _outcome('value_differs', 'dataframe', cells[2]),
        _outcome('cell_matched', 'rendered', cells[0]), _outcome('library_raised', 'rendered', cells[1]),
        _outcome('unit_column_not_shown', 'rendered', cells[2]),
        _outcome('page_not_compared', ''),
    ]
    row = {'accession_number': accession, 'form': '10-K', 'era': '2024-2026', 'group': 'commercial', 'topup': 0,
           'cik': 1, 'company': 'Stub Co'}
    return sc.FilingRun(row=row, outcome='ok', has_viewer=True, facts=facts, statements=statements, seconds=4.0)


def _write(tmp_path, runs):
    writer = sc.ScorecardWriter(tmp_path, {'seed': 7, 'size': 3, 'start': '2020-01-01', 'end': '2026-09-30',
                                           'random': 3, 'topup': 0, 'filings_drawn': 3,
                                           'excluded_accessions': 0, 'excluded_ciks': 0,
                                           'population_by_stratum': {'10-K 2024-2026': 10},
                                           'planned_by_stratum': {'10-K 2024-2026': 3},
                                           'drawn_by_stratum': {'10-K 2024-2026': 3},
                                           'group_minimums': {'bank': 1}, 'drawn_by_group': {'commercial': 3},
                                           'topup_by_group': {}},
                                provenance={'version': '0.0.test', 'commit': 'abc123', 'uncommitted_files': []})
    for run in runs:
        writer.add(run)
    return writer.finish()


def test_scorecard_pools_both_checks(tmp_path):
    error = sc.FilingRun(row={'accession_number': '0000000002-24-000002', 'form': '10-Q', 'topup': 1},
                         outcome='error', has_viewer=True, error_type='TypeError', error_stage='statement check',
                         error_message='boom', seconds=2.0)
    no_viewer = sc.FilingRun(row={'accession_number': '0000000003-24-000003', 'form': '20-F', 'topup': 0},
                             outcome='no_viewer', has_viewer=False, seconds=1.0)
    card = _write(tmp_path, [_ok_run('0000000001-24-000001'), error, no_viewer])

    run = card['sample']['run']
    assert (run['filings'], run['with_viewer'], run['compared'], run['no_viewer'], run['errors']) == (3, 2, 1, 1, 1)
    assert run['errors_by_type'] == {'TypeError (statement check)': 1}

    facts = card['facts_check']
    assert (facts['cells'], facts['matched'], facts['mismatched'], facts['missing'], facts['not_comparable']) == (
        6, 3, 1, 1, 1)
    assert facts['match_rate'] == 3 / 4 and facts['coverage'] == 4 / 6
    assert facts['not_comparable_by_reason'] == {'value <v> cannot be read as a number': 1}
    assert facts['missing_by_reason'] == {'no XBRL fact for this concept': 1}

    df, rendered = card['statement_check']['surfaces']['dataframe'], card['statement_check']['surfaces']['rendered']
    assert (df['compared_cells'], df['cell_matched'], df['value_rate'], df['coverage']) == (3, 2, 2 / 3, 3 / 6)
    # library_raised is in the denominator; unit_column_not_shown is not.
    assert (rendered['compared_cells'], rendered['cell_matched'], rendered['value_rate']) == (2, 1, 1 / 2)
    kinds = {k['kind']: k for k in df['kinds']}
    assert set(kinds) == set(KINDS)
    assert (kinds['cell_matched']['outcomes'], kinds['cell_matched']['filings']) == (2, 1)
    # A surface-independent outcome counts on every surface, as family_counts does.
    assert kinds['page_not_compared']['outcomes'] == 1
    assert df['families'] == {'disagreement': 1, 'presentation': 0, 'not_comparable': 1, 'matched': 2}

    assert card['library'] == {'version': '0.0.test', 'commit': 'abc123', 'uncommitted_files': []}
    assert card['run_time']['seconds_per_filing_median'] == 2.0
    assert json.loads((tmp_path / 'scorecard.json').read_text())['facts_check']['cells'] == 6


def test_scorecard_files(tmp_path):
    _write(tmp_path, [_ok_run('0000000001-24-000001'), _ok_run('0000000004-24-000004')])
    with open(tmp_path / 'cells.csv') as f:
        cells = list(csv.DictReader(f))
    with open(tmp_path / 'outcomes.csv') as f:
        outcomes = list(csv.DictReader(f))
    with open(tmp_path / 'filings.csv') as f:
        filings = list(csv.DictReader(f))
    assert len(cells) == 12 and {c['accession'] for c in cells} == {'0000000001-24-000001', '0000000004-24-000004'}
    assert len(outcomes) == 14 and outcomes[0]['fact_status'] == 'matched'
    assert [f['dataframe_value_rate'] for f in filings] == ['0.666667', '0.666667']
    md = (tmp_path / 'scorecard.md').read_text()
    assert '| 12 | 6 | 2 | 2 | 2 | 75.00% | 66.67% |' in md
    assert '| dataframe | 6 | 4 | 66.67% | 12 | 50.00% |' in md
    assert '## Limits' in md and 'commit `abc123`' in md


def test_limits_are_read_from_the_module_and_the_guide():
    limits = sc.collect_limits()
    sources = {lim['source'].split(',')[0] for lim in limits}
    assert sources == {'edgar/xbrl/statement_fidelity.py', 'docs/guides/sec-viewer-guide.md'}
    texts = [lim['text'] for lim in limits]
    assert any(t.startswith('Statement-of-equity pages (member columns') for t in texts)
    assert any(t.startswith('Only statement pages are compared') for t in texts)
    definitions = sc.headline_definitions()
    assert definitions[0] == 'Per surface:'
    assert [d.split('``')[1] for d in definitions[1:4]] == [
        'compared_cells(surface)', 'value_rate(surface)', 'coverage(surface)']


POPULATION = [
    {'form': form, 'company': f'Co {i}', 'cik': 1000 + i, 'filing_date': date(year, 3, 1 + i % 20),
     'accession_number': f'{1000 + i:010d}-{year % 100:02d}-{i:06d}'}
    for i, (form, year) in enumerate([(f, y) for f in ('10-K', '10-Q', '20-F', '40-F')
                                      for y in (2020, 2021, 2024, 2025) for _ in range(5)])
]


def _sic(cik):
    return '6022' if cik % 7 == 0 else '3571'   # banks are thin


def test_draw_is_reproducible_and_stratified():
    a = sc.draw_sample(11, 12, date(2020, 1, 1), date(2025, 12, 31), population=POPULATION, sic_lookup=_sic)
    b = sc.draw_sample(11, 12, date(2020, 1, 1), date(2025, 12, 31), population=list(reversed(POPULATION)),
                       sic_lookup=_sic)
    assert [r['accession_number'] for r in a.rows] == [r['accession_number'] for r in b.rows]
    # Weights per stratum (form weight over two eras) 10, 11, 1 and 0.5 of 45: 10-K 2.67 and 10-Q 2.93
    # round up by largest remainder, 20-F 0.27 and 40-F 0.13 get none.
    assert a.planned == {'10-K 2020-2023': 3, '10-K 2024-2025': 3, '10-Q 2020-2023': 3, '10-Q 2024-2025': 3,
                         '20-F 2020-2023': 0, '20-F 2024-2025': 0, '40-F 2020-2023': 0, '40-F 2024-2025': 0}
    assert sum(1 for r in a.rows if not r['topup']) == 12
    # The random draw already has 3 banks, over the minimum of ceil(0.025 x 12) = 1: no top-up.
    assert sum(1 for r in a.rows if r['group'] == 'bank') == 3 and not any(r['topup'] for r in a.rows)
    assert all(r['seed'] == 11 for r in a.rows)
    c = sc.draw_sample(12, 12, date(2020, 1, 1), date(2025, 12, 31), population=POPULATION, sic_lookup=_sic)
    assert [r['accession_number'] for r in a.rows] != [r['accession_number'] for r in c.rows]


def test_topup_adds_a_flagged_filing_for_a_thin_group():
    drawn = sc.draw_sample(11, 12, date(2020, 1, 1), date(2025, 12, 31), population=POPULATION,
                           sic_lookup=lambda cik: '3571')
    bank = next(r for r in POPULATION if r['accession_number'] not in {x['accession_number'] for x in drawn.rows})
    s = sc.draw_sample(11, 12, date(2020, 1, 1), date(2025, 12, 31), population=POPULATION,
                       sic_lookup=lambda cik: '6022' if cik == bank['cik'] else '3571')
    assert sorted(r['accession_number'] for r in s.rows if not r['topup']) == sorted(
        r['accession_number'] for r in drawn.rows)
    assert [(r['accession_number'], r['group']) for r in s.rows if r['topup']] == [(bank['accession_number'], 'bank')]
    assert s.definition()['topup_by_group'] == {'bank': 1}


def test_exclusions_and_bad_input(tmp_path):
    excluded = tmp_path / 'seen.txt'
    excluded.write_text('# earlier samples\n0001000000-20-000000\n000100000120000001\n1002\n')
    accessions, ciks = sc.read_exclusions(excluded)
    assert accessions == {'0001000000-20-000000', '0001000001-20-000001'} and ciks == {1002}
    s = sc.draw_sample(3, 20, date(2020, 1, 1), date(2025, 12, 31), population=POPULATION, sic_lookup=_sic,
                       exclude_accessions=accessions, exclude_ciks=ciks)
    drawn = {r['accession_number'] for r in s.rows}
    assert not drawn & accessions and all(int(r['cik']) != 1002 for r in s.rows)

    excluded.write_text('AAPL\n')
    with pytest.raises(sc.ScorecardError, match="seen.txt:1: 'AAPL' is neither an accession number"):
        sc.read_exclusions(excluded)
    with pytest.raises(sc.ScorecardError, match='is after --end'):
        sc.draw_sample(1, 5, date(2025, 1, 1), date(2024, 1, 1), population=POPULATION, sic_lookup=_sic)
    with pytest.raises(sc.ScorecardError, match='not in the past'):
        sc.draw_sample(1, 5, date(2020, 1, 1), date(2999, 1, 1), population=POPULATION, sic_lookup=_sic)


def test_sic_groups():
    assert [sc.sic_group(s) for s in ('6021', '6311', '6798', '4911', '6726', '3571', '', None)] == [
        'bank', 'insurer', 'reit', 'utility', 'fund_like', 'commercial', 'unknown', 'unknown']


def test_run_filing_computes_the_facts_check_once(monkeypatch):
    """Good Times 10-Q (0001214659-22-006372), from the statement-fidelity fixtures: one facts check per filing,
    shared by both checks."""
    from types import SimpleNamespace

    import edgar
    from tests.xbrl.statement_fidelity_fixtures import fixture_viewer_and_xbrl
    viewer, xbrl = fixture_viewer_and_xbrl('0001214659-22-006372')
    calls = []
    original = vv._facts_check

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(vv, '_facts_check', counted)
    monkeypatch.setattr(edgar, 'find', lambda accession: SimpleNamespace(viewer=viewer, xbrl=lambda: xbrl))
    run = sc.run_filing({'accession_number': '0001214659-22-006372'}, timeout=0)
    assert run.outcome == 'ok' and len(calls) == 1
    assert run.facts is run.statements.facts
    assert (run.facts.total, run.statements.compared_cells('dataframe')) == (54, 54)   # the fixture holds the cash-flow page only


def test_coregistrant_rows_are_one_filing():
    """The index lists a filing once per co-registrant: the draw keeps one row per accession, under the lowest
    CIK, whatever order the rows come in, and names the other CIKs."""
    import random as _random
    repeated = POPULATION + [dict(r, cik=r['cik'] + 5000, company=f"{r['company']} Sub") for r in POPULATION[::3]]
    shuffled = list(repeated)
    _random.Random(5).shuffle(shuffled)
    a = sc.draw_sample(11, 12, date(2020, 1, 1), date(2025, 12, 31), population=POPULATION, sic_lookup=_sic)
    b = sc.draw_sample(11, 12, date(2020, 1, 1), date(2025, 12, 31), population=repeated, sic_lookup=_sic)
    c = sc.draw_sample(11, 12, date(2020, 1, 1), date(2025, 12, 31), population=shuffled, sic_lookup=_sic)
    assert [r['accession_number'] for r in a.rows] == [r['accession_number'] for r in b.rows] == [
        r['accession_number'] for r in c.rows]
    assert [r['cik'] for r in b.rows] == [r['cik'] for r in a.rows]
    assert [r['co_registrant_ciks'] for r in c.rows] == [
        str(r['cik'] + 5000) if (r['cik'] - 1000) % 3 == 0 else '' for r in a.rows]
    assert sum(b.population.values()) == len(POPULATION)


def test_sic_lookup_failures_are_counted(tmp_path):
    def flaky(cik):
        if cik % 2:
            raise ConnectionError('no submissions')
        return '3571'
    s = sc.draw_sample(11, 12, date(2020, 1, 1), date(2025, 12, 31), population=POPULATION, sic_lookup=flaky)
    failed = {int(r['cik']) for r in s.rows if r['group'] == 'unknown'}
    assert failed and s.sic_lookup_failures >= len(failed)
    assert s.definition()['sic_lookup_failures'] == s.sic_lookup_failures
    writer = sc.ScorecardWriter(tmp_path, s.definition(), provenance={'version': 'x', 'commit': None,
                                                                      'uncommitted_files': None})
    writer.add(_ok_run('0000000001-24-000001'))
    writer.add(sc.FilingRun(row={'accession_number': '0000000003-24-000003', 'topup': 0}, outcome='no_viewer',
                            has_viewer=False))
    writer.finish()
    md = (tmp_path / 'scorecard.md').read_text()
    assert f"SIC lookups that failed (filer counted as unknown): {s.sic_lookup_failures}." in md
    assert "The 1 filing(s) with an error, no viewer or no XBRL are outside both checks' rates " \
           "(errors 0, no viewer 1, no XBRL 0)." in md


def test_a_timeout_while_recording_a_failure_does_not_escape(monkeypatch):
    """The alarm firing inside the failure handling is recorded as the filing's error."""
    import edgar

    def find(accession):
        raise ConnectionError('reset')
    monkeypatch.setattr(edgar, 'find', find)
    monkeypatch.setattr(sc, '_transient', lambda e: (_ for _ in ()).throw(sc._FilingTimeoutError('late alarm')))
    run = sc.run_filing({'accession_number': '0000000001-24-000001'}, timeout=0)
    assert (run.outcome, run.error_type, run.attempts) == ('error', '_FilingTimeoutError', 1)


def test_a_network_error_is_retried_once(monkeypatch):
    import edgar
    calls = []

    def find(accession):
        calls.append(accession)
        raise ConnectionError('reset')
    monkeypatch.setattr(edgar, 'find', find)
    monkeypatch.setattr(sc, 'RETRY_PAUSE', 0)
    run = sc.run_filing({'accession_number': '0000000001-24-000001'}, timeout=0)
    assert (len(calls), run.attempts, run.error_type, run.error_stage) == (2, 2, 'ConnectionError', 'find')
