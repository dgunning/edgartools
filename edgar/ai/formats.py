"""
AI-optimized text formatting utilities for EdgarTools.

Provides research-backed text formats optimized for LLM accuracy and token efficiency:
- Markdown-KV: Best accuracy (60.7%) for metadata
- TSV: Most efficient for tabular data

Based on research from improvingagents.com/blog/best-input-data-format-for-llms
"""

from typing import List, Dict

__all__ = ['to_markdown_kv', 'to_tsv']


def to_markdown_kv(data: dict, max_tokens: int = 2000) -> str:
    """
    Convert dict to Markdown Key-Value format optimized for LLMs.

    Research shows Markdown-KV format provides:
    - 60.7% accuracy (best among tested formats)
    - 25% fewer tokens than JSON
    - Better readability for both humans and AI

    Source: improvingagents.com/blog/best-input-data-format-for-llms

    Args:
        data: Dictionary with string keys and simple values
        max_tokens: Approximate token limit (4 chars/token heuristic)

    Returns:
        Markdown-formatted key-value text

    Example:
        >>> to_markdown_kv({"name": "Apple Inc.", "cik": "320193"})
        '**Name:** Apple Inc.\\n**Cik:** 320193'
    """
    lines = []
    for key, value in data.items():
        if value is None:
            continue
        # Convert key to title case for readability
        display_key = key.replace('_', ' ').title()
        lines.append(f"**{display_key}:** {value}")

    text = "\n".join(lines)

    # Token limiting (4 chars/token heuristic)
    max_chars = max_tokens * 4
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[Truncated for token limit]"

    return text


def to_tsv(rows: List[Dict], headers: List[str], max_tokens: int = 2000, limit: int = 10) -> str:
    """
    Convert list of dicts to TSV (tab-separated values) format.

    TSV is extremely token-efficient for tabular data and provides better
    accuracy than CSV. This pattern is proven in MultiPeriodStatement.to_llm_string().

    Args:
        rows: List of dicts with consistent keys
        headers: Column headers to include
        max_tokens: Approximate token limit (4 chars/token heuristic)
        limit: Maximum rows to include (default: 10)

    Returns:
        Tab-separated values with header row

    Example:
        >>> rows = [{"form": "10-K", "cik": "320193"}, {"form": "10-Q", "cik": "789019"}]
        >>> to_tsv(rows, ["form", "cik"], limit=2)
        'form\\tcik\\n10-K\\t320193\\n10-Q\\t789019'
    """
    lines = []

    # Header row
    lines.append("\t".join(headers))

    # Data rows
    for row in rows[:limit]:
        values = [str(row.get(h, "N/A")) for h in headers]
        lines.append("\t".join(values))

    text = "\n".join(lines)

    # Add summary if truncated
    if len(rows) > limit:
        text += f"\n\n[Showing {limit} of {len(rows)} rows]"

    # Token limiting
    max_chars = max_tokens * 4
    if len(text) > max_chars:
        # Estimate rows that fit
        avg_row_size = len(text) // len(lines) if lines else 100
        rows_that_fit = max(1, max_chars // avg_row_size)
        text = "\n".join(lines[:rows_that_fit]) + "\n\n[Truncated for token limit]"

    return text
