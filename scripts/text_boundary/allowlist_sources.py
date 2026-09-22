"""Where do the allowlist's 8,109 spaces come from?

Renders every fixture with and without the ParagraphNode.text() allowlist branch, and
for each space the allowlist is solely responsible for, records the two words it
separates plus enough context to find the markup in the source HTML.

Output is a JSON list of {fixture, left, right, context} — feed it to
allowlist_classify.py, which goes back to the raw HTML and asks the only question that
matters: was there whitespace between those two words in the file the SEC served?
"""
import difflib
import json
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
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("allowlist_sources.json")

ORIGINAL = ParagraphNode.text
records = []
pairs = Counter()

for f in sorted(FIXTURES.rglob("*.html")):
    raw = f.read_text(errors="replace")
    try:
        ParagraphNode.text = ORIGINAL
        before = HTMLParser(ParserConfig()).parse(raw).text().splitlines()
        ParagraphNode.text = make_text(drop_allowlist=True)
        after = HTMLParser(ParserConfig()).parse(raw).text().splitlines()
    except Exception as e:
        print(f"ERROR {f.name}: {e}")
        continue
    finally:
        ParagraphNode.text = ORIGINAL

    name = str(f.relative_to(FIXTURES))
    sm = difflib.SequenceMatcher(None, before, after, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != 'replace' or (i2 - i1) != (j2 - j1):
            continue
        for a, b in zip(before[i1:i2], after[j1:j2]):
            if a == b or a.replace(" ", "") != b.replace(" ", ""):
                continue
            ia = ib = 0
            while ia < len(a) and ib < len(b):
                if a[ia] == b[ib]:
                    ia += 1; ib += 1
                elif a[ia] == ' ':
                    left = re.search(r'\S+$', a[:ia])
                    right = re.match(r'\S+', a[ia + 1:])
                    if left and right:
                        pairs[(left.group(), right.group())] += 1
                        records.append({
                            "fixture": name,
                            "left": left.group(),
                            "right": right.group(),
                            "context": a[max(0, ia - 60):ia + 60],
                        })
                    ia += 1
                else:
                    break

print(f"{len(records)} allowlist-only spaces; {len(pairs)} distinct word pairs")
print("\nmost frequent pairs:")
for (l, r), n in pairs.most_common(25):
    print(f"  {n:4d}  {l!r} | {r!r}")
OUT.write_text(json.dumps(records))
print(f"\nwrote {OUT}")
