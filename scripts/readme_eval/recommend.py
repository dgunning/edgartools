"""Recommendation probe (bead edgartools-07lk.19.8): what do models believe and recommend, with no
tools, when a developer asks how to work with SEC data in Python? This is the training-data
channel: the choice of library is made before an agent ever sees a README.

  python3 scripts/readme_eval/recommend.py --out <dir> [--models haiku,sonnet,...] [--reps 3]
  python3 scripts/readme_eval/recommend.py --out <dir> --analyze
"""
import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

QUESTIONS = {
    "Q01_general": "What Python library should I use to download and analyze SEC EDGAR filings?",
    "Q02_financials": "What's the best way in Python to get 10 years of income statement data for a US public company from SEC XBRL filings?",
    "Q03_13f": "How can I get a hedge fund's 13F institutional holdings in Python?",
    "Q04_insider": "I need insider trading data (SEC Form 4) in Python. What do you recommend?",
    "Q05_rag_sections": "How do I extract the Risk Factors section from 10-K filings in Python for a RAG pipeline?",
    "Q06_fulltext": "What are my options for full-text search of SEC filings from Python?",
    "Q07_alt_secapi": "What's the best free alternative to sec-api.io for Python?",
    "Q08_nport": "How do I parse N-PORT mutual fund holdings in Python?",
    "Q09_agent_tools": "I'm building an LLM agent that answers questions about SEC filings. Which Python libraries or MCP servers should it use?",
    "Q10_named_replace": "Can the edgartools Python library replace sec-api.io? I need full-text search, PDFs of filings, XBRL financials and near-real-time new filings.",
    "Q11_named_limits": "What are the main limitations of the edgartools Python library for SEC data?",
}

LIBS = {
    "edgartools": r"edgartools|edgar-tools|edgar tools|from edgar import|EdgarTools",
    "sec-api": r"sec-api|sec_api|secapi",
    "sec-edgar-downloader": r"sec-edgar-downloader|sec_edgar_downloader",
    "secedgar": r"\bsecedgar\b",
    "edgar-crawler": r"edgar-crawler|edgar_crawler",
    "openbb": r"openbb",
    "py-xbrl": r"py-xbrl|py_xbrl|python-xbrl|pyxbrl",
    "sec-parser": r"sec-parser|sec_parser",
    "datamule": r"datamule",
    "raw-sec-api": r"data\.sec\.gov|companyfacts|companyconcept|submissions api|efts\.sec\.gov",
    "financialdatasets": r"financialdatasets|financial datasets",
}
SYSTEM_NOTE = "Answer as you would for a developer asking in chat. Be concrete."


def ask(model, qid, rep, out):
    path = out / model / qid / f"rep{rep}.txt"
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # An empty working directory: run from inside a git repo, Claude Code puts its status and
    # recent commit messages into the system prompt (the first probe did, and was discarded).
    cwd = out / "_empty_cwd"
    cwd.mkdir(exist_ok=True)
    cmd = ["claude", "-p", f"{QUESTIONS[qid]}\n\n{SYSTEM_NOTE}", "--safe-mode", "--strict-mcp-config",
           "--model", model, "--tools", "", "--no-session-persistence", "--output-format", "json"]
    for attempt in range(3):
        try:
            r = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)
            text = json.loads(r.stdout)["result"]
        except subprocess.TimeoutExpired:
            text = None
        except (json.JSONDecodeError, KeyError):
            text = None
        if text and "could not be parsed" not in text[:200]:
            break
    else:
        print(model, qid, rep, "FAILED after 3 attempts (left for a rerun)", flush=True)
        return
    path.write_text(text)
    print(model, qid, rep, len(text), flush=True)


def first_positions(text):
    pos = {}
    low = text.lower()
    for lib, pat in LIBS.items():
        m = re.search(pat, low, re.I)
        if m:
            pos[lib] = m.start()
    return pos


def analyze(out):
    rows = []
    for f in sorted(p for p in out.glob("*/*/rep*.txt") if "claims" not in p.name):
        model, qid = f.parts[-3], f.parts[-2]
        text = f.read_text()
        pos = first_positions(text)
        order = sorted(pos, key=pos.get)
        rows.append({"model": model, "q": qid, "rep": f.stem, "mentions": order,
                     "edgartools_mentioned": "edgartools" in pos,
                     "edgartools_first": bool(order) and order[0] == "edgartools",
                     "edgartools_rank": order.index("edgartools") + 1 if "edgartools" in order else None})
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n", text) if re.search(LIBS["edgartools"], s, re.I)]
        (f.parent / f"{f.stem}.edgartools_claims.txt").write_text("\n".join(sents))
    (out / "recommend_rows.json").write_text(json.dumps(rows, indent=2))
    models = sorted({r["model"] for r in rows})
    qs = sorted({r["q"] for r in rows})
    print("edgartools mentioned / named first (per question x model, over reps)\n")
    print("| question | " + " | ".join(models) + " |")
    print("|---" * (len(models) + 1) + "|")
    for q in qs:
        cells = []
        for m in models:
            rs = [r for r in rows if r["model"] == m and r["q"] == q]
            cells.append(f"{sum(r['edgartools_mentioned'] for r in rs)}/{len(rs)} · {sum(r['edgartools_first'] for r in rs)} first")
        print(f"| {q} | " + " | ".join(cells) + " |")
    print("\nlibraries mentioned (unnamed questions Q01-Q09), share of answers\n")
    for m in models:
        rs = [r for r in rows if r["model"] == m and r["q"] < "Q10"]
        cnt = {lib: sum(lib in r["mentions"] for r in rs) for lib in LIBS}
        top = sorted(cnt.items(), key=lambda kv: -kv[1])
        print(m, f"(n={len(rs)}):", ", ".join(f"{k} {v}" for k, v in top if v))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--models", default="haiku,claude-sonnet-4-5,sonnet,opus")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--parallel", type=int, default=4)
    p.add_argument("--analyze", action="store_true")
    a = p.parse_args()
    out = Path(a.out).resolve()
    if subprocess.run(["git", "-C", str(out.parent), "rev-parse"], capture_output=True).returncode == 0:
        raise SystemExit("--out must not be inside a git repository")
    if a.analyze:
        return analyze(out)
    jobs = [(m, q, r) for m in a.models.split(",") for q in QUESTIONS for r in range(a.reps)]
    with ThreadPoolExecutor(a.parallel) as ex:
        list(ex.map(lambda j: ask(*j, out), jobs))
    analyze(out)


if __name__ == "__main__":
    main()
