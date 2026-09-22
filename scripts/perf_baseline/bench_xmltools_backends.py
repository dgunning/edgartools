"""Before/after for the bs4 to lxml migration of `edgar/xmltools.py` (edgartools-07lk.11).

The epic requires every migration PR to report a measured before/after. This is the
harness for the `xmltools` tier: point it at an XML document one of the twelve
dependents parses and it answers three questions.

    1. REGRESSION  Does routing the bs4 path through the dual-backend adapter cost
                   anything? Until 07lk.11.3 finishes, every dependent still passes
                   bs4 nodes, so a slowdown here is paid by every user today.
    2. PAYOFF      What does switching a parse entry point to lxml buy, end to end?
    3. SPLIT       How much of that is the parse step versus the helper calls, which
                   is what tells you whether a given dependent is worth migrating.

Correctness is checked before any timing: a benchmark comparing two different
answers measures nothing. The run aborts if the adapter changed the bs4 answer, or
if the two backends disagree.

Usage:

    python scripts/perf_baseline/bench_xmltools_backends.py [xml_path] [--rev REV]

`xml_path` defaults to the Form D used by the 07lk.11.2 baseline. `--rev` picks the
git revision to treat as "before" (default HEAD), so a PR mid-migration can measure
against its own merge base.
"""
import argparse
import importlib.util
import subprocess
import sys
import tempfile
import timeit
from pathlib import Path

from bs4 import BeautifulSoup
from lxml import etree

REPO = Path(__file__).resolve().parents[2]
DEFAULT_XML = REPO / "data" / "D.1685REIT.xml"

# A realistic read: the fields Issuer.from_xml pulls from one <primaryIssuer>.
DEFAULT_ROOT = "primaryIssuer"
FIELDS = ["cik", "entityName", "issuerPhoneNumber", "jurisdictionOfInc", "entityType"]
NESTED = ("issuerAddress", ["street1", "street2", "city", "stateOrCountry", "zipCode"])
WRAPPED = "yearOfInc"
REPEATED = "value"


def load_reference(rev: str):
    """Load the `xmltools` from `rev` as a separate module, to time "before"."""
    source = subprocess.run(
        ["git", "show", f"{rev}:edgar/xmltools.py"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout
    path = Path(tempfile.mkdtemp()) / "_xmltools_reference.py"
    path.write_text(source)
    spec = importlib.util.spec_from_file_location("_xmltools_reference", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_xmltools_reference"] = module
    spec.loader.exec_module(module)
    return module


def extract(mod, node):
    values = [mod.child_text(node, field) for field in FIELDS]
    parent, children = NESTED
    nested = mod.find_element(node, parent)
    if nested is not None:
        values += [mod.child_text(nested, field) for field in children]
    values.append(mod.child_value(node, WRAPPED))
    values.append(mod.child_texts(node, REPEATED))
    return values


def bench(label, stmt, number):
    seconds = timeit.timeit(stmt, number=number) / number
    print(f"  {label:<44} {seconds * 1e6:9.1f} us")
    return seconds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("xml_path", nargs="?", type=Path, default=DEFAULT_XML)
    parser.add_argument("--root", default=DEFAULT_ROOT, help="element the parsers start from")
    parser.add_argument("--rev", default="HEAD", help='git revision to time as "before"')
    args = parser.parse_args()

    xml = args.xml_path.read_text()
    xml_bytes = xml.encode()

    before_mod = load_reference(args.rev)
    import edgar.xmltools as after_mod

    def bs4_node():
        return BeautifulSoup(xml, features="xml").find(args.root)

    def lxml_node():
        root = etree.fromstring(xml_bytes)
        return root if root.tag == args.root else root.find(f".//{args.root}")

    print(f"{args.xml_path.name}  ({len(xml_bytes):,} bytes, root <{args.root}>)  before={args.rev}\n")

    if extract(before_mod, bs4_node()) != extract(after_mod, bs4_node()):
        sys.exit("ABORT: the adapter changed the bs4 answer")
    if extract(after_mod, bs4_node()) != extract(after_mod, lxml_node()):
        sys.exit("ABORT: the two backends disagree")
    print("both backends and both revisions return identical values\n")

    tree_bs4, tree_lxml = bs4_node(), lxml_node()

    print("1. REGRESSION — helper calls on an already-parsed bs4 tree (n=2000)")
    before = bench(f"{args.rev} xmltools (bs4)", lambda: extract(before_mod, tree_bs4), 2000)
    after = bench("working tree, adapter dispatch (bs4)", lambda: extract(after_mod, tree_bs4), 2000)
    print(f"  -> adapter overhead on the bs4 path: {(after / before - 1) * 100:+.1f}%\n")

    print("2. PAYOFF — end to end, parse + extract (n=500)")
    e2e_bs4 = bench("bs4 parse + extract", lambda: extract(after_mod, bs4_node()), 500)
    e2e_lxml = bench("lxml parse + extract", lambda: extract(after_mod, lxml_node()), 500)
    print(f"  -> lxml end to end: {e2e_bs4 / e2e_lxml:.1f}x faster\n")

    print("3. SPLIT — where the win comes from (n=500 parse, n=2000 extract)")
    p_bs4 = bench("BeautifulSoup(xml, features='xml')", bs4_node, 500)
    p_lxml = bench("etree.fromstring(xml)", lxml_node, 500)
    x_bs4 = bench("extract only, bs4 tree", lambda: extract(after_mod, tree_bs4), 2000)
    x_lxml = bench("extract only, lxml tree", lambda: extract(after_mod, tree_lxml), 2000)
    print(f"  -> parse step:   {p_bs4 / p_lxml:.1f}x")
    print(f"  -> helper calls: {x_bs4 / x_lxml:.1f}x")


if __name__ == "__main__":
    main()
