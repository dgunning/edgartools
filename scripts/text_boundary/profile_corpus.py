"""Report which corpus documents can even exercise the allowlist.

ParagraphNode.text()'s allowlist fires only when a child's original_tag is one of
span/a/em/strong/i/b. A document built from <font> tags, or from EDGAR's pre-2001
<PRE>-with-<S>/<C> plain text, cannot trigger it — so it proves deletion is free there,
but it contributes nothing to the question of what deletion costs.

This separates the two, so a headline like "N of M documents changed" can be read against
the number of documents that could have changed at all.

Usage:
    PYTHONPATH=$REPO python scripts/text_boundary/profile_corpus.py [--corpus wide|fixtures]
"""
import argparse
import collections
import re
from pathlib import Path

ROOTS = {
    "fixtures": Path(__file__).resolve().parents[2] / "tests/fixtures/html",
    "wide": Path(__file__).resolve().parents[2] / "tests/fixtures/text_boundary_corpus",
}

ALLOWLIST_TAGS = ("span", "a", "em", "strong", "i", "b")
TAG_RE = re.compile(r"<\s*([a-zA-Z][a-zA-Z0-9]*)")


def profile(path):
    html = path.read_text(errors="replace")
    counts = collections.Counter(t.lower() for t in TAG_RE.findall(html))
    return {
        "bytes": len(html),
        "allowlist": sum(counts.get(t, 0) for t in ALLOWLIST_TAGS),
        "font": counts.get("font", 0),
        "span": counts.get("span", 0),
        "div": counts.get("div", 0),
        "table": counts.get("table", 0),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", choices=["wide", "fixtures"], default="wide")
    ap.add_argument("--threshold", type=int, default=50,
                    help="allowlist-tag count above which a document is 'informative'")
    args = ap.parse_args()

    root = ROOTS[args.corpus]
    rows = []
    for f in sorted(root.rglob("*.html")):
        p = profile(f)
        p["name"] = str(f.relative_to(root))
        rows.append(p)

    groups = collections.defaultdict(list)
    for r in rows:
        parts = Path(r["name"]).parts
        groups["/".join(parts[:2]) if len(parts) > 2 else parts[0]].append(r)

    print(f"corpus={args.corpus}  n={len(rows)}  "
          f"informative(allowlist tags >= {args.threshold})="
          f"{sum(1 for r in rows if r['allowlist'] >= args.threshold)}")
    print(f"\n{'group':32}{'n':>4}{'informative':>13}{'median_allow':>14}"
          f"{'median_font':>13}{'median_span':>13}")
    for g in sorted(groups):
        rs = groups[g]
        def med(k):
            v = sorted(r[k] for r in rs)
            return v[len(v) // 2]
        print(f"{g:32}{len(rs):>4}"
              f"{sum(1 for r in rs if r['allowlist'] >= args.threshold):>13}"
              f"{med('allowlist'):>14}{med('font'):>13}{med('span'):>13}")

    dead = [r for r in rows if r["allowlist"] < args.threshold]
    if dead:
        print(f"\n{len(dead)} document(s) cannot exercise the allowlist:")
        for r in sorted(dead, key=lambda r: r["name"])[:30]:
            print(f"   {r['name']:52} allow={r['allowlist']:<6} font={r['font']:<6} "
                  f"span={r['span']:<6} bytes={r['bytes']}")


if __name__ == "__main__":
    main()
