"""Print boundary proposals for eye review (edgartools-llmp.11).

For each requested fixture, every item section in DOCUMENT order with the
end of one section printed directly above the start of the next, so a reader
can judge each boundary from the two sides of it: does section k end where
k+1 begins, with nothing lost between them and nothing duplicated?

    python tests/fixtures/parser_corpus/propose_truth.py aapl-10-k-2024-11-01 ms-10-k-2025-02-21

Labels are fixture file stems, as consistency_corpus() names them.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scoring  # noqa: E402

from edgar.documents import HTMLParser, ParserConfig  # noqa: E402


def main(labels):
    corpus = {e["label"]: e for e in scoring.consistency_corpus()}
    for label in labels:
        e = corpus[label]
        html = Path(e["path"]).read_text(errors="ignore")
        doc = HTMLParser(ParserConfig(form=e["form"], detect_sections=True)).parse(html)
        secs = [(n, s) for n, s in doc.sections.items() if scoring.item_key(n)]
        # Document order: TOC sections carry no offsets, so order by the
        # position of the first 200 chars of their text in the document text.
        full = scoring.collapse(doc.text() or "")
        order = {}
        for n, s in secs:
            h = scoring.collapse(s.text() or "")[:120]
            i = full.find(h) if h else -1
            order[n] = i if i >= 0 else 10**9
        secs.sort(key=lambda ns: order[ns[0]])
        print(f"\n######## {label} {e['form']}  ({len(secs)} item sections)")  # noqa: T201
        for n, s in secs:
            t = s.text() or ""
            head, tail = scoring.head_tail(t)
            print(f"--- {n}  [{s.detection_method}, {len(t)} chars]")  # noqa: T201
            print(f"   START: {head!r}")  # noqa: T201
            print(f"   END:   {tail!r}")  # noqa: T201


if __name__ == "__main__":
    main(sys.argv[1:])
