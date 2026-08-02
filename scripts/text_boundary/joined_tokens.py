"""List every distinct token that variant G repairs, across all 57 fixtures.

For each changed line, find the space removals and report the word formed. If any
removal joins two pieces that were NOT one word, it will be obvious in this list.
"""
import difflib
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

joined = Counter()
from collections import defaultdict
ctxs = defaultdict(list)
suspicious = []
n_lines = 0

for f in sorted(FIXTURES.rglob("*.html")):
    raw = f.read_text(errors="replace")
    try:
        ParagraphNode.text = ORIGINAL
        before = HTMLParser(ParserConfig()).parse(raw).text().splitlines()
        ParagraphNode.text = make_text(no_word_split=True)
        after = HTMLParser(ParserConfig()).parse(raw).text().splitlines()
    except Exception as e:
        print(f"ERROR {f.name}: {e}")
        continue
    finally:
        ParagraphNode.text = ORIGINAL

    sm = difflib.SequenceMatcher(None, before, after, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != 'replace' or (i2 - i1) != (j2 - j1):
            continue
        for a, b in zip(before[i1:i2], after[j1:j2]):
            if a == b:
                continue
            n_lines += 1
            # walk both strings, recording each space present in `a` but not `b`
            ia = ib = 0
            while ia < len(a) and ib < len(b):
                if a[ia] == b[ib]:
                    ia += 1; ib += 1
                elif a[ia] == ' ':
                    left = re.search(r'[A-Za-z]+$', a[:ia])
                    right = re.match(r'[A-Za-z]+', a[ia + 1:])
                    if left and right:
                        key = f"{left.group()}|{right.group()}"
                        joined[key] += 1
                        if key in ("Yes|x", "No|x", "o|rm") and len(ctxs[key]) < 3:
                            ctxs[key].append((f.name, a[max(0, ia-60):ia+40]))
                    else:
                        suspicious.append((f.name, a[max(0, ia - 50):ia + 50]))
                    ia += 1
                else:
                    suspicious.append((f.name, f"UNEXPECTED at {ia}: {a[max(0,ia-40):ia+40]!r}"))
                    break

print(f"{n_lines} changed lines; {sum(joined.values())} space removals; "
      f"{len(joined)} distinct joins; {len(suspicious)} suspicious\n")
for pair, n in joined.most_common():
    left, right = pair.split("|")
    print(f"  {n:3d}  {left}+{right} -> {left+right}")
if suspicious:
    print("\nSUSPICIOUS:")
    for name, ctx in suspicious[:20]:
        print(f"  {name}: {ctx!r}")
