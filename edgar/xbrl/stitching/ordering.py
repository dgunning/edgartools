"""
XBRL Statement Ordering - Intelligent Ordering for Multi-Period Statements

This module provides consistent ordering for financial statements across multiple periods
by combining template-based, reference-based, and semantic positioning strategies.
"""

import re
from enum import Enum
from typing import Dict, List, Optional, Tuple

try:
    from rapidfuzz import fuzz
except ImportError:
    # Fallback to difflib if rapidfuzz is not available
    from difflib import SequenceMatcher

    class fuzz:
        @staticmethod
        def ratio(s1: str, s2: str) -> float:
            return SequenceMatcher(None, s1, s2).ratio() * 100


class StatementType(str, Enum):
    """Supported statement types for ordering"""
    INCOME_STATEMENT = "IncomeStatement"
    BALANCE_SHEET = "BalanceSheet"
    CASH_FLOW = "CashFlowStatement"
    EQUITY = "StatementOfEquity"


class FinancialStatementTemplates:
    """Canonical ordering templates for financial statements based on XBRL concepts"""

    INCOME_STATEMENT_TEMPLATE = [
        # Revenue Section (0-99)
        (0, "revenue_section", [
            # Product/Service Revenue Components
            "us-gaap:SalesRevenueGoodsNet",
            "us-gaap:ProductSales", 
            "us-gaap:SalesRevenueServicesNet",
            "us-gaap:SubscriptionRevenue",
            # Contract Revenue
            "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax",
            # Total Revenue
            "us-gaap:Revenue",
            "us-gaap:Revenues", 
            "us-gaap:SalesRevenueNet",
            "us-gaap:OperatingRevenue"
        ]),

        # Cost Section (100-199)
        (100, "cost_section", [
            "us-gaap:CostOfRevenueAbstract",  # Abstract
            "us-gaap:CostOfRevenue",  # Total
            "us-gaap:CostOfGoodsSold",
            "us-gaap:CostOfGoodsAndServicesSold",
            "us-gaap:CostOfSales",
            "us-gaap:DirectOperatingCosts",
            "us-gaap:CostsAndExpenses"
        ]),

        # Gross Profit (200-299)
        (200, "gross_profit", [
            "us-gaap:GrossProfit"
        ]),

        # Operating Expenses (300-399)
        (300, "operating_expenses", [
            # R&D Expenses
            "us-gaap:ResearchAndDevelopmentCosts",
            "us-gaap:ResearchAndDevelopmentExpense",
            # SG&A Expenses
            "us-gaap:SellingGeneralAndAdministrativeExpense",
            "us-gaap:GeneralAndAdministrativeExpense", 
            "us-gaap:AdministrativeExpense",
            "us-gaap:SellingAndMarketingExpense",
            "us-gaap:SellingExpense",
            "us-gaap:MarketingExpense",
            "us-gaap:AdvertisingExpense",
            # Total Operating Expenses
            "us-gaap:NoninterestExpense",
            "us-gaap:OperatingCostsAndExpenses",
            "us-gaap:OperatingExpenses"
        ]),

        # Operating Income (400-499)
        (400, "operating_income", [
            "us-gaap:OperatingIncomeLoss",
            "us-gaap:OperatingIncome",
            "us-gaap:IncomeLossFromContinuingOperationsBeforeInterestAndTaxes"
        ]),

        # Non-Operating (500-599)
        (500, "non_operating", [
            "us-gaap:InterestIncomeExpenseNet",
            "us-gaap:InterestAndDebtExpense",
            "us-gaap:InterestExpense",
            "us-gaap:InterestExpenseNonoperating",  # ADBE uses this for non-operating interest expense
            "us-gaap:InterestIncome",
            "us-gaap:InvestmentIncomeInterest",  # NVIDIA uses this variant
            "us-gaap:OtherNonoperatingIncomeExpense",
            "us-gaap:NonoperatingIncomeExpense",
            "orcl:NonoperatingIncomeExpenseIncludingEliminationOfNetIncomeLossAttributableToNoncontrollingInterests"
        ]),

        # Pre-Tax Income (600-699)
        (600, "pretax_income", [
            "us-gaap:IncomeLossBeforeIncomeTaxes",
            "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxes",
            "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "orcl:IncomeLossFromContinuingOperationsIncludingNoncontrollingInterestBeforeIncomeTaxesExtraordinaryItems"
        ]),

        # Tax (700-799)
        (700, "tax", [
            "us-gaap:IncomeTaxesPaidNet",
            "us-gaap:IncomeTaxExpenseBenefit"
        ]),

        # Net Income (800-899)
        (800, "net_income", [
            "us-gaap:IncomeLossFromContinuingOperationsIncludingPortionAttributableToNoncontrollingInterest",
            "us-gaap:IncomeLossFromContinuingOperations",
            "us-gaap:NetIncome",
            "us-gaap:NetIncomeLoss",
            "us-gaap:ProfitLoss",
            "us-gaap:NetIncomeLossAttributableToNonredeemableNoncontrollingInterest",
            "us-gaap:NetIncomeLossAttributableToNoncontrollingInterest"
        ]),

        # Per Share Data (900-999)
        (900, "per_share", [
            "us-gaap:EarningsPerShareAbstract",
            "us-gaap:EarningsPerShareBasic",
            "us-gaap:EarningsPerShareDiluted",
            "us-gaap:WeightedAverageNumberOfSharesOutstandingAbstract",
            "us-gaap:WeightedAverageNumberOfSharesOutstandingBasic",
            "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding"
        ])
    ]

    BALANCE_SHEET_TEMPLATE = [
        # Current Assets (0-199)
        (0, "current_assets", [
            "Cash and Cash Equivalents",
            "Cash",
            "Short-term Investments",
            "Marketable Securities",
            "Accounts Receivable",
            "Trade Receivables",
            "Inventory",
            "Prepaid Expenses",
            "Other Current Assets",
            "Total Current Assets"
        ]),

        # Non-Current Assets (200-399)
        (200, "noncurrent_assets", [
            "Property, Plant and Equipment",
            "Property and Equipment",
            "Long-term Investments",
            "Goodwill",
            "Intangible Assets",
            "Other Non-current Assets",
            "Total Non-current Assets",
            "Total Assets"
        ]),

        # Current Liabilities (400-599)
        (400, "current_liabilities", [
            "Accounts Payable",
            "Trade Payables",
            "Accrued Liabilities",
            "Accrued Expenses",
            "Short-term Debt",
            "Current Portion of Long-term Debt",
            "Other Current Liabilities",
            "Total Current Liabilities"
        ]),

        # Non-Current Liabilities (600-799)
        (600, "noncurrent_liabilities", [
            "Long-term Debt",
            "Deferred Revenue",
            "Deferred Tax Liabilities",
            "Other Non-current Liabilities",
            "Total Non-current Liabilities",
            "Total Liabilities"
        ]),

        # Equity (800-999)
        (800, "equity", [
            "Common Stock",
            "Additional Paid-in Capital",
            "Retained Earnings",
            "Accumulated Other Comprehensive Income",
            "Treasury Stock",
            "Total Stockholders' Equity",
            "Total Shareholders' Equity",
            "Total Equity"
        ])
    ]

    def get_template_position(self, item_concept: str, item_label: str, statement_type: str) -> Optional[float]:
        """
        Get template position for an item, prioritizing concept-based matching over label matching.

        Args:
            item_concept: The XBRL concept (e.g., "us-gaap:Revenue")
            item_label: The display label (e.g., "Contract Revenue") 
            statement_type: Type of statement ("IncomeStatement", "BalanceSheet", etc.)

        Returns:
            Float position in template, or None if no match found
        """
        # Handle different statement type formats
        if statement_type == "IncomeStatement":
            template_name = "INCOME_STATEMENT_TEMPLATE"
        elif statement_type == "BalanceSheet":
            template_name = "BALANCE_SHEET_TEMPLATE"
        else:
            template_name = f"{statement_type.upper()}_TEMPLATE"

        template = getattr(self, template_name, None)
        if not template:
            return None

        # Strategy 1: Direct concept matching (highest priority)
        if item_concept:
            normalized_concept = self._normalize_xbrl_concept(item_concept)
            for base_pos, _section_name, template_concepts in template:
                for i, template_concept in enumerate(template_concepts):
                    template_normalized = self._normalize_xbrl_concept(template_concept)
                    if normalized_concept == template_normalized:
                        return float(base_pos + i)

        # Strategy 2: Label-based matching as fallback (for compatibility)
        if item_label:
            for base_pos, _section_name, template_concepts in template:
                for i, template_concept in enumerate(template_concepts):
                    if self._labels_match(item_label, template_concept):
                        return float(base_pos + i)

        return None

    def _normalize_xbrl_concept(self, concept: str) -> str:
        """
        Normalize XBRL concept for matching.

        Handles variations in concept format:
        - "us-gaap:Revenue" vs "us-gaap_Revenue" 
        - Case sensitivity
        - Namespace prefixes
        """
        if not concept:
            return ""

        # Normalize separators (: vs _)
        normalized = concept.lower()
        normalized = normalized.replace(':', '_')

        # Handle common namespace variations
        # us-gaap, usgaap, gaap all should match
        if normalized.startswith('us-gaap_') or normalized.startswith('usgaap_'):
            normalized = 'us-gaap_' + normalized.split('_', 1)[1]
        elif normalized.startswith('gaap_'):
            normalized = 'us-gaap_' + normalized.split('_', 1)[1]

        return normalized

    def _labels_match(self, label1: str, label2: str) -> bool:
        """Check if two labels represent the same financial item (fallback for non-concept matching)"""
        if not label1 or not label2:
            return False

        # For XBRL concepts in templates, don't try to match against labels
        if ':' in label2 or '_gaap_' in label2.lower():
            return False

        # Use existing normalization logic for label matching
        norm1 = self._normalize_concept(label1)
        norm2 = self._normalize_concept(label2)

        # Exact match
        if norm1 == norm2:
            return True

        # Fuzzy matching for similar concepts
        similarity = fuzz.ratio(norm1, norm2) / 100.0
        return similarity > 0.7

    def _concepts_match(self, concept1: str, concept2: str) -> bool:
        """Check if two concepts represent the same financial item"""
        # Normalize for comparison
        norm1 = self._normalize_concept(concept1)
        norm2 = self._normalize_concept(concept2)

        # Exact match
        if norm1 == norm2:
            return True

        # Fuzzy matching for similar concepts
        similarity = fuzz.ratio(norm1, norm2) / 100.0
        return similarity > 0.7  # Lowered threshold for better matching

    def _normalize_concept(self, concept: str) -> str:
        """Normalize concept for comparison"""
        if not concept:
            return ""

        # Remove common variations
        normalized = concept.lower()
        normalized = re.sub(r'\s+', ' ', normalized)  # Normalize whitespace
        normalized = re.sub(r'[,\.]', '', normalized)  # Remove punctuation
        normalized = re.sub(r'\(.*?\)', '', normalized)  # Remove parenthetical
        normalized = re.sub(r'\bexpense\b', '', normalized)  # Remove 'expense' suffix
        normalized = re.sub(r'\bincome\b', '', normalized)  # Remove 'income' suffix for matching
        return normalized.strip()


class ReferenceOrderingStrategy:
    """Extract ordering from reference statement"""

    def establish_reference_order(self, statements: List[Dict]) -> Dict[str, float]:
        """Establish reference ordering from best available statement"""

        if not statements:
            return {}

        # Strategy: Use most recent statement (statements are ordered newest first)
        reference_statement = statements[0]

        reference_order = {}
        for i, item in enumerate(reference_statement.get('data', [])):
            concept = item.get('concept')
            label = item.get('label')

            if concept:
                # Store by both concept ID and label for flexibility
                reference_order[concept] = float(i)
                if label:
                    reference_order[label] = float(i)

        return reference_order


class SemanticPositioning:
    """Position concepts based on financial statement semantics"""

    def __init__(self, statement_type: str):
        self.statement_type = statement_type
        self.section_defaults = self._get_section_defaults()

    def _get_section_defaults(self) -> Dict[str, float]:
        """Default positions for each section when no other guidance available"""
        if self.statement_type == "IncomeStatement":
            return {
                "revenue": 50.0,
                "cost": 150.0,
                "gross_profit": 250.0,
                "expense": 350.0,
                "operating_income": 450.0,
                "non_operating": 550.0,
                "pretax_income": 650.0,
                "tax": 750.0,
                "net_income": 850.0,
                "per_share": 950.0
            }
        elif self.statement_type == "BalanceSheet":
            return {
                "current_assets": 100.0,
                "noncurrent_assets": 300.0,
                "current_liabilities": 500.0,
                "noncurrent_liabilities": 700.0,
                "equity": 900.0
            }
        return {}

    def infer_position(self, concept: str, existing_order: Dict[str, float]) -> float:
        """Infer semantic position for a new concept"""

        # Rule-based positioning
        section = self._classify_concept_section(concept)
        if section:
            return self._position_in_section(concept, section, existing_order)

        # Parent-child relationship positioning
        parent = self._find_parent_concept(concept, existing_order)
        if parent:
            return existing_order[parent] + 0.1  # Just after parent

        # Similarity-based positioning
        similar_concept = self._find_most_similar_concept(concept, existing_order)
        if similar_concept:
            return existing_order[similar_concept] + 0.1

        # Default to end
        return 999.0

    def _classify_concept_section(self, concept: str) -> Optional[str]:
        """Classify concept into financial statement section"""
        if not concept:
            return None

        concept_lower = concept.lower()

        if self.statement_type == "IncomeStatement":
            # Revenue indicators
            if any(term in concept_lower for term in ['revenue', 'sales']) and not any(term in concept_lower for term in ['cost', 'expense']):
                return "revenue"
            # Cost indicators  
            elif any(term in concept_lower for term in ['cost of', 'cogs']):
                return "cost"
            # Gross profit
            elif 'gross profit' in concept_lower or 'gross margin' in concept_lower:
                return "gross_profit"
            # Operating expenses
            elif any(term in concept_lower for term in ['r&d', 'research', 'selling', 'administrative', 'marketing']) or ('expense' in concept_lower and 'tax' not in concept_lower):
                return "expense"
            # Operating income
            elif 'operating income' in concept_lower or 'operating profit' in concept_lower:
                return "operating_income"
            # Non-operating
            elif any(term in concept_lower for term in ['interest', 'other income', 'nonoperating']):
                return "non_operating"
            # Pre-tax income
            elif 'before tax' in concept_lower or 'pretax' in concept_lower:
                return "pretax_income"
            # Tax
            elif 'tax' in concept_lower and 'expense' in concept_lower:
                return "tax"
            # Net income
            elif 'net income' in concept_lower or 'net earnings' in concept_lower:
                return "net_income"
            # Per share
            elif any(term in concept_lower for term in ['per share', 'earnings per', 'shares outstanding']):
                return "per_share"

        elif self.statement_type == "BalanceSheet":
            if any(term in concept_lower for term in ['cash', 'receivable', 'inventory', 'prepaid']) or ('current' in concept_lower and 'asset' in concept_lower):
                return "current_assets"
            elif any(term in concept_lower for term in ['property', 'equipment', 'goodwill', 'intangible']) or ('asset' in concept_lower and 'current' not in concept_lower):
                return "noncurrent_assets"
            elif any(term in concept_lower for term in ['payable', 'accrued']) or ('current' in concept_lower and 'liabilit' in concept_lower):
                return "current_liabilities"
            elif 'debt' in concept_lower or ('liabilit' in concept_lower and 'current' not in concept_lower):
                return "noncurrent_liabilities"
            elif any(term in concept_lower for term in ['equity', 'stock', 'retained earnings', 'capital']):
                return "equity"

        return None

    def _position_in_section(self, concept: str, section: str, existing_order: Dict[str, float]) -> float:
        """Position concept within its identified section"""
        section_concepts = [
            (label, pos) for label, pos in existing_order.items()
            if self._classify_concept_section(label) == section
        ]

        if not section_concepts:
            # Section doesn't exist yet - use template defaults
            return self.section_defaults.get(section, 999.0)

        # Find best position within section
        section_concepts.sort(key=lambda x: x[1])  # Sort by position

        # Simple strategy: place at end of section
        last_pos = section_concepts[-1][1]
        return last_pos + 0.1

    def _find_parent_concept(self, concept: str, existing_order: Dict[str, float]) -> Optional[str]:
        """Find parent concept in hierarchy"""
        if not concept:
            return None

        # Look for hierarchical relationships
        # e.g., "Software Revenue" -> "Revenue"
        concept_words = set(concept.lower().split())

        candidates = []
        for existing_concept in existing_order.keys():
            if not existing_concept:
                continue

            existing_words = set(existing_concept.lower().split())

            # Check if existing concept is a parent (subset of words)
            # Also check for common patterns like "expense" being a parent of "X expense"
            if (existing_words.issubset(concept_words) and len(existing_words) < len(concept_words)) or \
               (existing_concept.lower() in concept.lower() and existing_concept.lower() != concept.lower()):
                candidates.append((existing_concept, len(existing_words)))

        if candidates:
            # Return the most specific parent (most words in common)
            return max(candidates, key=lambda x: x[1])[0]

        return None

    def _find_most_similar_concept(self, concept: str, existing_order: Dict[str, float]) -> Optional[str]:
        """Find most similar existing concept"""
        if not concept:
            return None

        best_match = None
        best_similarity = 0.0

        for existing_concept in existing_order.keys():
            if not existing_concept:
                continue

            similarity = fuzz.ratio(concept.lower(), existing_concept.lower()) / 100.0
            if similarity > best_similarity and similarity > 0.5:  # Minimum threshold
                best_similarity = similarity
                best_match = existing_concept

        return best_match


class StatementOrderingManager:
    """Manages consistent ordering across multi-period statements"""

    def __init__(self, statement_type: str):
        self.statement_type = statement_type
        self.templates = FinancialStatementTemplates()
        self.reference_strategy = ReferenceOrderingStrategy()
        self.semantic_positioning = SemanticPositioning(statement_type)

    def determine_ordering(self, statements: List[Dict]) -> Dict[str, float]:
        """
        Determine unified ordering for all concepts across statements.

        Returns:
            Dict mapping concept -> sort_key (float for interpolation)
        """
        if not statements:
            return {}

        all_concepts = self._extract_all_concepts(statements)

        # Strategy 1: Template-based ordering (highest priority)
        template_positioned = self._apply_template_ordering(all_concepts, statements)

        # Strategy 2: Reference statement ordering for non-template items
        reference_positioned = self._apply_reference_ordering(
            all_concepts, statements, template_positioned
        )

        # Strategy 3: Semantic positioning for orphan concepts
        semantic_positioned = self._apply_semantic_positioning(
            all_concepts, template_positioned, reference_positioned
        )

        # Strategy 4: Section-aware consolidation to maintain template groupings
        final_ordering = self._consolidate_section_ordering(
            semantic_positioned, template_positioned, statements
        )

        return final_ordering

    def _extract_all_concepts(self, statements: List[Dict]) -> set:
        """Extract all unique concepts from statements"""
        all_concepts = set()

        for statement in statements:
            for item in statement.get('data', []):
                concept = item.get('concept')
                label = item.get('label')
                if concept:
                    all_concepts.add(concept)
                if label:
                    all_concepts.add(label)

        return all_concepts

    def _apply_template_ordering(self, concepts: set, statements: List[Dict]) -> Dict[str, float]:
        """Apply template-based ordering for known concepts using concept-first matching"""
        template_order = {}

        # Build a mapping of concepts/labels to their actual XBRL concepts for better matching
        concept_to_xbrl = {}
        label_to_xbrl = {}

        for statement in statements:
            for item in statement.get('data', []):
                concept = item.get('concept')
                label = item.get('label')

                if concept and label:
                    concept_to_xbrl[concept] = concept
                    label_to_xbrl[label] = concept
                elif concept:
                    concept_to_xbrl[concept] = concept

        # Apply template ordering with concept priority
        for concept_or_label in concepts:
            # Determine if this is a concept or label
            is_concept = concept_or_label in concept_to_xbrl
            is_label = concept_or_label in label_to_xbrl

            # Get the actual XBRL concept and label for this item
            if is_concept:
                xbrl_concept = concept_or_label
                # Try to find the corresponding label
                corresponding_label = None
                for stmt in statements:
                    for item in stmt.get('data', []):
                        if item.get('concept') == concept_or_label:
                            corresponding_label = item.get('label')
                            break
                    if corresponding_label:
                        break
            elif is_label:
                xbrl_concept = label_to_xbrl.get(concept_or_label)
                corresponding_label = concept_or_label
            else:
                # Neither concept nor label found in mappings
                xbrl_concept = None
                corresponding_label = concept_or_label

            # Try concept-based matching first, then label-based
            template_pos = self.templates.get_template_position(
                item_concept=xbrl_concept,
                item_label=corresponding_label,
                statement_type=self.statement_type
            )

            if template_pos is not None:
                template_order[concept_or_label] = template_pos

                # IMPORTANT: If we found a template position for a concept,
                # also apply it to the corresponding label (and vice versa)
                # This ensures consistent ordering regardless of whether the 
                # stitcher uses concept or label as the key
                if is_concept and corresponding_label and corresponding_label in concepts:
                    template_order[corresponding_label] = template_pos
                elif is_label and xbrl_concept and xbrl_concept in concepts:
                    template_order[xbrl_concept] = template_pos

        return template_order

    def _apply_reference_ordering(self, concepts: set, statements: List[Dict], 
                                 template_positioned: Dict[str, float]) -> Dict[str, float]:
        """Apply reference statement ordering for remaining concepts"""
        reference_order = self.reference_strategy.establish_reference_order(statements)

        combined_order = template_positioned.copy()

        for concept in concepts:
            if concept not in combined_order and concept in reference_order:
                combined_order[concept] = reference_order[concept]

        return combined_order

    def _apply_semantic_positioning(self, concepts: set, template_positioned: Dict[str, float],
                                   reference_positioned: Dict[str, float]) -> Dict[str, float]:
        """Apply semantic positioning for orphan concepts"""
        final_order = reference_positioned.copy()

        # Position remaining concepts using semantic rules
        for concept in concepts:
            if concept not in final_order:
                semantic_pos = self.semantic_positioning.infer_position(concept, final_order)
                final_order[concept] = semantic_pos

        return final_order

    def _consolidate_section_ordering(self, semantic_positioned: Dict[str, float], 
                                     template_positioned: Dict[str, float],
                                     statements: List[Dict]) -> Dict[str, float]:
        """
        Consolidate ordering to maintain template section groupings.

        This prevents reference ordering from breaking up logical template sections
        like per-share data (EPS + Shares Outstanding).
        """
        # Identify template sections and their concepts
        template_sections = self._identify_template_sections(template_positioned)

        # Separate template-positioned from non-template items
        template_items = {}
        non_template_items = {}

        for concept, position in semantic_positioned.items():
            if concept in template_positioned:
                template_items[concept] = position
            else:
                non_template_items[concept] = position

        # Re-organize to ensure section integrity
        final_ordering = {}

        # Process template sections in order
        for section_name, section_concepts in template_sections.items():
            # Find all template items (concepts and labels) that belong to this section
            section_template_items = []

            for concept in section_concepts:
                if concept in template_items:
                    section_template_items.append(concept)

            # Also find labels that correspond to concepts in this section
            # by checking if any template_items have the same template position
            section_template_positions = set()
            for concept in section_concepts:
                if concept in template_positioned:
                    section_template_positions.add(template_positioned[concept])

            # Find labels that have the same template positions as section concepts
            for item, pos in template_items.items():
                if pos in section_template_positions and item not in section_template_items:
                    section_template_items.append(item)

            if section_template_items:
                # Use the template base position for this section to ensure strong grouping
                section_base_pos = self._get_section_base_position(section_name)

                # For critical sections like per_share, use an even stronger override
                if section_name == "per_share":
                    # Force per-share items to be at the very end, regardless of hierarchy
                    section_base_pos = 950.0

                # Ensure all items in this section stay grouped together
                for i, item in enumerate(sorted(section_template_items, 
                                               key=lambda x: template_items.get(x, 999.0))):
                    final_ordering[item] = section_base_pos + i * 0.1

        # Add non-template items, adjusting positions to avoid breaking template sections
        section_ranges = self._get_section_ranges(final_ordering, template_sections)

        for concept, position in non_template_items.items():
            # Find appropriate insertion point that doesn't break template sections
            adjusted_position = self._find_insertion_point(position, section_ranges)
            final_ordering[concept] = adjusted_position

        return final_ordering

    def _get_section_base_position(self, section_name: str) -> float:
        """Get the base position for a template section"""
        if self.statement_type == "IncomeStatement":
            template = self.templates.INCOME_STATEMENT_TEMPLATE
        elif self.statement_type == "BalanceSheet":
            template = self.templates.BALANCE_SHEET_TEMPLATE
        else:
            return 999.0

        for base_pos, name, _concepts in template:
            if name == section_name:
                return float(base_pos)

        return 999.0

    def _identify_template_sections(self, template_positioned: Dict[str, float]) -> Dict[str, List[str]]:
        """Identify which concepts belong to which template sections"""
        sections = {}

        # Get the template for this statement type
        if self.statement_type == "IncomeStatement":
            template = self.templates.INCOME_STATEMENT_TEMPLATE
        elif self.statement_type == "BalanceSheet":
            template = self.templates.BALANCE_SHEET_TEMPLATE
        else:
            return {}

        # Build mapping of concepts to sections
        for _base_pos, section_name, template_concepts in template:
            section_concepts = []

            for concept in template_positioned.keys():
                # Check if this concept matches any template concept in this section
                for template_concept in template_concepts:
                    if self._concept_matches_template(concept, template_concept):
                        section_concepts.append(concept)
                        break

            if section_concepts:
                sections[section_name] = section_concepts

        return sections

    def _concept_matches_template(self, concept: str, template_concept: str) -> bool:
        """Check if a concept matches a template concept"""
        # For XBRL concepts, do direct comparison
        if ':' in template_concept or '_gaap_' in template_concept.lower():
            return self._normalize_xbrl_concept(concept) == self._normalize_xbrl_concept(template_concept)

        # For labels, use fuzzy matching
        return self._labels_match(concept, template_concept)

    def _get_section_ranges(self, final_ordering: Dict[str, float], 
                           template_sections: Dict[str, List[str]]) -> List[Tuple[float, float, str]]:
        """Get the position ranges occupied by each template section"""
        ranges = []

        for section_name, concepts in template_sections.items():
            section_positions = [final_ordering[c] for c in concepts if c in final_ordering]

            if section_positions:
                min_pos = min(section_positions)
                max_pos = max(section_positions)
                ranges.append((min_pos, max_pos, section_name))

        return sorted(ranges)

    def _find_insertion_point(self, desired_position: float, 
                             section_ranges: List[Tuple[float, float, str]]) -> float:
        """Find appropriate insertion point that doesn't break template sections"""

        # Check if desired position conflicts with any template section
        for min_pos, max_pos, section_name in section_ranges:
            if min_pos <= desired_position <= max_pos:
                # Position conflicts with a template section
                # Place it just before the section (unless it should logically be after)

                # Special handling for per-share section
                if section_name == "per_share" and desired_position < min_pos:
                    # Items that should come before per-share data
                    return min_pos - 1.0
                else:
                    # Place after the section
                    return max_pos + 1.0

        # No conflicts, use desired position
        return desired_position

    def _normalize_xbrl_concept(self, concept: str) -> str:
        """Delegate to templates class for concept normalization"""
        return self.templates._normalize_xbrl_concept(concept)

    def _labels_match(self, label1: str, label2: str) -> bool:
        """Delegate to templates class for label matching"""
        return self.templates._labels_match(label1, label2)
