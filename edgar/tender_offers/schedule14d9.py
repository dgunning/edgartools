"""
Schedule 14D-9 - Solicitation/Recommendation Statement.

Filed by a tender offer target company's board of directors, stating whether
shareholders should accept, reject, or remain neutral on the offer. SC 14D-9
filings are HTML-only (no structured XML cover page like Schedule 13D/G), so
this parses the primary document's rendered text directly with lxml.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, List, Optional

from lxml import html as lxml_html

if TYPE_CHECKING:
    from edgar._filings import Filing

__all__ = ["SC_14D9_FORMS", "Schedule14D9", "classify_recommendation"]

SC_14D9_FORMS = ["SC 14D9", "SC 14D9/A"]

# A left/right/straight quote immediately before "Item N" marks a cross-reference
# ("...as described in “Item 4...”") rather than the actual section heading.
# Filtering these out matters: the same failure mode (numbered-index / cross-reference
# text being mistaken for a real item anchor) previously produced fabricated item
# boundaries on 10-Q Part II parsing (GH #918).
_QUOTE_CHARS = "\"“‘'"

# Headings that mark the end of the board's actual recommendation statement and
# the start of the narrative that routinely poisons naive classification (prior
# board positions, a since-superseded stance, a financial advisor's opinion
# summary). Verified present, in this form or a superset of it, in 5 real SC 14D-9
# filings: Lisata Therapeutics, Genco Shipping & Trading, Woodbridge Liquidation
# Trust, and Moody National REIT II (two separate filings). Matched as a loose
# substring (e.g. "background of the" also matches Genco's "Background of the
# Genco Board's Recommendation Regarding the Offer") rather than an exact heading,
# since filers word the heading differently.
_SECTION_BOUNDARY_MARKERS = [
    r"background of the",
    r"reasons for the recommendation",
]

# Hard fallback cap, in characters, for filings that don't use either heading above
# and so have no detected boundary -- keeps classification bounded rather than
# running across an entire (possibly 100,000+ character) Item 4 section. Measured
# recommendation-statement lengths (start of Item 4 to the boundary heading) across
# the same 5 filings ranged 722-1067 chars, so this cap should rarely bind in
# practice; when it does, treat it as a sign the filing's structure is unusual and
# ``recommendation`` may need a second look.
_RECOMMENDATION_WINDOW_CHARS = 2500

# Checked in this order -- reject, then neutral, then accept -- because reject and
# neutral phrasing ("recommends...reject the offer", "express no opinion") is more
# specific and less likely to appear incidentally than accept phrasing ("recommends
# ...tender your shares"), which is the majority case and could otherwise mask a
# rarer reject/neutral statement if checked last. Bounding the window above is what
# actually prevents cross-matching; this ordering is a second line of defense.
_ACCEPT_PATTERNS = [
    r"recommends?\s+that\s+.{0,80}?accept\s+the\s+offer",
    r"recommends?\s+.{0,60}?tender\s+.{0,40}?shares?",
]
_REJECT_PATTERNS = [
    r"recommends?\s+that\s+.{0,80}?reject\s+the\s+offer",
    r"recommends?\s+.{0,60}?not\s+.{0,40}?tender",
    # "...recommends that the Interestholders not accept the Offer" (Woodbridge
    # Liquidation Trust, accession 0001140361-20-000734) -- a real rejection that
    # never uses the word "reject" or "tender" at all.
    r"recommends?\s+.{0,60}?not\s+.{0,20}?accept\s+the\s+offer",
]
_NEUTRAL_PATTERNS = [
    r"express(?:es|ing)?\s+no\s+opinion",
    r"remains?\s+neutral",
    r"no\s+recommendation",
]


def _find_real_item_starts(text: str, item_number: int) -> List[int]:
    """Positions of ``Item N.`` headings, excluding quoted cross-references."""
    pattern = re.compile(rf"Item\s*{item_number}\s*[.\-—]")
    starts = []
    for match in pattern.finditer(text):
        start = match.start()
        prev_char = text[start - 1] if start > 0 else ""
        if prev_char in _QUOTE_CHARS:
            continue
        starts.append(start)
    return starts


def extract_item_section(text: str, item_number: int, next_item_number: int) -> Optional[str]:
    """
    Extract the body text of ``Item {item_number}`` up to ``Item {next_item_number}``.

    A filing can contain several matches for an item heading: a table-of-contents
    entry, cross-references quoted elsewhere in the document, and the real section.
    Real sections carry substantially more text before the next item heading than
    TOC entries or references do, so among the unquoted candidates the longest span
    is taken as the real one.
    """
    starts = _find_real_item_starts(text, item_number)
    next_starts = _find_real_item_starts(text, next_item_number)

    best_span = None
    best_length = -1
    for start in starts:
        later_next = [n for n in next_starts if n > start]
        end = min(later_next) if later_next else len(text)
        length = end - start
        if length > best_length:
            best_length = length
            best_span = (start, end)

    if best_span is None:
        return None
    return text[best_span[0] : best_span[1]].strip()


def _recommendation_window(item4_text: str) -> str:
    """
    The board's recommendation statement: the whitespace-normalized opening of
    Item 4, cut at the first "Background of the..." / "Reasons for the
    Recommendation" heading -- whichever comes first -- or at
    ``_RECOMMENDATION_WINDOW_CHARS`` if neither heading is found.

    Whitespace is fully collapsed (not just nbsp runs) because source HTML line
    wraps routinely break a recommendation sentence across a newline mid-phrase
    (e.g. "...recommends that holders of Shares\\nREJECT the Offer..." in Genco
    Shipping's filing) -- left un-normalized, that newline defeats the ``.``
    wildcard in the classification patterns, silently missing a real match.

    Cutting at the heading, rather than at a fixed length alone, matters: the
    longest real recommendation statement measured (1067 chars) is still well
    inside a fixed cap generous enough to avoid truncating others, which means
    a length-only cutoff still admits the first few hundred characters of the
    background narrative -- exactly where a filing may restate an earlier,
    superseded board position.
    """
    normalized = re.sub(r"\s+", " ", item4_text).strip()
    lowered = normalized.lower()

    boundary = len(normalized)
    for marker in _SECTION_BOUNDARY_MARKERS:
        match = re.search(marker, lowered)
        if match:
            boundary = min(boundary, match.start())

    boundary = min(boundary, _RECOMMENDATION_WINDOW_CHARS)
    return normalized[:boundary].strip()


def classify_recommendation(item4_text: str) -> Optional[str]:
    """
    Classify the board's recommendation from Item 4 narrative text.

    Returns ``"accept"``, ``"reject"``, ``"neutral"``, or ``None``.

    Only ``_recommendation_window(item4_text)`` is examined, not the full
    section -- see that function's docstring for how the cut point is chosen.
    Item 4 as a whole also contains "Background of the Offer" / "Reasons for
    the Recommendation" narrative that can run to 100,000+ characters and
    routinely mentions earlier, superseded board positions or a financial
    advisor's opinion; classifying against the full section risks matching
    that history instead of the board's actual, current recommendation.

    Conservative by design: board recommendations are often hedged or
    conditional ("subject to the fiduciary out...", "no recommendation at
    this time pending..."), so this returns ``None`` rather than guessing
    whenever the language does not clearly match one of the three patterns.
    A confident wrong classification is worse than an honest "unknown" here.

    Known limitation: this still misclassifies a hedge that shares the same
    paragraph as the real recommendation with no heading between them, e.g.
    "...recommends accept. Previously the company had made no recommendation
    regarding the earlier proposal." -- there is no structural boundary to cut
    on there. Not observed in any of the 5 real filings checked against; if it
    turns up in practice, it needs more than a window (e.g. anchoring the match
    to the sentence containing "the Board" as subject).
    """
    if not item4_text:
        return None

    window = _recommendation_window(item4_text).lower()

    if any(re.search(p, window) for p in _REJECT_PATTERNS):
        return "reject"
    if any(re.search(p, window) for p in _NEUTRAL_PATTERNS):
        return "neutral"
    if any(re.search(p, window) for p in _ACCEPT_PATTERNS):
        return "accept"
    return None


class Schedule14D9:
    """
    Schedule 14D-9 - Solicitation/Recommendation Statement.

    Filed by a tender offer target company's board in response to a bidder's
    offer (SC TO-T) or the issuer's own tender offer (SC TO-I), stating
    whether shareholders should accept, reject, or remain neutral.

    Example:
        filing = Filing(form='SC 14D9', ...)
        schedule = Schedule14D9.from_filing(filing)
        schedule.recommendation        # "accept" / "reject" / "neutral" / None
        schedule.recommendation_text   # the raw Item 4 recommendation text
    """

    def __init__(
        self,
        filing: "Filing",
        item4_text: str,
    ):
        self._filing = filing
        self.item4_text = item4_text
        self.recommendation: Optional[str] = classify_recommendation(item4_text)

    @classmethod
    def from_filing(cls, filing: "Filing") -> "Schedule14D9":
        """
        Create a Schedule14D9 instance from a Filing object.

        Args:
            filing: Filing object with form 'SC 14D9' or 'SC 14D9/A'

        Raises:
            AssertionError: If filing is not a Schedule 14D-9 form
            ValueError: If Item 4 (The Solicitation or Recommendation) cannot
                be located in the document. This means the document failed to
                parse structurally, and is distinct from ``recommendation``
                being ``None``, which means Item 4 was found but its language
                did not clearly support accept/reject/neutral.
        """
        assert filing.form in SC_14D9_FORMS, f"Expected SC 14D9 form, got {filing.form}"

        html = filing.html()
        if not html:
            raise ValueError(f"No HTML document found for SC 14D9 filing {filing.accession_no}")

        tree = lxml_html.fromstring(html)
        text = tree.text_content()
        text = re.sub(r"[\xa0 ]+", " ", text)

        item4_text = extract_item_section(text, 4, 5)
        if not item4_text:
            raise ValueError(f"Could not locate Item 4 (The Solicitation or Recommendation) in SC 14D9 filing {filing.accession_no}")

        return cls(filing=filing, item4_text=item4_text)

    @property
    def company_name(self) -> str:
        """Name of the subject (target) company filing this statement."""
        return self._filing.company

    @property
    def cik(self) -> str:
        """CIK of the subject (target) company."""
        return str(self._filing.cik)

    @property
    def is_amendment(self) -> bool:
        """Check if this is an amendment filing."""
        return "/A" in self._filing.form

    @property
    def filing_date(self):
        """The filing date."""
        return self._filing.filing_date

    @property
    def recommendation_text(self) -> str:
        """
        The board's recommendation statement: the same bounded, whitespace-
        normalized window of Item 4 that ``recommendation`` is classified from
        (see ``_RECOMMENDATION_WINDOW_CHARS``), not an arbitrary truncation.

        Use ``item4_text`` for the full Item 4 section (background, reasons,
        fairness opinion summary, etc.), which can be very large.
        """
        return _recommendation_window(self.item4_text)

    @property
    def recommendation_text_truncated(self) -> bool:
        """
        True if ``recommendation_text`` was cut off before the end of Item 4,
        i.e. the recommendation statement itself may run longer than the
        calibrated window. Check this before treating ``recommendation_text``
        as a complete statement.
        """
        return len(re.sub(r"\s+", " ", self.item4_text).strip()) > _RECOMMENDATION_WINDOW_CHARS

    def __rich__(self):
        """Rich console rendering."""
        from edgar.tender_offers.rendering import render_schedule14d9

        return render_schedule14d9(self)

    def __repr__(self):
        from edgar.richtools import repr_rich

        return repr_rich(self.__rich__())
