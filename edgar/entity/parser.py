"""
Parser for converting SEC API data to the new Entity Facts format.

This module handles the conversion of raw SEC company facts JSON data
into the new unified FinancialFact model.
"""

import logging
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

    # Concept mapping for common financial statement items
    STATEMENT_MAPPING = {
        # Income Statement
        'Revenue': 'IncomeStatement',
        'Revenues': 'IncomeStatement',  # Fix for Issue #438 - ensure us-gaap:Revenues maps properly
        'RevenueFromContractWithCustomerExcludingAssessedTax': 'IncomeStatement',
        'SalesRevenueNet': 'IncomeStatement',
        'CostOfRevenue': 'IncomeStatement',
        'GrossProfit': 'IncomeStatement',
        'OperatingExpenses': 'IncomeStatement',
        'OperatingIncomeLoss': 'IncomeStatement',
        'NetIncomeLoss': 'IncomeStatement',
        'EarningsPerShareDiluted': 'IncomeStatement',

        # Balance Sheet
        'Assets': 'BalanceSheet',
        'AssetsCurrent': 'BalanceSheet',
        'CurrentAssets': 'BalanceSheet',
        'AssetsNoncurrent': 'BalanceSheet',
        'Liabilities': 'BalanceSheet',
        'LiabilitiesCurrent': 'BalanceSheet',
        'CurrentLiabilities': 'BalanceSheet',
        'LiabilitiesNoncurrent': 'BalanceSheet',
        'StockholdersEquity': 'BalanceSheet',
        'CashAndCashEquivalentsAtCarryingValue': 'BalanceSheet',

        # Cash Flow
        'NetCashProvidedByUsedInOperatingActivities': 'CashFlow',
        'NetCashProvidedByUsedInInvestingActivities': 'CashFlow',
        'NetCashProvidedByUsedInFinancingActivities': 'CashFlow',
        'CashAndCashEquivalentsPeriodIncreaseDecrease': 'CashFlow'
    }

    # Semantic tags for concepts
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
        try:
            cik = int(json_data.get('cik', 0))
            entity_name = json_data.get('entityName', 'Unknown')

            facts = []

            # Process facts from different taxonomies
            facts_data = json_data.get('facts', {})

            for taxonomy, taxonomy_facts in facts_data.items():
                for concept, concept_data in taxonomy_facts.items():
                    # Process units for this concept
                    units = concept_data.get('units', {})
                    label = concept_data.get('label', concept)
                    description = concept_data.get('description', '')

                    for unit, unit_facts in units.items():
                        for fact_data in unit_facts:
                            fact = cls._parse_single_fact(
                                concept=concept,
                                taxonomy=taxonomy,
                                label=label,
                                description=description,
                                unit=unit,
                                fact_data=fact_data
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
                          description: str,
                          unit: str,
                          fact_data: Dict[str, Any]) -> Optional[FinancialFact]:
        """
        Parse a single fact from SEC data.

        Args:
            concept: Concept identifier
            taxonomy: Taxonomy namespace
            label: Human-readable label
            description: Concept description
            unit: Unit of measure
            fact_data: Raw fact data

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

        # Determine statement type
        statement_type = cls._determine_statement_type(concept)

        # Get semantic tags
        semantic_tags = cls._get_semantic_tags(concept)

        # Get structural metadata from learned mappings
        structural_info = cls._get_structural_info(concept)

        # Determine data quality
        data_quality = cls._assess_data_quality(fact_data, fiscal_period)

        # Create business context
        business_context = cls._generate_business_context(label, description, unit)

        # Clean unit representation
        clean_unit = cls._clean_unit(unit)

        # Determine scale
        scale = cls._determine_scale(unit)

        return FinancialFact(
                concept=f"{taxonomy}:{concept}",
                taxonomy=taxonomy,
                label=label,
                value=value,
                numeric_value=numeric_value,
                unit=clean_unit,
                scale=scale,
                period_start=period_start,
                period_end=period_end,
                period_type=period_type,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                filing_date=filing_date,
                form_type=fact_data.get('form', ''),
                accession=fact_data.get('accn', ''),
                data_quality=data_quality,
                is_audited=fiscal_period == 'FY',  # Annual reports are typically audited
                is_restated=False,  # Would need additional logic to detect
                is_estimated=False,  # Would need additional logic to detect
                confidence_score=0.9 if data_quality == DataQuality.HIGH else 0.7,
                semantic_tags=semantic_tags,
                business_context=business_context,
                statement_type=statement_type,
                # Add structural metadata
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

        First checks static mappings, then falls back to learned mappings
        with confidence threshold.
        """
        # Remove namespace if present
        if ':' in concept:
            concept = concept.split(':')[-1]

        # Check static mappings first (highest confidence)
        if concept in cls.STATEMENT_MAPPING:
            return cls.STATEMENT_MAPPING[concept]

        # Check learned mappings
        try:
            learned_mappings = load_learned_mappings()
            if concept in learned_mappings:
                mapping = learned_mappings[concept]
                # Only use high-confidence learned mappings
                if mapping.get('confidence', 0) >= 0.5:  # 50% threshold
                    return mapping['statement_type']
        except Exception as e:
            log.debug("Error loading learned mappings: %s", e)

        return None

    @classmethod
    def _get_semantic_tags(cls, concept: str) -> List[str]:
        """Get semantic tags for a concept"""
        # Remove namespace if present
        if ':' in concept:
            concept = concept.split(':')[-1]

        return cls.SEMANTIC_TAGS.get(concept, [])

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

    @staticmethod
    def _clean_unit(unit: str) -> str:
        """Clean and standardize unit representation"""
        if not unit:
            return ""

        unit_mapping = {
            'USD': 'USD',
            'usd': 'USD',
            'pure': 'number',
            'shares': 'shares',
            'USD/shares': 'USD per share'
        }

        return unit_mapping.get(unit, unit)

    @staticmethod
    def _determine_scale(unit: str) -> Optional[int]:
        """Determine scale factor from unit"""
        # SEC data is typically already scaled
        # This would need more sophisticated logic based on the actual data
        return None
