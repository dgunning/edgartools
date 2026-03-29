"""
Parser for converting SEC API data to the new Entity Facts format.

This module handles the conversion of raw SEC company facts JSON data
into the new unified FinancialFact model.
"""

import logging
import sys
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.mappings_loader import load_learned_mappings
from edgar.entity.models import DataQuality, FinancialFact

log = logging.getLogger(__name__)


class EntityFactsParser:
    """
    Parser for converting SEC company facts to EntityFacts.

    This class handles the transformation of raw SEC API data into
    the new unified fact model with proper typing and AI-ready metadata.
    """

    # Shared empty tuple to avoid allocating a new [] per fact for the common case.
    # Tuple is immutable — prevents accidental mutation of shared sentinel.
    _EMPTY_TAGS: tuple = ()

    # Semantic tags for concepts (used for search and categorization)
    SEMANTIC_TAGS = {
        'Revenue': ['revenue', 'sales', 'operating'],
        'NetIncomeLoss': ['profit', 'earnings', 'bottom_line'],
        'Assets': ['assets', 'resources', 'balance_sheet'],
        'CashAndCashEquivalentsAtCarryingValue': ['cash', 'liquidity', 'current_assets']
    }

    @classmethod
    def parse_company_facts(cls, json_data: Dict[str, Any]) -> Optional[EntityFacts]:
        """
        Parse SEC company facts JSON into EntityFacts.

        Args:
            json_data: Raw JSON from SEC API

        Returns:
            EntityFacts object or None if parsing fails
        """
        if not json_data:
            log.error("No company facts data to parse (received %s)", type(json_data).__name__)
            return None

        try:
            cik = int(json_data.get('cik', 0))
            entity_name = json_data.get('entityName', 'Unknown')

            facts = []

            # String interning: many string fields repeat across thousands of facts.
            # For example, taxonomy (~3 unique), unit (~5), fiscal_period (~5),
            # form_type (~5), concept (~500-1000) each appear on every fact.
            # sys.intern deduplicates them to a single object, saving significant memory.
            _intern = sys.intern
            _intern_cache: Dict[str, str] = {}

            def _fast_intern(s: str) -> str:
                """Intern a string, using a local cache to avoid repeated dict lookups."""
                cached = _intern_cache.get(s)
                if cached is not None:
                    return cached
                interned = _intern(s)
                _intern_cache[s] = interned
                return interned

            # Process facts from different taxonomies
            facts_data = json_data.get('facts', {})

            # Pre-compute per-concept metadata once instead of per-fact
            _determine_statement_type = cls._determine_statement_type
            _get_semantic_tags = cls._get_semantic_tags
            _get_structural_info = cls._get_structural_info
            _generate_business_context = cls._generate_business_context
            _clean_unit = cls._clean_unit

            for taxonomy, taxonomy_facts in facts_data.items():
                interned_taxonomy = _fast_intern(taxonomy)
                for concept, concept_data in taxonomy_facts.items():
                    # Process units for this concept
                    units = concept_data.get('units', {})
                    label = concept_data.get('label', concept)
                    description = concept_data.get('description', '')

                    # Intern concept-level strings once (shared by all facts for this concept)
                    interned_concept = _fast_intern(concept)
                    interned_label = _fast_intern(label) if label else ''

                    # Hoist per-concept work out of the per-fact loop
                    statement_type = _determine_statement_type(interned_concept)
                    if statement_type:
                        statement_type = _fast_intern(statement_type)
                    semantic_tags = _get_semantic_tags(interned_concept)
                    # Note: structural_info is shared across all facts for this concept.
                    # It is only read (via .get()) in _parse_single_fact — do not mutate per-fact.
                    structural_info = _get_structural_info(interned_concept)
                    if structural_info.get('parent'):
                        structural_info['parent'] = _fast_intern(structural_info['parent'])
                    if structural_info.get('section'):
                        structural_info['section'] = _fast_intern(structural_info['section'])

                    for unit, unit_facts in units.items():
                        interned_unit = _fast_intern(unit)
                        clean_unit = _fast_intern(_clean_unit(interned_unit)) if interned_unit else ''
                        business_context = _fast_intern(
                            _generate_business_context(interned_label, description, interned_unit)
                        ) if interned_label or description else ''

                        for fact_data in unit_facts:
                            fact = cls._parse_single_fact(
                                concept=interned_concept,
                                taxonomy=interned_taxonomy,
                                label=interned_label,
                                unit=clean_unit,
                                fact_data=fact_data,
                                _fast_intern=_fast_intern,
                                statement_type=statement_type,
                                semantic_tags=semantic_tags,
                                structural_info=structural_info,
                                business_context=business_context,
                            )
                            if fact:
                                facts.append(fact)

            if not facts:
                log.warning("No facts found for CIK %s", cik)
                return None

            return EntityFacts(cik=cik, name=entity_name, facts=facts)

        except Exception as e:
            log.error("Error parsing company facts: %s", e)
            return None

    @classmethod
    def _parse_single_fact(cls,
                          concept: str,
                          taxonomy: str,
                          label: str,
                          unit: str,
                          fact_data: Dict[str, Any],
                          _fast_intern=None,
                          statement_type: Optional[str] = None,
                          semantic_tags: Optional[List[str]] = None,
                          structural_info: Optional[Dict[str, Any]] = None,
                          business_context: str = '') -> Optional[FinancialFact]:
        """
        Parse a single fact from SEC data.

        Args:
            concept: Concept identifier (already interned)
            taxonomy: Taxonomy namespace (already interned)
            label: Human-readable label (already interned)
            unit: Clean unit string (already interned)
            fact_data: Raw fact data from SEC JSON
            _fast_intern: Optional interning function for string deduplication
            statement_type: Pre-computed statement type (per-concept)
            semantic_tags: Pre-computed semantic tags (per-concept)
            structural_info: Pre-computed structural metadata (per-concept)
            business_context: Pre-computed business context (per-concept+unit)

        Returns:
            FinancialFact or None if parsing fails
        """

        # Extract core values
        value = fact_data.get('val')
        if value is None:
            return None

        # Parse dates
        period_end = cls._parse_date(fact_data.get('end'))
        period_start = cls._parse_date(fact_data.get('start'))
        filing_date = cls._parse_date(fact_data.get('filed'))

        # Determine period type
        if period_start:
            period_type = 'duration'
        else:
            period_type = 'instant'

        # Parse fiscal period info
        fiscal_year = cls._parse_fiscal_year(fact_data.get('fy'))
        fiscal_period = fact_data.get('fp', '')

        # Determine numeric value
        numeric_value = None
        if isinstance(value, (int, float)):
            numeric_value = float(value)
        elif isinstance(value, str) and value.replace('-', '').replace('.', '').isdigit():
            try:
                numeric_value = float(value)
            except ValueError:
                pass

        # Determine data quality (per-fact: depends on fiscal_period)
        data_quality = cls._assess_data_quality(fact_data, fiscal_period)

        if structural_info is None:
            structural_info = {}
        if semantic_tags is None:
            semantic_tags = cls._EMPTY_TAGS

        # Intern per-fact strings to deduplicate memory
        if _fast_intern is not None:
            full_concept = _fast_intern(f"{taxonomy}:{concept}")
            fiscal_period = _fast_intern(fiscal_period) if fiscal_period else ''
            period_type = _fast_intern(period_type)
            form_type = _fast_intern(fact_data.get('form', ''))
            accession = _fast_intern(fact_data.get('accn', ''))
        else:
            full_concept = f"{taxonomy}:{concept}"
            form_type = fact_data.get('form', '')
            accession = fact_data.get('accn', '')

        return FinancialFact(
                concept=full_concept,
                taxonomy=taxonomy,
                label=label,
                value=value,
                numeric_value=numeric_value,
                unit=unit,
                period_start=period_start,
                period_end=period_end,
                period_type=period_type,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                filing_date=filing_date,
                form_type=form_type,
                accession=accession,
                data_quality=data_quality,
                is_audited=fiscal_period == 'FY',
                confidence_score=0.9 if data_quality == DataQuality.HIGH else 0.7,
                semantic_tags=semantic_tags,
                business_context=business_context,
                statement_type=statement_type,
                depth=structural_info.get('depth'),
                parent_concept=structural_info.get('parent'),
                section=structural_info.get('section'),
                is_abstract=structural_info.get('is_abstract', False),
                is_total=structural_info.get('is_total', False),
                presentation_order=structural_info.get('avg_depth')
            )

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object"""
        if not date_str:
            return None

        try:
            # Try common date formats
            for fmt in ['%Y-%m-%d', '%Y%m%d', '%m/%d/%Y']:
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue

            # If all formats fail, try to parse as ISO format
            return datetime.fromisoformat(date_str).date()

        except Exception:
            return None

    @staticmethod
    def _parse_fiscal_year(fy_value: Any) -> int:
        """Parse fiscal year value"""
        if not fy_value:
            return 0

        try:
            return int(fy_value)
        except (ValueError, TypeError):
            return 0

    @classmethod
    def _determine_statement_type(cls, concept: str) -> Optional[str]:
        """
        Determine which financial statement a concept belongs to.

        Uses the unified concept mapper which combines:
        - concept_linkages.json (multi-statement concepts)
        - learned_mappings.json (learned from XBRL analysis)
        - fallback mappings (common US-GAAP concepts)
        """
        # Remove namespace if present
        if ':' in concept:
            concept = concept.split(':')[-1]

        try:
            from edgar.entity.mappings_loader import get_primary_statement
            return get_primary_statement(concept)
        except Exception as e:
            log.debug("Error getting primary statement from mapper: %s", e)
            return None

    @classmethod
    def _get_semantic_tags(cls, concept: str) -> List[str]:
        """Get semantic tags for a concept"""
        # Remove namespace if present
        if ':' in concept:
            concept = concept.split(':')[-1]

        return cls.SEMANTIC_TAGS.get(concept, cls._EMPTY_TAGS)

    @classmethod
    def _get_structural_info(cls, concept: str) -> Dict[str, Any]:
        """
        Get structural metadata for a concept from learned mappings.

        Returns dict with depth, parent, section, is_abstract, is_total
        """
        # Remove namespace if present
        if ':' in concept:
            concept = concept.split(':')[-1]

        try:
            learned_mappings = load_learned_mappings()
            if concept in learned_mappings:
                mapping = learned_mappings[concept]
                return {
                    'depth': int(mapping.get('avg_depth', 0)) if mapping.get('avg_depth') else None,
                    'parent': mapping.get('parent'),
                    'section': mapping.get('section'),
                    'is_abstract': mapping.get('is_abstract', False),
                    'is_total': mapping.get('is_total', False)
                }
        except Exception as e:
            log.debug("Error getting structural info: %s", e)

        return {}

    @staticmethod
    def _assess_data_quality(fact_data: Dict[str, Any], fiscal_period: str) -> DataQuality:
        """Assess the quality of a fact"""
        # Annual data is typically higher quality
        if fiscal_period == 'FY':
            return DataQuality.HIGH

        # Quarterly data
        if fiscal_period in ['Q1', 'Q2', 'Q3', 'Q4']:
            return DataQuality.HIGH

        # Other data
        return DataQuality.MEDIUM

    @staticmethod
    def _generate_business_context(label: str, description: str, unit: str) -> str:
        """Generate business context for a fact"""
        # Handle null/None values
        if not label:
            label = ""
        if not description:
            description = ""

        # Return description if it's longer and more informative than label
        if description and len(description) > len(label):
            return description

        # Generate context based on label and unit
        if label and 'Revenue' in label:
            return "Total revenue generated from operations"
        elif label and 'Income' in label:
            return "Net earnings after all expenses and taxes"
        elif label and 'Assets' in label:
            return "Total resources owned by the company"

        # Return label if available, otherwise empty string
        return label if label else ""

    _UNIT_MAPPING = {
        'USD': 'USD',
        'usd': 'USD',
        'pure': 'number',
        'shares': 'shares',
        'USD/shares': 'USD per share',
    }

    @classmethod
    def _clean_unit(cls, unit: str) -> str:
        """Clean and standardize unit representation"""
        if not unit:
            return ""
        return cls._UNIT_MAPPING.get(unit, unit)
