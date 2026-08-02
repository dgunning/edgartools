"""Decide, per space removal, whether a variant repaired a word or destroyed a boundary.

measure_variants.py counts both as "lost", and eyeballing a join like `CONSOLID+ATED`
against `o+Yes` does not scale past a few dozen. This classifies them with a test the
document answers itself:

    the removal joins L + R into LR
      -> REPAIR if LR occurs as a whole token elsewhere in the same document
                 (`CONSOLID`+`ATED` -> CONSOLIDATED, which appears throughout the filing)
      -> LOSS   if LR never occurs and both L and R stand alone as their own tokens
                 (`o`+`Yes` -> oYes, which appears nowhere; `o` and `Yes` are real tokens)
      -> UNKNOWN otherwise, listed in full for review

No dictionary and no language assumption — a filing that spells a word oddly is judged
against its own spelling. Removals next to an opening quote/paren/slash are counted
separately: the allowlist inserting a space after `("` is never right, so removing it is
always a repair.

Usage:
    PYTHONPATH=$REPO python scripts/text_boundary/classify_removals.py \
        --corpus wide --variant F_css_gap_only
"""
import argparse
import difflib
import re
import sys
import warnings
from collections import Counter, defaultdict
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
OPENING = '"“\'‘([{/'
TOKEN_RE = re.compile(r"[^\s]+")


def tokens(text):
    """Whole tokens, stripped of surrounding punctuation, for the occurrence test."""
    out = set()
    for t in TOKEN_RE.findall(text):
        out.add(t)
        out.add(t.strip('.,;:!?()[]{}"“”\'‘’*†‡'))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", choices=list(ROOTS), default="wide")
    ap.add_argument("--variant", default="F_css_gap_only")
    ap.add_argument("--show", type=int, default=40)
    args = ap.parse_args()

    root = ROOTS[args.corpus]
    original = ParagraphNode.text
    buckets = Counter()
    detail = defaultdict(list)

    for f in sorted(root.rglob("*.html")):
        rel = str(f.relative_to(root))
        raw = f.read_text(errors="replace")
        try:
            ParagraphNode.text = original
            btext = HTMLParser(ParserConfig()).parse(raw).text()
            ParagraphNode.text = make_text(**VARIANTS[args.variant])
            atext = HTMLParser(ParserConfig()).parse(raw).text()
        except Exception as e:
            print(f"ERROR {rel}: {e}")
            continue
        finally:
            ParagraphNode.text = original

        # Vocabulary comes from the BEFORE text only. The after text contains every
        # joined token by construction, so including it would score all removals as
        # repairs. A word split at one site is still spelled whole at its other sites,
        # which is exactly the evidence this test is after.
        vocab = tokens(btext)
        # Headings are set in caps, so `RI SK` in 'Item 1A. RI SK FACTORS' has no
        # all-caps RISK to match against — but the filing says 'Risk' in its prose a
        # hundred times. Case-folded matching is a second chance, reported separately so
        # the weaker evidence stays visible.
        vocab_ci = {t.lower() for t in vocab}
        before, after = btext.splitlines(), atext.splitlines()

        sm = difflib.SequenceMatcher(None, before, after, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "replace" or (i2 - i1) != (j2 - j1):
                continue
            for x, y in zip(before[i1:i2], after[j1:j2]):
                if x == y:
                    continue
                ia = ib = 0
                while ia < len(x) and ib < len(y):
                    if x[ia] == y[ib]:
                        ia += 1
                        ib += 1
                        continue
                    # A space the variant ADDED. Must be consumed from y alone, or the
                    # walk desynchronizes and every later column is compared against the
                    # wrong character — which reads as thousands of phantom removals.
                    if y[ib] == " ":
                        buckets["GAINED"] += 1
                        ib += 1
                        continue
                    if x[ia] != " ":
                        buckets["UNEXPECTED"] += 1
                        ia += 1
                        ib += 1
                        continue
                    prev_tok = re.search(r"\S+$", x[:ia])
                    next_tok = re.match(r"\S+", x[ia + 1:])
                    left = prev_tok.group() if prev_tok else ""
                    right = next_tok.group() if next_tok else ""
                    if left and left[-1] in OPENING:
                        kind = "REPAIR-PUNCT"
                    elif not left or not right:
                        kind = "UNKNOWN"
                    elif (left + right) in vocab:
                        kind = "REPAIR-WORD"
                    elif (left + right).lower() in vocab_ci:
                        kind = "REPAIR-WORD-CI"
                    elif left in vocab and right in vocab:
                        kind = "LOSS"
                    else:
                        kind = "UNKNOWN"
                    buckets[kind] += 1
                    detail[kind].append((rel, f"{left}+{right}", x.strip()[:120]))
                    ia += 1

    total = sum(buckets.values())
    print(f"corpus={args.corpus}  variant={args.variant}  {total} space removals\n")
    for k, n in buckets.most_common():
        print(f"   {k:14} {n:5}  {100 * n / total:5.1f}%")

    for kind in ("LOSS", "UNKNOWN"):
        sel = detail.get(kind, [])
        if not sel:
            continue
        print(f"\n----- {kind} ({len(sel)}) -----")
        counts = Counter(j for _, j, _ in sel)
        for join, n in counts.most_common():
            example = next(c for r, j, c in sel if j == join)
            where = {r for r, j, _ in sel if j == join}
            print(f"  {n:4}  {join:34} in {len(where)} doc(s)")
            print(f"        {example}")
        if len(counts) > args.show:
            print(f"  ... {len(counts) - args.show} more distinct joins")


if __name__ == "__main__":
    main()
