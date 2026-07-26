#!/usr/bin/env python
"""Fail if any VCR cassette carries a YAML tag that isn't plain data.

vcrpy deserializes cassettes with PyYAML's *unsafe* loader::

    from yaml import CLoader as Loader
    def deserialize(cassette_string):
        return yaml.load(cassette_string, Loader=Loader)

That loader constructs arbitrary Python objects from ``!!python/...`` tags at
load time, so a cassette is executable content rather than inert recorded
traffic. Anyone who lands a cassette — or gets one onto a branch a maintainer
checks out to review — runs code in CI and on developer machines. See beads
edgartools-j1ui.

This gate must run *before* anything that loads a cassette; by the time a test
session has started it is already too late.

Why an allowlist rather than grepping for ``!!python/``: YAML spells the same
tag three ways, and only the first contains that string. All three are accepted
by vcrpy's loader:

    c: !!python/object/apply:os.getpid []
    c: !<tag:yaml.org,2002:python/object/apply:os.getpid> []
    %TAG !e! tag:yaml.org,2002:python/object/apply:
    ---
    c: !e!os.getpid []

Scanning the parser's event stream sidesteps all of it: the parser resolves
handles and shorthands into full tag URIs, so every spelling arrives here
identically. Parsing also constructs no objects, which is both safe and quick —
the full corpus scans in single-digit seconds, where ``yaml.safe_load`` of the
same files takes minutes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterator, List, Tuple

import yaml

try:  # libyaml when available — roughly an order of magnitude faster
    from yaml import CSafeLoader as _Loader
except ImportError:  # pragma: no cover - depends on local libyaml
    from yaml import SafeLoader as _Loader

# Standard YAML 1.1 tags. A cassette is a recording of HTTP traffic: strings,
# maps, sequences, and base64 bodies. It has no business carrying anything else.
# (The current 171-cassette corpus uses exactly one explicit tag: !!binary.)
_YAML_STANDARD_TAGS = frozenset(
    f"tag:yaml.org,2002:{name}"
    for name in (
        "null", "bool", "int", "float", "binary", "timestamp",
        "str", "seq", "map", "omap", "pairs", "set", "merge", "value", "yaml",
    )
)

DEFAULT_ROOTS = ("tests",)


def iter_cassettes(roots: List[str]) -> Iterator[Path]:
    """Yield every YAML file under ``roots`` that could be loaded as a cassette."""
    for root in roots:
        base = Path(root)
        if base.is_file():
            yield base
            continue
        for pattern in ("*.yaml", "*.yml"):
            yield from sorted(base.rglob(pattern))


def scan(path: Path) -> List[Tuple[int, str]]:
    """Return [(line, tag)] for every non-standard tag in ``path``.

    A file that cannot be parsed is itself a finding — failing closed keeps a
    malformed or truncated cassette from slipping past the gate.
    """
    findings: List[Tuple[int, str]] = []
    try:
        with path.open(encoding="utf-8") as handle:
            for event in yaml.parse(handle, Loader=_Loader):
                tag = getattr(event, "tag", None)
                if tag and tag not in _YAML_STANDARD_TAGS:
                    line = getattr(event.start_mark, "line", -1) + 1
                    findings.append((line, tag))
    except yaml.YAMLError as exc:
        findings.append((-1, f"unparseable: {type(exc).__name__}"))
    except OSError as exc:
        findings.append((-1, f"unreadable: {exc}"))
    return findings


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "roots", nargs="*", default=list(DEFAULT_ROOTS),
        help="files or directories to scan (default: tests)",
    )
    args = parser.parse_args(argv)

    scanned = 0
    failed = False
    for path in iter_cassettes(args.roots):
        scanned += 1
        for line, tag in scan(path):
            failed = True
            where = f"{path}:{line}" if line > 0 else str(path)
            print(f"{where}: disallowed YAML tag {tag!r}", file=sys.stderr)

    if failed:
        print(
            f"\nRefusing {scanned} scanned file(s): a cassette carries a tag that "
            f"PyYAML's unsafe loader would construct.\n"
            f"Cassettes must contain plain recorded traffic only. If this is a "
            f"legitimate new tag, widen the allowlist in {Path(__file__).name} "
            f"deliberately — do not tag-strip a cassette to get past this.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {scanned} YAML file(s) scanned, no disallowed tags.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
