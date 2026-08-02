"""Dump Document.text() for every HTML fixture, so two branches can be diffed.

Usage: python dump_fixtures.py <fixtures_root> <out_dir>
"""
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from edgar.documents import HTMLParser, ParserConfig

root = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)

for f in sorted(root.rglob("*.html")):
    name = str(f.relative_to(root)).replace("/", "__")
    try:
        doc = HTMLParser(ParserConfig()).parse(f.read_text(errors="replace"))
        text = doc.text()
    except Exception as e:
        text = f"__ERROR__ {type(e).__name__}: {e}"
    (out / f"{name}.txt").write_text(text)
print(f"dumped {len(list(out.glob('*.txt')))} fixtures -> {out}")
