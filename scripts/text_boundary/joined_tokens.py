"""Name every word a variant's space removals form.

measure_variants.py cannot tell an intentional word repair from a destroyed boundary —
both show up as "lost". This can: for each changed line it walks the two strings, finds
each space present before and absent after, and reports the word the removal produces.
A repair reads as one word (`Chan+ges -> Changes`); a destroyed boundary reads as two
(`the+Company -> theCompany`). 200 entries you can read beats 8,000 diff lines you can't.

Usage:
    PYTHONPATH=$REPO python scripts/text_boundary/joined_tokens.py \
        [--corpus fixtures|wide] [--variant F_css_gap_only]
"""
import argparse
import difflib
import re
import sys
import warnings
from collections import Counter
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
from variants import VARIANTS, make_text  # noqa: E402

from edgar.documents import HTMLParser, ParserConfig  # noqa: E402
from edgar.documents.nodes import ParagraphNode  # noqa: E402

ROOTS = {
    "fixtures": Path(__file__).resolve().parents[2] / "tests/fixtures/html",
    "wide": Path(__file__).resolve().parents[2] / "tests/fixtures/text_boundary_corpus",
}

_ap = argparse.ArgumentParser()
_ap.add_argument("--corpus", choices=list(ROOTS), default="fixtures")
_ap.add_argument("--variant", default="no_word_split",
                 help=f"a name from VARIANTS ({', '.join(VARIANTS)}) or 'no_word_split'")
_args = _ap.parse_args()

FIXTURES = ROOTS[_args.corpus]
VARIANT_KWARGS = (VARIANTS[_args.variant] if _args.variant in VARIANTS
                  else dict(no_word_split=True))
print(f"corpus={_args.corpus} root={FIXTURES}\nvariant={_args.variant} {VARIANT_KWARGS}\n")
ORIGINAL = ParagraphNode.text

joined = Counter()
from collections import defaultdict
ctxs = defaultdict(list)
suspicious = []
n_lines = 0

for f in sorted(FIXTURES.rglob("*.html")):
    rel = str(f.relative_to(FIXTURES))
    raw = f.read_text(errors="replace")
    try:
        ParagraphNode.text = ORIGINAL
        before = HTMLParser(ParserConfig()).parse(raw).text().splitlines()
        ParagraphNode.text = make_text(**VARIANT_KWARGS)
        after = HTMLParser(ParserConfig()).parse(raw).text().splitlines()
    except Exception as e:
        print(f"ERROR {rel}: {e}")
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
                            ctxs[key].append((rel, a[max(0, ia-60):ia+40]))
                    else:
                        suspicious.append((rel, a[max(0, ia - 50):ia + 50]))
                    ia += 1
                else:
                    suspicious.append((rel, f"UNEXPECTED at {ia}: {a[max(0,ia-40):ia+40]!r}"))
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
