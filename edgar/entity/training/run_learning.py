#!/usr/bin/env python3
"""
Financial Statement Concept Learning Script

This script analyzes SEC filings to learn:
- Which concepts belong to which financial statements
- Parent-child relationships between concepts
- Occurrence rates across companies
- Display labels and ordering

Usage:
    python -m edgar.entity.training.run_learning [--companies N] [--exchange EXCHANGE] [--output DIR]

    # Or as a script
    python edgar/entity/training/run_learning.py --companies 100
"""

import argparse
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set

from . import STATEMENT_TYPES, get_output_dir

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# XBRL label role for totals (from edgar.xbrl.models)
TOTAL_LABEL = "http://www.xbrl.org/2003/role/totalLabel"


def get_calculation_totals(xbrl) -> Set[str]:
    """
    Get set of concepts that are totals (have children in calculation linkbase).

    In XBRL, the calculation linkbase defines roll-up relationships:
    Total = Child1 * weight1 + Child2 * weight2 + ...

    If a concept has children in the calculation tree, it's definitively a total.

    Args:
        xbrl: XBRL instance with parsed calculation trees

    Returns:
        Set of concept names that are calculation parents (totals)
    """
    totals = set()

    if not hasattr(xbrl, 'calculation_trees') or not xbrl.calculation_trees:
        return totals

    for calc_tree in xbrl.calculation_trees.values():
        if not hasattr(calc_tree, 'all_nodes'):
            continue
        for node in calc_tree.all_nodes.values():
            # If this node has children, it's a total
            if hasattr(node, 'children') and node.children:
                # Clean the element_id to match our concept format
                element_id = node.element_id if hasattr(node, 'element_id') else str(node)
                # Remove namespace prefix if present
                if ':' in element_id:
                    element_id = element_id.split(':')[1]
                element_id = element_id.replace('us-gaap_', '').replace('dei_', '')
                totals.add(element_id)

    return totals


def is_total_concept(item: dict, calculation_totals: Set[str], concept: str) -> bool:
    """
    Determine if a concept is a total using authoritative XBRL signals.

    Uses only authoritative sources (no label text heuristics which cause false positives):
    1. Explicit totalLabel in presentation linkbase
    2. Concept is a parent in calculation linkbase (has children)

    Note: Label text heuristics like checking for "Total " prefix were removed because
    they caused false positives with dimensional segment labels (e.g., "Total Walmart
    Shareholders' Equity" on individual line items, "Total Non-U.S. Revenues" on
    geographic segments).

    Args:
        item: Line item dict from get_statement()
        calculation_totals: Set of concepts that are calculation parents
        concept: Cleaned concept name

    Returns:
        True if concept is definitively a total per XBRL structure
    """
    # 1. Explicit totalLabel in presentation linkbase (most reliable)
    preferred_label = item.get('preferred_label', '')
    if preferred_label == TOTAL_LABEL:
        return True

    # 2. Concept is a parent in calculation linkbase (authoritative)
    if concept in calculation_totals:
        return True

    return False


@dataclass
class CompanyStats:
    """Statistics for a single company's filing."""
    cik: str  # Primary key - SEC Central Index Key
    ticker: str = ""
    name: str = ""
    filing_date: str = ""
    total_concepts: int = 0
    standard_concepts: int = 0
    custom_concepts: int = 0
    concepts_by_statement: Dict[str, int] = field(default_factory=dict)
    custom_prefix: str = ""  # e.g., 'aapl', 'msft'
    unique_concepts: List[str] = field(default_factory=list)
    processing_time_ms: float = 0


@dataclass
class ConceptObservation:
    """Single observation of a concept in a filing."""
    concept: str
    label: str
    statement_type: str
    parent: Optional[str] = None
    depth: int = 0
    is_abstract: bool = False
    is_total: bool = False
    order: int = 0


@dataclass
class ConceptStats:
    """Aggregated statistics for a concept."""
    concept: str
    statement_type: str
    occurrence_count: int = 0  # Total observations (may have duplicates per company)
    company_ciks: set = field(default_factory=set)  # Unique companies that have this concept
    labels: Dict[str, int] = field(default_factory=dict)
    parents: Dict[str, int] = field(default_factory=dict)
    depths: List[int] = field(default_factory=list)
    is_abstract_count: int = 0
    is_total_count: int = 0
    orders: List[int] = field(default_factory=list)

    def add_observation(self, obs: ConceptObservation, cik: str):
        """Add an observation to the statistics."""
        self.occurrence_count += 1
        self.company_ciks.add(cik)  # Track unique companies
        self.labels[obs.label] = self.labels.get(obs.label, 0) + 1
        if obs.parent:
            self.parents[obs.parent] = self.parents.get(obs.parent, 0) + 1
        self.depths.append(obs.depth)
        self.orders.append(obs.order)
        if obs.is_abstract:
            self.is_abstract_count += 1
        if obs.is_total:
            self.is_total_count += 1

    @property
    def company_count(self) -> int:
        """Number of unique companies that have this concept."""
        return len(self.company_ciks)

    def to_mapping(self, total_companies: int) -> Dict[str, Any]:
        """Convert to learned mapping format."""
        # Use unique company count, not observation count
        occurrence_rate = self.company_count / total_companies if total_companies > 0 else 0

        # Get most common label
        label = max(self.labels.items(), key=lambda x: x[1])[0] if self.labels else self.concept

        # Get most common parent
        parent = None
        if self.parents:
            parent = max(self.parents.items(), key=lambda x: x[1])[0]

        # Calculate averages
        avg_depth = sum(self.depths) / len(self.depths) if self.depths else 0
        avg_order = sum(self.orders) / len(self.orders) if self.orders else 0

        # Determine if abstract/total based on majority
        is_abstract = self.is_abstract_count > self.occurrence_count / 2
        is_total = self.is_total_count > self.occurrence_count / 2

        return {
            'statement_type': self.statement_type,
            'confidence': occurrence_rate,
            'label': label,
            'parent': parent,
            'is_abstract': is_abstract,
            'is_total': is_total,
            'section': None,  # Could be derived from parent
            'avg_depth': avg_depth,
            'occurrence_rate': occurrence_rate
        }


@dataclass
class MultiStatementInfo:
    """Tracks a concept's appearance across multiple statements."""
    concept: str
    statements: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def add_statement_appearance(self, statement_type: str, label: str,
                                  parent: Optional[str], depth: float,
                                  is_abstract: bool, is_total: bool,
                                  company_count: int):
        """Record an appearance in a statement type."""
        if statement_type not in self.statements:
            self.statements[statement_type] = {
                'company_count': 0,
                'labels': {},
                'parents': {},
                'avg_depth': 0,
                'depths': [],
                'is_abstract_count': 0,
                'is_total_count': 0
            }

        info = self.statements[statement_type]
        info['company_count'] = company_count
        info['labels'][label] = info['labels'].get(label, 0) + 1
        if parent:
            info['parents'][parent] = info['parents'].get(parent, 0) + 1
        info['depths'].append(depth)
        if is_abstract:
            info['is_abstract_count'] += 1
        if is_total:
            info['is_total_count'] += 1

    def to_dict(self, total_companies: int) -> Dict[str, Any]:
        """Convert to dictionary format for JSON output."""
        statement_details = {}
        for stmt_type, info in self.statements.items():
            occurrence_rate = info['company_count'] / total_companies if total_companies > 0 else 0
            most_common_label = max(info['labels'].items(), key=lambda x: x[1])[0] if info['labels'] else self.concept
            most_common_parent = max(info['parents'].items(), key=lambda x: x[1])[0] if info['parents'] else None
            avg_depth = sum(info['depths']) / len(info['depths']) if info['depths'] else 0

            statement_details[stmt_type] = {
                'occurrence_rate': occurrence_rate,
                'company_count': info['company_count'],
                'label': most_common_label,
                'parent': most_common_parent,
                'avg_depth': avg_depth,
                'is_abstract': info['is_abstract_count'] > len(info['depths']) / 2,
                'is_total': info['is_total_count'] > len(info['depths']) / 2
            }

        # Determine primary statement (highest occurrence)
        primary_stmt = max(statement_details.items(), key=lambda x: x[1]['occurrence_rate'])[0] if statement_details else None

        return {
            'concept': self.concept,
            'statement_count': len(self.statements),
            'primary_statement': primary_stmt,
            'statements': list(self.statements.keys()),
            'statement_details': statement_details
        }


class ConceptLearner:
    """Learns financial statement concept mappings from SEC filings."""

    def __init__(self, min_occurrence_rate: float = 0.3):
        self.min_occurrence_rate = min_occurrence_rate
        self.concept_stats: Dict[str, ConceptStats] = {}
        self.multi_statement_tracker: Dict[str, MultiStatementInfo] = {}  # Track concepts across statements
        self.companies_processed = 0
        self.successful_companies = 0
        self.errors: List[str] = []
        self.total_observations = 0
        # Per-company tracking for statistics
        self.company_stats: List[CompanyStats] = []
        self.all_concepts_seen: set = set()  # All unique concepts across all companies
        self.custom_concepts_seen: set = set()  # Custom concepts (company-specific)
        self.standard_concepts_seen: set = set()  # Standard US-GAAP concepts
        # Lookup tables (CIK is primary key)
        self.cik_to_ticker: Dict[str, str] = {}  # CIK -> ticker mapping
        self.ticker_to_cik: Dict[str, str] = {}  # ticker -> CIK mapping
        # Failure tracking by reason
        self.failure_reasons: Dict[str, List[str]] = {
            'no_10k_filings': [],      # Company has no 10-K filings (likely foreign filer using 20-F)
            'no_latest_filing': [],    # Could not get latest filing
            'no_xbrl_data': [],        # Filing has no XBRL data
            'processing_error': []     # Exception during processing
        }

    def process_company(self, ticker: str) -> bool:
        """Process a single company's latest 10-K filing."""
        import time
        import re
        start_time = time.time()

        # Initialize company stats with placeholder CIK (will be set after Company lookup)
        company_stat = CompanyStats(cik="", ticker=ticker)

        try:
            from edgar import Company

            logger.info(f"Processing {ticker}...")
            company = Company(ticker)

            # Get CIK (primary identifier)
            cik = str(company.cik).zfill(10) if hasattr(company, 'cik') else ""
            company_stat.cik = cik
            company_stat.ticker = ticker
            company_stat.name = company.name if hasattr(company, 'name') else ""

            # Populate lookup tables
            if cik:
                self.cik_to_ticker[cik] = ticker
                self.ticker_to_cik[ticker] = cik

            # Get latest 10-K filing
            filings = company.get_filings(form='10-K')
            if not filings:
                logger.warning(f"No 10-K filings found for {ticker}")
                self.failure_reasons['no_10k_filings'].append(ticker)
                return False

            latest = filings.latest()
            if not latest:
                logger.warning(f"Could not get latest 10-K for {ticker}")
                self.failure_reasons['no_latest_filing'].append(ticker)
                return False

            company_stat.filing_date = str(latest.filing_date) if hasattr(latest, 'filing_date') else ""

            # Parse XBRL
            xbrl = latest.xbrl()
            if not xbrl:
                logger.warning(f"No XBRL data for {ticker}")
                self.failure_reasons['no_xbrl_data'].append(ticker)
                return False

            # Build set of calculation totals for robust is_total detection
            calculation_totals = get_calculation_totals(xbrl)

            # Track concepts for this company
            company_concepts = set()
            company_custom = set()
            company_standard = set()
            concepts_by_stmt = defaultdict(int)
            custom_pattern = re.compile(r'^[a-z]+_')

            # Process each statement type
            observations = 0
            for stmt_type in STATEMENT_TYPES:
                obs_count, concepts = self._process_statement_with_tracking(
                    xbrl, stmt_type, company_concepts, company_custom, company_standard,
                    custom_pattern, cik, calculation_totals
                )
                observations += obs_count
                concepts_by_stmt[stmt_type] = len(concepts)

            # Update company stats
            company_stat.total_concepts = len(company_concepts)
            company_stat.standard_concepts = len(company_standard)
            company_stat.custom_concepts = len(company_custom)
            company_stat.concepts_by_statement = dict(concepts_by_stmt)
            company_stat.unique_concepts = list(company_concepts)

            # Identify custom prefix (most common lowercase prefix)
            if company_custom:
                prefixes = [c.split('_')[0] for c in company_custom if '_' in c]
                if prefixes:
                    company_stat.custom_prefix = max(set(prefixes), key=prefixes.count)

            # Update global tracking
            self.all_concepts_seen.update(company_concepts)
            self.custom_concepts_seen.update(company_custom)
            self.standard_concepts_seen.update(company_standard)

            self.total_observations += observations
            self.successful_companies += 1
            logger.info(f"  Extracted {observations} observations, {len(company_concepts)} unique concepts from {ticker}")
            return True

        except Exception as e:
            error_msg = f"Error processing {ticker}: {str(e)}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            self.failure_reasons['processing_error'].append(ticker)
            return False
        finally:
            self.companies_processed += 1
            company_stat.processing_time_ms = (time.time() - start_time) * 1000
            self.company_stats.append(company_stat)

    def _process_statement_with_tracking(self, xbrl, statement_type: str,
                                          company_concepts: set, company_custom: set,
                                          company_standard: set, custom_pattern, cik: str,
                                          calculation_totals: Set[str]) -> tuple:
        """Extract concepts with tracking for statistics.

        Args:
            xbrl: XBRL instance
            statement_type: Type of statement to process
            company_concepts: Set to track all concepts for this company
            company_custom: Set to track custom concepts
            company_standard: Set to track standard concepts
            custom_pattern: Regex pattern for identifying custom concepts
            cik: Company CIK for tracking
            calculation_totals: Set of concepts that are totals per calculation linkbase
        """
        concepts_in_stmt = set()
        try:
            statement_data = xbrl.get_statement(statement_type)
            if not statement_data:
                return 0, concepts_in_stmt

            observations = 0
            for idx, item in enumerate(statement_data):
                concept = item.get('concept', '')
                if not concept:
                    continue

                concept = self._clean_concept(concept)
                if not concept:
                    continue

                # Track for statistics
                company_concepts.add(concept)
                concepts_in_stmt.add(concept)

                if custom_pattern.match(concept):
                    company_custom.add(concept)
                else:
                    company_standard.add(concept)

                # Get parent and clean it
                parent_raw = item.get('parent')
                parent = self._clean_concept(parent_raw) if parent_raw else None

                # Determine if this is a total using robust XBRL-based detection
                # Uses: 1) totalLabel role, 2) calculation linkbase, 3) label heuristic
                is_total = is_total_concept(item, calculation_totals, concept)
                label = item.get('label', concept)

                # Create observation
                obs = ConceptObservation(
                    concept=concept,
                    label=label,
                    statement_type=statement_type,
                    parent=parent,
                    depth=item.get('level', 0),
                    is_abstract=item.get('is_abstract', False),
                    is_total=is_total,
                    order=idx
                )

                # Add to per-statement statistics
                key = f"{concept}:{statement_type}"
                if key not in self.concept_stats:
                    self.concept_stats[key] = ConceptStats(
                        concept=concept,
                        statement_type=statement_type
                    )
                self.concept_stats[key].add_observation(obs, cik)

                # Track multi-statement appearances
                if concept not in self.multi_statement_tracker:
                    self.multi_statement_tracker[concept] = MultiStatementInfo(concept=concept)

                observations += 1

            return observations, concepts_in_stmt

        except Exception as e:
            logger.debug(f"Could not process {statement_type}: {e}")
            return 0, concepts_in_stmt

    def _finalize_multi_statement_tracking(self):
        """Finalize multi-statement tracking after all companies processed."""
        # Update each multi-statement tracker with final counts from concept_stats
        for key, stats in self.concept_stats.items():
            concept = stats.concept
            stmt_type = stats.statement_type

            if concept in self.multi_statement_tracker:
                tracker = self.multi_statement_tracker[concept]

                # Get most common values from stats
                label = max(stats.labels.items(), key=lambda x: x[1])[0] if stats.labels else concept
                parent = max(stats.parents.items(), key=lambda x: x[1])[0] if stats.parents else None
                avg_depth = sum(stats.depths) / len(stats.depths) if stats.depths else 0
                is_abstract = stats.is_abstract_count > stats.occurrence_count / 2
                is_total = stats.is_total_count > stats.occurrence_count / 2

                # Get unique company count (properly deduplicated)
                company_count = stats.company_count

                tracker.add_statement_appearance(
                    statement_type=stmt_type,
                    label=label,
                    parent=parent,
                    depth=avg_depth,
                    is_abstract=is_abstract,
                    is_total=is_total,
                    company_count=company_count
                )

    def _generate_concept_linkages(self) -> Dict[str, Any]:
        """Generate concept linkages showing multi-statement relationships."""
        # Finalize tracking data
        self._finalize_multi_statement_tracking()

        # Categorize concepts
        single_statement = []
        multi_statement = []
        linkage_concepts = []  # Concepts that bridge statements (like NetIncomeLoss)

        for concept, tracker in self.multi_statement_tracker.items():
            info = tracker.to_dict(self.successful_companies)

            if info['statement_count'] == 1:
                single_statement.append(info)
            else:
                multi_statement.append(info)

                # Identify "linking" concepts (appear in many statements with high occurrence)
                if info['statement_count'] >= 3:
                    linkage_concepts.append(info)

        # Sort by statement count (most cross-cutting first)
        multi_statement.sort(key=lambda x: (-x['statement_count'], x['concept']))
        linkage_concepts.sort(key=lambda x: (-x['statement_count'], x['concept']))

        # Categorize multi-statement concepts by their role
        categorized = self._categorize_linkages(multi_statement)

        return {
            'metadata': {
                'generated': datetime.now().isoformat(),
                'companies_analyzed': self.successful_companies,
                'total_unique_concepts': len(self.multi_statement_tracker),
                'single_statement_concepts': len(single_statement),
                'multi_statement_concepts': len(multi_statement),
                'linkage_concepts': len(linkage_concepts)
            },
            'summary': {
                'by_statement_count': self._count_by_statement_count(multi_statement),
                'key_linkages': [c['concept'] for c in linkage_concepts[:10]]
            },
            'categories': categorized,
            'multi_statement_concepts': multi_statement,
            'linkage_concepts': linkage_concepts
        }

    def _categorize_linkages(self, multi_statement: List[Dict]) -> Dict[str, List[str]]:
        """Categorize multi-statement concepts by their bridging role."""
        categories = {
            'income_to_cashflow': [],      # Net income, depreciation flow to CF
            'balance_to_equity': [],        # Equity items bridging BS and SOE
            'balance_to_cashflow': [],      # Cash reconciliation items
            'income_to_comprehensive': [],  # Net income to comprehensive income
            'comprehensive_income': [],     # OCI items
            'xbrl_structural': [],          # XBRL scaffolding (Axis, Domain, Table, etc.)
            'other': []
        }

        for info in multi_statement:
            concept = info['concept']
            stmts = set(info['statements'])

            # 1. Check for XBRL structural concepts FIRST (they can appear anywhere)
            if any(marker in concept for marker in ['Table', 'LineItems', 'Axis', 'Domain', 'Member', 'Abstract']):
                categories['xbrl_structural'].append(concept)
                continue

            # 2. Categorize by meaningful statement relationships
            is_income_cashflow = 'IncomeStatement' in stmts and 'CashFlowStatement' in stmts
            is_balance_equity = 'BalanceSheet' in stmts and 'StatementOfEquity' in stmts
            is_balance_cashflow = 'BalanceSheet' in stmts and 'CashFlowStatement' in stmts
            is_income_comprehensive = 'IncomeStatement' in stmts and 'ComprehensiveIncome' in stmts

            # Income to CashFlow linkages (net income, depreciation, gains/losses)
            if is_income_cashflow:
                if any(term in concept for term in ['NetIncome', 'ProfitLoss', 'Depreciation',
                       'Amortization', 'GainLoss', 'Impairment', 'DeferredTax']):
                    categories['income_to_cashflow'].append(concept)
                else:
                    # Other income-to-cashflow concepts go to 'other'
                    categories['other'].append(concept)

            # Balance Sheet to Equity (stockholders equity, retained earnings)
            elif is_balance_equity:
                categories['balance_to_equity'].append(concept)

            # Balance Sheet to CashFlow (cash reconciliation)
            elif is_balance_cashflow:
                categories['balance_to_cashflow'].append(concept)

            # Income to Comprehensive Income
            elif is_income_comprehensive:
                categories['income_to_comprehensive'].append(concept)

            # Pure Comprehensive Income items
            elif 'ComprehensiveIncome' in stmts:
                categories['comprehensive_income'].append(concept)

            # Everything else
            else:
                categories['other'].append(concept)

        # Remove empty categories
        return {k: v for k, v in categories.items() if v}

    def _count_by_statement_count(self, multi_statement: List[Dict]) -> Dict[int, int]:
        """Count concepts by number of statements they appear in."""
        counts = defaultdict(int)
        for info in multi_statement:
            counts[info['statement_count']] += 1
        return dict(sorted(counts.items()))

    def _clean_concept(self, concept: Optional[str]) -> Optional[str]:
        """Clean concept name."""
        if not concept:
            return None
        if ':' in concept:
            concept = concept.split(':')[1]
        return concept.replace('us-gaap_', '').replace('dei_', '')

    def _validate_parent_references(self, learned_mappings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate parent references in learned mappings.

        Checks that each concept's parent exists in the mappings. If a parent
        is missing (below occurrence threshold), marks it as missing but preserves
        the reference for documentation.

        Args:
            learned_mappings: The learned mappings dictionary to validate

        Returns:
            Validation statistics
        """
        valid_parents = 0
        missing_parents = 0
        null_parents = 0
        missing_parent_concepts = []

        for concept, mapping in learned_mappings.items():
            parent = mapping.get('parent')

            if parent is None:
                null_parents += 1
            elif parent in learned_mappings:
                valid_parents += 1
            else:
                missing_parents += 1
                # Mark the parent as missing but preserve the reference
                mapping['parent_in_mappings'] = False
                missing_parent_concepts.append({
                    'concept': concept,
                    'missing_parent': parent,
                    'statement_type': mapping.get('statement_type')
                })

        # Log some examples of missing parents
        if missing_parent_concepts:
            logger.debug(f"Missing parent examples: {missing_parent_concepts[:5]}")

        return {
            'valid_parents': valid_parents,
            'missing_parents': missing_parents,
            'null_parents': null_parents,
            'missing_parent_details': missing_parent_concepts[:20]  # First 20 for debugging
        }

    def _generate_statistics(self, learned_mappings: Dict) -> Dict[str, Any]:
        """Generate comprehensive statistics about the learning run."""
        import statistics

        # Get successful company stats only
        successful_stats = [s for s in self.company_stats if s.total_concepts > 0]

        if not successful_stats:
            return {'error': 'No successful companies to analyze'}

        # Basic data stats
        concept_counts = [s.total_concepts for s in successful_stats]
        custom_counts = [s.custom_concepts for s in successful_stats]
        standard_counts = [s.standard_concepts for s in successful_stats]
        processing_times = [s.processing_time_ms for s in successful_stats]

        # Coverage analysis
        total_unique = len(self.all_concepts_seen)
        canonical_count = len(learned_mappings)
        custom_total = len(self.custom_concepts_seen)
        standard_total = len(self.standard_concepts_seen)

        # Calculate coverage metrics
        canonical_coverage = canonical_count / total_unique if total_unique > 0 else 0

        # Per-company coverage (how much of each company's concepts are in canonical)
        company_coverages = []
        for s in successful_stats:
            if s.total_concepts > 0:
                covered = sum(1 for c in s.unique_concepts if c in learned_mappings)
                coverage = covered / s.total_concepts
                company_coverages.append({
                    'cik': s.cik,  # Primary key
                    'ticker': s.ticker,
                    'name': s.name,
                    'total_concepts': s.total_concepts,
                    'canonical_covered': covered,
                    'coverage_rate': coverage,
                    'custom_concepts': s.custom_concepts,
                    'custom_rate': s.custom_concepts / s.total_concepts if s.total_concepts > 0 else 0,
                    'processing_time_ms': s.processing_time_ms
                })

        # Find outliers (companies with unusual concept counts)
        mean_concepts = statistics.mean(concept_counts)
        stdev_concepts = statistics.stdev(concept_counts) if len(concept_counts) > 1 else 0

        outliers = {
            'high_concept_count': [],
            'low_concept_count': [],
            'high_custom_rate': [],
            'low_coverage': []
        }

        for cov in company_coverages:
            # High concept count (> 2 std deviations above mean)
            if cov['total_concepts'] > mean_concepts + 2 * stdev_concepts:
                outliers['high_concept_count'].append({
                    'cik': cov['cik'],
                    'ticker': cov['ticker'],
                    'total_concepts': cov['total_concepts'],
                    'deviation': (cov['total_concepts'] - mean_concepts) / stdev_concepts if stdev_concepts > 0 else 0
                })

            # Low concept count (< 2 std deviations below mean)
            if cov['total_concepts'] < mean_concepts - 2 * stdev_concepts and cov['total_concepts'] > 0:
                outliers['low_concept_count'].append({
                    'cik': cov['cik'],
                    'ticker': cov['ticker'],
                    'total_concepts': cov['total_concepts'],
                    'deviation': (mean_concepts - cov['total_concepts']) / stdev_concepts if stdev_concepts > 0 else 0
                })

            # High custom rate (> 30% custom concepts)
            if cov['custom_rate'] > 0.30:
                outliers['high_custom_rate'].append({
                    'cik': cov['cik'],
                    'ticker': cov['ticker'],
                    'custom_rate': cov['custom_rate'],
                    'custom_concepts': cov['custom_concepts']
                })

            # Low coverage (< 50% canonical coverage)
            if cov['coverage_rate'] < 0.50:
                outliers['low_coverage'].append({
                    'cik': cov['cik'],
                    'ticker': cov['ticker'],
                    'coverage_rate': cov['coverage_rate'],
                    'total_concepts': cov['total_concepts']
                })

        # Sort outliers by severity
        for key in outliers:
            if 'rate' in key:
                outliers[key].sort(key=lambda x: -x.get('custom_rate', 0) if 'custom' in key else x.get('coverage_rate', 1))
            else:
                outliers[key].sort(key=lambda x: -x.get('deviation', 0))

        # Concept distribution by statement
        concepts_by_stmt = defaultdict(lambda: {'total': 0, 'canonical': 0, 'custom': 0})
        for key, stats in self.concept_stats.items():
            stmt_type = stats.statement_type
            concepts_by_stmt[stmt_type]['total'] += 1
            if stats.concept in learned_mappings:
                concepts_by_stmt[stmt_type]['canonical'] += 1
            if any(stats.concept.startswith(p) for p in ['aapl_', 'msft_', 'goog_', 'amzn_', 'meta_', 'jpm_', 'v_']):
                concepts_by_stmt[stmt_type]['custom'] += 1

        # Custom concept analysis by prefix
        custom_by_prefix = defaultdict(list)
        for concept in self.custom_concepts_seen:
            if '_' in concept:
                prefix = concept.split('_')[0]
                custom_by_prefix[prefix].append(concept)

        return {
            'metadata': {
                'generated': datetime.now().isoformat(),
                'min_occurrence_rate': self.min_occurrence_rate
            },
            'data_summary': {
                'companies_processed': self.companies_processed,
                'companies_successful': self.successful_companies,
                'companies_failed': self.companies_processed - self.successful_companies,
                'success_rate': self.successful_companies / self.companies_processed if self.companies_processed > 0 else 0,
                'total_observations': self.total_observations,
                'avg_processing_time_ms': statistics.mean(processing_times) if processing_times else 0,
                'total_processing_time_s': sum(processing_times) / 1000 if processing_times else 0
            },
            'failure_analysis': {
                'by_reason': {
                    reason: {
                        'count': len(tickers),
                        'tickers': tickers[:20]  # Show first 20 examples
                    }
                    for reason, tickers in self.failure_reasons.items()
                    if tickers  # Only include non-empty categories
                },
                'total_failures': sum(len(t) for t in self.failure_reasons.values())
            },
            'concept_counts': {
                'total_unique_concepts': total_unique,
                'standard_concepts': standard_total,
                'custom_concepts': custom_total,
                'custom_rate': custom_total / total_unique if total_unique > 0 else 0,
                'canonical_concepts': canonical_count,
                'canonical_rate': canonical_coverage,
                'filtered_out': total_unique - canonical_count,
                'filtered_rate': 1 - canonical_coverage
            },
            'per_company_stats': {
                'concepts': {
                    'min': min(concept_counts) if concept_counts else 0,
                    'max': max(concept_counts) if concept_counts else 0,
                    'mean': statistics.mean(concept_counts) if concept_counts else 0,
                    'median': statistics.median(concept_counts) if concept_counts else 0,
                    'stdev': statistics.stdev(concept_counts) if len(concept_counts) > 1 else 0
                },
                'custom_concepts': {
                    'min': min(custom_counts) if custom_counts else 0,
                    'max': max(custom_counts) if custom_counts else 0,
                    'mean': statistics.mean(custom_counts) if custom_counts else 0,
                    'median': statistics.median(custom_counts) if custom_counts else 0
                },
                'coverage': {
                    'min': min(c['coverage_rate'] for c in company_coverages) if company_coverages else 0,
                    'max': max(c['coverage_rate'] for c in company_coverages) if company_coverages else 0,
                    'mean': statistics.mean(c['coverage_rate'] for c in company_coverages) if company_coverages else 0,
                    'median': statistics.median([c['coverage_rate'] for c in company_coverages]) if company_coverages else 0
                }
            },
            'by_statement': {
                stmt: {
                    'total_concepts': data['total'],
                    'canonical_concepts': data['canonical'],
                    'canonical_rate': data['canonical'] / data['total'] if data['total'] > 0 else 0
                }
                for stmt, data in concepts_by_stmt.items()
            },
            'custom_concepts_by_company': {
                prefix: {
                    'count': len(concepts),
                    'examples': concepts[:5]
                }
                for prefix, concepts in sorted(custom_by_prefix.items(), key=lambda x: -len(x[1]))[:15]
            },
            'outliers': {
                'high_concept_count': outliers['high_concept_count'][:10],
                'low_concept_count': outliers['low_concept_count'][:10],
                'high_custom_rate': outliers['high_custom_rate'][:10],
                'low_coverage': outliers['low_coverage'][:10]
            },
            'company_details': sorted(company_coverages, key=lambda x: -x['coverage_rate']),  # All companies, sorted by coverage
            'lookups': {
                'cik_to_ticker': self.cik_to_ticker,
                'ticker_to_cik': self.ticker_to_cik
            }
        }

    def generate_outputs(self, output_dir: Path) -> Dict[str, Any]:
        """Generate all output files."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate learned mappings
        # First, group stats by concept to handle multi-statement concepts properly
        concept_to_stats: Dict[str, List[ConceptStats]] = defaultdict(list)
        for key, stats in self.concept_stats.items():
            occurrence_rate = stats.company_count / self.successful_companies if self.successful_companies > 0 else 0
            if occurrence_rate >= self.min_occurrence_rate:
                concept_to_stats[stats.concept].append(stats)

        # Now build learned_mappings, selecting primary statement for multi-statement concepts
        learned_mappings = {}
        for concept, stats_list in concept_to_stats.items():
            if len(stats_list) == 1:
                # Single statement - straightforward
                mapping = stats_list[0].to_mapping(self.successful_companies)
                learned_mappings[concept] = mapping
            else:
                # Multi-statement concept - select primary (highest occurrence)
                # Sort by company_count descending
                stats_list.sort(key=lambda s: s.company_count, reverse=True)
                primary_stats = stats_list[0]

                # Get primary mapping
                mapping = primary_stats.to_mapping(self.successful_companies)

                # Add info about other statements where this concept appears
                other_statements = []
                for other_stats in stats_list[1:]:
                    other_rate = other_stats.company_count / self.successful_companies if self.successful_companies > 0 else 0
                    other_statements.append({
                        'statement_type': other_stats.statement_type,
                        'occurrence_rate': other_rate,
                        'company_count': other_stats.company_count
                    })

                mapping['also_appears_in'] = other_statements
                mapping['is_multi_statement'] = True
                learned_mappings[concept] = mapping

        # Validate parent references and track missing parents
        validation_stats = self._validate_parent_references(learned_mappings)
        logger.info(f"Parent validation: {validation_stats['valid_parents']} valid, "
                   f"{validation_stats['missing_parents']} missing, "
                   f"{validation_stats['null_parents']} null")

        # Save learned_mappings.json
        with open(output_dir / 'learned_mappings.json', 'w') as f:
            json.dump(learned_mappings, f, indent=2)

        # Generate virtual trees
        virtual_trees = self._generate_virtual_trees(learned_mappings)
        with open(output_dir / 'virtual_trees.json', 'w') as f:
            json.dump(virtual_trees, f, indent=2)

        # Generate statement_mappings_v1.json (with metadata)
        statement_mappings = {
            'metadata': {
                'version': '1.0.0',
                'generated': datetime.now().isoformat(),
                'companies_analyzed': self.successful_companies,
                'min_occurrence_rate': self.min_occurrence_rate,
                'source': 'edgar.entity.training.run_learning'
            },
            'mappings': learned_mappings
        }
        with open(output_dir / 'statement_mappings_v1.json', 'w') as f:
            json.dump(statement_mappings, f, indent=2)

        # Generate canonical structures (raw data by statement type)
        canonical = self._generate_canonical_structures()
        with open(output_dir / 'canonical_structures.json', 'w') as f:
            json.dump(canonical, f, indent=2)

        # Generate learning summary
        summary = self._generate_summary(learned_mappings)
        with open(output_dir / 'learning_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)

        # Generate markdown report
        report = self._generate_report(learned_mappings, canonical)
        with open(output_dir / 'structural_learning_report.md', 'w') as f:
            f.write(report)

        # Generate concept linkages (multi-statement tracking)
        linkages = self._generate_concept_linkages()
        with open(output_dir / 'concept_linkages.json', 'w') as f:
            json.dump(linkages, f, indent=2)

        # Generate comprehensive statistics
        statistics = self._generate_statistics(learned_mappings)
        with open(output_dir / 'learning_statistics.json', 'w') as f:
            json.dump(statistics, f, indent=2)

        # Add linkage stats to summary
        summary['multi_statement_concepts'] = linkages['metadata']['multi_statement_concepts']
        summary['linkage_concepts'] = linkages['metadata']['linkage_concepts']

        # Update summary with file sizes
        summary['output_files'] = self._get_output_file_sizes(output_dir)

        # Rewrite summary with updated info
        with open(output_dir / 'learning_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Generated outputs in {output_dir}")
        logger.info(f"  - learned_mappings.json: {len(learned_mappings)} concepts")
        logger.info(f"  - virtual_trees.json: {len(virtual_trees)} statement types")
        logger.info(f"  - statement_mappings_v1.json")
        logger.info(f"  - canonical_structures.json")
        logger.info(f"  - learning_summary.json")
        logger.info(f"  - structural_learning_report.md")
        logger.info(f"  - concept_linkages.json: {linkages['metadata']['multi_statement_concepts']} multi-statement concepts")
        logger.info(f"  - learning_statistics.json: comprehensive stats with outliers")

        return summary

    def _get_output_file_sizes(self, output_dir: Path) -> Dict[str, int]:
        """Get sizes of output files in bytes."""
        files = [
            'learned_mappings.json',
            'virtual_trees.json',
            'statement_mappings_v1.json',
            'canonical_structures.json',
            'learning_summary.json',
            'structural_learning_report.md',
            'concept_linkages.json',
            'learning_statistics.json'
        ]
        sizes = {}
        for f in files:
            path = output_dir / f
            if path.exists():
                sizes[f] = path.stat().st_size
        return sizes

    def _generate_virtual_trees(self, learned_mappings: Dict) -> Dict:
        """Generate virtual trees from learned mappings."""
        trees = {}

        for stmt_type in STATEMENT_TYPES:
            # Get concepts for this statement type
            concepts = {
                k: v for k, v in learned_mappings.items()
                if v['statement_type'] == stmt_type
            }

            if not concepts:
                continue

            # Build tree structure
            nodes = {}
            roots = []

            for concept, data in concepts.items():
                node = {
                    'concept': concept,
                    'label': data['label'],
                    'parent': data['parent'],
                    'depth': data['avg_depth'],
                    'children': [],
                    'occurrence_rate': data['occurrence_rate'],
                    'is_abstract': data['is_abstract'],
                    'is_total': data['is_total']
                }
                nodes[concept] = node

                # Track roots (no parent or parent not in our concepts)
                if not data['parent'] or data['parent'] not in concepts:
                    roots.append(concept)

            # Build children lists
            for concept, data in concepts.items():
                parent = data['parent']
                if parent and parent in nodes:
                    nodes[parent]['children'].append(concept)

            trees[stmt_type] = {
                'statement_type': stmt_type,
                'nodes': nodes,
                'roots': roots,
                'sections': {}  # Could be populated based on depth/grouping
            }

        return trees

    def _generate_canonical_structures(self) -> Dict:
        """Generate canonical structures by statement type."""
        canonical = {}

        for stmt_type in STATEMENT_TYPES:
            concepts = []
            for key, stats in self.concept_stats.items():
                if stats.statement_type == stmt_type:
                    # Use unique company count for proper occurrence rate
                    occurrence_rate = stats.company_count / self.successful_companies if self.successful_companies > 0 else 0

                    # Get most common label
                    label = max(stats.labels.items(), key=lambda x: x[1])[0] if stats.labels else stats.concept

                    # Get most common parent
                    parent = None
                    if stats.parents:
                        parent = max(stats.parents.items(), key=lambda x: x[1])[0]

                    concepts.append({
                        'concept': stats.concept,
                        'label': label,
                        'occurrence_rate': occurrence_rate,
                        'company_count': stats.company_count,  # Unique companies
                        'observation_count': stats.occurrence_count,  # Total observations
                        'parent': parent,
                        'avg_depth': sum(stats.depths) / len(stats.depths) if stats.depths else 0,
                        'is_abstract': stats.is_abstract_count > stats.occurrence_count / 2,
                        'is_total': stats.is_total_count > stats.occurrence_count / 2
                    })

            # Sort by occurrence rate
            concepts.sort(key=lambda x: -x['occurrence_rate'])
            canonical[stmt_type] = concepts

        return canonical

    def _generate_summary(self, learned_mappings: Dict) -> Dict:
        """Generate learning summary."""
        # Count concepts by statement type
        stmt_counts = defaultdict(int)
        for concept, data in learned_mappings.items():
            stmt_counts[data['statement_type']] += 1

        return {
            'timestamp': datetime.now().isoformat(),
            'companies_processed': self.companies_processed,
            'successful_companies': self.successful_companies,
            'total_observations': self.total_observations,
            'canonical_concepts': dict(stmt_counts),
            'errors': len(self.errors)
        }

    def _generate_report(self, learned_mappings: Dict, canonical: Dict) -> str:
        """Generate markdown report."""
        lines = [
            "# Financial Statement Structural Learning Report",
            f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "\n## Summary",
            f"\n- **Companies Processed:** {self.companies_processed}",
            f"- **Successful Extractions:** {self.successful_companies}",
            f"- **Total Concept Observations:** {self.total_observations}",
            f"- **Errors:** {len(self.errors)}",
        ]

        # Statement breakdown
        for stmt_type in STATEMENT_TYPES:
            concepts = canonical.get(stmt_type, [])
            if not concepts:
                continue

            # Count concepts meeting threshold
            canonical_count = sum(1 for c in concepts if c['occurrence_rate'] >= self.min_occurrence_rate)

            lines.append(f"\n## {stmt_type}")
            lines.append(f"\n**Canonical Concepts:** {canonical_count}")

            # Show top concepts
            lines.append("\n### Core Concepts (>80% occurrence)")
            lines.append("\n| Concept | Label | Occurrence | Parent |")
            lines.append("|---------|-------|------------|--------|")

            for c in concepts[:10]:
                if c['occurrence_rate'] >= 0.8:
                    parent = c['parent'][:20] if c['parent'] else '-'
                    lines.append(
                        f"| {c['concept'][:30]} | {c['label'][:25]} | "
                        f"{c['occurrence_rate']:.0%} | {parent} |"
                    )

        return '\n'.join(lines)


def get_companies(exchange: str, count: int, random_state: int = 42) -> List[str]:
    """Get list of company tickers using CompanySubset API."""
    try:
        from edgar.reference.company_subsets import CompanySubset

        companies = (CompanySubset()
            .from_exchange(exchange)
            .sample(count, random_state=random_state)
            .get())

        return companies['ticker'].tolist()
    except ImportError:
        logger.warning("CompanySubset not available, using fallback list")
        # Fallback to well-known companies
        return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM', 'JNJ', 'V']


def main():
    parser = argparse.ArgumentParser(description='Financial Statement Concept Learning')
    parser.add_argument('--companies', type=int, default=100,
                       help='Number of companies to process (default: 100)')
    parser.add_argument('--exchange', type=str, default='NYSE',
                       help='Exchange to sample from (default: NYSE)')
    parser.add_argument('--output', type=str, default=None,
                       help='Output directory (default: training/output)')
    parser.add_argument('--min-occurrence', type=float, default=0.3,
                       help='Minimum occurrence rate threshold (default: 0.3)')
    parser.add_argument('--random-state', type=int, default=42,
                       help='Random seed for reproducibility (default: 42)')

    args = parser.parse_args()

    # Get companies
    logger.info(f"Selecting {args.companies} companies from {args.exchange}...")
    tickers = get_companies(args.exchange, args.companies, args.random_state)
    logger.info(f"Selected {len(tickers)} companies")

    # Initialize learner
    learner = ConceptLearner(min_occurrence_rate=args.min_occurrence)

    # Process companies
    for ticker in tickers:
        learner.process_company(ticker)

    # Generate outputs
    output_dir = get_output_dir(args.output)
    summary = learner.generate_outputs(output_dir)

    # Print summary
    print("\n" + "="*50)
    print("LEARNING COMPLETE")
    print("="*50)
    print(f"Companies processed: {summary['successful_companies']}/{summary['companies_processed']}")
    print(f"Total observations: {summary['total_observations']}")
    print(f"Canonical concepts by statement:")
    for stmt, count in summary['canonical_concepts'].items():
        print(f"  - {stmt}: {count}")
    print(f"\nOutput files written to: {output_dir}")


if __name__ == '__main__':
    main()
