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

import re
from dataclasses import dataclass, field
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
    # Inclusive item-number → Part ranges, e.g. (1, 4, "I"). Set only for forms
    # whose items are *unique* across parts (10-K), enabling part inference when
    # the TOC didn't surface explicit Part headers. Empty for forms where items
    # repeat across parts (10-Q: Part I Item 1 ≠ Part II Item 1) — there a part
    # must be detected, never inferred from the number.
    item_part_ranges: Tuple[Tuple[int, int, str], ...] = ()
    # Canonical, document-ordered Part sequence for forms whose items *repeat*
    # across parts so the number alone can't name the part (10-Q: ("I", "II") —
    # Part I Item 1 is Financial Statements, Part II Item 1 is Legal Proceedings).
    # Used to fill a Part when the TOC didn't surface explicit Part headers, by
    # locating the single Part I→Part II transition (see :meth:`infer_parts`).
    # Empty for forms with unique items (10-K, which uses ``item_part_ranges``).
    repeating_parts: Tuple[str, ...] = ()
    # Per-item expected content-size bands in characters, as (item_key, low, high)
    # with ``item_key`` the bare, upper-cased item ("1", "1A", "7"). Enforced
    # items only — a section whose extracted length falls outside its band is
    # flagged with a warning and reduced confidence rather than silently returned
    # (Verification Constitution #2; edgartools-9hwf). Curated from the h44r
    # fixture corpus; empty for forms with no enforced bands.
    size_bands: Tuple[Tuple[str, int, int], ...] = ()
    # Section/title vocabulary for the regex pattern extractor, as
    # {section_key: ((regex, title), ...)}. Item-based forms (10-K/10-Q/20-F/8-K)
    # key on "Item N" headers; title-based forms (424B and, later, S-1/DEF 14A)
    # key on prospectus titles ("Use of Proceeds", "Underwriting"). This is the
    # single home of the vocabulary the pattern extractor consumes today and the
    # TOC engine will consume after the Phase 3 routing flip (edgartools-llmp.3).
    section_patterns: Dict[str, Tuple[Tuple[str, str], ...]] = field(default_factory=dict)
    # True for forms whose TOC entries are section *titles* (424B prospectuses,
    # later S-1/DEF 14A) rather than "Item N" labels. Gates the TOC engine's
    # title-vocabulary parser (edgartools-llmp.3): when set, the analyzer matches
    # TOC link text against ``section_patterns`` to key sections; when unset (all
    # Item forms), that parser is never entered and the item-number path is used
    # exactly as before — so the flip cannot affect 10-K/10-Q/8-K/20-F.
    title_based: bool = False

    def match_section_pattern(self, text: str) -> Optional[str]:
        """Return the section key whose title vocabulary matches ``text``, else None.

        First key (in declaration order) with a matching regex wins, mirroring the
        pattern extractor's per-section iteration. Only meaningful for title-based
        forms; returns None when the form declares no ``section_patterns``.
        """
        cleaned = text.strip()
        for key, patterns in self.section_patterns.items():
            for regex, _title in patterns:
                if re.match(regex, cleaned, re.IGNORECASE):
                    return key
        return None

    def section_order(self, key: str) -> int:
        """Canonical sort order for a title-based section key (declaration index).

        Declaration order in ``section_patterns`` follows the canonical prospectus
        sequence (About → Summary → Risk Factors → Use of Proceeds → …), so it is
        a stable order for sections that carry no item number. Unknown keys sort
        last.
        """
        for i, k in enumerate(self.section_patterns):
            if k == key:
                return i
        return 99999

    def band_for(self, item_key: Optional[str]) -> Optional[Tuple[int, int]]:
        """Return the ``(low, high)`` size band for a bare item key, or None.

        None means the item is not size-enforced on this form (so callers must
        not flag it), matching the pre-schema ``SIZE_BANDS.get(form, {}).get(...)``
        miss behaviour.
        """
        if not item_key:
            return None
        key = item_key.upper()
        for k, low, high in self.size_bands:
            if k == key:
                return (low, high)
        return None

    def match_text(self, text_lower: str, use_exclusions: bool = True) -> Optional[str]:
        """Return the normalized item name for the first matching rule, else None."""
        for rule in self.text_rules:
            if rule.matches(text_lower, use_exclusions=use_exclusions):
                return rule.item
        return None

    def part_for_item(self, item_name: str) -> Optional[str]:
        """Infer the canonical Part ("Part II") for an item name ("Item 7").

        Returns None when the form has no item→part mapping (items repeat across
        parts, or unknown form) or the item number falls outside the ranges, so
        callers fall back to whatever part context was actually detected.
        """
        if not self.item_part_ranges:
            return None
        m = re.match(r'item\s*(\d+)', item_name, re.IGNORECASE)
        if not m:
            return None
        num = int(m.group(1))
        for lo, hi, roman in self.item_part_ranges:
            if lo <= num <= hi:
                return f"Part {roman}"
        return None

    @property
    def seed_part(self) -> Optional[str]:
        """The Part a document-order TOC walk starts in, before any Part header.

        For forms whose items repeat across an ordered Part sequence (10-Q: Part I
        then Part II), items appearing before any Part header belong to the first
        Part — a 10-Q always opens with Part I. Seeding the walk with that Part
        keeps Part I Item 1 (Financial Statements) from collapsing onto a bare
        "Item 1" key that downstream then resolves to Part II Item 1 (Legal
        Proceedings). Returns None for forms with unique items (10-K infers the
        Part from the item number) so their walk is unchanged (edgartools-3usf).
        """
        return f"Part {self.repeating_parts[0]}" if self.repeating_parts else None


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

# Canonical 10-K item→part layout (items are unique across parts):
# Part I: 1–4, Part II: 5–9, Part III: 10–14, Part IV: 15–16.
_TEN_K_ITEM_PART_RANGES = ((1, 4, "I"), (5, 9, "II"), (10, 14, "III"), (15, 16, "IV"))

# Per-item content-size bands (chars), enforced items only. Generated from the
# h44r corpus (tests/fixtures/parser_corpus/size_bands.json); regenerate the
# corpus and copy the enforced bands here when fixtures rotate. Bands are
# intentionally generous (median/5 .. median*8) so they flag only gross
# anomalies. Item 8's band assumes inlined financial statements — a filer that
# incorporates them by reference is legitimately small (handled by the rescue).
_TEN_K_SIZE_BANDS = (
    ("1",  8_034,  321_384),    # Business
    ("1A", 15_978, 639_136),    # Risk Factors
    ("1C", 1_542,  61_680),     # Cybersecurity
    ("7",  11_440, 457_616),    # MD&A
    ("8",  26_136, 1_045_472),  # Financial Statements (large-cap; see caveat)
    ("9A", 791,    31_640),     # Controls and Procedures
    ("16", 0,      16_400),     # Form 10-K Summary — optional, usually "None.";
                                # no undersize floor (a tiny body is correct, not
                                # truncated), high guard kept for over-capture.
                                # Floor was an artifact of Item 16 absorbing the
                                # signatures block before edgartools-nqzc split it.
)
_TEN_Q_SIZE_BANDS = (
    ("1", 18_009, 720_376),     # Financial Statements
    ("2", 10_134, 405_368),     # MD&A
    ("6", 518,    20_720),      # Exhibits
)

# Per-form section/title vocabulary for the regex pattern extractor (moved here
# from SectionExtractor.SECTION_PATTERNS — FormSchema is the single home of form
# knowledge, edgartools-llmp.2 / D2). Item-based forms key on "Item N" headers;
# 424B keys on prospectus titles. The extractor exposes a back-compat projection
# of these; a golden parity test guards against drift.
_TEN_K_SECTION_PATTERNS = {
    'business': (
        ('^(Item|ITEM)\\s+1\\.?\\s*Business', 'Item 1 - Business'),
        ('^Business\\s*$', 'Business'),
        ('^Business Overview', 'Business Overview'),
        ('^Our Business', 'Our Business'),
        ('^Company Overview', 'Company Overview'),
    ),
    'risk_factors': (
        ('^(Item|ITEM)\\s+1A\\.?\\s*Risk\\s+Factors', 'Item 1A - Risk Factors'),
        ('^Risk\\s+Factors', 'Risk Factors'),
        ('^Factors\\s+That\\s+May\\s+Affect', 'Risk Factors'),
    ),
    'unresolved_staff_comments': (
        ('^(Item|ITEM)\\s+1B\\.?\\s*Unresolved\\s+Staff\\s+Comments', 'Item 1B - Unresolved Staff Comments'),
        ('^Unresolved\\s+Staff\\s+Comments', 'Unresolved Staff Comments'),
    ),
    'cybersecurity': (
        ('^(Item|ITEM)\\s+1C\\.?\\s*Cybersecurity', 'Item 1C - Cybersecurity'),
        ('^Cybersecurity\\s+Risk\\s+Management', 'Cybersecurity'),
        ('^Cybersecurity', 'Cybersecurity'),
    ),
    'properties': (
        ('^(Item|ITEM)\\s+2\\.?\\s*Properties', 'Item 2 - Properties'),
        ('^Properties', 'Properties'),
        ('^Real\\s+Estate', 'Real Estate'),
    ),
    'legal_proceedings': (
        ('^(Item|ITEM)\\s+3\\.?\\s*Legal\\s+Proceedings', 'Item 3 - Legal Proceedings'),
        ('^Legal\\s+Proceedings', 'Legal Proceedings'),
        ('^Litigation', 'Litigation'),
    ),
    'market_risk': (
        ('^(Item|ITEM)\\s+7A\\.?\\s*Quantitative.*Disclosures', 'Item 7A - Market Risk'),
        ('^Market\\s+Risk', 'Market Risk'),
        ('^Quantitative.*Qualitative.*Market\\s+Risk', 'Market Risk'),
    ),
    'mda': (
        ('^(Item|ITEM)\\s+7\\.?\\s*Management.*Discussion', 'Item 7 - MD&A'),
        ('^Management.*Discussion.*Analysis', 'MD&A'),
        ('^MD&A', 'MD&A'),
    ),
    'financial_statements': (
        ('^(Item|ITEM)\\s+8\\.?\\s*Financial\\s+Statements', 'Item 8 - Financial Statements'),
        ('^Financial\\s+Statements', 'Financial Statements'),
        ('^Consolidated\\s+Financial\\s+Statements', 'Consolidated Financial Statements'),
    ),
    'controls_procedures': (
        ('^(Item|ITEM)\\s+9A\\.?\\s*Controls.*Procedures', 'Item 9A - Controls and Procedures'),
        ('^Controls.*Procedures', 'Controls and Procedures'),
        ('^Internal\\s+Control', 'Internal Controls'),
    ),
    # Part III — Items 10-14.  Many filers incorporate these by reference from
    # their proxy statement; the Part III block is a compact "see proxy" stub
    # where each item header is a bold paragraph (not a semantic heading node).
    # Adding these patterns registers each header as a boundary so that, e.g.,
    # Item 10's span terminates at the Item 11 header rather than absorbing it
    # (GH #880 / edgartools-01x4).  Keys use the part_iii_item_N convention so
    # that Section.parse_section_name() resolves part="III" and item="N"
    # automatically, matching what _ITEM_TO_PART_10K and __getitem__ expect.
    'part_iii_item_10': (
        ('^(Item|ITEM)\\s+10\\.?\\s*Directors', 'Item 10 - Directors, Executive Officers and Corporate Governance'),
    ),
    'part_iii_item_11': (
        ('^(Item|ITEM)\\s+11\\.?\\s*Executive\\s+Compensation', 'Item 11 - Executive Compensation'),
    ),
    'part_iii_item_12': (
        ('^(Item|ITEM)\\s+12\\.?\\s*Security\\s+Ownership', 'Item 12 - Security Ownership of Certain Beneficial Owners'),
    ),
    'part_iii_item_13': (
        ('^(Item|ITEM)\\s+13\\.?\\s*Certain\\s+Relationships', 'Item 13 - Certain Relationships and Related Transactions'),
    ),
    'part_iii_item_14': (
        ('^(Item|ITEM)\\s+14\\.?\\s*Principal\\s+Accountant', 'Item 14 - Principal Accountant Fees and Services'),
    ),
    # Part IV — Item 16 (Form 10-K Summary, optional).  Item 15 (Exhibits) is
    # already represented in the TOC-extraction path as 'part_iv_item_15'.
    'part_iv_item_16': (
        ('^(Item|ITEM)\\s+16\\.?\\s*Form\\s+10-K\\s+Summary', 'Item 16 - Form 10-K Summary'),
    ),
}

_TEN_Q_SECTION_PATTERNS = {
    'part_i_item_1': (
        ('^(Item|ITEM)\\s+1\\.?\\s*[-–—.]?\\s*Financial\\s+Statements', 'Item 1 - Financial Statements'),
        ('^Financial\\s+Statements', 'Financial Statements'),
        ('^Condensed.*Financial\\s+Statements', 'Condensed Financial Statements'),
    ),
    'part_i_item_2': (
        ('^(Item|ITEM)\\s+2\\.?\\s*[-–—.]?\\s*Management.*Discussion', 'Item 2 - MD&A'),
        ('^Management.*Discussion.*Analysis', 'MD&A'),
    ),
    'part_i_item_3': (
        ('^(Item|ITEM)\\s+3\\.?\\s*[-–—.]?\\s*Quantitative.*Disclosures', 'Item 3 - Market Risk'),
        ('^Market\\s+Risk', 'Market Risk'),
    ),
    'part_i_item_4': (
        ('^(Item|ITEM)\\s+4\\.?\\s*[-–—.]?\\s*Controls.*Procedures', 'Item 4 - Controls and Procedures'),
        ('^Controls.*Procedures', 'Controls and Procedures'),
    ),
    'part_ii_item_1': (
        ('^(Item|ITEM)\\s+1\\.?\\s*[-–—.]?\\s*Legal\\s+Proceedings', 'Item 1 - Legal Proceedings'),
        ('^Legal\\s+Proceedings', 'Legal Proceedings'),
    ),
    'part_ii_item_1a': (
        ('^(Item|ITEM)\\s+1A\\.?\\s*[-–—.]?\\s*Risk\\s+Factors', 'Item 1A - Risk Factors'),
        ('^Risk\\s+Factors', 'Risk Factors'),
    ),
    'part_ii_item_2': (
        ('^(Item|ITEM)\\s+2\\.?\\s*[-–—.]?\\s*Unregistered\\s+Sales', 'Item 2 - Unregistered Sales'),
        ('^Unregistered\\s+Sales.*Equity', 'Unregistered Sales'),
    ),
    'part_ii_item_3': (
        ('^(Item|ITEM)\\s+3\\.?\\s*[-–—.]?\\s*Defaults', 'Item 3 - Defaults Upon Senior Securities'),
        ('^Defaults\\s+Upon\\s+Senior', 'Defaults Upon Senior Securities'),
    ),
    'part_ii_item_4': (
        ('^(Item|ITEM)\\s+4\\.?\\s*[-–—.]?\\s*Mine\\s+Safety', 'Item 4 - Mine Safety Disclosures'),
        ('^Mine\\s+Safety', 'Mine Safety Disclosures'),
    ),
    'part_ii_item_5': (
        ('^(Item|ITEM)\\s+5\\.?\\s*[-–—.]?\\s*Other\\s+Information', 'Item 5 - Other Information'),
        ('^Other\\s+Information', 'Other Information'),
    ),
    'part_ii_item_6': (
        ('^(Item|ITEM)\\s+6\\.?\\s*[-–—.]?\\s*Exhibits', 'Item 6 - Exhibits'),
        ('^Exhibits', 'Exhibits'),
    ),
}

_TWENTY_F_SECTION_PATTERNS = {
    'item_1': (
        ('^(Item|ITEM)\\s+1\\.?\\s*[-–—.]?\\s*Identity.*Directors', 'Item 1 - Identity of Directors, Senior Management and Advisers'),
        ('^Identity.*Directors.*Senior\\s+Management', 'Identity of Directors'),
    ),
    'item_2': (
        ('^(Item|ITEM)\\s+2\\.?\\s*[-–—.]?\\s*Offer\\s+Statistics', 'Item 2 - Offer Statistics and Expected Timetable'),
        ('^Offer\\s+Statistics.*Timetable', 'Offer Statistics'),
    ),
    'item_3': (
        ('^(Item|ITEM)\\s+3\\.?\\s*[-–—.]?\\s*Key\\s+Information', 'Item 3 - Key Information'),
        ('^Key\\s+Information', 'Key Information'),
        ('^Risk\\s+Factors', 'Risk Factors'),
    ),
    'item_4': (
        ('^(Item|ITEM)\\s+4\\.?\\s*[-–—.]?\\s*Information\\s+on\\s+the\\s+Company', 'Item 4 - Information on the Company'),
        ('^Information\\s+on\\s+the\\s+Company', 'Information on the Company'),
        ('^Business\\s+Overview', 'Business Overview'),
    ),
    'item_4a': (
        ('^(Item|ITEM)\\s+4A\\.?\\s*[-–—.]?\\s*Unresolved\\s+Staff', 'Item 4A - Unresolved Staff Comments'),
        ('^Unresolved\\s+Staff\\s+Comments', 'Unresolved Staff Comments'),
    ),
    'item_5': (
        ('^(Item|ITEM)\\s+5\\.?\\s*[-–—.]?\\s*Operating.*Financial\\s+Review', 'Item 5 - Operating and Financial Review and Prospects'),
        ('^Operating.*Financial\\s+Review', 'Operating and Financial Review'),
        ('^Management.*Discussion.*Analysis', 'MD&A'),
    ),
    'item_6': (
        ('^(Item|ITEM)\\s+6\\.?\\s*[-–—.]?\\s*Directors.*Senior\\s+Management.*Employees', 'Item 6 - Directors, Senior Management and Employees'),
        ('^Directors.*Senior\\s+Management.*Employees', 'Directors and Employees'),
    ),
    'item_7': (
        ('^(Item|ITEM)\\s+7\\.?\\s*[-–—.]?\\s*Major\\s+Shareholders', 'Item 7 - Major Shareholders and Related Party Transactions'),
        ('^Major\\s+Shareholders.*Related\\s+Party', 'Major Shareholders'),
    ),
    'item_8': (
        ('^(Item|ITEM)\\s+8\\.?\\s*[-–—.]?\\s*Financial\\s+Information', 'Item 8 - Financial Information'),
        ('^Financial\\s+Information', 'Financial Information'),
    ),
    'item_9': (
        ('^(Item|ITEM)\\s+9\\.?\\s*[-–—.]?\\s*The\\s+Offer\\s+and\\s+Listing', 'Item 9 - The Offer and Listing'),
        ('^The\\s+Offer\\s+and\\s+Listing', 'Offer and Listing'),
    ),
    'item_10': (
        ('^(Item|ITEM)\\s+10\\.?\\s*[-–—.]?\\s*Additional\\s+Information', 'Item 10 - Additional Information'),
        ('^Additional\\s+Information', 'Additional Information'),
    ),
    'item_11': (
        ('^(Item|ITEM)\\s+11\\.?\\s*[-–—.]?\\s*Quantitative.*Qualitative.*Market\\s+Risk', 'Item 11 - Quantitative and Qualitative Disclosures About Market Risk'),
        ('^Quantitative.*Qualitative.*Market\\s+Risk', 'Market Risk Disclosures'),
    ),
    'item_12': (
        ('^(Item|ITEM)\\s+12\\.?\\s*[-–—.]?\\s*Description.*Securities', 'Item 12 - Description of Securities Other Than Equity Securities'),
        ('^Description.*Securities.*Equity', 'Securities Description'),
    ),
    'item_13': (
        ('^(Item|ITEM)\\s+13\\.?\\s*[-–—.]?\\s*Defaults', 'Item 13 - Defaults, Dividend Arrearages and Delinquencies'),
        ('^Defaults.*Dividend.*Arrearages', 'Defaults and Arrearages'),
    ),
    'item_14': (
        ('^(Item|ITEM)\\s+14\\.?\\s*[-–—.]?\\s*Material\\s+Modifications', 'Item 14 - Material Modifications to the Rights of Security Holders'),
        ('^Material\\s+Modifications.*Rights', 'Material Modifications'),
    ),
    'item_15': (
        ('^(Item|ITEM)\\s+15\\.?\\s*[-–—.]?\\s*Controls.*Procedures', 'Item 15 - Controls and Procedures'),
        ('^Controls.*Procedures', 'Controls and Procedures'),
    ),
    'item_16': (
        ('^(Item|ITEM)\\s+16\\.?\\s*[-–—.]?\\s*\\[?Reserved\\]?', 'Item 16 - [Reserved]'),
    ),
    'item_16a': (
        ('^(Item|ITEM)\\s+16A\\.?\\s*[-–—.]?\\s*Audit\\s+Committee', 'Item 16A - Audit Committee Financial Expert'),
        ('^Audit\\s+Committee\\s+Financial\\s+Expert', 'Audit Committee Expert'),
    ),
    'item_16b': (
        ('^(Item|ITEM)\\s+16B\\.?\\s*[-–—.]?\\s*Code\\s+of\\s+Ethics', 'Item 16B - Code of Ethics'),
        ('^Code\\s+of\\s+Ethics', 'Code of Ethics'),
    ),
    'item_16c': (
        ('^(Item|ITEM)\\s+16C\\.?\\s*[-–—.]?\\s*Principal\\s+Accountant', 'Item 16C - Principal Accountant Fees and Services'),
        ('^Principal\\s+Accountant\\s+Fees', 'Accountant Fees'),
    ),
    'item_16d': (
        ('^(Item|ITEM)\\s+16D\\.?\\s*[-–—.]?\\s*Exemptions.*Audit\\s+Committees', 'Item 16D - Exemptions from the Listing Standards for Audit Committees'),
        ('^Exemptions.*Listing\\s+Standards', 'Audit Committee Exemptions'),
    ),
    'item_16e': (
        ('^(Item|ITEM)\\s+16E\\.?\\s*[-–—.]?\\s*Purchases.*Equity\\s+Securities', 'Item 16E - Purchases of Equity Securities by the Issuer'),
        ('^Purchases.*Equity\\s+Securities.*Issuer', 'Equity Purchases'),
    ),
    'item_16f': (
        ('^(Item|ITEM)\\s+16F\\.?\\s*[-–—.]?\\s*Change.*Certifying\\s+Accountant', "Item 16F - Change in Registrant's Certifying Accountant"),
        ('^Change.*Certifying\\s+Accountant', 'Accountant Change'),
    ),
    'item_16g': (
        ('^(Item|ITEM)\\s+16G\\.?\\s*[-–—.]?\\s*Corporate\\s+Governance', 'Item 16G - Corporate Governance'),
        ('^Corporate\\s+Governance', 'Corporate Governance'),
    ),
    'item_16h': (
        ('^(Item|ITEM)\\s+16H\\.?\\s*[-–—.]?\\s*Mine\\s+Safety', 'Item 16H - Mine Safety Disclosure'),
        ('^Mine\\s+Safety\\s+Disclosure', 'Mine Safety'),
    ),
    'item_16i': (
        ('^(Item|ITEM)\\s+16I\\.?\\s*[-–—.]?\\s*Disclosure.*Foreign\\s+Jurisdictions', 'Item 16I - Disclosure Regarding Foreign Jurisdictions That Prevent Inspections'),
        ('^Disclosure.*Foreign\\s+Jurisdictions.*Inspections', 'Foreign Jurisdiction Disclosure'),
        ('^(Item|ITEM)\\s+16I\\.?\\s*$', 'Item 16I'),
    ),
    'item_16j': (
        ('^(Item|ITEM)\\s+16J\\.?\\s*[-–—.]?\\s*Insider\\s+Trading', 'Item 16J - Insider Trading Policies'),
        ('^Insider\\s+Trading\\s+Policies', 'Insider Trading Policies'),
        ('^(Item|ITEM)\\s+16J\\.?\\s*$', 'Item 16J'),
    ),
    'item_16k': (
        ('^(Item|ITEM)\\s+16K\\.?\\s*[-–—.]?\\s*Cybersecurity', 'Item 16K - Cybersecurity'),
        ('^Cybersecurity', 'Cybersecurity'),
        ('^(Item|ITEM)\\s+16K\\.?\\s*$', 'Item 16K'),
    ),
    'item_17': (
        ('^(Item|ITEM)\\s+17\\.?\\s*[-–—.]?\\s*Financial\\s+Statements', 'Item 17 - Financial Statements'),
    ),
    'item_18': (
        ('^(Item|ITEM)\\s+18\\.?\\s*[-–—.]?\\s*Financial\\s+Statements', 'Item 18 - Financial Statements'),
    ),
    'item_19': (
        ('^(Item|ITEM)\\s+19\\.?\\s*[-–—.]?\\s*Exhibits', 'Item 19 - Exhibits'),
        ('^Exhibits', 'Exhibits'),
    ),
    'part_i': (
        ('^PART\\s+I\\s*$', 'Part I'),
    ),
    'part_ii': (
        ('^PART\\s+II\\s*$', 'Part II'),
    ),
    'part_iii': (
        ('^PART\\s+III\\s*$', 'Part III'),
    ),
    'part_iv': (
        ('^PART\\s+IV\\s*$', 'Part IV'),
    ),
    'part_v': (
        ('^PART\\s+V\\s*$', 'Part V'),
    ),
    'signatures': (
        ('^SIGNATURES?\\s*$', 'Signatures'),
    ),
}

_EIGHT_K_SECTION_PATTERNS = {
    'item_101': (
        ('^(Item|ITEM)\\s+1\\.\\s*01', 'Item 1.01 - Entry into Material Agreement'),
        ('^Entry.*Material.*Agreement', 'Material Agreement'),
    ),
    'item_102': (
        ('^(Item|ITEM)\\s+1\\.\\s*02', 'Item 1.02 - Termination of Material Agreement'),
        ('^Termination.*Material.*Agreement', 'Termination of Agreement'),
    ),
    'item_103': (
        ('^(Item|ITEM)\\s+1\\.\\s*03', 'Item 1.03 - Bankruptcy or Receivership'),
        ('^Bankruptcy.*Receivership', 'Bankruptcy'),
    ),
    'item_104': (
        ('^(Item|ITEM)\\s+1\\.\\s*04', 'Item 1.04 - Mine Safety'),
        ('^Mine\\s+Safety', 'Mine Safety'),
    ),
    'item_105': (
        ('^(Item|ITEM)\\s+1\\.\\s*05', 'Item 1.05 - Material Cybersecurity Incidents'),
        ('^Material\\s+Cybersecurity', 'Cybersecurity Incidents'),
    ),
    'item_201': (
        ('^(Item|ITEM)\\s+2\\.\\s*01', 'Item 2.01 - Completion of Acquisition'),
        ('^Completion.*Acquisition', 'Acquisition'),
    ),
    'item_202': (
        ('^(Item|ITEM)\\s+2\\.\\s*02', 'Item 2.02 - Results of Operations'),
        ('^Results.*Operations', 'Results of Operations'),
    ),
    'item_203': (
        ('^(Item|ITEM)\\s+2\\.\\s*03', 'Item 2.03 - Creation of Direct Financial Obligation'),
        ('^Creation.*Financial\\s+Obligation', 'Financial Obligation'),
    ),
    'item_204': (
        ('^(Item|ITEM)\\s+2\\.\\s*04', 'Item 2.04 - Triggering Events'),
        ('^Triggering\\s+Events', 'Triggering Events'),
    ),
    'item_205': (
        ('^(Item|ITEM)\\s+2\\.\\s*05', 'Item 2.05 - Costs with Exit or Disposal'),
        ('^Costs.*Exit.*Disposal', 'Exit or Disposal Costs'),
    ),
    'item_206': (
        ('^(Item|ITEM)\\s+2\\.\\s*06', 'Item 2.06 - Material Impairments'),
        ('^Material\\s+Impairments', 'Material Impairments'),
    ),
    'item_301': (
        ('^(Item|ITEM)\\s+3\\.\\s*01', 'Item 3.01 - Notice of Delisting'),
        ('^Notice.*Delisting', 'Delisting Notice'),
    ),
    'item_302': (
        ('^(Item|ITEM)\\s+3\\.\\s*02', 'Item 3.02 - Unregistered Sales of Equity'),
        ('^Unregistered\\s+Sales', 'Unregistered Sales'),
    ),
    'item_303': (
        ('^(Item|ITEM)\\s+3\\.\\s*03', 'Item 3.03 - Material Modification to Rights'),
        ('^Material\\s+Modification.*Rights', 'Rights Modification'),
    ),
    'item_401': (
        ('^(Item|ITEM)\\s+4\\.\\s*01', 'Item 4.01 - Changes in Certifying Accountant'),
        ('^Changes.*Accountant', 'Accountant Changes'),
    ),
    'item_402': (
        ('^(Item|ITEM)\\s+4\\.\\s*02', 'Item 4.02 - Non-Reliance on Financial Statements'),
        ('^Non-Reliance.*Financial', 'Non-Reliance'),
    ),
    'item_501': (
        ('^(Item|ITEM)\\s+5\\.\\s*01', 'Item 5.01 - Changes in Control'),
        ('^Changes.*Control', 'Changes in Control'),
    ),
    'item_502': (
        ('^(Item|ITEM)\\s+5\\.\\s*02', 'Item 5.02 - Departure/Election of Directors'),
        ('^Departure.*Directors.*Officers', 'Director/Officer Changes'),
    ),
    'item_503': (
        ('^(Item|ITEM)\\s+5\\.\\s*03', 'Item 5.03 - Amendments to Articles/Bylaws'),
        ('^Amendments.*Articles.*Bylaws', 'Charter Amendments'),
    ),
    'item_504': (
        ('^(Item|ITEM)\\s+5\\.\\s*04', 'Item 5.04 - Temporary Suspension of Trading'),
        ('^Temporary\\s+Suspension', 'Suspension of Trading'),
    ),
    'item_505': (
        ('^(Item|ITEM)\\s+5\\.\\s*05', 'Item 5.05 - Amendment to Code of Ethics'),
        ('^Amendment.*Code.*Ethics', 'Code of Ethics'),
    ),
    'item_506': (
        ('^(Item|ITEM)\\s+5\\.\\s*06', 'Item 5.06 - Change in Shell Company Status'),
        ('^Change.*Shell\\s+Company', 'Shell Company Status'),
    ),
    'item_507': (
        ('^(Item|ITEM)\\s+5\\.\\s*07', 'Item 5.07 - Submission of Matters to Vote'),
        ('^Submission.*Vote', 'Shareholder Vote'),
    ),
    'item_508': (
        ('^(Item|ITEM)\\s+5\\.\\s*08', 'Item 5.08 - Shareholder Nominations'),
        ('^Shareholder\\s+Nominations', 'Shareholder Nominations'),
    ),
    'item_601': (
        ('^(Item|ITEM)\\s+6\\.\\s*01', 'Item 6.01 - ABS Informational Material'),
        ('^ABS\\s+Informational', 'ABS Information'),
    ),
    'item_602': (
        ('^(Item|ITEM)\\s+6\\.\\s*02', 'Item 6.02 - Change of Servicer/Trustee'),
        ('^Change.*Servicer.*Trustee', 'Servicer Change'),
    ),
    'item_603': (
        ('^(Item|ITEM)\\s+6\\.\\s*03', 'Item 6.03 - Change in Credit Enhancement'),
        ('^Change.*Credit\\s+Enhancement', 'Credit Enhancement'),
    ),
    'item_604': (
        ('^(Item|ITEM)\\s+6\\.\\s*04', 'Item 6.04 - Failure to Make Distribution'),
        ('^Failure.*Distribution', 'Distribution Failure'),
    ),
    'item_605': (
        ('^(Item|ITEM)\\s+6\\.\\s*05', 'Item 6.05 - Securities Act Updating'),
        ('^Securities\\s+Act\\s+Updating', 'Securities Act Update'),
    ),
    'item_606': (
        ('^(Item|ITEM)\\s+6\\.\\s*06', 'Item 6.06 - Static Pool'),
        ('^Static\\s+Pool', 'Static Pool'),
    ),
    'item_701': (
        ('^(Item|ITEM)\\s+7\\.\\s*01', 'Item 7.01 - Regulation FD Disclosure'),
        ('^Regulation\\s+FD', 'Regulation FD'),
    ),
    'item_801': (
        ('^(Item|ITEM)\\s+8\\.\\s*01', 'Item 8.01 - Other Events'),
        ('^Other\\s+Events', 'Other Events'),
    ),
    'item_901': (
        ('^(Item|ITEM)\\s+9\\.\\s*01', 'Item 9.01 - Financial Statements and Exhibits'),
        ('^Financial.*Exhibits', 'Financial Statements and Exhibits'),
    ),
    # SIGNATURES is the terminal section of every 8-K (and 8-K/A). Registering it
    # here as a named section gives `_find_section_end` a hard boundary so the last
    # item never over-extends into the signatures block, and makes the block
    # retrievable as `document.sections.named("signatures")`.
    # Pattern mirrors the 20-F entry (edgartools-papt, GH #879).
    'signatures': (
        ('^SIGNATURES?\\s*$', 'Signatures'),
    ),
}

_FOUR24B_SECTION_PATTERNS = {
    'about_this_prospectus': (
        ('^ABOUT\\s+THIS\\s+PROSPECTUS', 'About This Prospectus'),
        ('^About\\s+This\\s+Prospectus', 'About This Prospectus'),
    ),
    'summary': (
        ('^(?:THE\\s+)?OFFERING\\s*$', 'The Offering'),
        ('^SUMMARY\\s*$', 'Summary'),
        ('^Summary\\s*$', 'Summary'),
        ('^PROSPECTUS\\s+SUMMARY', 'Prospectus Summary'),
    ),
    'risk_factors': (
        ('^RISK\\s+FACTORS\\s*$', 'Risk Factors'),
        ('^Risk\\s+Factors\\s*$', 'Risk Factors'),
    ),
    'use_of_proceeds': (
        ('^USE\\s+OF\\s+PROCEEDS\\s*$', 'Use of Proceeds'),
        ('^Use\\s+of\\s+Proceeds\\s*$', 'Use of Proceeds'),
    ),
    'dilution': (
        ('^DILUTION\\s*$', 'Dilution'),
        ('^Dilution\\s*$', 'Dilution'),
    ),
    'capitalization': (
        ('^CAPITALIZATION\\s*$', 'Capitalization'),
        ('^Capitalization\\s*$', 'Capitalization'),
    ),
    'description_of_securities': (
        ('^DESCRIPTION\\s+OF\\s+(?:CAPITAL\\s+)?STOCK', 'Description of Capital Stock'),
        ('^Description\\s+of\\s+(?:Capital\\s+)?Stock', 'Description of Capital Stock'),
        ('^DESCRIPTION\\s+OF\\s+(?:THE\\s+)?SECURITIES', 'Description of Securities'),
        ('^Description\\s+of\\s+(?:the\\s+)?Securities', 'Description of Securities'),
        ('^DESCRIPTION\\s+OF\\s+(?:THE\\s+)?NOTES', 'Description of Notes'),
        ('^Description\\s+of\\s+(?:the\\s+)?Notes', 'Description of Notes'),
    ),
    'description_of_debt_securities': (
        ('^DESCRIPTION\\s+OF\\s+DEBT\\s+SECURITIES', 'Description of Debt Securities'),
        ('^Description\\s+of\\s+Debt\\s+Securities', 'Description of Debt Securities'),
    ),
    'description_of_warrants': (
        ('^DESCRIPTION\\s+OF\\s+WARRANTS', 'Description of Warrants'),
        ('^Description\\s+of\\s+Warrants', 'Description of Warrants'),
    ),
    'selling_stockholders': (
        ('^SELLING\\s+(?:STOCK|SECURITY)\\s*HOLDERS', 'Selling Stockholders'),
        ('^Selling\\s+(?:Stock|Security)\\s*[Hh]olders', 'Selling Stockholders'),
    ),
    'underwriting': (
        ('^UNDERWRITING\\s*$', 'Underwriting'),
        ('^Underwriting\\s*$', 'Underwriting'),
    ),
    'plan_of_distribution': (
        ('^PLAN\\s+OF\\s+DISTRIBUTION', 'Plan of Distribution'),
        ('^Plan\\s+of\\s+Distribution', 'Plan of Distribution'),
    ),
    'legal_matters': (
        ('^LEGAL\\s+MATTERS\\s*$', 'Legal Matters'),
        ('^Legal\\s+Matters\\s*$', 'Legal Matters'),
    ),
    'experts': (
        ('^EXPERTS\\s*$', 'Experts'),
        ('^Experts\\s*$', 'Experts'),
    ),
    'tax_considerations': (
        ('^(?:U\\.?S\\.?\\s+)?(?:FEDERAL\\s+)?(?:INCOME\\s+)?TAX\\s+CONSIDERATIONS', 'Tax Considerations'),
        ('^(?:U\\.?S\\.?\\s+)?(?:Federal\\s+)?(?:Income\\s+)?Tax\\s+Considerations', 'Tax Considerations'),
        ('^(?:CERTAIN|MATERIAL)\\s+.*TAX\\s+(?:CONSIDERATIONS|CONSEQUENCES)', 'Tax Considerations'),
    ),
    'where_you_can_find_more_information': (
        ('^WHERE\\s+YOU\\s+CAN\\s+FIND\\s+(?:MORE|ADDITIONAL)\\s+INFORMATION', 'Where You Can Find More Information'),
        ('^Where\\s+You\\s+Can\\s+Find\\s+(?:More|Additional)\\s+Information', 'Where You Can Find More Information'),
    ),
    'incorporation_by_reference': (
        ('^INCORPORATION\\s+(?:OF\\s+CERTAIN\\s+(?:INFORMATION|DOCUMENTS)\\s+)?BY\\s+REFERENCE', 'Incorporation by Reference'),
        ('^Incorporation\\s+(?:of\\s+Certain\\s+(?:Information|Documents)\\s+)?by\\s+Reference', 'Incorporation by Reference'),
    ),
}

# The full prospectus title vocabulary, shared by BOTH the S-1 and 424B schemas.
# A registration statement (S-1) and a final prospectus (424B4) are the same
# offering document, so they carry the same sections — Forward-Looking Statements /
# Dividend Policy / MD&A / Business / Management / Executive Compensation /
# Related-Party Transactions / Principal Stockholders / Shares Eligible for Future
# Sale, on top of the core offering sections (Use of Proceeds, Dilution,
# Underwriting, Experts, ...). The core entries reference the `_FOUR24B_SECTION_PATTERNS`
# tuples so the shared sections stay in lockstep; the debt-prospectus entries
# (Description of Debt Securities) likewise come from there. Declaration order
# follows the canonical prospectus sequence (summary → risk → ... → experts),
# which FormSchema.section_order() uses to sort title sections that carry no item
# number.
#
# 424B originally carried only the core offering sections, on the theory that a
# 424B "usually omits" the narrative ones. That holds for short shelf/debt
# takedowns (424B2/B5) but NOT for full IPO prospectuses (424B1/B4), which repeat
# the entire S-1 body. With the sparse vocabulary those narrative sections went
# unmatched, the authoritative-TOC-span clustering split on the resulting gap, and
# the last matched section (e.g. Dilution) absorbed everything after it —
# hundreds of KB of MD&A + Business + financial statements (gh-878 / edgartools-ti82).
# Sharing the full vocabulary surfaces those sections (bounding their neighbours)
# and is a no-op for takedowns that genuinely lack them.
_S1_SECTION_PATTERNS = {
    'about_this_prospectus': _FOUR24B_SECTION_PATTERNS['about_this_prospectus'],
    'summary': _FOUR24B_SECTION_PATTERNS['summary'],
    'risk_factors': _FOUR24B_SECTION_PATTERNS['risk_factors'],
    'forward_looking_statements': (
        ('^(?:SPECIAL\\s+NOTE\\s+(?:REGARDING|ABOUT)\\s+)?(?:CAUTIONARY\\s+(?:NOTE|STATEMENT)\\s+(?:REGARDING\\s+)?)?FORWARD[- ]LOOKING\\s+STATEMENTS', 'Forward-Looking Statements'),
        ('^(?:Special\\s+Note\\s+(?:Regarding|About)\\s+)?(?:Cautionary\\s+(?:Note|Statement)\\s+(?:Regarding\\s+)?)?Forward[- ]Looking\\s+Statements', 'Forward-Looking Statements'),
    ),
    'use_of_proceeds': _FOUR24B_SECTION_PATTERNS['use_of_proceeds'],
    'dividend_policy': (
        ('^DIVIDEND\\s+POLICY', 'Dividend Policy'),
        ('^Dividend\\s+Policy', 'Dividend Policy'),
        ('^DIVIDENDS\\s*$', 'Dividends'),
        ('^Dividends\\s*$', 'Dividends'),
    ),
    'capitalization': _FOUR24B_SECTION_PATTERNS['capitalization'],
    'dilution': _FOUR24B_SECTION_PATTERNS['dilution'],
    'mda': (
        ("^(?:MANAGEMENT.?S\\s+)?DISCUSSION\\s+AND\\s+ANALYSIS", 'MD&A'),
        ("^(?:Management.?s\\s+)?Discussion\\s+and\\s+Analysis", 'MD&A'),
    ),
    'business': (
        ('^BUSINESS\\s*$', 'Business'),
        ('^Business\\s*$', 'Business'),
        ('^OUR\\s+BUSINESS', 'Our Business'),
        ('^Our\\s+Business', 'Our Business'),
    ),
    'management': (
        ('^MANAGEMENT\\s*$', 'Management'),
        ('^Management\\s*$', 'Management'),
        ('^DIRECTORS.*EXECUTIVE\\s+OFFICERS', 'Directors and Executive Officers'),
        ('^Directors.*Executive\\s+Officers', 'Directors and Executive Officers'),
    ),
    'executive_compensation': (
        ('^EXECUTIVE\\s+COMPENSATION', 'Executive Compensation'),
        ('^Executive\\s+Compensation', 'Executive Compensation'),
    ),
    'related_party_transactions': (
        ('^CERTAIN\\s+RELATIONSHIPS\\s+AND\\s+RELATED\\s*(?:PARTY|PERSON)?\\s*TRANSACTIONS', 'Certain Relationships and Related Party Transactions'),
        ('^Certain\\s+Relationships\\s+and\\s+Related\\s*(?:Party|Person)?\\s*Transactions', 'Certain Relationships and Related Party Transactions'),
        ('^RELATED\\s*(?:PARTY|PERSON)\\s+TRANSACTIONS', 'Related Party Transactions'),
        ('^Related\\s*(?:Party|Person)\\s+Transactions', 'Related Party Transactions'),
    ),
    'principal_stockholders': (
        ('^PRINCIPAL\\s+(?:AND\\s+SELLING\\s+)?(?:STOCK|SECURITY)\\s*HOLDERS', 'Principal Stockholders'),
        ('^Principal\\s+(?:and\\s+Selling\\s+)?(?:Stock|Security)\\s*[Hh]olders', 'Principal Stockholders'),
        ('^(?:SECURITY\\s+)?OWNERSHIP\\s+OF\\s+CERTAIN\\s+BENEFICIAL', 'Security Ownership'),
        ('^(?:Security\\s+)?Ownership\\s+of\\s+Certain\\s+Beneficial', 'Security Ownership'),
    ),
    'selling_stockholders': _FOUR24B_SECTION_PATTERNS['selling_stockholders'],
    'description_of_securities': _FOUR24B_SECTION_PATTERNS['description_of_securities'],
    'description_of_debt_securities': _FOUR24B_SECTION_PATTERNS['description_of_debt_securities'],
    'description_of_warrants': _FOUR24B_SECTION_PATTERNS['description_of_warrants'],
    'shares_eligible_for_future_sale': (
        ('^SHARES\\s+(?:OR\\s+SECURITIES\\s+)?ELIGIBLE\\s+FOR\\s+FUTURE\\s+SALE', 'Shares Eligible for Future Sale'),
        ('^Shares\\s+(?:or\\s+Securities\\s+)?Eligible\\s+for\\s+Future\\s+Sale', 'Shares Eligible for Future Sale'),
    ),
    'tax_considerations': _FOUR24B_SECTION_PATTERNS['tax_considerations'],
    'underwriting': _FOUR24B_SECTION_PATTERNS['underwriting'],
    'plan_of_distribution': _FOUR24B_SECTION_PATTERNS['plan_of_distribution'],
    'legal_matters': _FOUR24B_SECTION_PATTERNS['legal_matters'],
    'experts': _FOUR24B_SECTION_PATTERNS['experts'],
    'where_you_can_find_more_information': _FOUR24B_SECTION_PATTERNS['where_you_can_find_more_information'],
    'incorporation_by_reference': _FOUR24B_SECTION_PATTERNS['incorporation_by_reference'],
}

# DEF 14A proxy statements are title-based too (edgartools-x341 / gh-867), but
# their vocabulary is Schedule 14A / Reg S-K governance + compensation rather than
# prospectus offering sections. Declaration order follows the canonical proxy
# sequence (notice → summary → proposals → governance → compensation → audit →
# ownership → general). First key whose regex matches wins (FormSchema.match_
# section_pattern), so more-specific keys precede the broader ones they could be
# confused with (director_compensation before executive_compensation; CD&A and
# equity-plan keyed on their own distinctive phrases). Multiple numbered proposals
# all collapse to voting_proposals (the issue's single-key contract): first wins,
# the rest still contribute TOC boundaries so nothing bleeds.
_DEF14A_SECTION_PATTERNS = {
    'notice_of_meeting': (
        ('^NOTICE\\s+OF\\s+(?:THE\\s+)?(?:\\d{4}\\s+)?(?:ANNUAL|SPECIAL)\\s+MEETING', 'Notice of Annual Meeting'),
        ('^Notice\\s+of\\s+(?:the\\s+)?(?:\\d{4}\\s+)?(?:Annual|Special)\\s+Meeting', 'Notice of Annual Meeting'),
    ),
    'proxy_summary': (
        ('^PROXY\\s+(?:STATEMENT\\s+)?SUMMARY', 'Proxy Summary'),
        ('^Proxy\\s+(?:Statement\\s+)?Summary', 'Proxy Summary'),
    ),
    'voting_proposals': (
        ('^(?:PROPOSAL|ITEM)\\s+(?:NO\\.?\\s*)?\\d+', 'Voting Proposal'),
        ('^(?:Proposal|Item)\\s+(?:No\\.?\\s*)?\\d+', 'Voting Proposal'),
        ('^MANAGEMENT\\s+PROPOSALS?', 'Management Proposals'),
        ('^Management\\s+Proposals?', 'Management Proposals'),
        ('^ELECTION\\s+OF\\s+DIRECTORS', 'Election of Directors'),
        ('^Election\\s+of\\s+Directors', 'Election of Directors'),
    ),
    'corporate_governance': (
        ('^CORPORATE\\s+GOVERNANCE', 'Corporate Governance'),
        ('^Corporate\\s+Governance', 'Corporate Governance'),
        ('^BOARD\\s+OF\\s+DIRECTORS\\s*$', 'Board of Directors'),
        ('^Board\\s+of\\s+Directors\\s*$', 'Board of Directors'),
    ),
    'director_compensation': (
        ('^DIRECTOR\\s+COMPENSATION', 'Director Compensation'),
        ('^Director\\s+Compensation', 'Director Compensation'),
        ('^COMPENSATION\\s+OF\\s+DIRECTORS', 'Director Compensation'),
        ('^Compensation\\s+of\\s+Directors', 'Director Compensation'),
    ),
    'compensation_discussion_and_analysis': (
        ('^COMPENSATION\\s+DISCUSSION\\s+AND\\s+ANALYSIS', 'Compensation Discussion and Analysis'),
        ('^Compensation\\s+Discussion\\s+and\\s+Analysis', 'Compensation Discussion and Analysis'),
    ),
    'pay_versus_performance': (
        ('^PAY\\s+(?:VERSUS|VS\\.?|FOR)\\s+PERFORMANCE', 'Pay Versus Performance'),
        ('^Pay\\s+(?:Versus|Vs\\.?|for)\\s+Performance', 'Pay Versus Performance'),
    ),
    'executive_compensation': (
        ('^EXECUTIVE\\s+COMPENSATION', 'Executive Compensation'),
        ('^Executive\\s+Compensation', 'Executive Compensation'),
        ('^COMPENSATION\\s+OF\\s+(?:NAMED\\s+)?EXECUTIVE', 'Executive Compensation'),
        ('^Compensation\\s+of\\s+(?:Named\\s+)?Executive', 'Executive Compensation'),
    ),
    'equity_compensation_plan_information': (
        ('^EQUITY\\s+COMPENSATION\\s+PLAN\\s+INFORMATION', 'Equity Compensation Plan Information'),
        ('^Equity\\s+Compensation\\s+Plan\\s+Information', 'Equity Compensation Plan Information'),
    ),
    'audit_matters': (
        ('^AUDIT\\b.*\\b(?:COMMITTEE|REPORT|MATTERS|FEES)\\b', 'Audit Matters'),
        ('^Audit\\b.*\\b(?:Committee|Report|Matters|Fees)\\b', 'Audit Matters'),
        ('^REPORT\\s+OF\\s+THE\\s+AUDIT', 'Audit Committee Report'),
        ('^Report\\s+of\\s+the\\s+Audit', 'Audit Committee Report'),
    ),
    'security_ownership': (
        ('^SECURITY\\s+OWNERSHIP', 'Security Ownership'),
        ('^Security\\s+Ownership', 'Security Ownership'),
        ('^(?:STOCK\\s+)?OWNERSHIP\\s+OF\\s+(?:CERTAIN\\s+)?(?:BENEFICIAL|DIRECTORS)', 'Security Ownership'),
        ('^(?:Stock\\s+)?Ownership\\s+of\\s+(?:Certain\\s+)?(?:Beneficial|Directors)', 'Security Ownership'),
        ('^BENEFICIAL\\s+OWNERSHIP', 'Security Ownership'),
        ('^Beneficial\\s+Ownership', 'Security Ownership'),
    ),
    'related_party_transactions': (
        ('^CERTAIN\\s+RELATIONSHIPS', 'Certain Relationships and Related Party Transactions'),
        ('^Certain\\s+Relationships', 'Certain Relationships and Related Party Transactions'),
        ('^RELATED\\s+PART(?:Y|IES)', 'Related Party Transactions'),
        ('^Related\\s+Part(?:y|ies)', 'Related Party Transactions'),
    ),
    'stockholder_proposals': (
        # Allow an optional "Proposal Nos. 5-8" group prefix: filers fuse the
        # proposal-number tab and the section title into one TOC entry
        # ("PROPOSAL NOs. 5- Shareholder Proposals"), which the plural "NOs."
        # keeps out of the voting_proposals "Proposal N" pattern (edgartools-zas6).
        ('^(?:PROPOSALS?\\s+NOS?\\.?[\\s\\d.,&–—-]*)?(?:STOCKHOLDER|SHAREHOLDER)\\s+PROPOSALS?', 'Stockholder Proposals'),
        ('^(?:Proposals?\\s+Nos?\\.?[\\s\\d.,&–—-]*)?(?:Stockholder|Shareholder)\\s+Proposals?', 'Stockholder Proposals'),
    ),
    'general_information': (
        ('^GENERAL\\s+INFORMATION', 'General Information'),
        ('^General\\s+Information', 'General Information'),
        ('^(?:QUESTIONS\\s+AND\\s+ANSWERS|ABOUT\\s+THE\\s+(?:ANNUAL\\s+)?MEETING)', 'General Information'),
        ('^(?:Questions\\s+and\\s+Answers|About\\s+the\\s+(?:Annual\\s+)?Meeting)', 'General Information'),
    ),
    'other_matters': (
        ('^OTHER\\s+MATTERS', 'Other Matters'),
        ('^Other\\s+Matters', 'Other Matters'),
    ),
}

TEN_K_SCHEMA = FormSchema(max_bare_item=15, text_rules=_TEN_K_RULES,
                          skip_unmatched_text=False,
                          item_part_ranges=_TEN_K_ITEM_PART_RANGES,
                          size_bands=_TEN_K_SIZE_BANDS,
                          section_patterns=_TEN_K_SECTION_PATTERNS)
TEN_Q_SCHEMA = FormSchema(max_bare_item=6, text_rules=_TEN_Q_RULES, skip_unmatched_text=True,
                          repeating_parts=("I", "II"), size_bands=_TEN_Q_SIZE_BANDS,
                          section_patterns=_TEN_Q_SECTION_PATTERNS)
# 20-F / 8-K / 424B carry no 10-K-style item-number TOC vocabulary, so every
# field except section_patterns matches DEFAULT_SCHEMA — the TOC analyzer behaves
# exactly as it did when these forms resolved to DEFAULT_SCHEMA. They exist as
# named schemas only to home their pattern vocabulary.
TWENTY_F_SCHEMA = FormSchema(section_patterns=_TWENTY_F_SECTION_PATTERNS)
EIGHT_K_SCHEMA = FormSchema(section_patterns=_EIGHT_K_SECTION_PATTERNS)
# 424B prospectuses are title-based: title_based gates the TOC engine's
# title-vocabulary parser (edgartools-llmp.3). 20-F/8-K keep title_based=False —
# their TOC is Item-number-based like a 10-K's. 424B shares the full prospectus
# vocabulary with S-1 (`_S1_SECTION_PATTERNS`): a final IPO prospectus (424B4)
# repeats the entire S-1 body, so it must recognise the same narrative sections —
# without them the trailing matched section swallowed hundreds of KB (gh-878).
FOUR24B_SCHEMA = FormSchema(section_patterns=_S1_SECTION_PATTERNS, title_based=True)
# S-1 registration statements are title-based prospectuses too (edgartools-ybth /
# gh-866): title_based routes anchored S-1s through the TOC engine exactly like a
# 424B, dissolving the same content-bleed by construction. Item forms keep
# title_based=False and are untouched.
S1_SCHEMA = FormSchema(section_patterns=_S1_SECTION_PATTERNS, title_based=True)
# DEF 14A / PRE 14A proxy statements (edgartools-x341 / gh-867). title_based=True
# routes proxies through the TOC title engine. The flip was HELD until the proxy
# failure modes were solved — body back-references (authoritative-TOC selection,
# 4m4x), hierarchical sub-entries (indent depth, gb99), fragmented/divider TOCs
# (coalescing + divider depth, zas6), and header-only slivers (drop guardrail,
# this issue) — then verified across a 32-filer diverse corpus (30/32 emit clean
# labeled sections, no mislabeled slivers; residuals NEE/BRK-B are honest
# fallbacks tracked as jmso/bpab). Now flipped.
DEF14A_SCHEMA = FormSchema(section_patterns=_DEF14A_SECTION_PATTERNS, title_based=True)
# Forms without any registered vocabulary (40-F, ...): no text fallback
# (raw text is returned), default bare-item cap, no patterns.
DEFAULT_SCHEMA = FormSchema(max_bare_item=15, text_rules=(), skip_unmatched_text=False)

_SCHEMAS: Dict[str, FormSchema] = {
    "10-K": TEN_K_SCHEMA,
    "10-K/A": TEN_K_SCHEMA,
    "10-Q": TEN_Q_SCHEMA,
    "10-Q/A": TEN_Q_SCHEMA,
    "20-F": TWENTY_F_SCHEMA,
    "8-K": EIGHT_K_SCHEMA,
    "424B": FOUR24B_SCHEMA,
    "S-1": S1_SCHEMA,
    "S-1/A": S1_SCHEMA,
    "DEF 14A": DEF14A_SCHEMA,
    "PRE 14A": DEF14A_SCHEMA,
}


def get_form_schema(form: Optional[str]) -> FormSchema:
    """Resolve a form string to its schema.

    ``None`` resolves to the 10-K schema, preserving the legacy default where an
    unspecified form was treated as 10-K-shaped.
    """
    if form is None:
        return TEN_K_SCHEMA
    # All 424B variants (424B1..424B8, /A amendments) share the one prospectus
    # schema — the pattern extractor already collapses them to the '424B' key.
    if form.startswith("424B"):
        return FOUR24B_SCHEMA
    return _SCHEMAS.get(form, DEFAULT_SCHEMA)
