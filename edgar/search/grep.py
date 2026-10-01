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
from typing import Iterator, List, Optional
from edgar.richtools import repr_rich


@dataclass
class GrepMatch:
    """A single grep match with location and context."""
    location: str        # "primary", "EX-10.1", "Note 4 - Fair Value", etc.
    match: str           # The matched text itself
    context: str         # Surrounding text with match in context

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

    def __init__(self, pattern: str, matches: List[GrepMatch]):
        self.pattern = pattern
        self.matches = matches

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


def _overlapping(compiled: re.Pattern, text: str) -> Iterator[re.Match]:
    pos = 0
    while (m := compiled.search(text, pos)) is not None:
        yield m
        pos = m.start() + 1


def _grep_text(text: str, pattern: str, location: str,
               regex: bool = False, context_chars: int = 100) -> List[GrepMatch]:
    """Core grep function: search text for pattern, return matches with context.

    Always case-insensitive (SEC text has inconsistent casing).
    """
    if not text or not pattern:
        return []

    if regex:
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return []
        found = compiled.finditer(text)
    else:
        # Searched in the original text, not text.lower(): lowercasing can change
        # length ("İ" becomes two characters) and shift every later position.
        # Overlapping matches are kept, as the substring scan this replaced did.
        found = _overlapping(re.compile(re.escape(pattern), re.IGNORECASE), text)

    matches = []
    for m in found:
        start = max(0, m.start() - context_chars)
        end = min(len(text), m.end() + context_chars)
        context = text[start:end].strip()
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."
        matches.append(GrepMatch(
            location=location,
            match=m.group(),
            context=context,
        ))

    return matches
