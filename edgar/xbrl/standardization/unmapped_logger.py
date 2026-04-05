"""
Unmapped tag logging for continuous mapping improvement.

Phase 5 of Context-Aware Standardization (Issue #494).

This module provides CSV-based logging of unmapped and ambiguous tags
during standardization, enabling systematic mapping coverage expansion.

Features:
- Log unmapped tags with context for analysis
- Log ambiguous tag resolutions for review
- CSV export in Excel-friendly format
- Suggested mapping inference with confidence scores
"""

import csv
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class UnmappedTagEntry:
    """Entry for an unmapped XBRL tag."""

    concept: str
    """The XBRL concept that couldn't be mapped."""

    label: str
    """The display label from the filing."""

    cik: Optional[str] = None
    """Company CIK (Central Index Key)."""

    company_name: Optional[str] = None
    """Company name for context."""

    statement_type: Optional[str] = None
    """Statement type (BalanceSheet, IncomeStatement, etc.)."""

    section: Optional[str] = None
    """Section within the statement (Current Assets, etc.)."""

    calculation_parent: Optional[str] = None
    """Calculation parent concept if available."""

    suggested_mapping: Optional[str] = None
    """Suggested standard concept mapping."""

    confidence: float = 0.0
    """Confidence score for suggested mapping (0.0 - 1.0)."""

    notes: Optional[str] = None
    """Additional notes or context."""

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    """When this entry was logged."""


@dataclass
class AmbiguousResolutionEntry:
    """Entry for an ambiguous tag resolution."""

    concept: str
    """The XBRL concept that was ambiguous."""

    label: str
    """The display label from the filing."""

    candidates: List[str]
    """List of possible standard concepts."""

    resolved_to: Optional[str]
    """The concept it was resolved to."""

    resolution_method: str
    """How it was resolved (section, is_total, fallback)."""

    cik: Optional[str] = None
    """Company CIK."""

    company_name: Optional[str] = None
    """Company name for context."""

    statement_type: Optional[str] = None
    """Statement type."""

    section: Optional[str] = None
    """Section within the statement."""

    confidence: float = 1.0
    """Confidence in the resolution (1.0 = certain, lower = uncertain)."""

    notes: Optional[str] = None
    """Additional notes."""

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    """When this entry was logged."""


class UnmappedTagLogger:
    """
    Logger for tracking unmapped and ambiguous XBRL tags.

    Provides CSV export for systematic mapping coverage expansion.

    Example:
        >>> logger = UnmappedTagLogger()
        >>> logger.log_unmapped(
        ...     concept="us-gaap:NewRevenueConcept",
        ...     label="Total Subscription Revenue",
        ...     cik="1234567",
        ...     statement_type="IncomeStatement"
        ... )
        >>> logger.log_ambiguous(
        ...     concept="us-gaap:AccountsPayableCurrentAndNoncurrent",
        ...     label="Trade Payables",
        ...     candidates=["TradePayables", "OtherNonCurrentLiabilities"],
        ...     resolved_to="TradePayables",
        ...     resolution_method="section"
        ... )
        >>> logger.save_to_csv("/path/to/unmapped_tags.csv")
    """

    def __init__(self, auto_suggest: bool = True):
        """
        Initialize the unmapped tag logger.

        Args:
            auto_suggest: If True, automatically suggest mappings for unmapped tags.
        """
        self._unmapped_entries: List[UnmappedTagEntry] = []
        self._ambiguous_entries: List[AmbiguousResolutionEntry] = []
        self._seen_unmapped: Set[str] = set()  # Deduplicate
        self._seen_ambiguous: Set[str] = set()
        self._auto_suggest = auto_suggest

    def log_unmapped(
        self,
        concept: str,
        label: str,
        cik: Optional[str] = None,
        company_name: Optional[str] = None,
        statement_type: Optional[str] = None,
        section: Optional[str] = None,
        calculation_parent: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """
        Log an unmapped XBRL tag.

        Args:
            concept: The XBRL concept that couldn't be mapped
            label: The display label from the filing
            cik: Company CIK
            company_name: Company name
            statement_type: Statement type
            section: Section within the statement
            calculation_parent: Calculation parent concept
            notes: Additional notes
        """
        # Deduplicate by concept + statement_type
        key = f"{concept}:{statement_type or ''}"
        if key in self._seen_unmapped:
            return
        self._seen_unmapped.add(key)

        # Auto-suggest mapping if enabled
        suggested = None
        confidence = 0.0
        if self._auto_suggest:
            suggested, confidence = self._suggest_mapping(concept, label, statement_type)

        entry = UnmappedTagEntry(
            concept=concept,
            label=label,
            cik=cik,
            company_name=company_name,
            statement_type=statement_type,
            section=section,
            calculation_parent=calculation_parent,
            suggested_mapping=suggested,
            confidence=confidence,
            notes=notes,
        )

        self._unmapped_entries.append(entry)
        logger.debug("Logged unmapped tag: %s (%s)", concept, label)

    def log_ambiguous(
        self,
        concept: str,
        label: str,
        candidates: List[str],
        resolved_to: Optional[str],
        resolution_method: str,
        cik: Optional[str] = None,
        company_name: Optional[str] = None,
        statement_type: Optional[str] = None,
        section: Optional[str] = None,
        confidence: float = 1.0,
        notes: Optional[str] = None,
    ) -> None:
        """
        Log an ambiguous tag resolution.

        Args:
            concept: The XBRL concept that was ambiguous
            label: The display label from the filing
            candidates: List of possible standard concepts
            resolved_to: The concept it was resolved to
            resolution_method: How it was resolved (section, is_total, fallback)
            cik: Company CIK
            company_name: Company name
            statement_type: Statement type
            section: Section within the statement
            confidence: Confidence in the resolution
            notes: Additional notes
        """
        # Deduplicate by concept + section + resolution
        key = f"{concept}:{section or ''}:{resolved_to or ''}"
        if key in self._seen_ambiguous:
            return
        self._seen_ambiguous.add(key)

        entry = AmbiguousResolutionEntry(
            concept=concept,
            label=label,
            candidates=candidates,
            resolved_to=resolved_to,
            resolution_method=resolution_method,
            cik=cik,
            company_name=company_name,
            statement_type=statement_type,
            section=section,
            confidence=confidence,
            notes=notes,
        )

        self._ambiguous_entries.append(entry)
        logger.debug(
            "Logged ambiguous resolution: %s -> %s (%s)",
            concept, resolved_to, resolution_method
        )

    def _suggest_mapping(
        self,
        concept: str,
        label: str,
        statement_type: Optional[str]
    ) -> tuple[Optional[str], float]:
        """
        Suggest a standard concept mapping based on label analysis.

        Args:
            concept: The unmapped concept
            label: The display label
            statement_type: The statement type

        Returns:
            Tuple of (suggested_mapping, confidence)
        """
        label_lower = label.lower()

        # Common patterns for suggestion
        suggestions = {
            # Revenue patterns
            ("revenue", "IncomeStatement"): ("Revenue", 0.85),
            ("sales", "IncomeStatement"): ("Revenue", 0.75),
            ("net sales", "IncomeStatement"): ("Revenue", 0.80),
            # Expense patterns
            ("cost of", "IncomeStatement"): ("CostOfGoodsAndServicesSold", 0.70),
            ("research", "IncomeStatement"): ("ResearchAndDevelopementExpenses", 0.75),
            ("selling", "IncomeStatement"): ("SellingGeneralAndAdminExpenses", 0.70),
            # Asset patterns
            ("cash", "BalanceSheet"): ("CashAndMarketableSecurities", 0.75),
            ("receivable", "BalanceSheet"): ("TradeReceivables", 0.70),
            ("inventory", "BalanceSheet"): ("Inventories", 0.85),
            ("property", "BalanceSheet"): ("PlantPropertyEquipmentNet", 0.70),
            ("goodwill", "BalanceSheet"): ("Goodwill", 0.90),
            ("intangible", "BalanceSheet"): ("IntangibleAssets", 0.80),
            # Liability patterns
            ("payable", "BalanceSheet"): ("TradePayables", 0.70),
            ("debt", "BalanceSheet"): ("LongTermDebt", 0.65),
            ("deferred", "BalanceSheet"): ("OtherOperatingCurrentLiabilities", 0.50),
            # Equity patterns
            ("equity", "BalanceSheet"): ("CommonEquity", 0.60),
            ("retained", "BalanceSheet"): ("CommonEquity", 0.65),
        }

        for (pattern, stmt), (suggestion, conf) in suggestions.items():
            if pattern in label_lower:
                if stmt is None or statement_type == stmt:
                    return suggestion, conf

        return None, 0.0

    def save_unmapped_csv(self, output_path: str) -> int:
        """
        Save unmapped tags to a CSV file.

        Args:
            output_path: Path to the output CSV file

        Returns:
            Number of entries written
        """
        if not self._unmapped_entries:
            logger.info("No unmapped entries to save")
            return 0

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        fieldnames = [
            "concept", "label", "suggested_mapping", "confidence",
            "cik", "company_name", "statement_type", "section",
            "calculation_parent", "notes", "timestamp"
        ]

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for entry in self._unmapped_entries:
                writer.writerow({
                    "concept": entry.concept,
                    "label": entry.label,
                    "suggested_mapping": entry.suggested_mapping or "",
                    "confidence": f"{entry.confidence:.2f}" if entry.confidence else "",
                    "cik": entry.cik or "",
                    "company_name": entry.company_name or "",
                    "statement_type": entry.statement_type or "",
                    "section": entry.section or "",
                    "calculation_parent": entry.calculation_parent or "",
                    "notes": entry.notes or "",
                    "timestamp": entry.timestamp,
                })

        logger.info("Saved %d unmapped entries to %s", len(self._unmapped_entries), output_path)
        return len(self._unmapped_entries)

    def save_ambiguous_csv(self, output_path: str) -> int:
        """
        Save ambiguous resolutions to a CSV file.

        Args:
            output_path: Path to the output CSV file

        Returns:
            Number of entries written
        """
        if not self._ambiguous_entries:
            logger.info("No ambiguous entries to save")
            return 0

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        fieldnames = [
            "concept", "label", "candidates", "resolved_to", "resolution_method",
            "confidence", "cik", "company_name", "statement_type", "section",
            "notes", "timestamp"
        ]

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for entry in self._ambiguous_entries:
                writer.writerow({
                    "concept": entry.concept,
                    "label": entry.label,
                    "candidates": "|".join(entry.candidates),  # Pipe-separated for Excel
                    "resolved_to": entry.resolved_to or "",
                    "resolution_method": entry.resolution_method,
                    "confidence": f"{entry.confidence:.2f}",
                    "cik": entry.cik or "",
                    "company_name": entry.company_name or "",
                    "statement_type": entry.statement_type or "",
                    "section": entry.section or "",
                    "notes": entry.notes or "",
                    "timestamp": entry.timestamp,
                })

        logger.info("Saved %d ambiguous entries to %s", len(self._ambiguous_entries), output_path)
        return len(self._ambiguous_entries)

    def save_to_csv(self, output_dir: str) -> tuple[int, int]:
        """
        Save both unmapped and ambiguous logs to CSV files.

        Args:
            output_dir: Directory to save CSV files

        Returns:
            Tuple of (unmapped_count, ambiguous_count)
        """
        os.makedirs(output_dir, exist_ok=True)

        unmapped_path = os.path.join(output_dir, "unmapped_tags.csv")
        ambiguous_path = os.path.join(output_dir, "ambiguous_resolutions.csv")

        unmapped_count = self.save_unmapped_csv(unmapped_path)
        ambiguous_count = self.save_ambiguous_csv(ambiguous_path)

        return unmapped_count, ambiguous_count

    def clear(self) -> None:
        """Clear all logged entries."""
        self._unmapped_entries.clear()
        self._ambiguous_entries.clear()
        self._seen_unmapped.clear()
        self._seen_ambiguous.clear()

    @property
    def unmapped_count(self) -> int:
        """Number of unmapped entries logged."""
        return len(self._unmapped_entries)

    @property
    def ambiguous_count(self) -> int:
        """Number of ambiguous resolution entries logged."""
        return len(self._ambiguous_entries)

    @property
    def stats(self) -> Dict[str, int]:
        """Get logging statistics."""
        return {
            "unmapped_count": self.unmapped_count,
            "ambiguous_count": self.ambiguous_count,
            "total_count": self.unmapped_count + self.ambiguous_count,
        }

    def get_unmapped_by_statement(self) -> Dict[str, List[UnmappedTagEntry]]:
        """
        Group unmapped entries by statement type.

        Returns:
            Dict mapping statement type to list of entries
        """
        result: Dict[str, List[UnmappedTagEntry]] = {}
        for entry in self._unmapped_entries:
            stmt = entry.statement_type or "Unknown"
            if stmt not in result:
                result[stmt] = []
            result[stmt].append(entry)
        return result

    def get_high_confidence_suggestions(self, min_confidence: float = 0.7) -> List[UnmappedTagEntry]:
        """
        Get unmapped entries with high-confidence suggestions.

        Args:
            min_confidence: Minimum confidence threshold

        Returns:
            List of entries with suggested mappings above threshold
        """
        return [
            entry for entry in self._unmapped_entries
            if entry.suggested_mapping and entry.confidence >= min_confidence
        ]

    def __rich__(self):
        """Rich console representation."""
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        # Create summary table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="dim")
        table.add_column("Count", justify="right")

        table.add_row("Unmapped Tags", str(self.unmapped_count))
        table.add_row("Ambiguous Resolutions", str(self.ambiguous_count))
        table.add_row("Total Logged", str(self.unmapped_count + self.ambiguous_count))

        # High confidence suggestions
        high_conf = self.get_high_confidence_suggestions()
        if high_conf:
            table.add_row("High-Confidence Suggestions", str(len(high_conf)))

        return Panel(
            table,
            title="[bold]Unmapped Tag Logger[/bold]",
            border_style="blue"
        )


# Module-level singleton for convenience
_default_logger: Optional[UnmappedTagLogger] = None


def get_unmapped_logger() -> UnmappedTagLogger:
    """
    Get the default unmapped tag logger singleton.

    Returns:
        The default UnmappedTagLogger instance
    """
    global _default_logger
    if _default_logger is None:
        _default_logger = UnmappedTagLogger()
    return _default_logger


def log_unmapped(
    concept: str,
    label: str,
    **kwargs
) -> None:
    """
    Convenience function to log an unmapped tag.

    Args:
        concept: The XBRL concept that couldn't be mapped
        label: The display label
        **kwargs: Additional context (cik, company_name, etc.)
    """
    get_unmapped_logger().log_unmapped(concept, label, **kwargs)


def log_ambiguous(
    concept: str,
    label: str,
    candidates: List[str],
    resolved_to: Optional[str],
    resolution_method: str,
    **kwargs
) -> None:
    """
    Convenience function to log an ambiguous resolution.

    Args:
        concept: The XBRL concept
        label: The display label
        candidates: List of possible mappings
        resolved_to: The resolved mapping
        resolution_method: How it was resolved
        **kwargs: Additional context
    """
    get_unmapped_logger().log_ambiguous(
        concept, label, candidates, resolved_to, resolution_method, **kwargs
    )
