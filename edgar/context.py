"""
Context composition utilities for edgartools.

Compose multiple edgartools objects into a single LLM-ready context string
with automatic token budget management.
"""

from typing import List, Optional, Protocol, Union, runtime_checkable

__all__ = ['HasContext', 'compose_context']


@runtime_checkable
class HasContext(Protocol):
    """Protocol for objects that can produce AI-optimized context strings.

    Any edgartools object with a to_context() method satisfies this protocol
    automatically — no inheritance required. This includes Company, Filing,
    Filings, TenK, Form4, ThirteenF, ProxyStatement, Statement, and all
    other data objects.
    """
    def to_context(self, detail: str = 'standard') -> str: ...


def compose_context(
    objects: Union[HasContext, List[HasContext]],
    max_tokens: int = 2000,
    detail: str = 'standard',
    separator: str = '\n\n---\n\n',
) -> str:
    """Compose one or more edgartools objects into a single LLM-ready context string.

    Takes any objects that satisfy the HasContext protocol (i.e., have a
    to_context() method) and assembles them into one string that fits
    within a token budget. Accepts a single object or a list.

    Token budget strategy:
    - First object gets priority (60% of budget at standard detail)
    - Remaining objects share the rest equally
    - If an object exceeds its budget, it's downgraded to minimal
    - Objects without to_context() fall back to str()

    Args:
        objects: List of edgartools objects with to_context() methods
        max_tokens: Approximate token budget (4 chars/token heuristic)
        detail: Starting detail level ('minimal', 'standard', 'full')
        separator: String between each object's context

    Returns:
        Combined context string

    Examples:
        >>> from edgar import Company, compose_context
        >>> company = Company("AAPL")
        >>> tenk = company.get_filings(form="10-K").latest().obj()
        >>> compose_context([company, tenk])
        'COMPANY: Apple Inc.\\n...'

        >>> # Single object
        >>> compose_context(tenk)
        'TENK: Apple Inc. Annual Report\\n...'

        >>> # With token budget — auto-downgraded to minimal
        >>> compose_context([company, tenk, filing], max_tokens=500)
        'COMPANY: Apple Inc.\\n...'
    """
    # Accept single object or list
    if not objects:
        return ""
    if not isinstance(objects, list):
        objects = [objects]

    max_chars = max_tokens * 4
    sep_chars = len(separator)
    total_sep_chars = sep_chars * (len(objects) - 1) if len(objects) > 1 else 0
    available_chars = max_chars - total_sep_chars

    # Budget allocation: first object gets 60%, rest split equally
    if len(objects) == 1:
        budgets = [available_chars]
    else:
        first_budget = int(available_chars * 0.6)
        remaining = available_chars - first_budget
        per_remaining = remaining // (len(objects) - 1) if len(objects) > 1 else 0
        budgets = [first_budget] + [per_remaining] * (len(objects) - 1)

    parts = []
    for obj, budget in zip(objects, budgets):
        ctx = _get_context(obj, detail, budget)
        if ctx:
            parts.append(ctx)

    return separator.join(parts)


def _call_to_context(obj, detail: str) -> str:
    """Call to_context() with graceful fallback for non-standard signatures.

    Some objects (Financials, XBRL) have non-standard signatures that don't
    accept a detail parameter. Fall back to no-arg call if detail is rejected.
    """
    try:
        return obj.to_context(detail=detail)
    except TypeError:
        return obj.to_context()


def _get_context(obj, detail: str, budget_chars: int) -> Optional[str]:
    """Get context for a single object, respecting char budget."""
    if not hasattr(obj, 'to_context'):
        # Fallback: use str() for objects without to_context
        label = type(obj).__name__
        s = str(obj)
        if len(s) > budget_chars:
            s = s[:budget_chars - 20] + f"\n[Truncated {label}]"
        return s

    # Try requested detail level first
    ctx = _call_to_context(obj, detail)
    if len(ctx) <= budget_chars:
        return ctx

    # Over budget — try downgrading
    if detail == 'full':
        ctx = _call_to_context(obj, 'standard')
        if len(ctx) <= budget_chars:
            return ctx

    if detail in ('full', 'standard'):
        ctx = _call_to_context(obj, 'minimal')
        if len(ctx) <= budget_chars:
            return ctx
        # Even minimal is over budget — truncate
        if len(ctx) > budget_chars:
            ctx = ctx[:budget_chars - 30] + "\n[Truncated for token limit]"
        return ctx

    return ctx
