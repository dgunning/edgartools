"""
Grep — exact-match content search for SEC filings.

grep = "Where does this exact text appear?" — every match with location and context.
search = "What's relevant to this topic?" — BM25 fuzzy ranking.

Usage:
    >>> filing.grep("going concern")
    >>> tenk.grep("going concern")
    >>> tenk.notes.grep("Level 3")
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional
from edgar.richtools import repr_rich


@dataclass
class GrepMatch:
    """A single grep match with location and context."""
    location: str        # "primary", "EX-10.1", "Note 4 - Fair Value", etc.
    match: str           # The matched text itself
    context: str         # Surrounding text with match in context
    char_offset: Optional[int] = None  # Character offset in the source text
    overflowed: bool = False  # Internal sentinel for a bounded search that stopped early

    def __repr__(self):
        # Truncate context for repr
        ctx = self.context
        if len(ctx) > 80:
            ctx = ctx[:77] + "..."
        return f"{self.location}:  {ctx}"

    def __str__(self):
        return f"{self.location}:  {self.context}"


class GrepResult:
    """Collection of grep matches — list-like with summary display."""

    def __init__(self, pattern: str, matches: List[GrepMatch], overflowed: bool = False):
        self.pattern = pattern
        self.matches = matches
        self.overflowed = overflowed or any(match.overflowed for match in matches)

    def __len__(self):
        return len(self.matches)

    def __iter__(self):
        return iter(self.matches)

    def __getitem__(self, index):
        return self.matches[index]

    def __bool__(self):
        return len(self.matches) > 0

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __rich__(self):
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text

        if not self.matches:
            return Panel(Text("No matches found", style="dim"),
                        title=f"grep '{self.pattern}'")

        table = Table(show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("Location", style="cyan", min_width=15)
        table.add_column("Context", min_width=50)

        for m in self.matches[:20]:  # Cap display at 20
            table.add_row(m.location, m.context)

        title = f"grep '{self.pattern}' ({len(self.matches)} matches)"
        if len(self.matches) > 20:
            title += f" — showing first 20"
        return Panel(table, title=title)

    def to_context(self, detail: str = 'standard') -> str:
        """AI-optimized context string.

        Args:
            detail: 'minimal' (count only), 'standard' (location + context), 'full' (all matches)
        """
        if not self.matches:
            return f"grep '{self.pattern}': 0 matches"

        if detail == 'minimal':
            locations = sorted(set(m.location for m in self.matches))
            return f"grep '{self.pattern}': {len(self.matches)} matches in {', '.join(locations)}"

        limit = 10 if detail == 'standard' else len(self.matches)
        lines = [f"grep '{self.pattern}': {len(self.matches)} matches"]
        for m in self.matches[:limit]:
            lines.append(f"  {m.location}:  {m.context}")
        if len(self.matches) > limit:
            lines.append(f"  ... {len(self.matches) - limit} more matches")
        return "\n".join(lines)

    def __repr_html__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())


def _lowercase_expansion_boundaries(text: str) -> list[tuple[int, int, int, int]]:
    """Return sparse lowered/source boundaries for lowercase expansions.

    Each tuple contains ``(lower_start, lower_end, source_index,
    extra_before)``. Ordinary one-to-one characters need no stored mapping.
    """
    boundaries = []
    lowered_offset = 0
    cumulative_extra = 0
    for source_index, character in enumerate(text):
        lowered_length = len(character.lower())
        if lowered_length > 1:
            boundaries.append((
                lowered_offset,
                lowered_offset + lowered_length,
                source_index,
                cumulative_extra,
            ))
            cumulative_extra += lowered_length - 1
        lowered_offset += lowered_length
    return boundaries


def _lowered_index_to_source_index(
    lowered_index: int,
    boundaries: list[tuple[int, int, int, int]],
) -> int:
    """Translate one lowered-text index using sparse expansion boundaries."""
    low = 0
    high = len(boundaries)
    while low < high:
        middle = (low + high) // 2
        if boundaries[middle][0] <= lowered_index:
            low = middle + 1
        else:
            high = middle

    if low == 0:
        return lowered_index

    lower_start, lower_end, source_index, extra_before = boundaries[low - 1]
    if lowered_index < lower_end:
        return source_index

    extra_after = extra_before + (lower_end - lower_start - 1)
    return lowered_index - extra_after


def _grep_text(
    text: str,
    pattern: str,
    location: str,
    regex: bool = False,
    context_chars: int = 100,
    *,
    max_matches: Optional[int] = None,
    max_match_chars: Optional[int] = None,
    regex_timeout: Optional[float] = None,
) -> List[GrepMatch]:
    """Core grep function: search text for pattern, return matches with context.

    Always case-insensitive (SEC text has inconsistent casing). Optional
    limits return one marked sentinel after the permitted matches or when a
    match span exceeds ``max_match_chars``. Without limits, behavior is unchanged.
    """
    if not text or not pattern:
        return []

    matches = []

    def add_overflow_sentinel(offset: int) -> None:
        matches.append(GrepMatch(location, "", "", char_offset=offset, overflowed=True))

    if regex:
        regex_engine = re
        if regex_timeout is not None:
            # The standard-library engine has no timeout. This path is used by
            # bounded MCP searches; ordinary Filing.grep() keeps stdlib re.
            try:
                import regex as regex_engine
            except ImportError as exc:
                raise RuntimeError(
                    "Timed regex search requires the 'regex' package from the 'ai' extra."
                ) from exc
        try:
            compiled = regex_engine.compile(pattern, regex_engine.IGNORECASE)
        except regex_engine.error:
            return []

        regex_matches = (
            compiled.finditer(text)
            if regex_timeout is None
            else compiled.finditer(text, timeout=regex_timeout)
        )

        for m in regex_matches:
            match_start = m.start()
            match_end = m.end()
            if max_match_chars is not None and match_end - match_start > max_match_chars:
                add_overflow_sentinel(match_start)
                break
            if max_matches is not None and len(matches) >= max_matches:
                add_overflow_sentinel(match_start)
                break
            start = max(0, match_start - context_chars)
            end = min(len(text), match_end + context_chars)
            context = text[start:end].strip()
            if start > 0:
                context = "..." + context
            if end < len(text):
                context = context + "..."
            matches.append(GrepMatch(
                location=location,
                match=m.group(),
                context=context,
                char_offset=match_start,
            ))
    else:
        # Case-insensitive substring search
        text_lower = text.lower()
        pattern_lower = pattern.lower()
        expansion_boundaries = None
        if len(text_lower) != len(text):
            # Only expanded characters need explicit entries; ordinary text
            # indexes map by subtracting cumulative expansion lengths.
            expansion_boundaries = _lowercase_expansion_boundaries(text)
        start_pos = 0
        while True:
            pos = text_lower.find(pattern_lower, start_pos)
            if pos == -1:
                break
            lower_match_end = pos + len(pattern_lower)
            source_start = (
                _lowered_index_to_source_index(pos, expansion_boundaries)
                if expansion_boundaries is not None
                else pos
            )
            source_end = (
                _lowered_index_to_source_index(lower_match_end - 1, expansion_boundaries) + 1
                if expansion_boundaries is not None
                else lower_match_end
            )
            if max_match_chars is not None and source_end - source_start > max_match_chars:
                add_overflow_sentinel(source_start)
                break
            if max_matches is not None and len(matches) >= max_matches:
                add_overflow_sentinel(source_start)
                break
            ctx_start = max(0, source_start - context_chars)
            ctx_end = min(len(text), source_end + context_chars)
            context = text[ctx_start:ctx_end].strip()
            if ctx_start > 0:
                context = "..." + context
            if ctx_end < len(text):
                context = context + "..."
            matches.append(GrepMatch(
                location=location,
                match=text[source_start:source_end],
                context=context,
                char_offset=source_start,
            ))
            start_pos = pos + 1

    return matches
