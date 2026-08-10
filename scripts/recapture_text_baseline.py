#!/usr/bin/env python
"""Re-capture the Filing.text() golden hashes, and prove the change was benign.

``tests/issues/regression/test_filing_text_baseline.py`` pins the SHA-256 of
``Filing.text()`` on a five-filing corpus. Every text-pipeline change moves
those hashes, and each of the eight re-captures so far was done by hand: run
the test, copy the new hash out of the failure, then write a paragraph
explaining that the diff was whitespace-only. The comment block at the top of
that file is now ~120 lines of exactly that prose.

The prose is good forensics and worth keeping. Writing it by hand a ninth time
is not, because the *claim* it makes -- "every changed line differs by inserted
spaces only, with no character content changed" -- is mechanically checkable
and was being asserted by a human reading a diff.

    hatch run python scripts/recapture_text_baseline.py --explain \\
        "table header rows now render in the body (bead edgartools-xxxx)"

WHERE THE "BEFORE" TEXT COMES FROM. A SHA-256 cannot be reversed, so the old
text has to be produced by the old code. The script checks out ``--before``
(default ``origin/main``) into a temporary git worktree, replays the same
cassettes there, and diffs that against the working tree's output. This is the
same rule the test file already states for recording cassettes -- capture
against ``main``, never against a tree with the change applied -- and it means
no "remember to snapshot first" step that can be forgotten.

Nothing here touches the network: both passes replay the committed cassettes
in ``tests/cassettes/``. If the cassettes differ between the two refs the diff
would be conflating a code change with a data change, so that is checked and
refused rather than reported.

EXIT CODES: 0 the invariant held and hashes were rewritten; 1 usage or setup
failure; 2 the text changed in a way that is NOT whitespace-only -- which is
not necessarily wrong, but it is the moment to stop and read the diff rather
than paste a hash.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASELINE_FILE = Path("tests/issues/regression/test_filing_text_baseline.py")
CASSETTE_DIR = Path("tests/cassettes")


# ---------------------------------------------------------------- baseline I/O

def read_baseline(root: Path) -> dict[str, tuple[dict, str]]:
    """Pull BASELINE out of the test module without importing it.

    AST rather than import because this also runs against a checkout of another
    ref, where importing the test module would import that ref's ``edgar``
    package into this process.
    """
    tree = ast.parse((root / BASELINE_FILE).read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(getattr(t, "id", None) == "BASELINE" for t in node.targets):
            continue
        out: dict[str, tuple[dict, str]] = {}
        for key, value in zip(node.value.keys, node.value.values):
            kwargs_node, hash_node = value.elts
            kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in kwargs_node.keywords}
            out[ast.literal_eval(key)] = (kwargs, ast.literal_eval(hash_node))
        return out
    raise SystemExit(f"no BASELINE dict found in {BASELINE_FILE}")


# ------------------------------------------------------------------ extraction

def emit(root: Path, outdir: Path) -> int:
    """Worker: write each baseline filing's text to ``outdir``.

    Runs as a subprocess so it can be pointed at a different checkout. Replays
    cassettes through the same safe YAML loader the suite installs -- vcrpy
    otherwise deserialises with PyYAML's unsafe loader, and this reads
    cassettes from a ref the caller may not have reviewed.
    """
    sys.path.insert(0, str(root))
    from tests._vcr_safety import install_safe_yaml_deserializer

    install_safe_yaml_deserializer()

    import vcr

    import edgar
    from edgar import Filing

    # The whole point of this subprocess is to run ONE ref's code. The hatch
    # environment also has a released edgartools installed, so if sys.path
    # ordering ever stops favouring the checkout, this silently diffs the
    # working tree against itself and reports "no change" — a green result for
    # a comparison that never happened.
    edgar_root = Path(edgar.__file__).resolve().parent.parent
    if edgar_root != root.resolve():
        print(f"imported edgar from {edgar_root}, expected {root.resolve()}",
              file=sys.stderr)
        return 1

    outdir.mkdir(parents=True, exist_ok=True)
    for accession, (kwargs, _) in read_baseline(root).items():
        cassette = root / CASSETTE_DIR / f"filing_text_baseline_{accession}.yaml"
        if not cassette.exists():
            print(f"missing cassette: {cassette}", file=sys.stderr)
            return 1
        with vcr.use_cassette(
            str(cassette),
            record_mode="none",
            match_on=["method", "scheme", "host", "port", "path", "query"],
            filter_headers=["User-Agent", "Authorization"],
            decode_compressed_response=True,
        ):
            text = Filing(**kwargs).text()
        (outdir / f"{accession}.txt").write_text(text, encoding="utf-8")
    return 0


def run_emit(root: Path, outdir: Path) -> None:
    env = dict(os.environ)
    env.setdefault("EDGAR_IDENTITY", "Dev Gunning developer-gunning@gmail.com")
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--emit", str(outdir),
         "--root", str(root)],
        env=env, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"extraction failed in {root}:\n{proc.stdout}\n{proc.stderr}"
        )


# ----------------------------------------------------------------- the check

_WS = re.compile(r"\s+")


def whitespace_only(old: str, new: str) -> bool:
    """True when the two differ by whitespace alone.

    This is the invariant the comment block asserts by hand. Comparing with all
    whitespace stripped catches the case that matters -- a character of content
    appearing or disappearing -- while allowing the space insertions every
    word-boundary fix produces.
    """
    return _WS.sub("", old) == _WS.sub("", new)


def summarise(accession: str, old: str, new: str, sample: int) -> list[str]:
    """Human-readable account of one filing's change, for the changelog entry."""
    o, n = old.splitlines(), new.splitlines()
    diff = [ln for ln in difflib.unified_diff(o, n, lineterm="", n=0)
            if ln[:1] in "+-" and ln[:3] not in ("+++", "---")]
    changed = len(diff) // 2
    lines = [f"  {accession}: {len(o)} -> {len(n)} lines, ~{changed} changed"]
    for ln in diff[: sample * 2]:
        lines.append(f"      {ln[:150]}")
    return lines


# ------------------------------------------------------------------- rewriting

def rewrite_hashes(root: Path, new_hashes: dict[str, str]) -> list[str]:
    """Replace changed hashes in the test file. Returns the accessions rewritten."""
    path = root / BASELINE_FILE
    src = path.read_text(encoding="utf-8")
    changed = []
    for accession, (_, old_hash) in read_baseline(root).items():
        new_hash = new_hashes[accession]
        if new_hash == old_hash:
            continue
        if src.count(f'"{old_hash}"') != 1:
            raise SystemExit(
                f"hash for {accession} is not uniquely locatable in the file; "
                "refusing to rewrite"
            )
        src = src.replace(f'"{old_hash}"', f'"{new_hash}"')
        changed.append(accession)
    path.write_text(src, encoding="utf-8")
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--emit", metavar="OUTDIR",
                    help=argparse.SUPPRESS)  # internal worker mode
    ap.add_argument("--root", default=str(REPO), help=argparse.SUPPRESS)
    ap.add_argument("--explain", help="why the output changed; goes in the entry")
    ap.add_argument("--before", default="origin/main",
                    help="ref holding the pre-change code (default origin/main)")
    ap.add_argument("--sample", type=int, default=4,
                    help="changed lines to quote per filing (default 4)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report and print the entry, but do not rewrite hashes")
    args = ap.parse_args()

    if args.emit:
        return emit(Path(args.root), Path(args.emit))

    if not args.explain and not args.dry_run:
        ap.error("--explain is required (or use --dry-run)")

    tmp = Path(tempfile.mkdtemp(prefix="recapture-baseline-"))
    worktree = tmp / "before"
    try:
        subprocess.run(["git", "worktree", "add", "--detach", str(worktree), args.before],
                       cwd=REPO, check=True, capture_output=True, text=True)

        # Same cassettes on both sides, or the diff is measuring two things.
        for accession in read_baseline(REPO):
            name = f"filing_text_baseline_{accession}.yaml"
            here, there = REPO / CASSETTE_DIR / name, worktree / CASSETTE_DIR / name
            if not there.exists():
                raise SystemExit(f"{args.before} has no cassette {name}")
            if hashlib.sha256(here.read_bytes()).hexdigest() != \
               hashlib.sha256(there.read_bytes()).hexdigest():
                raise SystemExit(
                    f"cassette {name} differs between HEAD and {args.before}. The "
                    "diff would conflate a code change with a recording change; "
                    "re-record deliberately and re-run."
                )

        run_emit(worktree, tmp / "old")
        run_emit(REPO, tmp / "new")

        report: list[str] = []
        new_hashes: dict[str, str] = {}
        violations: list[str] = []
        unchanged = 0

        for accession in read_baseline(REPO):
            old = (tmp / "old" / f"{accession}.txt").read_text(encoding="utf-8")
            new = (tmp / "new" / f"{accession}.txt").read_text(encoding="utf-8")
            new_hashes[accession] = hashlib.sha256(new.encode("utf-8")).hexdigest()
            if old == new:
                unchanged += 1
                continue
            report += summarise(accession, old, new, args.sample)
            if not whitespace_only(old, new):
                violations.append(accession)
                report.append("      ^^ NOT whitespace-only: content changed")

        if not report:
            print(f"No change against {args.before}. Nothing to re-capture.")
            return 0

        entry = [
            "#",
            f"# Re-captured against {args.before}: {args.explain or '(dry run)'}",
            f"# {len(read_baseline(REPO)) - unchanged} of "
            f"{len(read_baseline(REPO))} filings moved; {unchanged} byte-identical.",
        ]
        entry += ["# " + ln for ln in report]
        entry.append(
            "# Verified mechanically: every changed line differs by whitespace only."
            if not violations else
            "# WARNING: content changed on " + ", ".join(violations) +
            " — this is NOT a whitespace-only re-capture. Explain it deliberately."
        )
        block = "\n".join(entry)

        print(block)
        print()

        if violations:
            print(f"REFUSING to rewrite hashes: {len(violations)} filing(s) changed "
                  "content, not just whitespace. Read the diff above.", file=sys.stderr)
            return 2

        if args.dry_run:
            print("--dry-run: hashes not rewritten.")
            return 0

        changed = rewrite_hashes(REPO, new_hashes)
        print(f"Rewrote {len(changed)} hash(es) in {BASELINE_FILE}.")
        print("Paste the block above into that file's comment block, and re-run the test.")
        return 0
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(worktree)],
                       cwd=REPO, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
