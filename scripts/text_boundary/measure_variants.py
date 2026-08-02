"""Diff each ParagraphNode.text() variant against the current implementation.

Runs over all 57 HTML fixtures and the 5 test_filing_text_baseline filings, and
classifies every changed line as space-gained / space-lost / content-changed.
"""
import difflib
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).parent))
from variants import VARIANTS, make_text  # noqa: E402

from edgar.documents import HTMLParser, ParserConfig  # noqa: E402
from edgar.documents.nodes import ParagraphNode  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "tests/fixtures/html"
BASELINE_TXT = Path(sys.argv[1]) if len(sys.argv) > 1 else None  # dir of current .txt for the 5 filings

ORIGINAL = ParagraphNode.text


def render_all():
    """Parse every fixture with whatever ParagraphNode.text is currently installed."""
    out = {}
    for f in sorted(FIXTURES.rglob("*.html")):
        name = str(f.relative_to(FIXTURES))
        try:
            doc = HTMLParser(ParserConfig()).parse(f.read_text(errors="replace"))
            out[name] = doc.text()
        except Exception as e:
            out[name] = f"__ERROR__ {type(e).__name__}: {e}"
    return out


def classify(old_text, new_text):
    old, new = old_text.splitlines(), new_text.splitlines()
    if old == new:
        return 0, 0, 0, []
    gained = lost = other = 0
    samples = []
    sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if tag == 'replace' and (i2 - i1) == (j2 - j1):
            for a, b in zip(old[i1:i2], new[j1:j2]):
                if a.replace(" ", "") == b.replace(" ", ""):
                    if len(b) > len(a):
                        gained += 1
                        if len(samples) < 6: samples.append(("GAINED", a, b))
                    elif len(b) < len(a):
                        lost += 1
                        if len(samples) < 6: samples.append(("LOST", a, b))
                else:
                    other += 1
                    if len(samples) < 6: samples.append(("CONTENT", a, b))
        else:
            other += (i2 - i1) + (j2 - j1)
            if len(samples) < 6:
                samples.append((f"STRUCT-{tag}", "\n".join(old[i1:i2])[:160], "\n".join(new[j1:j2])[:160]))
    return gained, lost, other, samples


print("rendering fixtures with CURRENT implementation...")
base = render_all()

for vname, kwargs in VARIANTS.items():
    ParagraphNode.text = make_text(**kwargs)
    got = render_all()
    ParagraphNode.text = ORIGINAL

    tg = tl = to = 0
    changed = []
    all_samples = []
    for name in base:
        g, l, o, s = classify(base[name], got[name])
        if g or l or o:
            changed.append((name, g, l, o))
            tg += g; tl += l; to += o
            all_samples.extend((name, *x) for x in s)
    print(f"\n=== {vname}: {len(changed)}/{len(base)} fixtures changed  "
          f"gained={tg} lost={tl} content/struct={to}")
    for name, g, l, o in changed[:12]:
        print(f"     {name}: +{g} -{l} other={o}")
    for name, kind, a, b in all_samples[:10]:
        print(f"   [{kind}] {name}\n     - {a[:170]}\n     + {b[:170]}")
