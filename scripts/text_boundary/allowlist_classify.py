"""Go back to the raw HTML and ask whether the allowlist is inventing or restoring.

Takes allowlist_sources.py's JSON, finds each word pair in the file the SEC served, and
reports what sits between the two words. A boundary the allowlist *restores* has real
whitespace (or an &nbsp;, or a <br>) in the source that something downstream deleted —
that is another instance of the delete-vs-collapse bug. A boundary it *invents* has
nothing but tags between the words, which a browser would render glued too.

Entities are decoded first, so &#160; counts as the whitespace it renders as.
"""
import html as htmllib
import json
import re
import sys
from collections import Counter
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "tests/fixtures/html"
records = json.loads(Path(sys.argv[1]).read_text())
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 0

TAG = re.compile(r'<[^>]*>')
BETWEEN = r'((?:\s|<[^>]*>)*?)'


def outside_tag_text(chunk: str) -> str:
    """The characters between the two words that are not part of a tag."""
    return TAG.sub('', chunk)


def classify(gap: str):
    """What kind of boundary the source actually has."""
    bare = outside_tag_text(gap)
    if bare.strip('​'):                     # anything not a zero-width space
        if bare.strip() == '':
            return 'whitespace-in-source'        # real space/newline/nbsp: RESTORED
        return 'other-text'
    tags = TAG.findall(gap)
    if not tags:
        return 'nothing-at-all'
    names = [re.match(r'</?\s*([A-Za-z0-9:_-]+)', t) for t in tags]
    names = [m.group(1).lower() for m in names if m]
    if any(n in ('br', 'hr') for n in names):
        return 'br-in-source'                    # a line break: RESTORED
    if any(n in ('td', 'th', 'tr', 'table') for n in names):
        return 'table-cell-boundary'
    if any(n in ('p', 'div', 'li', 'ul', 'ol', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6')
           for n in names):
        return 'block-boundary'
    return 'inline-tags-only'                    # nothing but spans: INVENTED


# One lookup per distinct (fixture, left, right): a shape repeated 300 times is one
# shape. Weight by how often it occurs so the percentages still describe the 8,109.
seen = {}
for rec in records:
    seen.setdefault((rec["fixture"], rec["left"], rec["right"]), [rec, 0])[1] += 1
work = list(seen.values())
print(f"{len(records)} spaces -> {len(work)} distinct (fixture, left, right) shapes\n")

cache = {}
counts = Counter()
weighted = Counter()
examples = {}
unmatched = 0

for i, (rec, weight) in enumerate(work):
    if LIMIT and i >= LIMIT:
        break
    path = FIXTURES / rec["fixture"]
    if path not in cache:
        cache[path] = htmllib.unescape(path.read_text(errors="replace"))
    doc = cache[path]
    left, right = rec["left"], rec["right"]
    if len(left) > 40 or len(right) > 40:
        unmatched += 1
        continue
    m = re.search(re.escape(left) + BETWEEN + re.escape(right), doc)
    if not m:
        unmatched += 1
        continue
    kind = classify(m.group(1))
    counts[kind] += 1
    weighted[kind] += weight
    examples.setdefault(kind, []).append(
        (rec["fixture"], left, right, m.group(1)[:150])
    )

total = sum(counts.values())
wtotal = sum(weighted.values())
print(f"matched {total} of {total + unmatched} distinct shapes "
      f"({unmatched} not re-locatable in the source)\n")
print(f"{'shapes':>7} {'':6} {'spaces':>7} {'':6}  kind")
for kind, n in counts.most_common():
    print(f"  {n:5d} {100 * n / total:5.1f}%   {weighted[kind]:5d} "
          f"{100 * weighted[kind] / wtotal:5.1f}%   {kind}")
print()
for kind in counts:
    print(f"\n=== {kind}")
    for fixture, left, right, gap in examples[kind][:4]:
        print(f"  {fixture}: {left!r} | {right!r}")
        print(f"     between: {gap!r}")
