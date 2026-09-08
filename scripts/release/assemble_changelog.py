# ruff: noqa: T201, S603, S607  -- a CLI script: it prints, and it shells out to git
"""Fold changelog fragments from changelog.d/ into CHANGELOG.md's [Unreleased] section.

Each PR adds one file to changelog.d/ instead of editing CHANGELOG.md, so
concurrent PRs never conflict on the changelog. At release time this script
moves every fragment into [Unreleased] and deletes it.

Fragment naming: ``<id>.<section>.md`` where ``<id>`` is the bead ID, issue
number, or a short slug, and ``<section>`` is one of the Keep a Changelog
headings (added, changed, deprecated, removed, fixed, security, performance).

Fragment body: the bullet text, written exactly as it should appear. A leading
``- `` is optional; multi-line bodies are kept as one bullet.

Usage:
    python scripts/release/assemble_changelog.py           # write CHANGELOG.md, delete fragments
    python scripts/release/assemble_changelog.py --check   # print what would be added, change nothing
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHANGELOG = ROOT / "CHANGELOG.md"
FRAGMENT_DIR = ROOT / "changelog.d"

# Order the sections appear in under [Unreleased].
SECTIONS = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security", "Performance"]
FRAGMENT_NAME = re.compile(r"^(?P<id>[^.]+)\.(?P<section>[a-z]+)\.md$")
# A bullet is a bold headline plus one or two sentences with one measured value.
# The root-cause narrative belongs in the commit and the PR, not here.
MAX_FRAGMENT_CHARS = 500


def _commit_time(path: Path) -> int:
    """Unix time the fragment was last committed; 0 for an uncommitted file."""
    out = subprocess.run(
        ["git", "log", "-1", "--format=%ct", "--", str(path)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    ).stdout.strip()
    return int(out) if out else 0


def load_fragments() -> dict[str, list[tuple[Path, str]]]:
    """Return {section heading: [(path, bullet), ...]} newest fragment first."""
    by_section: dict[str, list[tuple[Path, str]]] = {s: [] for s in SECTIONS}
    bad: list[str] = []
    for path in sorted(FRAGMENT_DIR.glob("*.md")):
        if path.name == "README.md":
            continue
        m = FRAGMENT_NAME.match(path.name)
        section = m.group("section").capitalize() if m else None
        if section not in by_section:
            bad.append(path.name)
            continue
        body = path.read_text(encoding="utf-8").strip()
        if not body:
            bad.append(f"{path.name} (empty)")
            continue
        if body.startswith("- "):
            body = body[2:]
        if len(body) > MAX_FRAGMENT_CHARS:
            bad.append(f"{path.name} ({len(body)} chars, limit {MAX_FRAGMENT_CHARS})")
            continue
        by_section[section].append((path, "- " + body))
    if bad:
        sys.exit(
            "Bad changelog fragments (expected <id>.<section>.md with a non-empty body of at most "
            f"{MAX_FRAGMENT_CHARS} chars, section in {[s.lower() for s in SECTIONS]}): {', '.join(bad)}"
        )
    # Newest at the top of each section, matching the hand-written convention.
    # Uncommitted fragments (time 0) sort last, which is fine for --check.
    for entries in by_section.values():
        entries.sort(key=lambda e: _commit_time(e[0]), reverse=True)
    return {s: e for s, e in by_section.items() if e}


def merge_into_unreleased(text: str, fragments: dict[str, list[tuple[Path, str]]]) -> str:
    """Insert fragment bullets at the top of their section under [Unreleased].

    Creates missing section headings in SECTIONS order. Never touches a dated
    section, so a fragment can only ever land in the next release.
    """
    lines = text.split("\n")
    try:
        start = next(i for i, ln in enumerate(lines) if ln.startswith("## [Unreleased]"))
    except StopIteration:
        sys.exit("CHANGELOG.md has no '## [Unreleased]' heading")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))

    block = lines[start + 1:end]
    for section in SECTIONS:
        entries = fragments.get(section)
        if not entries:
            continue
        bullets = [b for _, b in entries]
        heading = f"### {section}"
        if heading in block:
            at = block.index(heading) + 1
            while at < len(block) and block[at].strip() == "":
                at += 1
            block[at:at] = bullets
        else:
            # Keep headings in canonical order: insert before the first later section.
            later = [f"### {s}" for s in SECTIONS[SECTIONS.index(section) + 1:]]
            at = next((i for i, ln in enumerate(block) if ln in later), None)
            new = [heading, ""] + bullets + [""]
            if at is None:
                while block and block[-1].strip() == "":
                    block.pop()
                block += ["", *new]
            else:
                block[at:at] = new
    # Exactly one blank line before the next dated heading.
    while block and block[-1].strip() == "":
        block.pop()
    block.append("")
    return "\n".join(lines[: start + 1] + block + lines[end:])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="validate and print fragments; change nothing")
    args = parser.parse_args()

    fragments = load_fragments()
    count = sum(len(v) for v in fragments.values())
    if not count:
        print("No changelog fragments in changelog.d/")
        return
    if args.check:
        for section, entries in fragments.items():
            print(f"### {section}")
            for path, bullet in entries:
                print(f"  [{path.name}] {bullet[:100]}")
        print(f"{count} fragment(s) ready to assemble")
        return

    CHANGELOG.write_text(merge_into_unreleased(CHANGELOG.read_text(encoding="utf-8"), fragments), encoding="utf-8")
    for entries in fragments.values():
        for path, _ in entries:
            path.unlink()
    print(f"Assembled {count} fragment(s) into CHANGELOG.md [Unreleased]; fragments deleted")


if __name__ == "__main__":
    main()
