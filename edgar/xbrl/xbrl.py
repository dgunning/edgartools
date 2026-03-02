"""
XBRL Parser - Top-level integration module for XBRL parsing.

This module provides the XBRL class, which integrates all components of the XBRL parsing system:
- Instance Document Parser
- Presentation Linkbase Parser
- Calculation Linkbase Parser
- Definition Linkbase Parser

The XBRL class provides a unified interface for working with XBRL data,
organizing facts according to presentation hierarchies, validating calculations,
and handling dimensional qualifiers.
"""
import datetime
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

if TYPE_CHECKING:
    from edgar.xbrl.facts import FactQuery
    from edgar.xbrl.models import Fact, Footnote

import pandas as pd
from rich import box
from rich.table import Column, Table
from rich.table import Table as RichTable

from edgar.attachments import Attachments
from edgar.config import VERBOSE_EXCEPTIONS
from edgar.core import log
from edgar.richtools import repr_rich
from edgar.xbrl.core import STANDARD_LABEL
from edgar.xbrl.models import PresentationNode
from edgar.xbrl.parsers import XBRLParser
from edgar.xbrl.period_selector import select_periods
from edgar.xbrl.periods import get_period_views
from edgar.xbrl.rendering import RenderedStatement, generate_rich_representation, render_statement
from edgar.xbrl.statement_resolver import StatementResolver
from edgar.xbrl.statements import statement_to_concepts


class XBRLFilingWithNoXbrlData(Exception):
    """Exception raised when a filing does not contain XBRL data."""

    def __init__(self, message: str):
        super().__init__(message)


class XBRLAttachments:
    """
    An adapter for the Attachments class that provides easy access to the XBRL documents.
    """

    def __init__(self, attachments: Attachments):
        self._documents = dict()
        if attachments.data_files:
            for attachment in attachments.data_files:
                if attachment.document_type in ["XML", 'EX-101.INS'] and attachment.extension.endswith(
                        ('.xml', '.XML')):
                    content = attachment.content
                    if content and '<xbrl' in content[:2000]:
                        self._documents['instance'] = attachment
                elif attachment.document_type == 'EX-101.SCH':
                    self._documents['schema'] = attachment
                elif attachment.document_type == 'EX-101.DEF':
                    self._documents['definition'] = attachment
                elif attachment.document_type == 'EX-101.CAL':
                    self._documents['calculation'] = attachment
                elif attachment.document_type == 'EX-101.LAB':
                    self._documents['label'] = attachment
                elif attachment.document_type == 'EX-101.PRE':
                    self._documents['presentation'] = attachment

    @property
    def empty(self):
        return not self._documents

    @property
    def has_instance_document(self):
        return 'instance' in self._documents

    @property
    def instance_only(self):
        return len(self._documents) == 1 and 'instance' in self._documents

    def get(self, doc_type: str):
        return self._documents.get(doc_type)

    def __rich__(self):
        table = Table(Column("Type"),
                      Column("Document"),
                      title="XBRL Documents",
                      box=box.SIMPLE)
        for doc_type, attachment in self._documents.items():
            table.add_row(doc_type, attachment.description)
        return table

    def __repr__(self):
        return repr_rich(self)


class XBRL:
    """
    Integrated XBRL parser that combines all linkbase parsers.

    This is the top-level object that integrates all components of the XBRL parsing system,
    providing access to facts organized according to presentation hierarchies and
    allowing for dimensional analysis and calculation validation.
    """

    def __init__(self):
        # Use the parser component
        self.parser = XBRLParser()

        # Statement resolver for matching statements
        self._statement_resolver = None

        # Cached indices for fast statement lookup (for backward compatibility)
        self._statement_indices = {}
        self._statement_by_standard_name = {}
        self._statement_by_primary_concept = {}
        self._statement_by_role_uri = {}
        self._statement_by_role_name = {}
        self._all_statements_cached = None

        # SGML period_of_report for date discrepancy detection
        self._sgml_period_of_report: Optional[str] = None
        self._validated_period_of_report_cache: Optional[str] = None
        self._period_of_report_warning_logged: bool = False

        # Standardization cache for this XBRL instance (lazy-initialized)
        self._standardization_cache = None

        # Reverse index: element_name -> list of context_ids with facts (lazy-initialized)
        self._element_context_index = None

    def _is_dimension_display_statement(self, statement_type: str, role_definition: str) -> bool:
        """
        Determine if a statement should display dimensioned line items.
        Args:
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
            role_definition: The definition of the statement role
        Returns:
            bool: True if dimensions should be displayed, False otherwise
        """
        # Look for keywords in role definition that suggest dimensional breakdowns
        dimension_keywords = [
            'segment', 'geography', 'geographic', 'region', 'product', 'business',
            'by country', 'by region', 'by product', 'by segment', 'revenues by'
        ]

        role_def_lower = role_definition.lower() if role_definition else ""

        # For core financial statements, check if they contain segment information
        if statement_type in ['BalanceSheet', 'IncomeStatement', 'CashFlowStatement',
                              'StatementOfEquity', 'ComprehensiveIncome']:

            # Allow dimensional display if the role definition suggests segment/product breakdown
            if any(keyword in role_def_lower for keyword in dimension_keywords):
                return True

            # For income statements specifically, check if there are segment-related dimensional facts
            if statement_type == 'IncomeStatement':
                # Check if there are facts with ProductOrServiceAxis dimensions
                try:
                    # Look for revenue facts with ProductOrServiceAxis dimensions
                    revenue_concepts = [
                        'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
                        'us-gaap:Revenues',
                        'us-gaap:SalesRevenueNet'
                    ]

                    for _fact_key, fact in self.parser.facts.items():
                        # Check if this is a revenue-related concept
                        concept_name = fact.element_id if hasattr(fact, 'element_id') else getattr(fact, 'concept',
                                                                                                   str(fact))
                        if any(revenue_concept in concept_name for revenue_concept in revenue_concepts):

                            # Check if this fact has ProductOrServiceAxis dimension
                            context = self.parser.contexts.get(fact.context_ref)
                            if context and hasattr(context, 'dimensions') and context.dimensions:
                                for dim_name, _dim_value in context.dimensions.items():
                                    if 'ProductOrServiceAxis' in dim_name:
                                        return True

                    return False
                except Exception:
                    # If any error occurs, default to False
                    return False

            # For other core statements, skip dimensional display by default
            return False

        # For non-core statements, check if they contain dimensional breakdowns
        return any(keyword in role_def_lower for keyword in dimension_keywords)

    @property
    def element_catalog(self):
        return self.parser.element_catalog

    @property
    def contexts(self):
        return self.parser.contexts

    @property
    def footnotes(self):
        """Access to XBRL footnotes."""
        return self.parser.footnotes

    @property
    def standardization(self):
        """
        Access the standardization cache for this XBRL instance.

        The cache provides efficient label standardization by:
        - Caching concept-to-label mappings
        - Caching standardized statement data
        - Using the module-level singleton mapper

        Example:
            >>> xbrl = filing.xbrl()
            >>> # Get standardized label for a concept
            >>> label = xbrl.standardization.get_standard_label(
            ...     'us-gaap_Revenue', 'Revenues',
            ...     {'statement_type': 'IncomeStatement'}
            ... )
            >>> # Standardize statement data with caching
            >>> data = xbrl.standardization.standardize_statement_data(
            ...     raw_data, 'IncomeStatement'
            ... )

        Returns:
            StandardizationCache instance for this XBRL
        """
        if self._standardization_cache is None:
            from edgar.xbrl.standardization import StandardizationCache
            self._standardization_cache = StandardizationCache(self)
        return self._standardization_cache

    @property
    def _facts(self):
        return self.parser.facts

    @property
    def units(self):
        return self.parser.units

    @property
    def presentation_roles(self):
        return self.parser.presentation_roles

    @property
    def presentation_trees(self):
        return self.parser.presentation_trees

    @property
    def calculation_roles(self):
        return self.parser.calculation_roles

    @property
    def calculation_trees(self):
        return self.parser.calculation_trees

    @property
    def definition_roles(self):
        return self.parser.definition_roles

    @property
    def tables(self):
        return self.parser.tables

    @property
    def axes(self):
        return self.parser.axes

    @property
    def domains(self):
        return self.parser.domains

    @property
    def entity_info(self):
        return self.parser.entity_info

    @property
    def reporting_periods(self):
        return self.parser.reporting_periods

    @property
    def period_of_report(self) -> Optional[str]:
        """Get the document period end date, with discrepancy detection."""
        return self._get_validated_period_of_report()

    def _get_xbrl_period_of_report(self) -> Optional[str]:
        """Get the raw XBRL document_period_end_date without validation."""
        if 'document_period_end_date' in self.entity_info:
            period = self.entity_info['document_period_end_date']
            return period.strftime('%Y-%m-%d') if isinstance(period, datetime.date) else period
        return None

    def _get_validated_period_of_report(self) -> Optional[str]:
        """
        Get period_of_report with discrepancy detection and correction.

        When XBRL and SGML header dates differ, uses heuristics to choose
        the correct date by examining which year has actual annual data.
        Results are cached to avoid repeated computation and warning spam.
        """
        # Return cached result if available
        if self._validated_period_of_report_cache is not None:
            return self._validated_period_of_report_cache

        xbrl_date = self._get_xbrl_period_of_report()
        sgml_date = self._sgml_period_of_report

        # If no SGML date or dates match, return XBRL date
        if not sgml_date or xbrl_date == sgml_date:
            self._validated_period_of_report_cache = xbrl_date
            return xbrl_date

        # Dates differ - apply heuristics
        log.debug(f"Date discrepancy: XBRL={xbrl_date}, SGML={sgml_date}")

        # Find annual periods in actual data
        annual_periods = self._find_annual_periods()

        if not annual_periods:
            # No annual periods found, fall back to XBRL date
            self._validated_period_of_report_cache = xbrl_date
            return xbrl_date

        # Extract years from both dates
        xbrl_year = int(xbrl_date[:4]) if xbrl_date else None
        sgml_year = int(sgml_date[:4]) if sgml_date else None

        # Check if any annual period ends in the SGML year
        sgml_year_has_annual = False

        for period in annual_periods:
            end_date = period.get('end_date', '')
            if end_date:
                period_year = int(end_date[:4])
                if period_year == sgml_year:
                    sgml_year_has_annual = True
                    break

        # Decision logic:
        # The SGML header is authoritative. If SGML year has annual data present,
        # prefer SGML date over potentially incorrect XBRL DocumentPeriodEndDate.
        if sgml_year_has_annual:
            if not self._period_of_report_warning_logged:
                log.warning(
                    f"Correcting document_period_end_date: XBRL has {xbrl_date}, "
                    f"but SGML header indicates {sgml_date} and data contains {sgml_year} annual period. "
                    f"Using SGML date: {sgml_date}"
                )
                self._period_of_report_warning_logged = True
            self._validated_period_of_report_cache = sgml_date
            return sgml_date

        # Fall back to XBRL date
        self._validated_period_of_report_cache = xbrl_date
        return xbrl_date

    def _find_annual_periods(self) -> List[Dict]:
        """
        Find periods that are 300-370 days (annual periods).

        Returns:
            List of period dicts with annual duration
        """
        annual = []
        for period in self.reporting_periods:
            period_key = period.get('key', '')
            if 'duration' in period_key:
                start = period.get('start_date')
                end = period.get('end_date')
                if start and end:
                    try:
                        start_dt = datetime.datetime.strptime(start, '%Y-%m-%d')
                        end_dt = datetime.datetime.strptime(end, '%Y-%m-%d')
                        days = (end_dt - start_dt).days
                        if 300 <= days <= 370:
                            annual.append(period)
                    except (ValueError, TypeError):
                        pass
        return annual

    @property
    def entity_name(self):
        return self.entity_info.get('entity_name')

    @property
    def document_type(self):
        return self.entity_info.get('document_type')

    @property
    def context_period_map(self):
        return self.parser.context_period_map

    @property
    def element_context_index(self) -> Dict[str, List[str]]:
        """Reverse index: element_name -> list of context_ids with facts.

        Built lazily on first access by scanning all parsed facts.
        Used by _find_facts_for_element() to avoid iterating all contexts.
        """
        if self._element_context_index is None:
            index: Dict[str, List[str]] = {}
            for fact in self.parser.facts.values():
                elem = fact.element_id.replace(':', '_')
                if elem not in index:
                    index[elem] = []
                index[elem].append(fact.context_ref)
            self._element_context_index = index
        return self._element_context_index

    @classmethod
    def from_directory(cls, directory_path: Union[str, Path]) -> 'XBRL':
        """
        Parse all XBRL files in a directory.
        Args:
            directory_path: Path to directory containing XBRL files
        Returns:
            XBRL object with parsed data
        """
        xbrl = cls()
        xbrl.parser.parse_directory(directory_path)

        # Try to create legacy instance as well for compatibility
        directory = Path(directory_path)
        for file_path in directory.glob("*"):
            if file_path.is_file() and file_path.name.lower().endswith('.xml') and '<xbrl' in file_path.read_text()[
                :2000]:
                break

        return xbrl

    @classmethod
    def from_files(cls, instance_file: Optional[Union[str, Path]] = None,
                   schema_file: Optional[Union[str, Path]] = None,
                   presentation_file: Optional[Union[str, Path]] = None,
                   calculation_file: Optional[Union[str, Path]] = None,
                   definition_file: Optional[Union[str, Path]] = None,
                   label_file: Optional[Union[str, Path]] = None) -> 'XBRL':
        """
        Create an XBRL object from individual files.
        Args:
            instance_file: Path to instance document file
            schema_file: Path to schema file
            presentation_file: Path to presentation linkbase file
            calculation_file: Path to calculation linkbase file
            definition_file: Path to definition linkbase file
            label_file: Path to label linkbase file

        Returns:
            XBRL object with parsed data
        """
        xbrl = cls()

        # Parse schema first
        if schema_file:
            xbrl.parser.parse_schema(schema_file)

        # Parse linkbase files
        if label_file:
            xbrl.parser.parse_labels(label_file)

        if presentation_file:
            xbrl.parser.parse_presentation(presentation_file)

        if calculation_file:
            xbrl.parser.parse_calculation(calculation_file)

        if definition_file:
            xbrl.parser.parse_definition(definition_file)

        # Parse instance last
        if instance_file:
            xbrl.parser.parse_instance(instance_file)

        return xbrl

    @classmethod
    def from_filing(cls, filing) -> Optional['XBRL']:
        """
        Create an XBRL object from a Filing object.

        Args:
            filing: Filing object with attachments containing XBRL files

        Returns:
            XBRL object with parsed data
        """
        if filing.form.endswith("/A"):
            log.warning(dedent(f"""
            {filing}
            is an amended filing and may not contain full XBRL data e.g. some statements might be missing.
            Consider using the original filing instead if available with `get_filings(form="10-K", amendments=False)`
            """))

        xbrl = cls()

        xbrl_attachments = XBRLAttachments(filing.attachments)

        if xbrl_attachments.empty:
            log.warning(f"No XBRL attachments found in filing {filing}")
            return None

        if xbrl_attachments.get('schema'):
            xbrl.parser.parse_schema_content(xbrl_attachments.get('schema').content)

        if xbrl_attachments.get('label'):
            xbrl.parser.parse_labels_content(xbrl_attachments.get('label').content)

        if xbrl_attachments.get('presentation'):
            xbrl.parser.parse_presentation_content(xbrl_attachments.get('presentation').content)

        if xbrl_attachments.get('calculation'):
            xbrl.parser.parse_calculation_content(xbrl_attachments.get('calculation').content)

        if xbrl_attachments.get('definition'):
            xbrl.parser.parse_definition_content(xbrl_attachments.get('definition').content)

        if xbrl_attachments.get('instance'):
            xbrl.parser.parse_instance_content(xbrl_attachments.get('instance').content)

        # Capture SGML period_of_report for date discrepancy detection
        try:
            xbrl._sgml_period_of_report = filing.period_of_report
        except Exception:
            pass

        return xbrl

    @property
    def statements(self):
        from edgar.xbrl.statements import Statements
        return Statements(self)

    @property
    def fund_statements(self):
        """
        Access fund-specific statements (Schedule of Investments, Financial Highlights).

        This property provides specialized access to financial statements that are
        specific to investment companies (BDCs, closed-end funds, interval funds, etc.).

        Returns:
            FundStatements: Interface for fund statement access

        Example:
            >>> xbrl = filing.xbrl()
            >>> if xbrl.fund_statements.is_fund_filing():
            ...     soi = xbrl.fund_statements.schedule_of_investments()
            ...     if soi:
            ...         print(soi)
        """
        from edgar.xbrl.fund_statements import FundStatements
        if not hasattr(self, '_fund_statements'):
            self._fund_statements = FundStatements(self)
        return self._fund_statements

    def notes(self) -> List:
        """
        Get all note sections from the XBRL filing.

        Returns:
            List of Statement objects for notes

        Example:
            >>> xbrl = filing.xbrl()
            >>> for note in xbrl.notes():
            ...     print(note.title)
        """
        return self.statements.notes()

    def disclosures(self) -> List:
        """
        Get all disclosure sections from the XBRL filing.

        Returns:
            List of Statement objects for disclosures

        Example:
            >>> xbrl = filing.xbrl()
            >>> for disc in xbrl.disclosures():
            ...     print(disc.title)
        """
        return self.statements.disclosures()

    def list_tables(self) -> Dict[str, List]:
        """
        List all tables in the XBRL filing, organized by category.

        Returns a dict with keys: 'statement', 'note', 'disclosure', 'document', 'other'.
        Each value is a list of statement dicts with 'index', 'definition', 'role_name', etc.

        Example:
            >>> xbrl = filing.xbrl()
            >>> tables = xbrl.list_tables()
            >>> for note in tables['note']:
            ...     print(note['definition'])
        """
        return self.statements.get_statements_by_category()

    def get_table(self, name: str) -> Optional[Any]:
        """
        Get a table (statement, note, or disclosure) by name with smart resolution.

        Searches in order: exact type match, role_name contains, definition contains.
        Works for any table in the filing — financial statements, notes, or disclosures.

        Args:
            name: Table name to search for (e.g. 'IncomeStatement', 'debt', 'revenue recognition')

        Returns:
            Statement if found, None otherwise

        Example:
            >>> xbrl = filing.xbrl()
            >>> debt_note = xbrl.get_table("debt")
            >>> revenue = xbrl.get_table("revenue recognition")
        """
        return self.statements.get(name)

    def get_disclosure(self, role_uri: str) -> Optional[Any]:
        """
        Get a disclosure or note by its exact role URI.

        For advanced users who know the specific XBRL role URI.

        Args:
            role_uri: Full role URI (e.g. 'http://company.com/role/DebtDisclosure')

        Returns:
            Statement if the role exists, None otherwise

        Example:
            >>> xbrl = filing.xbrl()
            >>> tables = xbrl.list_tables()
            >>> role = tables['disclosure'][0]['role']
            >>> stmt = xbrl.get_disclosure(role)
        """
        from edgar.xbrl.statements import Statement
        if role_uri in self.presentation_trees:
            return Statement(self, role_uri)
        return None

    @property
    def facts(self):
        from edgar.xbrl.facts import FactsView
        if not hasattr(self, '_facts_view'):
            self._facts_view = FactsView(self)
        return self._facts_view

    @property
    def current_period(self):
        """
        Convenient access to current period financial data.

        Provides simplified access to the most recent period's financial data
        without comparative information. This addresses common use cases where
        users only need the current period data.

        Returns:
            CurrentPeriodView: Interface for accessing current period data

        Example:
            >>> xbrl = filing.xbrl()
            >>> current = xbrl.current_period
            >>> balance_sheet = current.balance_sheet()
            >>> income = current.income_statement(raw_concepts=True)
        """
        from edgar.xbrl.current_period import CurrentPeriodView
        if not hasattr(self, '_current_period_view'):
            self._current_period_view = CurrentPeriodView(self)
        return self._current_period_view

    def query(self,
              include_dimensions: bool = False,
              include_contexts: bool = False,
              include_element_info: bool = False) -> 'FactQuery':
        """
        Start a new query for XBRL facts.
        """
        fact_query = self.facts.query()
        # Explicitly set the include_dimensions flag based on the parameter
        fact_query._include_dimensions = include_dimensions
        if not include_contexts:
            fact_query = fact_query.exclude_contexts()
        if not include_element_info:
            fact_query = fact_query.exclude_element_info()
        return fact_query

    def get_all_statements(self) -> List[Dict[str, Any]]:
        """
        Get all available financial statements.

        Returns:
            List of statement metadata (role, definition, element count)
        """
        # Return cached result if available
        if self._all_statements_cached is not None:
            return self._all_statements_cached

        statements = []

        # Reset indices
        self._statement_indices = {}
        self._statement_by_standard_name = {}
        self._statement_by_primary_concept = {}
        self._statement_by_role_uri = {}
        self._statement_by_role_name = {}

        for role, tree in self.presentation_trees.items():
            # Check if this role appears to be a financial statement
            role_def = tree.definition.lower()
            statement_type = None
            primary_concept = next(iter(tree.all_nodes))
            statement_category = None

            # First try to match using statement_to_concepts (for backward compatibility)
            for statement_alias, statement_info in statement_to_concepts.items():
                if primary_concept == statement_info.concept:
                    if 'parenthetical' in role_def:
                        statement_type = f"{statement_alias}Parenthetical"
                    else:
                        statement_type = statement_alias
                    if 'BalanceSheet' not in statement_type:
                        break

            # If we didn't find a match, try additional patterns for notes and disclosures
            if not statement_type:
                if 'us-gaap_NotesToFinancialStatementsAbstract' in primary_concept or 'note' in role_def:
                    statement_type = "Notes"
                    statement_category = "note"
                elif 'us-gaap_DisclosuresAbstract' in primary_concept or 'disclosure' in role_def:
                    statement_type = "Disclosures"
                    statement_category = "disclosure"
                elif 'us-gaap_AccountingPoliciesAbstract' in primary_concept or 'accounting policies' in role_def:
                    statement_type = "AccountingPolicies"
                    statement_category = "note"
                elif 'us-gaap_SegmentDisclosureAbstract' in primary_concept or 'segment' in role_def:
                    statement_type = "SegmentDisclosure"
                    statement_category = "disclosure"
            # Try to extract role name from URI
            role_name = role.split('/')[-1] if '/' in role else role.split('#')[-1] if '#' in role else ''

            # Create the statement metadata
            statement = {
                'role': role,
                'definition': tree.definition,
                'element_count': len(tree.all_nodes),
                'type': statement_type,
                'primary_concept': primary_concept,
                'role_name': role_name,
                'category': statement_category  # This will be None for backward compatibility unless set above
            }

            statements.append(statement)

            # Build lookup indices
            # By role URI
            self._statement_by_role_uri[role] = statement

            # By role name (short name)
            if role_name:
                role_name_lower = role_name.lower()
                if role_name_lower not in self._statement_by_role_name:
                    self._statement_by_role_name[role_name_lower] = []
                self._statement_by_role_name[role_name_lower].append(statement)

            # By standard name
            if statement_type:
                if statement_type not in self._statement_by_standard_name:
                    self._statement_by_standard_name[statement_type] = []
                self._statement_by_standard_name[statement_type].append(statement)

            # By primary concept
            if primary_concept:
                if primary_concept not in self._statement_by_primary_concept:
                    self._statement_by_primary_concept[primary_concept] = []
                self._statement_by_primary_concept[primary_concept].append(statement)

            # Also index by definition (without spaces, lowercase)
            if statement['definition']:
                def_key = statement['definition'].lower().replace(' ', '')
                if def_key not in self._statement_indices:
                    self._statement_indices[def_key] = []
                self._statement_indices[def_key].append(statement)

        # Cache the result
        self._all_statements_cached = statements
        return statements

    def get_statement_by_type(self, statement_type: str, include_dimensions: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get the first statement matching the given type.

        Args:
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', 'Notes', etc.)
            include_dimensions: Whether to include dimensional segment data (default: False)

        Returns:
            Statement data if found, None otherwise
        """
        # Use find_statement instead of the flawed index-based lookup
        matching_statements, found_role, actual_statement_type = self.find_statement(statement_type)

        if not found_role or not matching_statements:
            return None

        # Get statement data using the found role
        statement_data = self.get_statement(found_role, should_display_dimensions=include_dimensions)

        if statement_data:
            # Extract periods from the statement data
            periods = {}
            for item in statement_data:
                for period_id, _value in item.get('values', {}).items():
                    if period_id not in periods:
                        # Get period label from reporting_periods
                        period_label = period_id
                        for period in self.reporting_periods:
                            if period['key'] == period_id:
                                period_label = period['label']
                                break
                        periods[period_id] = {'label': period_label}

            return {
                'role': found_role,
                'definition': matching_statements[0]['definition'],
                'statement_type': actual_statement_type,
                'periods': periods,
                'data': statement_data
            }

        return None

    @classmethod
    def stitch_statements(cls, xbrl_list: List['XBRL'],
                          statement_type: str = 'IncomeStatement',
                          period_type: str = 'RECENT_PERIODS',
                          max_periods: int = 3,
                          standard: bool = True) -> Dict[str, Any]:
        """
        Stitch together statements from multiple XBRL objects.

        Args:
            xbrl_list: List of XBRL objects, should be from the same company and ordered by date
            statement_type: Type of statement to stitch ('IncomeStatement', 'BalanceSheet', etc.)
            period_type: Type of period view to generate
            max_periods: Maximum number of periods to include (default: 3)
            standard: Whether to use standardized concept labels (default: True)

        Returns:
            Stitched statement data
        """
        from edgar.xbrl.stitching import stitch_statements as _stitch_statements
        return _stitch_statements(xbrl_list, statement_type, period_type, max_periods, standard)

    def render_stitched_statement(self, stitched_data: Dict[str, Any],
                                  statement_title: str,
                                  statement_type: str) -> 'RichTable':
        """
        Render a stitched statement.

        Args:
            stitched_data: Stitched statement data
            statement_title: Title of the statement
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)

        Returns:
            RichTable: A formatted table representation of the stitched statement
        """
        from edgar.xbrl.stitching import render_stitched_statement as _render_stitched_statement
        return _render_stitched_statement(stitched_data, statement_title, statement_type, self.entity_info)

    def _get_valid_dimensional_members(self, tree) -> Dict[str, Set[str]]:
        """
        Extract valid dimensional members from a presentation tree.

        The presentation linkbase defines which dimensional members should appear
        on a statement. This function builds a mapping from axis to valid members
        by examining the Domain nodes in the tree.

        Pattern in presentation tree:
        - Axis nodes (e.g., PropertyPlantAndEquipmentByTypeAxis) have Domain children
        - Domain nodes (e.g., PropertyPlantAndEquipmentTypeDomain) have Member children
        - The valid members are the children of the Domain nodes

        Args:
            tree: PresentationTree for the statement

        Returns:
            Dict mapping axis names (normalized) to sets of valid member names (normalized)
        """
        valid_members = {}

        for node_id, node in tree.all_nodes.items():
            # Find Domain nodes - they contain valid members as children
            if 'Domain' in node_id and node.children:
                # Find the parent Axis node
                # Domain nodes are children of Axis nodes
                parent_node = tree.all_nodes.get(node.parent)
                if parent_node and 'Axis' in node.parent:
                    # Normalize axis name (remove prefix, use underscore)
                    axis_name = node.parent.replace(':', '_')

                    # Collect all member children (normalized)
                    members = set()
                    for child in node.children:
                        # Normalize member name
                        members.add(child.replace(':', '_'))

                    valid_members[axis_name] = members

        return valid_members

    def get_statement(self, role_or_type: str,
                      period_filter: Optional[str] = None,
                      should_display_dimensions: Optional[bool] = None,
                      view: Optional['StatementView'] = None) -> List[Dict[str, Any]]:
        """
        Get a financial statement by role URI, statement type, or statement short name.

        Args:
            role_or_type: Can be one of:
                - Extended link role URI (e.g. "http://apple.com/role/ConsolidatedStatementOfIncome")
                - Statement type name (e.g. "BalanceSheet")
                - Statement short name (e.g. "ConsolidatedStatementOfIncome")
            period_filter: Optional period key to filter facts
            should_display_dimensions: Whether to display dimensions for this statement.
                If None, the method will determine based on statement type and role.
            view: StatementView controlling dimensional filtering:
                  STANDARD: Strict member filtering per presentation linkbase
                  DETAILED: Relaxed filtering - show all dimensional facts (fixes GH-574)
                  SUMMARY: No dimensional facts shown

        Returns:
            List of line items with values
        """
        from edgar.xbrl.presentation import StatementView
        # Use the centralized statement finder to get statement information
        matching_statements, found_role, actual_statement_type = self.find_statement(role_or_type)

        # If no matching statement found, return empty list
        if not found_role or found_role not in self.presentation_trees:
            return []

        tree = self.presentation_trees[found_role]

        # Find the root element
        root_id = tree.root_element_id

        # If should_display_dimensions wasn't provided, default to True
        # Issue #504: Always include dimensional data by default - users can filter themselves if needed
        if should_display_dimensions is None:
            should_display_dimensions = True

        # Get valid dimensional members from presentation tree
        # This ensures we only show members that are actually defined in the linkbase
        valid_dimensional_members = self._get_valid_dimensional_members(tree) if should_display_dimensions else {}

        # Generate line items recursively
        line_items = []
        self._generate_line_items(root_id, tree.all_nodes, line_items, period_filter, None,
                                  should_display_dimensions, valid_dimensional_members, view)

        # Apply revenue deduplication for income statements to fix Issue #438
        if actual_statement_type == 'IncomeStatement':
            from edgar.xbrl.deduplication_strategy import RevenueDeduplicator
            line_items = RevenueDeduplicator.deduplicate_statement_items(line_items)

        # Issue #575: Reorder items so components appear before their totals
        # This fixes cases where the presentation linkbase has incorrect ordering
        # (e.g., IESC filing puts Cash at the end instead of with Current Assets)
        if actual_statement_type == 'BalanceSheet':
            line_items = self._reorder_by_calculation_parent(line_items)

        # Issue edgartools-os99: Adjust levels when calculation tree reveals flat subtotal patterns
        line_items = self._adjust_levels_by_calculation_parent(line_items)

        return line_items

    def _generate_line_items(self, element_id: str, nodes: Dict[str, PresentationNode],
                             result: List[Dict[str, Any]], period_filter: Optional[str] = None,
                             path: Optional[List[str]] = None, should_display_dimensions: bool = False,
                             valid_dimensional_members: Optional[Dict[str, Set[str]]] = None,
                             view: Optional['StatementView'] = None) -> None:
        """
        Recursively generate line items for a statement.

        Args:
            element_id: Current element ID
            nodes: Dictionary of presentation nodes
            result: List to append line items to
            period_filter: Optional period key to filter facts
            path: Current path in hierarchy
            should_display_dimensions: Whether to display dimensions for this statement
            valid_dimensional_members: Dict mapping axis names to sets of valid member names
                from the presentation linkbase. Only facts with members in this set will be shown.
            view: StatementView controlling dimensional filtering:
                  STANDARD: Strict member filtering per presentation linkbase
                  DETAILED: Relaxed filtering - show all dimensional facts (fixes GH-574)
                  SUMMARY: No dimensional facts shown
        """
        from edgar.xbrl.presentation import StatementView
        if element_id not in nodes:
            return

        # Update path
        if path is None:
            path = []

        current_path = path + [element_id]

        # Get node information
        node = nodes[element_id]

        # Get label
        label = node.display_label

        # Get values and decimals across periods
        values = {}
        decimals = {}  # Store decimals info for each period
        units = {}  # Store unit_ref for each period
        period_types = {}  # Store period_type ('instant' or 'duration') for each period

        # Issue #463: Get balance and weight from element catalog and calculation trees
        # (same approach as FactsView.get_facts())
        balance = None  # Debit/credit classification from XBRL schema
        weight = None   # Calculation weight from calculation linkbase

        # Get balance from element catalog
        element_id_normalized = element_id.replace(':', '_')
        if element_id_normalized in self.element_catalog:
            element = self.element_catalog[element_id_normalized]
            balance = element.balance
            if balance is None:
                # Fallback to static US-GAAP mapping
                from edgar.xbrl.parsers.concepts import get_balance_type
                balance = get_balance_type(element_id)

        # Get weight and calculation parent from calculation trees (Issue #463, #514)
        calculation_parent = None
        if hasattr(self, 'calculation_trees') and self.calculation_trees:
            for calc_tree in self.calculation_trees.values():
                if element_id_normalized in calc_tree.all_nodes:
                    calc_node = calc_tree.all_nodes[element_id_normalized]
                    weight = calc_node.weight
                    calculation_parent = calc_node.parent  # Metric parent (Issue #514 refinement)
                    break  # Use first weight/parent found

        # Calculate preferred_sign from preferred_label (for Issue #463)
        # This determines display transformation: -1 = negate, 1 = as-is, None = not specified
        preferred_sign_value = None
        if node.preferred_label:
            # Check if this is a negatedLabel (indicates value should be negated for display)
            # Use pattern matching to support any XBRL namespace version (2003, 2009, future versions)
            # Matches: 'negatedLabel', 'negatedTerseLabel', 'http://www.xbrl.org/YYYY/role/negated*Label', etc.
            label_lower = node.preferred_label.lower()
            is_negated = 'negated' in label_lower and (
                label_lower.startswith('negated') or  # Short form: 'negatedLabel'
                '/role/negated' in label_lower        # Full URI: 'http://www.xbrl.org/*/role/negated*'
            )
            preferred_sign_value = -1 if is_negated else 1

        # Find facts for any of these concept names
        all_relevant_facts = self._find_facts_for_element(node.element_name, period_filter)

        # Group facts by period for better selection
        facts_by_period = {}

        # Process all found facts and group by period
        for context_id, wrapped_fact in all_relevant_facts.items():
            # Get period key for this context
            period_key = self.context_period_map.get(context_id)
            if not period_key:
                continue  # Skip if no period key found

            # Initialize period entry if not exists
            if period_key not in facts_by_period:
                facts_by_period[period_key] = []

            # Add this fact to the period
            facts_by_period[period_key].append((context_id, wrapped_fact))

        # should_display_dimensions is now passed as a parameter from the calling method

        # Process facts by period, with different handling based on statement type
        from collections import defaultdict
        dimensioned_facts = defaultdict(list)  # For dimensioned statement types

        for period_key, period_facts in facts_by_period.items():
            if should_display_dimensions:
                # For statements that should display dimensions, group facts by dimension
                # Issue #564: Collect non-dimensioned facts separately to select most precise
                non_dimensioned_facts_for_period = []

                for context_id, wrapped_fact in period_facts:
                    fact = wrapped_fact['fact']
                    dimension_info = wrapped_fact['dimension_info']
                    dimension_key = wrapped_fact['dimension_key']

                    if dimension_info:
                        # Check if this dimensional fact has valid members per the presentation linkbase
                        # This filters out facts from other disclosures that happen to use the same concept
                        # but with different dimensional members (e.g., revenue members on balance sheet)
                        is_valid_dimension = True

                        # DETAILED view bypasses strict member filtering (GH-574 fix)
                        # This restores iPhone/iPad/Mac data for companies like AAPL
                        if view == StatementView.DETAILED:
                            # Show all dimensional facts regardless of presentation linkbase
                            is_valid_dimension = True
                        elif valid_dimensional_members:
                            # STANDARD view: strict filtering per presentation linkbase
                            for dim_data in dimension_info:
                                # Get the axis and member from the dimension info
                                axis = dim_data.get('dimension', '').replace(':', '_')
                                member = dim_data.get('member', '').replace(':', '_')

                                # If this axis is defined in the presentation tree,
                                # check if the member is valid
                                if axis in valid_dimensional_members:
                                    if member not in valid_dimensional_members[axis]:
                                        # Member not in presentation tree - skip this fact
                                        is_valid_dimension = False
                                        break

                        if not is_valid_dimension:
                            # Skip this dimensional fact - member not in presentation linkbase
                            continue

                        # Use the dimension_key we already generated
                        dim_key_str = dimension_key

                        # Store dimensioned fact with the full dimension metadata
                        dimensioned_facts[dim_key_str].append((period_key, fact, dimension_info))
                    else:
                        # Collect non-dimensioned facts to select most precise later
                        non_dimensioned_facts_for_period.append((context_id, wrapped_fact))

                # Issue #564: Select the most precise non-dimensioned fact for this period
                # (Multiple contexts may map to same period; select highest precision)
                if non_dimensioned_facts_for_period and not values.get(period_key):
                    if len(non_dimensioned_facts_for_period) == 1:
                        context_id, wrapped_fact = non_dimensioned_facts_for_period[0]
                        fact = wrapped_fact['fact']
                    else:
                        # Multiple non-dimensioned contexts for same period - select by precision
                        best = max(non_dimensioned_facts_for_period,
                                   key=lambda x: self._get_fact_precision(x[1]['fact']))
                        context_id, wrapped_fact = best
                        fact = wrapped_fact['fact']

                    # Store the selected fact's value
                    values[period_key] = fact.numeric_value if fact.numeric_value is not None else fact.value

                    # Store the decimals info for proper scaling
                    if fact.decimals is not None:
                        try:
                            if fact.decimals == 'INF':
                                decimals[period_key] = 0  # Infinite precision, no scaling
                            else:
                                decimals[period_key] = int(fact.decimals)
                        except (ValueError, TypeError):
                            decimals[period_key] = 0  # Default

                    # Store unit_ref for this period
                    units[period_key] = fact.unit_ref

                    # Store period_type from context
                    if context_id in self.contexts:
                        context = self.contexts[context_id]
                        if hasattr(context, 'period') and context.period:
                            pt = context.period.get('type') if isinstance(context.period, dict) else getattr(context.period, 'type', None)
                            period_types[period_key] = pt

            else:
                # For standard financial statements, prefer non-dimensioned facts
                # Issue #564: Select by (1) fewest dimensions, (2) highest precision
                if len(period_facts) == 1:
                    context_id, wrapped_fact = period_facts[0]
                    fact = wrapped_fact['fact']
                else:
                    # Multiple contexts for same period - select best by dimensions and precision
                    # min() with tuple key: (dimension_count ASC, -precision DESC)
                    best = min(period_facts,
                               key=lambda x: (len(x[1]['dimension_info']),
                                              -self._get_fact_precision(x[1]['fact'])))
                    context_id, wrapped_fact = best
                    fact = wrapped_fact['fact']

                # Store the value
                values[period_key] = fact.numeric_value if fact.numeric_value is not None else fact.value

                # Store the decimals info for proper scaling
                if fact.decimals is not None:
                    try:
                        if fact.decimals == 'INF':
                            decimals[period_key] = 0  # Infinite precision, no scaling
                        else:
                            decimals[period_key] = int(fact.decimals)
                    except (ValueError, TypeError):
                        decimals[period_key] = 0  # Default if decimals can't be converted

                # Store unit_ref for this period
                units[period_key] = fact.unit_ref

                # Store period_type from context
                if context_id in self.contexts:
                    context = self.contexts[context_id]
                    if hasattr(context, 'period') and context.period:
                        pt = context.period.get('type') if isinstance(context.period, dict) else getattr(context.period, 'type', None)
                        period_types[period_key] = pt

        # Create preferred_signs dict for all periods (same value for all periods of this concept)
        preferred_signs = {}
        if preferred_sign_value is not None:
            for period_key in values.keys():
                preferred_signs[period_key] = preferred_sign_value

        # For dimensional statements with dimension data, handle the parent item specially
        if should_display_dimensions and dimensioned_facts:
            # Create parent line item with total values AND dimensional children
            # This ensures users see both the total (e.g., Total Revenue = $25,500M)
            # and the dimensional breakdown (e.g., Auto Revenue = $19,878M, Energy = $3,014M)
            line_item = {
                'concept': element_id,
                'name': node.element_name,
                'all_names': [node.element_name],
                'label': label,  # Keep original label, don't add colon
                'values': values,  # Show the total values
                'decimals': decimals,  # Include decimals for formatting
                'units': units,  # Include unit_ref for each period
                'period_types': period_types,  # Include period_type for each period
                'preferred_signs': preferred_signs,  # Include preferred_sign for display (Issue #463)
                'balance': balance,  # Include balance (debit/credit) for display (Issue #463)
                'weight': weight,  # Include calculation weight for metadata (Issue #463)
                'parent': node.parent,  # Presentation tree parent (may be abstract) (Issue #514)
                'calculation_parent': calculation_parent,  # Calculation tree parent (metric) (Issue #514 refinement)
                'level': node.depth,
                'preferred_label': node.preferred_label,
                'is_abstract': node.is_abstract,  # Issue #450: Use node's actual abstract flag
                'children': node.children,
                'has_values': len(values) > 0,  # True if we have total values
                'has_dimension_children': True,  # Mark as having dimension children
                'is_company_preferred_label': node.is_company_preferred_label  # Skip standardization if company-preferred
            }
        else:
            # Non-dimensional case: Create normal line item with values
            line_item = {
                'concept': element_id,
                'name': node.element_name,
                'all_names': [node.element_name],
                'label': label,
                'values': values,
                'decimals': decimals,  # Add decimals info for formatting
                'units': units,  # Include unit_ref for each period
                'period_types': period_types,  # Include period_type for each period
                'preferred_signs': preferred_signs,  # Include preferred_sign for display (Issue #463)
                'balance': balance,  # Include balance (debit/credit) for display (Issue #463)
                'weight': weight,  # Include calculation weight for metadata (Issue #463)
                'parent': node.parent,  # Presentation tree parent (may be abstract) (Issue #514)
                'calculation_parent': calculation_parent,  # Calculation tree parent (metric) (Issue #514 refinement)
                'level': node.depth,
                'preferred_label': node.preferred_label,
                'is_abstract': node.is_abstract,
                'children': node.children,
                'has_values': len(values) > 0,  # Flag to indicate if we found values
                'is_company_preferred_label': node.is_company_preferred_label  # Skip standardization if company-preferred
            }

        # Add to result
        result.append(line_item)

        # For dimensional statements, add dimensioned facts as child line items
        if should_display_dimensions and dimensioned_facts:
            # Add each dimension as a child line item with increased depth
            for dim_key, facts_list in dimensioned_facts.items():
                dim_values = {}
                dim_decimals = {}
                dim_units = {}  # Store unit_ref for each period
                dim_period_types = {}  # Store period_type for each period
                dim_metadata = None  # Store metadata from the first fact

                # Collect values for each period
                for fact_data in facts_list:
                    try:
                        # Unpack with consistent 3-part tuples from our updated code
                        period_key, fact, dimensions_info = fact_data

                        # Store the dimension metadata from the first fact
                        if dim_metadata is None:
                            dim_metadata = dimensions_info

                        # Extract value from fact
                        dim_values[period_key] = fact.numeric_value if fact.numeric_value is not None else fact.value
                    except (ValueError, TypeError, IndexError) as e:
                        # Try to handle older format (period_key, fact) tuple for backward compatibility
                        try:
                            if isinstance(fact_data, tuple) and len(fact_data) == 2:
                                period_key, fact = fact_data
                                dim_values[
                                    period_key] = fact.numeric_value if fact.numeric_value is not None else fact.value
                        except Exception:
                            # Log the error and continue
                            log.warning(f"Error processing dimension fact data: {e}")
                            continue

                    # Store decimals
                    if fact.decimals is not None:
                        try:
                            if fact.decimals == 'INF':
                                dim_decimals[period_key] = 0
                            else:
                                dim_decimals[period_key] = int(fact.decimals)
                        except (ValueError, TypeError):
                            dim_decimals[period_key] = 0

                    # Store unit_ref for this period
                    dim_units[period_key] = fact.unit_ref

                    # Store period_type from context
                    context_id = fact.context_ref
                    if context_id in self.contexts:
                        context = self.contexts[context_id]
                        if hasattr(context, 'period') and context.period:
                            pt = context.period.get('type') if isinstance(context.period, dict) else getattr(context.period, 'type', None)
                            dim_period_types[period_key] = pt

                # For better display, use the member label for dimension items,
                # but make sure we don't add the parent concept name as well

                # Default to the full dimension key (e.g., "Region: Americas")
                display_label = dim_key

                # Try various member label formats based on dimension structure
                if dim_metadata:
                    if len(dim_metadata) == 1:
                        # For single dimensions, just use the member label (e.g., "Americas")
                        display_label = dim_metadata[0]['member_label']
                    else:
                        # For multiple dimensions, create a combined label with all member names
                        # (e.g., "Americas - iPhone")
                        member_labels = [info['member_label'] for info in dim_metadata if 'member_label' in info]
                        if member_labels:
                            display_label = " - ".join(member_labels)

                # Create preferred_signs dict for dimensional line items (same value for all periods)
                dim_preferred_signs = {}
                if preferred_sign_value is not None:
                    for period_key in dim_values.keys():
                        dim_preferred_signs[period_key] = preferred_sign_value

                # Create dimension line item
                dim_line_item = {
                    'concept': element_id,  # Use same concept
                    'name': node.element_name,
                    'all_names': [node.element_name],
                    'label': display_label,  # Use optimized dimension label
                    'full_dimension_label': dim_key,  # Keep full dimension notation for reference
                    'values': dim_values,
                    'decimals': dim_decimals,
                    'units': dim_units,  # Include unit_ref for each period
                    'period_types': dim_period_types,  # Include period_type for each period
                    'preferred_signs': dim_preferred_signs,  # Include preferred_sign for display (Issue #463)
                    'level': node.depth + 1,  # Increase depth by 1
                    'preferred_label': node.preferred_label,
                    'is_abstract': False,
                    'children': [],
                    'has_values': len(dim_values) > 0,
                    'is_dimension': True,  # Mark as a dimension item
                    'dimension_metadata': dim_metadata  # Store full dimension information
                }

                # Add to result
                result.append(dim_line_item)

        # Process children
        for child_id in node.children:
            self._generate_line_items(child_id, nodes, result, period_filter, current_path,
                                      should_display_dimensions, valid_dimensional_members, view)

    @staticmethod
    def _reorder_by_calculation_parent(line_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Reorder line items so that components appear before their totals.

        Issue #575: Some filings (e.g., IESC) have presentation linkbase orders that
        put components after their totals (e.g., Cash at the end instead of with
        Current Assets). This method uses the calculation_parent relationship to
        move misplaced items to appear just before their calculation parent.

        Args:
            line_items: List of line items from the presentation tree

        Returns:
            Reordered list with components before their totals
        """
        if not line_items:
            return line_items

        # Build a concept -> index map
        concept_to_index = {item['concept']: i for i, item in enumerate(line_items)}

        # Find items that need to be moved (appear after their calculation parent)
        items_to_move = []
        for i, item in enumerate(line_items):
            calc_parent = item.get('calculation_parent')
            if calc_parent and calc_parent in concept_to_index:
                parent_index = concept_to_index[calc_parent]
                if i > parent_index:
                    # This item appears after its parent - needs to be moved
                    items_to_move.append((i, item, calc_parent))

        if not items_to_move:
            return line_items

        # Remove items that need to be moved (in reverse order to preserve indices)
        result = list(line_items)
        for i, item, _ in sorted(items_to_move, key=lambda x: x[0], reverse=True):
            result.pop(i)

        # Re-insert items before their calculation parent
        # Process in order of where they should be inserted
        for _, item, calc_parent in sorted(items_to_move, key=lambda x: concept_to_index.get(x[2], 0)):
            # Find current index of the calculation parent in the result
            parent_index = None
            for j, r_item in enumerate(result):
                if r_item['concept'] == calc_parent:
                    parent_index = j
                    break

            if parent_index is not None:
                # Insert before the parent
                result.insert(parent_index, item)
            else:
                # Parent not found (shouldn't happen), append at end
                result.append(item)

        return result

    @staticmethod
    def _adjust_levels_by_calculation_parent(line_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Adjust levels so children indent under their calculation parent totals.

        When the presentation tree puts components at the same level as their
        subtotal, use the calculation tree to indent the components.
        Only fires when all 4 conditions are met (very conservative).
        """
        if not line_items:
            return line_items

        from edgar.xbrl.models import TOTAL_LABEL

        # Build concept -> index map
        concept_to_index = {item['concept']: i for i, item in enumerate(line_items)}

        for item in line_items:
            calc_parent = item.get('calculation_parent')
            if not calc_parent or calc_parent not in concept_to_index:
                continue

            parent_idx = concept_to_index[calc_parent]
            item_idx = concept_to_index[item['concept']]
            parent_item = line_items[parent_idx]

            # All 4 conditions must be true
            if (parent_idx > item_idx                                    # parent appears after (subtotal pattern)
                    and parent_item['level'] == item['level']            # same level
                    and parent_item.get('preferred_label') == TOTAL_LABEL):  # parent has total label
                item['level'] += 1

        return line_items

    @staticmethod
    def _get_fact_precision(fact) -> int:
        """
        Get a numeric precision value for a fact based on its decimals attribute.

        Higher return value = more precise:
        - INF (infinite precision) returns 1_000_000
        - Numeric decimals return their value (e.g., -6 for millions, 2 for hundredths)
        - None or invalid returns 0 (default/unknown precision)

        Args:
            fact: An XBRL Fact object with a decimals attribute

        Returns:
            Integer precision value for comparison (higher = more precise)
        """
        if fact.decimals == 'INF':
            return 1_000_000  # Infinite precision = highest
        elif fact.decimals is not None:
            try:
                return int(fact.decimals)
            except (ValueError, TypeError):
                return 0
        return 0  # Default/unknown precision

    @staticmethod
    def _select_most_precise_fact(facts: list):
        """
        Select the most precise fact from a list of facts.

        When multiple facts exist for the same concept/context with different
        precision (decimals attribute), this selects the one with highest precision.
        This is critical for maintaining data accuracy (Issue #564).

        Args:
            facts: List of Fact objects to choose from

        Returns:
            The fact with highest precision, or None if list is empty
        """
        if not facts:
            return None
        if len(facts) == 1:
            return facts[0]

        best_fact = None
        best_precision = None

        for fact in facts:
            precision = XBRL._get_fact_precision(fact)
            if best_precision is None or precision > best_precision:
                best_precision = precision
                best_fact = fact

        return best_fact

    def _find_facts_for_element(self, element_name: str, period_filter: Optional[str] = None,
                                dimensions: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Find facts for a specific element, optionally filtered by period and dimensions.
        Args:
            element_name: Element name to find facts for
            period_filter: Optional period key to filter contexts
            dimensions: Optional dictionary of dimension names to dimension values to filter by
        Returns:
            Dictionary of facts by context ID with dimension information attached
        """
        if not element_name:
            return {}  # No element name provided

        relevant_facts = {}

        # Use reverse index to only check contexts that actually have facts for this element
        context_ids = self.element_context_index.get(element_name, [])
        for context_id in context_ids:
            # Issue #564: Get ALL facts for this element/context and select the most precise
            facts_list = self.parser.get_facts_by_key(element_name, context_id)
            fact = self._select_most_precise_fact(facts_list)

            if fact:
                # If period filter is specified, check if context matches period
                if period_filter:
                    period_key = self.context_period_map.get(context_id)
                    if period_key != period_filter:
                        continue  # Skip if period doesn't match

                # If dimensions are specified, check if context has matching dimensions
                if dimensions:
                    context = self.contexts.get(context_id)
                    if not context or not hasattr(context, 'dimensions'):
                        continue  # Skip if context doesn't have dimensions

                    # Check if all specified dimensions match
                    matches_all_dimensions = True
                    for dim_name, dim_value in dimensions.items():
                        # Normalize dimension name if it contains a colon
                        normalized_dim_name = dim_name.replace(':', '_')

                        # Check if this dimension exists and matches the expected value
                        if normalized_dim_name not in context.dimensions or context.dimensions[
                            normalized_dim_name] != dim_value:
                            matches_all_dimensions = False
                            break

                    if not matches_all_dimensions:
                        continue  # Skip if dimensions don't match

                # Get the context and extract dimension information
                context = self.contexts.get(context_id)

                # Create a wrapper around the fact with dimension information
                wrapped_fact = {
                    'fact': fact,
                    'dimension_info': [],
                    'dimension_key': ""
                }

                if context and hasattr(context, 'dimensions') and context.dimensions:
                    # Build rich dimension information with formatted labels
                    dimension_info = []
                    dim_keys = []

                    for dim_name, dim_value in sorted(context.dimensions.items()):
                        dim_value = dim_value.replace(":", "_")
                        # Initialize with technical names
                        dim_label = dim_name
                        mem_label = dim_value

                        # Get richer label information from element catalog
                        dim_element = None
                        mem_element = None

                        # Try to get human-readable dimension name
                        if dim_name in self.element_catalog:
                            dim_element = self.element_catalog[dim_name]
                            # Try different label roles in order of preference
                            for role in ['http://www.xbrl.org/2003/role/terseLabel',
                                         'http://www.xbrl.org/2003/role/label',
                                         'http://www.xbrl.org/2003/role/verboseLabel']:
                                if role in dim_element.labels:
                                    dim_label = dim_element.labels[role]
                                    break

                        # Try to get human-readable member name
                        if dim_value in self.element_catalog:
                            mem_element = self.element_catalog[dim_value]
                            # Try different label roles in order of preference
                            # Prefer verboseLabel which provides full accounting terms
                            # (e.g., "Rental equipment, net" vs "Sales of rental equipment")
                            for role in ['http://www.xbrl.org/2003/role/verboseLabel',
                                         'http://www.xbrl.org/2003/role/terseLabel',
                                         'http://www.xbrl.org/2003/role/label']:
                                if role in mem_element.labels:
                                    mem_label = mem_element.labels[role]
                                    break

                        # Clean up labels (remove [Axis], [Member], etc.)
                        dim_label = dim_label.replace('[Axis]', '').replace('[Domain]', '').strip()
                        mem_label = mem_label.replace('[Member]', '').strip()

                        # Format key for display
                        format_key = f"{dim_label}: {mem_label}"
                        dim_keys.append(format_key)

                        # Store rich dimension information
                        dimension_info.append({
                            'dimension': dim_name,
                            'member': dim_value,
                            'dimension_label': dim_label,
                            'member_label': mem_label,
                            'format_key': format_key,
                            'dimension_element': dim_element,
                            'member_element': mem_element
                        })

                    # Store dimension information in the wrapper
                    wrapped_fact['dimension_info'] = dimension_info
                    wrapped_fact['dimension_key'] = ", ".join(sorted(dim_keys))

                # If we get here, all filters passed
                relevant_facts[context_id] = wrapped_fact

        return relevant_facts

    def get_period_views(self, statement_type: str) -> List[Dict[str, Any]]:
        """
        Get available period views for a statement type.
        Args:
            statement_type: Type of statement to get period views for

        Returns:
            List of period view options with name, description, and period keys
        """
        return get_period_views(self, statement_type)

    def get_statements_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all statements matching a specific category.
        Args:
            category: Category of statements to find ('statement', 'note', 'disclosure', 'document', or 'other')
        Returns:
            List of statement metadata matching the category
        """
        # Ensure indices are built
        if not self._all_statements_cached:
            self.get_all_statements()

        result = []

        # Find all statements with matching category
        for stmt in self._all_statements_cached:
            if stmt.get('category') == category:
                result.append(stmt)

        return result

    def find_statement(self, statement_type: str, is_parenthetical: bool = False) -> Tuple[
        List[Dict[str, Any]], Optional[str], str]:
        """
        Find a statement by type, role, or name.

        Args:
            statement_type: Type of statement (e.g., "BalanceSheet") or role URI or statement name
            is_parenthetical: Whether to look for a parenthetical statement
        Returns:
            Tuple of:
                - List of matching statements
                - Found role URI (or None if not found)
                - Actual statement type (may be different from input if matched by role/name)
        """
        # Initialize statement resolver if not already done
        if self._statement_resolver is None:
            self._statement_resolver = StatementResolver(self)

        # Use the enhanced statement resolver
        matching_statements, found_role, actual_statement_type, confidence = self._statement_resolver.find_statement(
            statement_type, is_parenthetical
        )

        # For backward compatibility, ensure indices are built
        if not self._all_statements_cached:
            self.get_all_statements()

        # If we couldn't find anything with the resolver, fall back to the old implementation
        if not matching_statements:
            # Original implementation (fallback)
            matching_statements = []
            found_role = None
            actual_statement_type = statement_type

            # Try to find the statement by standard name first
            if statement_type in self._statement_by_standard_name:
                matching_statements = self._statement_by_standard_name[statement_type]
                if matching_statements:
                    found_role = matching_statements[0]['role']

            # Issue #518: Special fallback for IncomeStatement -> ComprehensiveIncome
            # Many filings have ComprehensiveIncome instead of separate IncomeStatement
            if not matching_statements and statement_type == 'IncomeStatement':
                if 'ComprehensiveIncome' in self._statement_by_standard_name:
                    matching_statements = self._statement_by_standard_name['ComprehensiveIncome']
                    if matching_statements:
                        found_role = matching_statements[0]['role']
                        if VERBOSE_EXCEPTIONS:
                            log.info("IncomeStatement not found, using ComprehensiveIncome as fallback")

            # If not found by standard name, try by role URI
            if not matching_statements and statement_type.startswith(
                    'http') and statement_type in self._statement_by_role_uri:
                matching_statements = [self._statement_by_role_uri[statement_type]]
                found_role = statement_type

            # If not found, try by role name (case-insensitive)
            if not matching_statements:
                role_or_type_lower = statement_type.lower()
                if role_or_type_lower in self._statement_by_role_name:
                    matching_statements = self._statement_by_role_name[role_or_type_lower]
                    if matching_statements:
                        found_role = matching_statements[0]['role']

            # If still not found, try by definition
            if not matching_statements:
                def_key = statement_type.lower().replace(' ', '')
                if def_key in self._statement_indices:
                    matching_statements = self._statement_indices[def_key]
                    if matching_statements:
                        found_role = matching_statements[0]['role']

            # If still not found, try partial matching on role name
            if not matching_statements:
                for role_name, statements in self._statement_by_role_name.items():
                    if statement_type.lower() in role_name:
                        matching_statements = statements
                        found_role = statements[0]['role']
                        break

            # Issue #518: Validate statement type matches to prevent returning wrong statement
            # Don't return CashFlowStatement when IncomeStatement was requested
            if matching_statements and matching_statements[0].get('type'):
                matched_type = matching_statements[0]['type']
                financial_statement_types = ['BalanceSheet', 'IncomeStatement', 'CashFlowStatement',
                                             'ComprehensiveIncome', 'StatementOfEquity']
                # If requesting a specific financial statement and got a different one, reject it
                if statement_type in financial_statement_types and matched_type != statement_type:
                    if VERBOSE_EXCEPTIONS:
                        log.warning(f"Found {matched_type} when looking for {statement_type}, rejecting type mismatch")
                    matching_statements = []
                    found_role = None

            # Update actual statement type if we found a match
            if matching_statements and matching_statements[0]['type']:
                actual_statement_type = matching_statements[0]['type']

        return matching_statements, found_role, actual_statement_type

    def render_statement(self, statement_type: str = "BalanceSheet",
                         period_filter: Optional[str] = None,
                         period_view: Optional[str] = None,
                         standard: bool = True,
                         show_date_range: bool = False,
                         parenthetical: bool = False,
                         include_dimensions: bool = False,
                         view: Optional['StatementView'] = None) -> Optional[RenderedStatement]:
        """
        Render a statement in a rich table format similar to how it would appear in an actual filing.
        Args:
            statement_type: Type of statement to render (e.g., "BalanceSheet", "IncomeStatement")
                           or a specific statement role/name (e.g., "CONSOLIDATEDBALANCESHEETS")
            period_filter: Optional period key to filter by specific reporting period
            period_view: Optional name of a predefined period view (e.g., "Quarterly: Current vs Previous")
            standard: Whether to use standardized concept labels (default: True)
            show_date_range: Whether to show full date ranges for duration periods (default: False)
            parenthetical: Whether to look for a parenthetical statement (default: False)
            include_dimensions: Whether to include dimensional segment data (default: False)
            view: StatementView controlling dimensional filtering (STANDARD, DETAILED, SUMMARY)
        Returns:
            RichTable: A formatted table representation of the statement
        """
        from edgar.xbrl.presentation import StatementView

        # Find the statement using the unified statement finder with parenthetical support
        matching_statements, found_role, actual_statement_type = self.find_statement(statement_type, parenthetical)

        # Get statement definition from matching statements
        role_definition = ""
        if matching_statements:
            role_definition = matching_statements[0]['definition']

        # Issue #569: Always get full dimensional data from get_statement
        # Then filter breakdown dimensions (geographic, segment) in render_statement
        # This ensures face-level classification dimensions (PPE type, equity) are shown
        should_display_dimensions = True

        # Get the statement data with all dimensional data, passing view for filtering
        statement_data = self.get_statement(statement_type, period_filter, should_display_dimensions, view=view)
        if not statement_data:
            return None

        # Get the statement title
        statement_info = statement_to_concepts.get(actual_statement_type)
        if statement_info:
            statement_title = statement_info.title
        else:
            # Try to get a nice title from the role definition
            if role_definition:
                statement_title = role_definition.split(' - ')[-1].strip()
            else:
                statement_title = statement_type

        # Add "Parenthetical" to the title if appropriate
        if parenthetical:
            statement_title = f"{statement_title} (Parenthetical)"

        # Get periods to display using unified period selection
        periods_to_display = select_periods(
            self, actual_statement_type, max_periods=4
        )

        # Render the statement
        # Issue #569: Pass include_dimensions to filter breakdown dimensions in render
        # Issue #577/cf9o: Pass role_uri for definition linkbase-based filtering
        # StatementView: Pass view for STANDARD/DETAILED/SUMMARY filtering
        return render_statement(
            statement_data,
            periods_to_display,
            statement_title,
            actual_statement_type,
            self.entity_info,
            standard,
            show_date_range,
            show_comparisons=True,
            xbrl_instance=self,
            include_dimensions=include_dimensions,
            role_uri=found_role,
            view=view
        )

    def to_pandas(self, statement_role: Optional[str] = None, standard: bool = True) -> Dict[str, pd.DataFrame]:
        """
        Convert XBRL data to pandas DataFrames.
        Args:
            statement_role: Optional role URI to convert only a specific statement
            standard: Whether to use standardized concept labels (default: True)
        Returns:
            Dictionary of DataFrames for different aspects of the XBRL data
        """

        dataframes = {}

        # Convert contexts to DataFrame
        context_data = []
        for context_id, context in self.contexts.items():
            ctx_dict = context.model_dump()
            ctx_dict['context_id'] = context_id

            # Extract entity info
            if 'entity' in ctx_dict and ctx_dict['entity']:
                ctx_dict['entity_identifier'] = ctx_dict['entity'].get('identifier')
                ctx_dict['entity_scheme'] = ctx_dict['entity'].get('scheme')

            # Extract period info
            if 'period' in ctx_dict and ctx_dict['period']:
                ctx_dict['period_type'] = ctx_dict['period'].get('type')
                if ctx_dict['period_type'] == 'instant':
                    ctx_dict['period_instant'] = ctx_dict['period'].get('instant')
                elif ctx_dict['period_type'] == 'duration':
                    ctx_dict['period_start'] = ctx_dict['period'].get('startDate')
                    ctx_dict['period_end'] = ctx_dict['period'].get('endDate')

            # Extract dimensions
            if 'dimensions' in ctx_dict and ctx_dict['dimensions']:
                for dim_name, dim_value in ctx_dict['dimensions'].items():
                    dim_key = f"dim_{dim_name.replace(':', '_')}"
                    ctx_dict[dim_key] = dim_value

            context_data.append(ctx_dict)

        if context_data:
            dataframes['contexts'] = pd.DataFrame(context_data)

        # Convert facts to DataFrame
        fact_data = []
        for fact_key, fact in self._facts.items():
            fact_dict = fact.model_dump()
            fact_dict['fact_key'] = fact_key

            # Try to get additional information
            if fact.context_ref in self.contexts:
                context = self.contexts[fact.context_ref]

                # Add period information
                if 'period' in context.model_dump() and context.period:
                    fact_dict['period_type'] = context.period.get('type')
                    if fact_dict['period_type'] == 'instant':
                        fact_dict['period_instant'] = context.period.get('instant')
                    elif fact_dict['period_type'] == 'duration':
                        fact_dict['period_start'] = context.period.get('startDate')
                        fact_dict['period_end'] = context.period.get('endDate')

                # Add entity information
                if 'entity' in context.model_dump() and context.entity:
                    fact_dict['entity_identifier'] = context.entity.get('identifier')

                # Add dimensions
                if 'dimensions' in context.model_dump() and context.dimensions:
                    for dim_name, dim_value in context.dimensions.items():
                        dim_key = f"dim_{dim_name.replace(':', '_')}"
                        fact_dict[dim_key] = dim_value

            # Try to get element information
            element_id = fact.element_id
            if element_id in self.element_catalog:
                element = self.element_catalog[element_id]
                fact_dict['element_name'] = element.name
                fact_dict['element_type'] = element.data_type
                fact_dict['element_period_type'] = element.period_type
                fact_dict['element_balance'] = element.balance

                # Add label
                label = None
                if element.labels:
                    # Try standard label first
                    label = element.labels.get(STANDARD_LABEL)
                    if not label:
                        # Take first available label
                        label = next(iter(element.labels.values()), None)
                fact_dict['element_label'] = label

            fact_data.append(fact_dict)

        if fact_data:
            dataframes['facts'] = pd.DataFrame(fact_data)

        # Convert entity info to DataFrame
        if self.entity_info:
            dataframes['entity_info'] = pd.DataFrame([self.entity_info])

        # Convert specific statement if requested
        if statement_role:
            # Try direct role URI
            statement_data = self.get_statement(statement_role)

            # If not found, try by statement type
            if not statement_data and not statement_role.startswith('http'):
                # Find the role for this statement type
                all_statements = self.get_all_statements()
                matching_statements = [stmt for stmt in all_statements if stmt['type'] == statement_role]

                if matching_statements:
                    role = matching_statements[0]['role']
                    statement_data = self.get_statement(role)

            # Convert statement data to DataFrame if found
            if statement_data:
                # Apply standardization if requested
                if standard:
                    # Get statement type for context
                    stmt_type = statement_role
                    if not stmt_type.startswith('http'):
                        stmt_type = statement_role
                    else:
                        # Try to determine statement type from role
                        all_statements = self.get_all_statements()
                        for stmt in all_statements:
                            if stmt['role'] == statement_role:
                                stmt_type = stmt['type']
                                break

                    # Apply standardization using XBRL instance's cache (disable statement caching
                    # for consistency with other call sites where input data varies)
                    statement_data = self.standardization.standardize_statement_data(
                        statement_data, stmt_type, use_cache=False
                    )

                # Create rows for the DataFrame
                rows = []

                # Add columns for all found periods
                all_periods = set()
                for item in statement_data:
                    for period in item.get('values', {}).keys():
                        all_periods.add(period)

                # Sort periods (typically instant or duration_start_end format)
                sorted_periods = sorted(all_periods)

                for item in statement_data:
                    row = {
                        'concept': item['concept'],
                        'label': item['label'],
                        'level': item['level'],
                        'is_abstract': item['is_abstract'],
                        'has_values': item.get('has_values', False),
                    }

                    # Add original label if standardized
                    if 'original_label' in item:
                        row['original_label'] = item['original_label']

                    # Add period values
                    for period in sorted_periods:
                        value = item.get('values', {}).get(period)
                        row[period] = value

                    rows.append(row)

                if rows:
                    dataframes['statement'] = pd.DataFrame(rows)
                    # Rename columns to remove duration/instant prefixes
                    dataframes['statement'].columns = [
                        col.replace('duration_', '').replace('instant_', '')
                        for col in dataframes['statement'].columns
                    ]

        return dataframes

    def get_footnotes_for_fact(self, fact_id: str) -> List['Footnote']:
        """Get all footnotes associated with a specific fact ID.
        Args:
            fact_id: The ID of the fact to get footnotes for
        Returns:
            List of Footnote objects associated with the fact
        """
        footnotes = []

        # First check if any fact has this ID and get its footnote references
        for fact in self.parser.facts.values():
            if fact.fact_id == fact_id:
                # Get the footnote objects for each footnote ID
                for footnote_id in fact.footnotes:
                    if footnote_id in self.parser.footnotes:
                        footnotes.append(self.parser.footnotes[footnote_id])
                break

        return footnotes

    def get_facts_with_footnotes(self) -> Dict[str, 'Fact']:
        """Get all facts that have associated footnotes.
        Returns:
            Dictionary of fact_key -> Fact for all facts with footnotes
        """
        facts_with_footnotes = {}
        for key, fact in self.parser.facts.items():
            if fact.footnotes:
                facts_with_footnotes[key] = fact
        return facts_with_footnotes

    def get_currency_for_fact(self, element_name: str, period_key: str) -> Optional[str]:
        """
        Get currency for a specific fact/period on-demand with caching.

        Args:
            element_name: The XBRL element name
            period_key: The period key to look up

        Returns:
            Currency measure string (e.g., 'iso4217:EUR') or None if not found
        """
        # Create cache key
        cache_key = f"{element_name}_{period_key}"

        # Check cache first
        if not hasattr(self, '_currency_cache'):
            self._currency_cache = {}

        if cache_key in self._currency_cache:
            return self._currency_cache[cache_key]

        # Find facts for this element and period
        facts = self._find_facts_for_element(element_name, period_key)

        # Look for the first fact with currency information
        currency_measure = None
        for _, wrapped_fact in facts.items():
            fact = wrapped_fact['fact']
            if hasattr(fact, 'unit_ref') and fact.unit_ref and fact.unit_ref in self.units:
                unit_info = self.units[fact.unit_ref]
                if 'measure' in unit_info:
                    currency_measure = unit_info['measure']
                    break

        # Cache the result (including None values to avoid repeated lookups)
        self._currency_cache[cache_key] = currency_measure
        return currency_measure

    # =========================================================================
    # DEFINITION LINKBASE - DIMENSION VALIDATION
    # =========================================================================

    def get_valid_dimensions_for_role(self, role_uri: str) -> set:
        """
        Get axes (dimensions) that are valid for a statement role per definition linkbase.

        The definition linkbase declares which dimensions are valid for each statement
        via hypercube (table) definitions. This is the authoritative source for determining
        whether a dimensional fact is a "face value" or a "breakdown".

        Args:
            role_uri: The statement role URI (e.g., "http://company.com/role/IncomeStatement")

        Returns:
            Set of axis element IDs that are valid for this role.
            Returns empty set if no hypercube definitions exist for this role.

        Example:
            >>> xbrl = filing.xbrl()
            >>> axes = xbrl.get_valid_dimensions_for_role(
            ...     "http://www.boeing.com/role/ConsolidatedStatementsofOperations"
            ... )
            >>> print(axes)
            {'srt_ProductOrServiceAxis'}
        """
        if not hasattr(self, '_valid_dimensions_cache'):
            self._valid_dimensions_cache = {}

        if role_uri in self._valid_dimensions_cache:
            return self._valid_dimensions_cache[role_uri]

        valid_axes = set()

        # Get tables defined for this role
        if role_uri in self.tables:
            for table in self.tables[role_uri]:
                valid_axes.update(table.axes)

        self._valid_dimensions_cache[role_uri] = valid_axes
        return valid_axes

    def _normalize_axis_id(self, axis_id: str) -> str:
        """
        Normalize axis ID to consistent format for comparison.

        Handles both formats:
        - Underscore format: srt_ProductOrServiceAxis (from definition linkbase)
        - Colon format: srt:ProductOrServiceAxis (from dimension metadata)

        Returns the base axis name for comparison.
        """
        # Extract just the axis name (after prefix)
        if ':' in axis_id:
            return axis_id.split(':', 1)[1]
        if '_' in axis_id:
            # Handle cases like 'srt_ProductOrServiceAxis' -> 'ProductOrServiceAxis'
            # But also handle 'us-gaap_StatementTable' correctly
            parts = axis_id.split('_', 1)
            if len(parts) == 2:
                return parts[1]
        return axis_id

    def is_dimension_valid_for_role(self, dimension: str, role_uri: str) -> bool:
        """
        Check if a dimension (axis) is declared valid for a statement role.

        This checks the definition linkbase hypercube declarations to determine
        if a dimension should be treated as a "face value" dimension for this
        statement (as opposed to a breakdown/detail dimension).

        Args:
            dimension: The dimension/axis name (e.g., "srt:ProductOrServiceAxis")
            role_uri: The statement role URI

        Returns:
            True if the dimension is declared valid for this role's hypercubes.
            False if not declared (meaning it's likely a breakdown dimension).

        Example:
            >>> xbrl.is_dimension_valid_for_role(
            ...     "srt:ProductOrServiceAxis",
            ...     "http://www.boeing.com/role/ConsolidatedStatementsofOperations"
            ... )
            True
        """
        valid_axes = self.get_valid_dimensions_for_role(role_uri)

        if not valid_axes:
            # No definition linkbase data for this role
            return False

        # Normalize the input dimension for comparison
        dim_normalized = self._normalize_axis_id(dimension)

        # Check if any valid axis matches
        for axis in valid_axes:
            axis_normalized = self._normalize_axis_id(axis)
            if dim_normalized == axis_normalized:
                return True

        return False

    def has_definition_linkbase_for_role(self, role_uri: str) -> bool:
        """
        Check if definition linkbase data exists for a statement role.

        This is useful for determining whether to use definition linkbase-based
        dimension filtering or fall back to heuristic-based filtering.

        Args:
            role_uri: The statement role URI

        Returns:
            True if hypercube/table definitions exist for this role.
        """
        return role_uri in self.tables and len(self.tables[role_uri]) > 0

    def __rich__(self):
        """Rich representation for pretty printing in console."""
        return generate_rich_representation(self)

    def __repr__(self):
        return repr_rich(self.__rich__())


    def to_context(self, max_tokens: int = 2000) -> str:
        """
        Get AI-optimized text representation of XBRL document.

        Returns a compact Markdown-KV format optimized for LLM consumption,
        including entity information, filing details, period coverage, available
        statements, and common usage patterns.

        This format uses 64.7% fewer tokens than the visual repr() format while
        retaining all essential information.

        Args:
            max_tokens: Target token budget (currently not enforced, reserved for future use)

        Returns:
            Compact Markdown-KV text representation optimized for AI consumption

        Example:
            >>> xbrl = filing.xbrl()
            >>> text = xbrl.to_context()
            >>> print(text)
            **Entity:** Apple Inc. (AAPL)
            **CIK:** 0000320193
            **Form:** 10-K
            ...
        """
        lines = []

        # Entity information
        if self.entity_info:
            entity_name = self.entity_info.get('entity_name', 'Unknown Entity')
            ticker = self.entity_info.get('ticker', '')
            cik = self.entity_info.get('identifier', '')

            # Entity line with ticker if available
            entity_line = f"**Entity:** {entity_name}"
            if ticker:
                entity_line += f" ({ticker})"
            lines.append(entity_line)

            if cik:
                lines.append(f"**CIK:** {cik}")

            # Filing details
            doc_type = self.entity_info.get('document_type', '')
            if doc_type:
                lines.append(f"**Form:** {doc_type}")

            fiscal_year = self.entity_info.get('fiscal_year', '')
            fiscal_period = self.entity_info.get('fiscal_period', '')
            period_end = self.entity_info.get('document_period_end_date', '')

            if fiscal_period and fiscal_year:
                period_display = f"Fiscal Year {fiscal_year}" if fiscal_period == 'FY' else f"{fiscal_period} {fiscal_year}"
                if period_end:
                    period_display += f" (ended {period_end})"
                lines.append(f"**Fiscal Period:** {period_display}")

            # Data volume
            lines.append(f"**Facts:** {len(self._facts):,}")
            lines.append(f"**Contexts:** {len(self.contexts):,}")

        # Period coverage
        if self.reporting_periods:
            lines.append("")
            lines.append("**Available Data Coverage:**")

            # Categorize periods
            annual_periods = []
            quarterly_periods = []

            for period in self.reporting_periods[:10]:
                label = period.get('label', '')
                if not label:
                    continue

                if 'Annual:' in label or 'FY' in label.upper():
                    # Extract fiscal year
                    import re
                    year_match = re.search(r'to .* (\d{4})', label)
                    if year_match:
                        annual_periods.append(f"FY {year_match.group(1)}")
                    else:
                        annual_periods.append(label)
                elif 'Quarterly:' in label or any(q in label for q in ['Q1', 'Q2', 'Q3', 'Q4']):
                    clean_label = label.replace('Quarterly:', '').strip()
                    quarterly_periods.append(clean_label)

            if annual_periods:
                lines.append(f"  Annual: {', '.join(annual_periods[:3])}")
            if quarterly_periods:
                lines.append(f"  Quarterly: {', '.join(quarterly_periods[:2])}")

        # Available statements
        statements = self.get_all_statements()
        if statements:
            lines.append("")
            lines.append("**Available Statements:**")
            # Group by core vs other statements
            core_statements = set()
            other_statements = []

            core_types = {'IncomeStatement', 'BalanceSheet', 'CashFlowStatement',
                         'StatementOfEquity', 'ComprehensiveIncome'}

            for stmt in statements:
                stmt_type = stmt.get('type', '')
                if stmt_type in core_types:
                    core_statements.add(stmt_type)
                elif stmt_type:
                    other_statements.append(stmt_type)

            # Show core statements first (in consistent order)
            if core_statements:
                ordered_core = [s for s in ['IncomeStatement', 'ComprehensiveIncome', 'BalanceSheet',
                                            'StatementOfEquity', 'CashFlowStatement'] if s in core_statements]
                lines.append(f"  Core: {', '.join(ordered_core)}")
            if other_statements and len(other_statements) <= 5:
                lines.append(f"  Other: {', '.join(other_statements)}")
            elif other_statements:
                lines.append(f"  Other: {len(other_statements)} additional statements")

        # Common actions (compact version)
        lines.append("")
        lines.append("**Common Actions:**")
        lines.append("  # List all available statements")
        lines.append("  xbrl.statements")
        lines.append("")
        lines.append("  # View core financial statements")
        lines.append("  stmt = xbrl.statements.income_statement()")
        lines.append("  stmt = xbrl.statements.balance_sheet()")
        lines.append("  stmt = xbrl.statements.cash_flow_statement()")
        lines.append("  stmt = xbrl.statements.statement_of_equity()")
        lines.append("  stmt = xbrl.statements.comprehensive_income()")
        lines.append("")
        lines.append("  # Get current period only (returns XBRL with filtered context)")
        lines.append("  current = xbrl.current_period")
        lines.append("  stmt = current.income_statement()")
        lines.append("")
        lines.append("  # Convert statement to DataFrame")
        lines.append("  df = stmt.to_dataframe()")
        lines.append("")
        lines.append("  # Query specific facts")
        lines.append("  revenue = xbrl.facts.query().by_concept('Revenue').to_dataframe()")
        lines.append("")
        lines.append("💡 Use xbrl.docs for comprehensive API guide")

        return "\n".join(lines)

    def text(self, max_tokens: int = 2000) -> str:
        """
        Deprecated: Use to_context() instead.

        Get AI-optimized text representation of XBRL document.
        This method is deprecated and will be removed in a future version.
        Use to_context() for consistent naming with other AI-native methods.

        Args:
            max_tokens: Target token budget (currently not enforced, reserved for future use)

        Returns:
            Compact Markdown-KV text representation optimized for AI consumption
        """
        import warnings
        warnings.warn(
            "XBRL.text() is deprecated and will be removed in a future version. "
            "Use XBRL.to_context() instead for consistent naming.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.to_context(max_tokens=max_tokens)

    @property
    def docs(self):
        """
        Get comprehensive documentation for the XBRL class.

        Returns a Docs object with detailed API documentation including usage patterns,
        examples, and guidance for working with XBRL data. The documentation is searchable
        using the .search() method.

        Returns:
            Docs: Documentation object with rich display and search capabilities

        Example:
            >>> xbrl.docs  # Display full documentation
            >>> xbrl.docs.search("extract revenue")  # Search for specific topics
        """
        from edgar.richtools import Docs
        return Docs(self)
