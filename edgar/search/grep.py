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


def _grep_text(text: str, pattern: str, location: str,
               regex: bool = False, context_chars: int = 100) -> List[GrepMatch]:
    """Core grep function: search text for pattern, return matches with context.

    Always case-insensitive (SEC text has inconsistent casing).
    """
    if not text or not pattern:
        return []

    matches = []

    if regex:
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return []
        for m in compiled.finditer(text):
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
    else:
        # Case-insensitive substring search
        text_lower = text.lower()
        pattern_lower = pattern.lower()
        start_pos = 0
        while True:
            pos = text_lower.find(pattern_lower, start_pos)
            if pos == -1:
                break
            ctx_start = max(0, pos - context_chars)
            ctx_end = min(len(text), pos + len(pattern) + context_chars)
            context = text[ctx_start:ctx_end].strip()
            if ctx_start > 0:
                context = "..." + context
            if ctx_end < len(text):
                context = context + "..."
            matches.append(GrepMatch(
                location=location,
                match=text[pos:pos + len(pattern)],
                context=context,
            ))
            start_pos = pos + 1

    return matches
