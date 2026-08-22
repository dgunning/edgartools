"""Parity gate for the SECTION_PATTERNS -> FormSchema migration (edgartools-llmp.2).

The per-form section/title vocabulary historically lived as a 490-line
``SectionExtractor.SECTION_PATTERNS`` class dict. Phase 2 moves that data onto
each ``FormSchema`` (the single home of form knowledge), leaving the pattern
extractor to read it from the schema. This module is the parity safety net the
design mandates *before* the move:

  * ``section_patterns_golden.json`` is a verbatim dump of the pre-migration
    dict. The projection the extractor exposes must remain byte-identical to it,
    so any transcription drift in the move fails loudly. The 424B entry was
    deliberately re-snapshotted when 424B adopted the full prospectus vocabulary
    it now shares with S-1 (gh-878 / edgartools-ti82): a final IPO prospectus
    repeats the entire S-1 body, so 424B must recognise the same narrative
    sections. The 10-K entry was re-snapshotted for edgartools-4agg, which added
    the seven items that had no vocabulary entry at all (4, 5, 6, 9, 9B, 9C, 15)
    — on a filing whose only usable headers are "Item N" markers those items were
    unrecoverable and their content was absorbed by the preceding item. That
    change is purely additive: no pre-existing pattern was edited or removed.
    The 10-K, 10-Q and 20-F entries were re-snapshotted again for the
    item-separator fix (edgartools-dt1f): every item-numbered pattern now takes
    its separator from ``_ITEM_SEP`` rather than spelling ``\\.?\\s*`` inline,
    so that "Item 1: Business" and "Item 1 - Business" match as well as
    "Item 1. Business". Each new pattern accepts a strict superset of what its
    predecessor accepted — see
    tests/issues/regression/test_dt1f_item_separator.py, which asserts that
    superset property against this file's own previous spelling rather than
    trusting the re-snapshot.
    The same three entries were re-snapshotted once more on 2026-08-22 for
    edgartools-dt1f.1 Defect B: ``_ITEM_SEP`` gained an optional parenthesized
    designation, so "ITEM 9A(T). CONTROLS AND PROCEDURES" — the SEC's
    transitional designation for a smaller reporting company's internal-control
    report, roughly 2007-2010 — matches item 9A instead of dying on the "(".
    68 of the 274 patterns changed and every one of them by that substitution
    alone: no pattern was edited, reordered, relabelled or removed, and the new
    separator accepts a strict superset of the old spellings. Both properties
    were asserted mechanically before the file was rewritten, which is the only
    thing that makes a re-snapshot meaningful — a golden regenerated from the
    code it is supposed to be guarding proves nothing on its own.
    The 10-K entry alone was re-snapshotted on 2026-08-22 for edgartools-dt1f.1
    Defect A: Items 4 and 14 have each carried two titles, and only the modern
    one was in the vocabulary, so every pre-2011 "Item 4: Submission of Matters
    to a Vote of Security Holders" and pre-2003 "Item 14: Exhibits, Financial
    Statement Schedules and Reports on Form 8-K" was found as a header and then
    discarded at match time. Two patterns were APPENDED, one to each key; the
    same mechanical check as above was run first and showed every pre-existing
    pattern, label and ordering byte-identical, with the diff confined to those
    two additions.
  * The data must actually live on the schema now (``FormSchema.section_patterns``),
    not only on the extractor — that is what lets the Phase 3 routing flip
    (edgartools-llmp.3) feed prospectus section text through the TOC engine using
    the same vocabulary.
  * A behavioural check on a synthetic 424B confirms title-based detection is
    unchanged (the 424B parity gate called out in the redesign doc).
"""
import json
from pathlib import Path

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from edgar.documents.extractors.pattern_section_extractor import SectionExtractor
from edgar.documents.form_schema import get_form_schema

_GOLDEN = Path(__file__).parent / "fixtures" / "parser_corpus" / "section_patterns_golden.json"


def _load_golden():
    with open(_GOLDEN) as f:
        return json.load(f)


def test_section_patterns_match_golden():
    """The migrated forms' pattern tables stay byte-identical to the pre-migration dump.

    Scoped to the golden's own keys so a *new* title-based form (S-1,
    edgartools-ybth) can be added without weakening the migration-drift guard on
    the original five forms.
    """
    golden = _load_golden()
    current = {
        form: {sec: [list(t) for t in pats] for sec, pats in secs.items()}
        for form, secs in SectionExtractor.SECTION_PATTERNS.items()
        if form in golden
    }
    assert current == golden, "SECTION_PATTERNS drifted from the golden snapshot"


def test_form_keyset_unchanged():
    """The set of forms with pattern vocab must not grow or shrink silently.

    S-1 joined the original five when the Phase 3 flip extended to registration
    statements (edgartools-ybth / gh-866); DEF 14A / PRE 14A joined when the proxy
    title engine flipped (edgartools-x341 / gh-867). Any further change must be
    deliberate.
    """
    assert set(SectionExtractor.SECTION_PATTERNS) == {
        "10-K", "10-Q", "20-F", "8-K", "424B", "S-1", "DEF 14A", "PRE 14A"
    }


def test_patterns_live_on_the_schema():
    """Each form's patterns are sourced from its FormSchema, not only the extractor."""
    golden = _load_golden()
    for form, secs in golden.items():
        schema_patterns = get_form_schema(form).section_patterns
        assert schema_patterns, f"{form} schema carries no section_patterns"
        projected = {sec: [list(t) for t in pats] for sec, pats in schema_patterns.items()}
        assert projected == secs, f"{form}: schema patterns differ from golden"


def test_424b_variants_resolve_to_424b_schema():
    """424B1..424B8 share the one 424B vocabulary (extractor maps them already)."""
    base = get_form_schema("424B").section_patterns
    assert base, "424B schema missing patterns"
    # The extractor maps any 424B* form to the '424B' key; the schema is the home.
    assert "use_of_proceeds" in base and "underwriting" in base


def test_424b_title_detection_unchanged():
    """Behavioural parity: a synthetic 424B still detects its title-based sections."""
    html = """
    <html><body>
    <h2>Use of Proceeds</h2><p>We intend to use the net proceeds for general purposes.</p>
    <h2>Dilution</h2><p>Your interest will be diluted.</p>
    <h2>Underwriting</h2><p>The underwriters have agreed to purchase the shares.</p>
    </body></html>
    """
    sections = parse_html(html, ParserConfig(form="424B5")).sections
    assert "use_of_proceeds" in sections
    assert "dilution" in sections
    assert "underwriting" in sections
