"""Enumerate every space the tag allowlist still provides that the CSS-gap rule does not.

This is the list that decides whether ParagraphNode.text()'s allowlist can be deleted.
After the CSS-gap rule landed (398c0bc0) it is 257 spaces across 57 fixtures — small
enough to read in full, unlike the 8,109 the allowlist provides in total.

Renders each fixture twice: as shipped (CSS gap + allowlist) and with the allowlist
removed (CSS gap only). Both renderings differ only in spacing, so gap positions are
compared against the space-stripped line — which, unlike a character walk, does not lose
its place on a line that both gains and loses a space.

Each residual space is then located in the raw HTML and reported with the CSS on both
sides, so the shapes can be counted and given a principled signal of their own.
"""
import html as htmllib
import re
import sys
import warnings
from collections import Counter
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
from variants import make_text  # noqa: E402

from edgar.documents import HTMLParser, ParserConfig  # noqa: E402
from edgar.documents.nodes import ParagraphNode  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "tests/fixtures/html"
ORIGINAL = ParagraphNode.text
TAG = re.compile(r'<[^>]*>')
OPEN_TAG = re.compile(r'<\s*([A-Za-z0-9:_-]+)([^>]*)>')
BETWEEN = r'((?:\s|<[^>]*>)*?)'


def gap_positions(line: str) -> dict:
    """Map index-in-stripped-line -> True for every space in `line`.

    A space at stripped index i means 'there is a gap before the i-th non-space
    character'. Two renderings of the same line share a stripped form, so these
    indices are directly comparable.
    """
    out = {}
    i = 0
    for ch in line:
        if ch == ' ':
            out[i] = True
        else:
            i += 1
    return out


def words_around(line: str, stripped_index: int):
    """The words either side of the gap at `stripped_index` in `line`."""
    i = 0
    for pos, ch in enumerate(line):
        if ch != ' ':
            if i == stripped_index:
                left = re.search(r'\S+$', line[:pos].rstrip() + '') or None
                # walk back over the space(s) to the preceding word
                before = line[:pos].rstrip()
                left = re.search(r'\S+$', before)
                right = re.match(r'\S+', line[pos:])
                return (left.group() if left else ''), (right.group() if right else '')
            i += 1
    return '', ''


def props(attrs: str) -> dict:
    m = re.search(r'style\s*=\s*"([^"]*)"', attrs, re.I)
    if not m:
        return {}
    out = {}
    for decl in m.group(1).split(';'):
        if ':' in decl:
            k, v = decl.split(':', 1)
            out[k.strip().lower()] = v.strip()
    return out


def nonzero(v: str) -> bool:
    m = re.match(r'\s*(-?[\d.]+)', v or '')
    return bool(m) and float(m.group(1)) > 0


def family(p: dict) -> str:
    """First font family, unquoted and folded — same normalisation as Style.font_family."""
    v = p.get('font-family', '')
    return v.split(',')[0].strip().strip('\'"').strip().lower()


def shape_of(doc: str, left: str, right: str):
    """Classify what separates `left` from `right` in the source, and how."""
    if not left or not right or len(left) > 40 or len(right) > 40:
        return 'unlocatable', ''
    m = re.search(re.escape(left) + BETWEEN + re.escape(right), doc)
    if not m:
        return 'unlocatable', ''
    gap = m.group(1)
    bare = TAG.sub('', gap)
    if bare.strip():
        return 'other-text', gap[:120]
    if bare:
        return 'whitespace-in-source', gap[:120]
    tags = TAG.findall(gap)
    if not tags:
        return 'nothing-at-all', ''
    names = [n.group(1).lower() for n in (OPEN_TAG.match(t) or re.match(r'</\s*([A-Za-z0-9:_-]+)', t)
             for t in tags) if n]
    names = []
    for t in tags:
        n = re.match(r'</?\s*([A-Za-z0-9:_-]+)', t)
        if n:
            names.append(n.group(1).lower())
    if any(n in ('br', 'hr') for n in names):
        return 'br-or-hr', gap[:120]
    if any(n in ('td', 'th', 'tr', 'table') for n in names):
        return 'table-cell', gap[:120]
    if any(n in ('p', 'div', 'li', 'ul', 'ol') or re.fullmatch(r'h[1-6]', n) for n in names):
        return 'block-boundary', gap[:120]

    opens = OPEN_TAG.findall(gap)
    rp = props(opens[-1][1]) if opens else {}
    back = doc[max(0, m.start() - 900):m.start()]
    lo = None
    for om in OPEN_TAG.finditer(back):
        lo = om
    lp = props(lo.group(2)) if lo else {}

    # Ordered by how directly the property draws the gap, most direct first. A
    # white-space:pre* declaration is checked LAST because it is nearly universal in
    # Word-exported filings and says nothing about this boundary on its own.
    if nonzero(rp.get('padding-left', '')) or nonzero(rp.get('margin-left', '')):
        return 'right-has-left-gap', str(rp)[:90]       # should not appear: shipped rule covers it
    if 'inline-block' in lp.get('display', '') and lp.get('width'):
        return 'left-is-fixed-width-marker-box', f"display={lp.get('display')} width={lp.get('width')}"
    if nonzero(lp.get('padding-right', '')) or nonzero(lp.get('margin-right', '')):
        return 'left-has-right-gap', str(lp)[:90]
    if nonzero(lp.get('text-indent', '')) or nonzero(rp.get('text-indent', '')):
        return 'text-indent', f"left={lp.get('text-indent')} right={rp.get('text-indent')}"
    lf, rf = family(lp), family(rp)
    if lf and rf and lf != rf:
        return 'typeface-change', f"{lf!r} -> {rf!r}"
    ws = (rp.get('white-space', '') + ' ' + lp.get('white-space', '')).strip()
    if 'pre' in ws:
        return 'white-space-pre-only', ws
    return 'no-signal', f"left={str(lp)[:60]} right={str(rp)[:60]}"


shapes = Counter()
examples = {}
total = 0
per_fixture = Counter()
cache = {}

for f in sorted(FIXTURES.rglob("*.html")):
    raw = f.read_text(errors="replace")
    try:
        ParagraphNode.text = ORIGINAL
        shipped = HTMLParser(ParserConfig()).parse(raw).text().splitlines()
        ParagraphNode.text = make_text(left_gap=True)
        cssonly = HTMLParser(ParserConfig()).parse(raw).text().splitlines()
    except Exception as e:
        print(f"ERROR {f.name}: {e}", flush=True)
        continue
    finally:
        ParagraphNode.text = ORIGINAL

    name = str(f.relative_to(FIXTURES))
    # Align line-for-line where possible; both renderings have the same line count in
    # practice, but fall back to a difflib alignment if a line re-wraps.
    import difflib
    sm = difflib.SequenceMatcher(None, shipped, cssonly, autojunk=False)
    pairs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'replace' and (i2 - i1) == (j2 - j1):
            pairs.extend(zip(shipped[i1:i2], cssonly[j1:j2]))
    for a, b in pairs:
        if a == b or a.replace(' ', '') != b.replace(' ', ''):
            continue
        ga, gb = gap_positions(a), gap_positions(b)
        removed = sorted(set(ga) - set(gb))
        if not removed:
            continue
        if f not in cache:
            cache[f] = htmllib.unescape(raw)
        doc = cache[f]
        for idx in removed:
            left, right = words_around(a, idx)
            kind, detail = shape_of(doc, left, right)
            shapes[kind] += 1
            total += 1
            per_fixture[name] += 1
            examples.setdefault(kind, []).append((name, left, right, detail))

print(f"\n=== {total} spaces the allowlist still provides that the CSS-gap rule does not\n")
for kind, n in shapes.most_common():
    print(f"  {n:4d}  {100 * n / max(total, 1):5.1f}%  {kind}")
print("\nby fixture:")
for name, n in per_fixture.most_common(12):
    print(f"  {n:4d}  {name}")
for kind in shapes:
    print(f"\n=== {kind} ({shapes[kind]})")
    for name, left, right, detail in examples[kind][:8]:
        print(f"  {name}: {left!r} | {right!r}")
        if detail:
            print(f"     {detail}")
