"""Diff each ParagraphNode.text() variant against the current implementation.

Runs over the fixture corpus and classifies every changed line as space-gained /
space-lost / content-changed.

Two corpora, selected with --corpus:
  fixtures  the 57 HTML fixtures under tests/fixtures/html — modern large-cap 10-K/10-Q
  wide      the widened corpus built by build_wide_corpus.py — five markup eras across
            nine form types, which is what the allowlist question needs (see that script)
  both      render both, reported separately

Results are grouped by corpus subdirectory so a loss can be attributed to an era or a
form rather than just to a file.
"""
import argparse
import difflib
import sys
import warnings
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

ORIGINAL = ParagraphNode.text


def render_all(root):
    """Parse every fixture with whatever ParagraphNode.text is currently installed."""
    out = {}
    for f in sorted(root.rglob("*.html")):
        name = str(f.relative_to(root))
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


def measure(corpus, root, show_samples):
    if not root.exists():
        print(f"!! {corpus} corpus not found at {root} — skipping")
        return
    print(f"\n#### corpus={corpus}  root={root}")
    print("rendering with CURRENT implementation...")
    base = render_all(root)
    print(f"  {len(base)} documents")

    for vname, kwargs in VARIANTS.items():
        ParagraphNode.text = make_text(**kwargs)
        got = render_all(root)
        ParagraphNode.text = ORIGINAL

        tg = tl = to = 0
        changed = []
        all_samples = []
        by_group = {}
        for name in base:
            g, l, o, s = classify(base[name], got[name])
            # Group by the first path segment: ticker for the fixture corpus, era for
            # the wide one. Second segment is the form.
            parts = Path(name).parts
            group = parts[0] if len(parts) < 3 else f"{parts[0]}/{parts[1]}"
            agg = by_group.setdefault(group, [0, 0, 0, 0])
            agg[3] += 1
            if g or l or o:
                changed.append((name, g, l, o))
                tg += g; tl += l; to += o
                agg[0] += g; agg[1] += l; agg[2] += o
                all_samples.extend((name, *x) for x in s)
        print(f"\n=== [{corpus}] {vname}: {len(changed)}/{len(base)} docs changed  "
              f"gained={tg} lost={tl} content/struct={to}")
        for group in sorted(by_group):
            g, l, o, n = by_group[group]
            if g or l or o:
                print(f"     {group:28} n={n:3}  +{g:<6} -{l:<6} other={o}")
        for name, g, l, o in sorted(changed, key=lambda x: -x[2])[:10]:
            print(f"     {name}: +{g} -{l} other={o}")
        if show_samples:
            for name, kind, a, b in all_samples[:10]:
                print(f"   [{kind}] {name}\n     - {a[:170]}\n     + {b[:170]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", choices=["fixtures", "wide", "both"], default="fixtures")
    ap.add_argument("--samples", action="store_true", help="print changed-line samples")
    args = ap.parse_args()

    names = ["fixtures", "wide"] if args.corpus == "both" else [args.corpus]
    for corpus in names:
        measure(corpus, ROOTS[corpus], args.samples)


if __name__ == "__main__":
    main()
