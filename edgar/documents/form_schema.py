"""
Per-form section schema (edgartools-fhno; design sprint Decision D1).

The TOC analyzer historically baked 10-K shape into supposedly form-agnostic
code: a bare-item-number cap of 15, a text-keyword table mapping
"Financial Statements" → Item 8, and a matching sort table — all gated by
scattered ``if self.form in ("10-Q", ...)`` / ``if self.form not in
("10-K", ...)`` branches. Each new form (10-Q, 20-F, 40-F, S-1, DEF 14A) was
bolted on as another branch, and the branch count only grew.

This module makes form-awareness **data, not branches**: a declarative
``FormSchema`` per form, consulted by a form-agnostic analyzer. Adding a form is
adding a table entry, not editing conditionals across `toc_analyzer.py`.

Behavioural note — the schema preserves one pre-existing inconsistency to avoid
a behaviour change during the refactor: section-name normalization applies an
"…and the word 'item' is absent" exclusion to a few keyword rules (so
"Item 1 Business"-style text isn't double-mapped), but the sort-order lookup
does not. Both are reproduced exactly via the ``use_exclusions`` flag on
:meth:`FormSchema.match_text`. Unifying them is a candidate cleanup, tracked
separately.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class TextItemRule:
    """Map TOC entry text to a normalized item name by keyword.

    A rule matches when every string in ``required`` is a substring of the
    lower-cased text and (when exclusions are applied) none of ``excluded`` is.
    """
    item: str                       # normalized name, e.g. "Item 1"
    required: Tuple[str, ...]        # all must be present (AND)
    excluded: Tuple[str, ...] = ()   # none may be present (when use_exclusions)

    def matches(self, text_lower: str, use_exclusions: bool = True) -> bool:
        if not all(s in text_lower for s in self.required):
            return False
        if use_exclusions and any(s in text_lower for s in self.excluded):
            return False
        return True


@dataclass(frozen=True)
class FormSchema:
    """Declarative description of how a form's TOC maps to sections.

    Attributes:
        max_bare_item: Largest plausible *bare* item number in a TOC cell. Caps
            the page-number-vs-item heuristic — a 10-Q has only Items 1–6, so a
            ``<td>8</td>`` page cell must not become "Item 8".
        text_rules: Ordered keyword→item rules for the text fallback, first match
            wins. Empty for forms with no 10-K-style item vocabulary (e.g. 20-F).
        skip_unmatched_text: When a text rule doesn't match, return "" (signal to
            skip the row) instead of the raw text. True only for 10-Q, where
            emitting raw section text produced bogus ``part_i_<text>`` keys.
    """
    max_bare_item: int = 15
    text_rules: Tuple[TextItemRule, ...] = ()
    skip_unmatched_text: bool = False

    def match_text(self, text_lower: str, use_exclusions: bool = True) -> Optional[str]:
        """Return the normalized item name for the first matching rule, else None."""
        for rule in self.text_rules:
            if rule.matches(text_lower, use_exclusions=use_exclusions):
                return rule.item
        return None


# 10-K text vocabulary. Order mirrors the historical elif chain (first match
# wins). The "item" exclusion on the first four prevents double-mapping text
# that already contains an explicit "Item N" (which a higher-priority regex
# handles first).
_TEN_K_RULES: Tuple[TextItemRule, ...] = (
    TextItemRule("Item 1",  ("business",), ("item",)),
    TextItemRule("Item 1A", ("risk factors",), ("item",)),
    TextItemRule("Item 2",  ("properties",), ("item",)),
    TextItemRule("Item 3",  ("legal proceedings",), ("item",)),
    TextItemRule("Item 7",  ("management", "discussion")),
    TextItemRule("Item 8",  ("financial statements",)),
    TextItemRule("Item 15", ("exhibits",)),
)

# 10-Q keeps only the safe overlap with 10-K: Risk Factors is Part II Item 1A on
# both. Every other 10-K mapping is wrong on a 10-Q, so unmatched text is skipped
# rather than emitted (see skip_unmatched_text).
_TEN_Q_RULES: Tuple[TextItemRule, ...] = (
    TextItemRule("Item 1A", ("risk factors",), ("item",)),
)

TEN_K_SCHEMA = FormSchema(max_bare_item=15, text_rules=_TEN_K_RULES, skip_unmatched_text=False)
TEN_Q_SCHEMA = FormSchema(max_bare_item=6, text_rules=_TEN_Q_RULES, skip_unmatched_text=True)
# Forms without a 10-K-style item vocabulary (20-F, 40-F, S-1, ...): no text
# fallback (raw text is returned), default bare-item cap.
DEFAULT_SCHEMA = FormSchema(max_bare_item=15, text_rules=(), skip_unmatched_text=False)

_SCHEMAS: Dict[str, FormSchema] = {
    "10-K": TEN_K_SCHEMA,
    "10-K/A": TEN_K_SCHEMA,
    "10-Q": TEN_Q_SCHEMA,
    "10-Q/A": TEN_Q_SCHEMA,
}


def get_form_schema(form: Optional[str]) -> FormSchema:
    """Resolve a form string to its schema.

    ``None`` resolves to the 10-K schema, preserving the legacy default where an
    unspecified form was treated as 10-K-shaped.
    """
    if form is None:
        return TEN_K_SCHEMA
    return _SCHEMAS.get(form, DEFAULT_SCHEMA)
