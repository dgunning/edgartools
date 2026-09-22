"""For the boundaries with only inline tags between them, is the gap drawn in CSS?

A bullet in its own span followed by its text in another span, with no whitespace
between them, renders as '•The Company' unless something else supplies the gap. Filers
supply it with CSS: a margin/padding on one side, a text-indent, or a list layout. This
reports which property is actually present, so we can tell whether ParagraphNode.text()'s
tag allowlist is compensating for something measurable (in which case honour that
instead) or is simply guessing.
"""
import html as htmllib
import json
import re
import sys
from collections import Counter
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "tests/fixtures/html"
records = json.loads(Path(sys.argv[1]).read_text())
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 1200

TAG = re.compile(r'<[^>]*>')
BETWEEN = r'((?:\s|<[^>]*>)*?)'
OPEN_TAG = re.compile(r'<\s*([A-Za-z0-9:_-]+)([^>]*)>')

GAP_PROPS = ('padding-left', 'margin-left', 'text-indent', 'padding-right',
             'margin-right', 'display', 'white-space')


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


def nonzero(value: str) -> bool:
    m = re.match(r'\s*(-?[\d.]+)', value or '')
    return bool(m) and float(m.group(1)) > 0


seen = {}
for rec in records:
    seen.setdefault((rec["fixture"], rec["left"], rec["right"]), [rec, 0])[1] += 1
work = list(seen.values())

cache = {}
verdict = Counter()
weighted = Counter()
detail = Counter()
examples = {}
skipped = 0

for i, (rec, weight) in enumerate(work):
    if i >= LIMIT:
        break
    left, right = rec["left"], rec["right"]
    if len(left) > 40 or len(right) > 40 or len(left) < 1:
        skipped += 1
        continue
    path = FIXTURES / rec["fixture"]
    if path not in cache:
        cache[path] = htmllib.unescape(path.read_text(errors="replace"))
    doc = cache[path]
    m = re.search(re.escape(left) + BETWEEN + re.escape(right), doc)
    if not m:
        skipped += 1
        continue
    gap = m.group(1)
    if TAG.sub('', gap).strip() or not TAG.findall(gap):
        skipped += 1          # not the inline-tags-only case; handled by allowlist_classify
        continue

    # the element that opens immediately before `right`, and the one that closed before it
    opens = OPEN_TAG.findall(gap)
    right_props = props(opens[-1][1]) if opens else {}
    # the left-hand element's own opening tag: walk back from the match start
    back = doc[max(0, m.start() - 900):m.start()]
    left_open = None
    for om in OPEN_TAG.finditer(back):
        left_open = om
    left_props = props(left_open.group(2)) if left_open else {}

    hits = []
    if nonzero(right_props.get('padding-left', '')) or nonzero(right_props.get('margin-left', '')):
        hits.append('right-has-left-gap')
    if nonzero(left_props.get('padding-right', '')) or nonzero(left_props.get('margin-right', '')):
        hits.append('left-has-right-gap')
    if 'pre' in (right_props.get('white-space', '') + left_props.get('white-space', '')):
        hits.append('white-space-pre')
    if nonzero(right_props.get('text-indent', '')):
        hits.append('text-indent')

    key = '+'.join(hits) if hits else 'NO-CSS-GAP'
    verdict['has-css-gap' if hits else 'no-css-gap'] += 1
    weighted['has-css-gap' if hits else 'no-css-gap'] += weight
    detail[key] += weight
    examples.setdefault(key, []).append(
        (rec["fixture"], left, right, str(left_props)[:110], str(right_props)[:110])
    )

tot = sum(verdict.values()) or 1
wtot = sum(weighted.values()) or 1
print(f"inline-tags-only boundaries examined: {tot} distinct shapes "
      f"({sum(weighted.values())} spaces); {skipped} skipped\n")
for k in ('has-css-gap', 'no-css-gap'):
    print(f"  {verdict[k]:5d} shapes {100*verdict[k]/tot:5.1f}%   "
          f"{weighted[k]:5d} spaces {100*weighted[k]/wtot:5.1f}%   {k}")
print("\nby property present (weighted by occurrences):")
for k, n in detail.most_common(12):
    print(f"  {n:5d}  {k}")
print()
for k in list(detail)[:6]:
    print(f"\n=== {k}")
    for fixture, left, right, lp, rp in examples[k][:3]:
        print(f"  {fixture}: {left!r} | {right!r}")
        print(f"     left  {lp}")
        print(f"     right {rp}")
