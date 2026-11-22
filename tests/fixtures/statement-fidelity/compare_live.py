"""Check that each statement-fidelity fixture reproduces the live filing's outcomes for its page.

Runs ``compare_statements_to_viewer`` on the live filing (one filing at a time)
and on the fixture, and compares the outcomes for the fixture's page as
multisets of every field of ``StatementFidelityResults.to_dataframe()``
(labels, values and reasons included), and the page's access path. Prints one line per fixture and the
differing outcomes; exits 1 when any fixture differs.

Usage: hatch run python tests/fixtures/statement-fidelity/compare_live.py [ACCESSION ...]
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

from edgar import find
from edgar.xbrl.viewer import FilingViewer

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tests.xbrl.statement_fidelity_fixtures import FIXTURE_DIR, fixture_viewer_and_xbrl  # noqa: E402


def normal(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return repr(float(value))  # one form for int and float columns; keeps -0.0
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def outcomes(results, role):
    frame = results.to_dataframe()
    return Counter(tuple((k, normal(v)) for k, v in sorted(rec.items()))
                   for rec in frame.to_dict('records') if rec['role'] == role)


def main(accessions) -> int:
    differing = 0
    for d in sorted(p for p in FIXTURE_DIR.iterdir() if p.is_dir()):
        if accessions and d.name not in accessions:
            continue
        manifest = json.loads((d / 'manifest.json').read_text())
        viewer, xbrl = fixture_viewer_and_xbrl(d.name)
        fixture_results = viewer.compare_statements(xbrl)
        fixture = outcomes(fixture_results, manifest['role'])
        filing = find(d.name)
        live_results = FilingViewer.from_filing(filing).compare_statements(filing.xbrl())
        live = outcomes(live_results, manifest['role'])
        only_fixture, only_live = fixture - live, live - fixture
        # The page's statement must be reached the same way (typed getter or by role).
        access = {p.access for p in fixture_results.pages}, {p.access for p in live_results.pages
                                                            if p.role == manifest['role']}
        if access[0] != access[1]:
            print('  access differs: fixture', access[0], 'live', access[1])  # noqa: T201
            differing += 1
        print(d.name, manifest['short_name'], 'outcomes', sum(fixture.values()), 'live', sum(live.values()),  # noqa: T201
              'only fixture', sum(only_fixture.values()), 'only live', sum(only_live.values()))
        for tag, diff in (('fixture', only_fixture), ('live', only_live)):
            for record, n in list(diff.items())[:5]:
                print(f'  only {tag} x{n}:', dict(record))  # noqa: T201
        differing += bool(only_fixture or only_live)
    return 1 if differing else 0


if __name__ == '__main__':
    sys.exit(main(set(sys.argv[1:])))
