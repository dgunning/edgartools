"""
Financial statement processing for XBRL data.

This module provides functions for working with financial statements.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from rich import box
from rich.table import Table

from edgar.richtools import repr_rich
from edgar.xbrl.exceptions import StatementNotFound


@dataclass
class StatementInfo:
    name: str
    concept: str
    title: str


statement_to_concepts = {
    "IncomeStatement": StatementInfo(name="IncomeStatement",
                                     concept="us-gaap_IncomeStatementAbstract",
                                     title="Consolidated Statement of Income"),
    "BalanceSheet": StatementInfo(name="BalanceSheet",
                                  concept="us-gaap_StatementOfFinancialPositionAbstract",
                                  title="Consolidated Balance Sheets",
                                  ),
    "CashFlowStatement": StatementInfo(name="CashFlowStatement",
                                       concept="us-gaap_StatementOfCashFlowsAbstract",
                                       title="Consolidated Statement of Cash Flows"),
    "StatementOfEquity": StatementInfo(name="StatementOfEquity",
                                       concept="us-gaap_StatementOfStockholdersEquityAbstract",
                                       title="Consolidated Statement of Equity"
                                       ),
    "ComprehensiveIncome": StatementInfo(name="ComprehensiveIncome",
                                         concept="us-gaap_StatementOfIncomeAndComprehensiveIncomeAbstract",
                                         title="Consolidated Statement of Comprehensive Income"
                                         ),
    "CoverPage": StatementInfo(name="CoverPage",
                               concept="dei_CoverAbstract",
                                 title="Cover Page"
                                 ),

}


class StatementValidationError(Exception):
    """Raised when statement validation fails."""
    pass


class Statement:
    """
    A single financial statement extracted from XBRL data.

    This class provides convenient methods for rendering and manipulating a specific
    financial statement. It includes validation, normalization, and analysis capabilities.

    Features:
    - Statement structure validation
    - Error handling for missing/malformed data
    - Statement normalization across different companies
    - Common financial analysis methods
    - Ratio calculations and trend analysis
    """

    # Required concepts for each statement type
    REQUIRED_CONCEPTS = {
        'BalanceSheet': [
            'us-gaap_Assets',
            'us-gaap_Liabilities',
            'us-gaap_StockholdersEquity'
        ],
        'IncomeStatement': [
            'us-gaap_Revenues',
            'us-gaap_NetIncomeLoss'
        ],
        'CashFlowStatement': [
            'us-gaap_CashAndCashEquivalentsPeriodIncreaseDecrease',
            'us-gaap_CashAndCashEquivalentsAtCarryingValue'
        ]
    }

    def __init__(self, xbrl, role_or_type: str, canonical_type: Optional[str] = None, 
               skip_concept_check: bool = False):
        """
        Initialize with an XBRL object and statement identifier.

        Args:
            xbrl: XBRL object containing parsed data
            role_or_type: Role URI, statement type, or statement short name
            canonical_type: Optional canonical statement type (e.g., "BalanceSheet", "IncomeStatement")
                         If provided, this type will be used for specialized processing logic
            skip_concept_check: If True, skip checking for required concepts (useful for testing)

        Raises:
            StatementValidationError: If statement validation fails
        """
        self.xbrl = xbrl
        self.role_or_type = role_or_type
        self.canonical_type = canonical_type

    def is_segmented(self) -> bool:
        """
        Check if the statement is a segmented statement.

        Returns:
            True if the statement is segmented, False otherwise
        """
        return self.role_or_type.startswith("Segment")

    def render(self, period_filter: Optional[str] = None,
               period_view: Optional[str] = None,
               standard: bool = True,
               show_date_range: bool = False,
               include_dimensions: bool = True) -> Any:
        """
        Render the statement as a formatted table.

        Args:
            period_filter: Optional period key to filter facts
            period_view: Optional name of a predefined period view
            standard: Whether to use standardized concept labels
            show_date_range: Whether to show full date ranges for duration periods
            include_dimensions: Whether to include dimensional segment data

        Returns:
            Rich Table containing the rendered statement
        """
        # Use the canonical type for rendering if available, otherwise use the role
        rendering_type = self.canonical_type if self.canonical_type else self.role_or_type

        return self.xbrl.render_statement(rendering_type,
                                          period_filter=period_filter,
                                          period_view=period_view,
                                          standard=standard,
                                          show_date_range=show_date_range,
                                          include_dimensions=include_dimensions)

    def __rich__(self) -> Any:
        """
        Rich console representation.

        Returns:
            Rich Table object if rich is available, else string representation
        """
        if Table is None:
            return str(self)
        return self.render()

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        """String representation using improved rendering with proper width."""
        rendered_statement = self.render()
        return str(rendered_statement)  # Delegates to RenderedStatement.__str__()

    @property
    def docs(self):
        """
        Get comprehensive documentation for the Statement class.

        Returns a Docs object with detailed API documentation including usage patterns,
        examples, and guidance for working with financial statement data. The documentation
        is searchable using the .search() method.

        Returns:
            Docs: Documentation object with rich display and search capabilities

        Example:
            >>> statement.docs  # Display full documentation
            >>> statement.docs.search("convert to dataframe")  # Search for specific topics
        """
        from edgar.richtools import Docs
        return Docs(self)

    @property
    def primary_concept(self):
        data = self.get_raw_data()
        return data[0]['all_names'][0]

    def to_dataframe(self,
                     period_filter:str=None,
                     period_view:str=None,
                     standard:bool=True,
                     include_dimensions:bool=True,
                     include_unit:bool=False,
                     include_point_in_time:bool=False,
                     presentation:bool=False) -> Any:
        """Convert statement to pandas DataFrame.

        Args:
            period_filter: Optional period key to filter facts
            period_view: Optional name of a predefined period view
            standard: Whether to use standardized concept labels
            include_dimensions: Whether to include dimensional segment data
            include_unit: If True, add a 'unit' column with unit information (e.g., 'usd', 'shares', 'usdPerShare')
            include_point_in_time: If True, add a 'point_in_time' boolean column (True for 'instant', False for 'duration')
            presentation: If True, apply HTML-matching presentation logic (Issue #463)
                         Cash Flow: outflows (balance='credit') shown as negative
                         Income: apply preferred_sign transformations
                         Default: False (raw instance values)

        Returns:
            DataFrame with raw values + metadata (balance, weight, preferred_sign) by default
        """
        try:
            # Build DataFrame from raw data (Issue #463)
            df = self._build_dataframe_from_raw_data(
                period_filter=period_filter,
                period_view=period_view,
                standard=standard,
                include_dimensions=include_dimensions,
                include_unit=include_unit,
                include_point_in_time=include_point_in_time
            )

            if df is None or isinstance(df, str) or df.empty:
                return df

            # Add metadata columns (balance, weight, preferred_sign) - Issue #463
            df = self._add_metadata_columns(df)

            # Apply presentation transformation if requested (Issue #463)
            if presentation:
                df = self._apply_presentation(df)

            return df

        except ImportError:
            return "Pandas is required for DataFrame conversion"

    def _build_dataframe_from_raw_data(
        self,
        period_filter: Optional[str] = None,
        period_view: Optional[str] = None,
        standard: bool = True,
        include_dimensions: bool = True,
        include_unit: bool = False,
        include_point_in_time: bool = False
    ) -> pd.DataFrame:
        """
        Build DataFrame directly from raw statement data (Issue #463).

        This bypasses the rendering pipeline to get raw instance values.
        """
        from edgar.xbrl.core import get_unit_display_name
        from edgar.xbrl.core import is_point_in_time as get_is_point_in_time
        from edgar.xbrl.periods import determine_periods_to_display

        # Get raw statement data
        raw_data = self.get_raw_data(period_filter=period_filter)
        if not raw_data:
            return pd.DataFrame()

        # Determine which periods to display
        statement_type = self.canonical_type if self.canonical_type else self.role_or_type

        if period_view:
            # Use specified period view
            from edgar.xbrl.periods import get_period_views
            period_views = get_period_views(self.xbrl, statement_type)
            periods_to_display = period_views.get(period_view, [])
            if not periods_to_display:
                # Fallback to default
                periods_to_display = determine_periods_to_display(self.xbrl, statement_type)
        else:
            # Use default period selection
            periods_to_display = determine_periods_to_display(self.xbrl, statement_type)

        if not periods_to_display:
            return pd.DataFrame()

        # Build DataFrame rows
        df_rows = []

        for item in raw_data:
            # Skip if filtering by dimensions
            if not include_dimensions and item.get('dimension'):
                continue

            # Build base row
            row = {
                'concept': item.get('concept', ''),
                'label': item.get('label', '')
            }

            # Add period values (raw from instance document)
            values_dict = item.get('values', {})
            for period_key, period_label in periods_to_display:
                # Use end date as column name (more concise than full label)
                # Extract date from period_key (e.g., "duration_2016-09-25_2017-09-30" → "2017-09-30")
                if '_' in period_key:
                    parts = period_key.split('_')
                    if len(parts) >= 2:
                        # Use end date for duration periods, or the date for instant periods
                        column_name = parts[-1] if len(parts) > 2 else parts[1]
                    else:
                        column_name = period_label
                else:
                    column_name = period_label

                # Use raw value from instance document
                row[column_name] = values_dict.get(period_key)

            # Add unit if requested
            if include_unit:
                units_dict = item.get('units', {})
                # Get first available unit (should be same for all periods)
                unit_ref = None
                for period_key, _ in periods_to_display:
                    if period_key in units_dict and units_dict[period_key] is not None:
                        unit_ref = units_dict[period_key]
                        break
                row['unit'] = get_unit_display_name(unit_ref)

            # Add point_in_time if requested
            if include_point_in_time:
                period_types_dict = item.get('period_types', {})
                # Get first available period type
                period_type = None
                for period_key, _ in periods_to_display:
                    if period_key in period_types_dict and period_types_dict[period_key] is not None:
                        period_type = period_types_dict[period_key]
                        break
                row['point_in_time'] = get_is_point_in_time(period_type)

            # Add structural columns
            row['level'] = item.get('level', 0)
            row['abstract'] = item.get('is_abstract', False)
            row['dimension'] = item.get('is_dimension', False)

            df_rows.append(row)

        return pd.DataFrame(df_rows)

    def _add_metadata_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add metadata columns (balance, weight, preferred_sign) to DataFrame.

        Issue #463: Users need access to XBRL metadata to understand value transformations.

        Note: preferred_sign comes from statement's raw data (presentation linkbase),
        not from facts. It's period-specific in raw data, but we use a representative
        value (from first period) for the metadata column.
        """
        if df.empty or 'concept' not in df.columns:
            return df

        # Get statement's raw data to access preferred_signs
        raw_data = self.get_raw_data()
        raw_data_by_concept = {item.get('concept'): item for item in raw_data}

        # Create metadata dictionaries to populate
        balance_map = {}
        weight_map = {}
        preferred_sign_map = {}

        # For each unique concept in the DataFrame
        for concept in df['concept'].unique():
            if not concept:
                continue

            # Get balance and weight from facts (concept-level attributes)
            facts_df = self.xbrl.facts.query().by_concept(concept, exact=True).limit(1).to_dataframe()

            if not facts_df.empty:
                fact = facts_df.iloc[0]
                balance_map[concept] = fact.get('balance')
                weight_map[concept] = fact.get('weight')

            # Get preferred_sign from statement raw data (presentation linkbase)
            # preferred_sign is period-specific, so we take the first available value
            if concept in raw_data_by_concept:
                item = raw_data_by_concept[concept]
                preferred_signs = item.get('preferred_signs', {})
                if preferred_signs:
                    # Use first period's preferred_sign as representative value
                    preferred_sign_map[concept] = next(iter(preferred_signs.values()))

        # Add metadata columns
        df['balance'] = df['concept'].map(balance_map)
        df['weight'] = df['concept'].map(weight_map)
        df['preferred_sign'] = df['concept'].map(preferred_sign_map)

        return df

    def _apply_presentation(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply presentation logic to match SEC HTML display.

        Issue #463: Transform values to match how they appear in official SEC filings.
        Uses preferred_sign from presentation linkbase (not balance attribute).
        - preferred_sign = -1: negate for display (expenses, dividends, outflows)
        - preferred_sign = 1: show as-is
        - preferred_sign = None: no transformation
        """
        if df.empty:
            return df

        result = df.copy()

        # Get period columns (exclude metadata and structural columns)
        metadata_cols = ['concept', 'label', 'balance', 'weight', 'preferred_sign',
                        'level', 'abstract', 'dimension', 'unit', 'point_in_time']
        period_cols = [col for col in df.columns if col not in metadata_cols]

        # Get statement type
        statement_type = self.canonical_type if self.canonical_type else self.role_or_type

        # For Income Statement and Cash Flow Statement: Use preferred_sign
        if statement_type in ('IncomeStatement', 'CashFlowStatement'):
            if 'preferred_sign' in result.columns:
                for col in period_cols:
                    if col in result.columns and pd.api.types.is_numeric_dtype(result[col]):
                        # Apply preferred_sign where it's not None and not 0
                        mask = result['preferred_sign'].notna() & (result['preferred_sign'] != 0)
                        result.loc[mask, col] = result.loc[mask, col] * result.loc[mask, 'preferred_sign']

        # Balance Sheet: no transformation

        return result


    def _validate_statement(self, skip_concept_check: bool = False) -> None:
        """
        Validate the statement structure and required concepts.

        Args:
            skip_concept_check: If True, skip checking for required concepts (useful for testing)
        """
        data = self.get_raw_data()
        if not data:
            raise StatementValidationError(f"No data found for statement {self.role_or_type}")

        # Determine the statement type to validate against
        validate_type = self.canonical_type if self.canonical_type else self.role_or_type

        # Check for required concepts if this is a standard statement type
        if validate_type in self.REQUIRED_CONCEPTS and not skip_concept_check:
            missing_concepts = []
            for concept in self.REQUIRED_CONCEPTS[validate_type]:
                if not any(concept in item.get('all_names', []) for item in data):
                    missing_concepts.append(concept)

            if missing_concepts:
                raise StatementValidationError(
                    f"Missing required concepts for {validate_type}: {', '.join(missing_concepts)}")

    def calculate_ratios(self) -> Dict[str, float]:
        """Calculate common financial ratios for this statement."""
        ratios = {}
        data = self.get_raw_data()

        # Use canonical type if available, otherwise use role_or_type
        statement_type = self.canonical_type if self.canonical_type else self.role_or_type

        if statement_type == 'BalanceSheet':
            # Calculate balance sheet ratios
            ratios.update(self._calculate_balance_sheet_ratios(data))
        elif statement_type == 'IncomeStatement':
            # Calculate income statement ratios
            ratios.update(self._calculate_income_statement_ratios(data))

        return ratios

    def _calculate_balance_sheet_ratios(self, data: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate balance sheet specific ratios."""
        ratios = {}

        # Current ratio
        current_assets = self._get_concept_value(data, 'us-gaap_CurrentAssets')
        current_liabilities = self._get_concept_value(data, 'us-gaap_CurrentLiabilities')
        if current_assets and current_liabilities:
            ratios['current_ratio'] = current_assets / current_liabilities

        # Quick ratio
        inventory = self._get_concept_value(data, 'us-gaap_Inventory')
        if current_assets and current_liabilities and inventory:
            ratios['quick_ratio'] = (current_assets - inventory) / current_liabilities

        return ratios

    def _calculate_income_statement_ratios(self, data: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate income statement specific ratios."""
        ratios = {}

        # Gross margin
        revenue = self._get_concept_value(data, 'us-gaap_Revenues')
        gross_profit = self._get_concept_value(data, 'us-gaap_GrossProfit')
        if revenue and gross_profit:
            ratios['gross_margin'] = gross_profit / revenue

        # Net margin
        net_income = self._get_concept_value(data, 'us-gaap_NetIncomeLoss')
        if revenue and net_income:
            ratios['net_margin'] = net_income / revenue

        return ratios

    def _get_concept_value(self, data: List[Dict[str, Any]], concept: str) -> Optional[float]:
        """Get the value for a specific concept from statement data."""
        for item in data:
            if concept in item.get('all_names', []):
                values = item.get('values', {})
                if values:
                    return float(next(iter(values.values())))
        return None

    def analyze_trends(self, periods: int = 4) -> Dict[str, List[float]]:
        """Analyze trends in key metrics over time."""
        trends = {}

        # Use canonical type if available, otherwise use role_or_type
        statement_type = self.canonical_type if self.canonical_type else self.role_or_type

        # Get data for multiple periods
        period_views = self.xbrl.get_period_views(statement_type)
        if not period_views:
            return trends

        periods_to_analyze = period_views[0].get('periods', [])[:periods]

        for period in periods_to_analyze:
            data = self.get_raw_data(period)

            if statement_type == 'BalanceSheet':
                self._analyze_balance_sheet_trends(data, trends, period)
            elif statement_type == 'IncomeStatement':
                self._analyze_income_statement_trends(data, trends, period)

        return trends

    def _analyze_balance_sheet_trends(self, data: List[Dict[str, Any]], 
                                     trends: Dict[str, List[float]], 
                                     period: str) -> None:
        """Analyze balance sheet trends."""
        metrics = {
            'total_assets': 'us-gaap_Assets',
            'total_liabilities': 'us-gaap_Liabilities',
            'equity': 'us-gaap_StockholdersEquity'
        }

        for metric_name, concept in metrics.items():
            value = self._get_concept_value(data, concept)
            if value:
                if metric_name not in trends:
                    trends[metric_name] = []
                trends[metric_name].append(value)

    def _analyze_income_statement_trends(self, data: List[Dict[str, Any]], 
                                        trends: Dict[str, List[float]], 
                                        period: str) -> None:
        """Analyze income statement trends."""
        metrics = {
            'revenue': 'us-gaap_Revenues',
            'gross_profit': 'us-gaap_GrossProfit',
            'net_income': 'us-gaap_NetIncomeLoss'
        }

        for metric_name, concept in metrics.items():
            value = self._get_concept_value(data, concept)
            if value:
                if metric_name not in trends:
                    trends[metric_name] = []
                trends[metric_name].append(value)

    def get_raw_data(self, period_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get the raw statement data.

        Args:
            period_filter: Optional period key to filter facts

        Returns:
            List of line items with values

        Raises:
            StatementValidationError: If data retrieval fails
        """
        # Use the canonical type if available, otherwise use the role
        statement_id = self.canonical_type if self.canonical_type else self.role_or_type

        data = self.xbrl.get_statement(statement_id, period_filter=period_filter)
        if data is None:
            raise StatementValidationError(f"Failed to retrieve data for statement {statement_id}")
        return data


class Statements:
    """
    High-level interface for working with XBRL financial statements.

    This class provides a user-friendly way to access and manipulate 
    financial statements extracted from XBRL data.
    """

    def __init__(self, xbrl):
        """
        Initialize with an XBRL object.

        Args:
            xbrl: XBRL object containing parsed data
        """
        self.xbrl = xbrl
        self.statements = xbrl.get_all_statements()

        # Create statement type lookup for quick access
        self.statement_by_type = {}
        for stmt in self.statements:
            if stmt['type']:
                if stmt['type'] not in self.statement_by_type:
                    self.statement_by_type[stmt['type']] = []
                self.statement_by_type[stmt['type']].append(stmt)

    @staticmethod
    def classify_statement(stmt: dict) -> str:
        """
        Classify a statement into a category based on its type.

        Categories:
        - 'statement': Core financial statements (Income Statement, Balance Sheet, etc.)
        - 'note': Notes to financial statements
        - 'disclosure': Disclosure sections
        - 'document': Document sections (like CoverPage)
        - 'other': Everything else

        Args:
            stmt: Statement dictionary with 'type' and optional 'category' fields

        Returns:
            str: Category name ('statement', 'note', 'disclosure', 'document', or 'other')

        Example:
            >>> stmt = {'type': 'IncomeStatement', 'title': 'Income Statement'}
            >>> Statements.classify_statement(stmt)
            'statement'

            >>> stmt = {'type': 'DebtDisclosure', 'title': 'Debt Disclosure'}
            >>> Statements.classify_statement(stmt)
            'disclosure'
        """
        # Use explicit category if provided
        category = stmt.get('category')
        if category:
            return category

        # Infer from type
        stmt_type = stmt.get('type', '')
        if not stmt_type:
            return 'other'

        if 'Note' in stmt_type:
            return 'note'
        elif 'Disclosure' in stmt_type:
            return 'disclosure'
        elif stmt_type == 'CoverPage':
            return 'document'
        elif stmt_type in ('BalanceSheet', 'IncomeStatement', 'CashFlowStatement',
                           'StatementOfEquity', 'ComprehensiveIncome') or 'Statement' in stmt_type:
            return 'statement'
        else:
            return 'other'

    def get_statements_by_category(self) -> dict:
        """
        Get statements organized by category.

        Returns a dictionary with statements grouped into categories:
        - 'statement': Core financial statements
        - 'note': Notes to financial statements
        - 'disclosure': Disclosure sections
        - 'document': Document sections
        - 'other': Other sections

        Each statement in the lists includes an 'index' field for positional reference.

        Returns:
            dict: Dictionary with category keys, each containing a list of statement dicts

        Example:
            >>> categories = xbrl.statements.get_statements_by_category()
            >>> # Get all disclosures
            >>> disclosures = categories['disclosure']
            >>> for disc in disclosures:
            ...     print(f"{disc['index']}: {disc['title']}")
            >>>
            >>> # Get all notes
            >>> notes = categories['note']
            >>> # Get core financial statements
            >>> statements = categories['statement']
        """
        categories = {
            'statement': [],
            'note': [],
            'disclosure': [],
            'document': [],
            'other': []
        }

        for index, stmt in enumerate(self.statements):
            category = self.classify_statement(stmt)
            stmt_with_index = dict(stmt)
            stmt_with_index['index'] = index
            categories[category].append(stmt_with_index)

        return categories

    def _handle_statement_error(self, e: Exception, statement_type: str) -> Optional[Statement]:
        """
        Common error handler for statement resolution failures.

        Args:
            e: The exception that occurred
            statement_type: Type of statement that failed to resolve

        Returns:
            None (always, for consistency)
        """
        from edgar.core import log

        if isinstance(e, StatementNotFound):
            # Custom exception already has detailed context
            log.warning(str(e))
        else:
            # For other exceptions, extract context manually
            entity_name = getattr(self.xbrl, 'entity_name', 'Unknown')
            cik = getattr(self.xbrl, 'cik', 'Unknown')
            period_of_report = getattr(self.xbrl, 'period_of_report', 'Unknown')

            log.warning(
                f"Failed to resolve {statement_type.lower().replace('_', ' ')} for {entity_name} "
                f"(CIK: {cik}, Period: {period_of_report}): {type(e).__name__}: {str(e)}"
            )

        return None

    def find_statement_by_primary_concept(self, statement_type: str, is_parenthetical: bool = False) -> Optional[str]:
        """
        Find a statement by its primary concept.

        Args:
            statement_type: Statement type (e.g., 'BalanceSheet', 'IncomeStatement')
            is_parenthetical: Whether to look for a parenthetical statement
                             (only applicable for BalanceSheet)

        Returns:
            Role URI for the matching statement, or None if not found
        """
        if statement_type not in statement_to_concepts:
            return None

        # Get information about the statement's identifying concept
        concept_info = statement_to_concepts[statement_type]
        concept = concept_info.concept

        # Find all statements of the requested type
        matching_statements = self.statement_by_type.get(statement_type, [])

        if not matching_statements:
            return None

        # Parenthetical check is only relevant for BalanceSheet
        check_parenthetical = statement_type == 'BalanceSheet'

        # Try to find a statement containing the specific concept
        for stmt in matching_statements:
            role = stmt['role']

            # Check for parenthetical in the role name if it's a BalanceSheet
            if check_parenthetical:
                role_lower = role.lower()
                is_role_parenthetical = 'parenthetical' in role_lower

                # Skip if parenthetical status doesn't match what we're looking for
                if is_parenthetical != is_role_parenthetical:
                    continue

            # Examine the presentation tree for this role
            if role in self.xbrl.presentation_trees:
                tree = self.xbrl.presentation_trees[role]
                # Check if the identifying concept is in this tree
                normalized_concept = concept.replace(':', '_')
                for element_id in tree.all_nodes:
                    # Check both original and normalized form
                    if element_id == concept or element_id == normalized_concept:
                        return role

        # If no exact concept match, fall back to the first statement of the type
        # that matches the parenthetical requirement for BalanceSheet
        if check_parenthetical:
            for stmt in matching_statements:
                role = stmt['role']
                role_lower = role.lower()
                is_role_parenthetical = 'parenthetical' in role_lower

                if is_parenthetical == is_role_parenthetical:
                    return role

        # If still no match, return the first statement
        return matching_statements[0]['role']

    def __getitem__(self, item: Union[int, str]) -> Optional[Statement]:
        """
        Get a statement by index, type, or role.

        Args:
            item: Integer index, string statement type, or role URI

        Returns:
            Statement instance for the requested statement
        """
        if isinstance(item, int):
            if 0 <= item < len(self.statements):
                stmt = self.statements[item]
                # Get the canonical type if available
                canonical_type = None
                if stmt.get('type') in statement_to_concepts:
                    canonical_type = stmt.get('type')
                return Statement(self.xbrl, stmt['role'], canonical_type=canonical_type)
        elif isinstance(item, str):
            # Check if it's a standard statement type with a specific concept marker
            if item in statement_to_concepts:
                # Get the statement role using the primary concept
                role = self.find_statement_by_primary_concept(item)
                if role:
                    return Statement(self.xbrl, role, canonical_type=item)

                # If no concept match, fall back to the type
                return Statement(self.xbrl, item, canonical_type=item)

            # If it's a statement type with multiple statements, return the first one
            if item in self.statement_by_type and self.statement_by_type[item]:
                return Statement(self.xbrl, item, canonical_type=item)

            # Otherwise, try to use it directly as a role or statement name
            # Try to determine canonical type from the name
            canonical_type = None
            for std_type in statement_to_concepts.keys():
                if std_type.lower() in item.lower():
                    canonical_type = std_type
                    break
            return Statement(self.xbrl, item, canonical_type=canonical_type)

    def __rich__(self) -> Any:
        """
        Rich console representation.

        Returns:
            Rich Table object if rich is available, else string representation
        """
        if Table is None:
            return str(self)

        from rich.console import Group
        from rich.text import Text

        # Group statements by category using the extracted method
        statements_by_category = self.get_statements_by_category()

        # Create a table for each category that has statements
        tables = []

        # Define styles and titles for each category
        category_styles = {
            'statement': {'title': "Financial Statements", 'color': "green"},
            'note': {'title': "Notes to Financial Statements", 'color': "blue"},
            'disclosure': {'title': "Disclosures", 'color': "cyan"},
            'document': {'title': "Document Sections", 'color': "magenta"},
            'other': {'title': "Other Sections", 'color': "yellow"}
        }

        # Order of categories in the display
        category_order = ['statement', 'note', 'disclosure', 'document', 'other']

        for category in category_order:
            stmts = statements_by_category[category]
            if not stmts:
                continue

            # Create a table for this category
            style = category_styles[category]

            # Create title with color
            title = Text(style['title'])
            title.stylize(f"bold {style['color']}")

            table = Table(
                title=title,
                box=box.SIMPLE,
                title_justify="left",
                highlight=True
            )

            # Add columns
            table.add_column("#", style="dim", width=3)
            table.add_column("Name", style=style['color'])
            table.add_column("Type", style="italic")
            table.add_column("Parenthetical", width=14)

            # Sort statements by type and name for better organization
            # Handle None values to prevent TypeError when sorting
            sorted_stmts = sorted(stmts, key=lambda s: (s.get('type') or '', s.get('definition') or ''))

            # Add rows
            for stmt in sorted_stmts:
                # Check if this is a parenthetical statement
                is_parenthetical = False
                role_or_def = stmt.get('definition', '').lower()
                if 'parenthetical' in role_or_def:
                    is_parenthetical = True

                # Format parenthetical indicator
                parenthetical_text = "✓" if is_parenthetical else ""

                table.add_row(
                    str(stmt['index']),
                    stmt.get('definition', 'Untitled'),
                    stmt.get('type', '') or "",
                    parenthetical_text,
                )

            tables.append(table)

        # If no statements found in any category, show a message
        if not tables:
            return Text("No statements found")

        # Create a group containing all tables
        return Group(*tables)

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        """String representation with statements organized by category."""
        # Group statements by category
        statements_by_category = {
            'statement': [],
            'note': [],
            'disclosure': [],
            'document': [],
            'other': []
        }

        # The 'type' field will always exist, but 'category' may not
        for index, stmt in enumerate(self.statements):
            # Determine category based on either explicit category or infer from type
            category = stmt.get('category')
            if not category:
                # Fallback logic - infer category from type
                stmt_type = stmt.get('type', '')
                if stmt_type:
                    if 'Note' in stmt_type:
                        category = 'note'
                    elif 'Disclosure' in stmt_type:
                        category = 'disclosure'
                    elif stmt_type == 'CoverPage':
                        category = 'document'
                    elif stmt_type in ('BalanceSheet', 'IncomeStatement', 'CashFlowStatement', 
                                      'StatementOfEquity', 'ComprehensiveIncome') or 'Statement' in stmt_type:
                        category = 'statement'
                    else:
                        category = 'other'
                else:
                    category = 'other'

            # Add to the appropriate category
            statements_by_category[category].append((index, stmt))

        lines = ["Available Statements:"]

        # Define category titles and order
        category_titles = {
            'statement': "Financial Statements:",
            'note': "Notes to Financial Statements:",
            'disclosure': "Disclosures:",
            'document': "Document Sections:",
            'other': "Other Sections:"
        }

        category_order = ['statement', 'note', 'disclosure', 'document', 'other']

        for category in category_order:
            stmts = statements_by_category[category]
            if not stmts:
                continue

            lines.append("")
            lines.append(category_titles[category])

            # Sort statements by type and name for better organization
            # Handle None values to prevent TypeError when sorting
            sorted_stmts = sorted(stmts, key=lambda s: (s[1].get('type') or '', s[1].get('definition') or ''))

            for index, stmt in sorted_stmts:
                # Indicate if parenthetical
                is_parenthetical = 'parenthetical' in stmt.get('definition', '').lower()
                parenthetical_text = " (Parenthetical)" if is_parenthetical else ""

                lines.append(f"  {index}. {stmt.get('definition', 'Untitled')}{parenthetical_text}")

        if len(lines) == 1:  # Only the header is present
            lines.append("  No statements found")

        return "\n".join(lines)

    def cover_page(self) -> Statement:
        """
        Get the cover page statement.

        Returns:
            A cover page statement
        """
        role = self.find_statement_by_primary_concept("CoverPage")
        if role:
            return Statement(self.xbrl, role, canonical_type="CoverPage")

        # Try using the xbrl.render_statement with parenthetical parameter
        if hasattr(self.xbrl, 'find_statement'):
            matching_statements, found_role, _ = self.xbrl.find_statement("CoverPage")
            if found_role:
                return Statement(self.xbrl, found_role, canonical_type="CoverPage")

        return self["CoverPage"]

    def balance_sheet(self, parenthetical: bool = False) -> Optional[Statement]:
        """
        Get a balance sheet.

        Args:
            parenthetical: Whether to get the parenthetical balance sheet

        Returns:
            A balance sheet statement, or None if unable to resolve the statement
        """
        try:
            role = self.find_statement_by_primary_concept("BalanceSheet", is_parenthetical=parenthetical)
            if role:
                return Statement(self.xbrl, role, canonical_type="BalanceSheet")

            # Try using the xbrl.render_statement with parenthetical parameter
            if hasattr(self.xbrl, 'find_statement'):
                matching_statements, found_role, _ = self.xbrl.find_statement("BalanceSheet", parenthetical)
                if found_role:
                    return Statement(self.xbrl, found_role, canonical_type="BalanceSheet")

            return self["BalanceSheet"]
        except Exception as e:
            return self._handle_statement_error(e, "BalanceSheet")

    def income_statement(self, parenthetical: bool = False, skip_concept_check: bool = False) -> Optional[Statement]:
        """
        Get an income statement.

        Args:
            parenthetical: Whether to get the parenthetical income statement
            skip_concept_check: If True, skip checking for required concepts (useful for testing)

        Returns:
            An income statement, or None if unable to resolve the statement

        Note:
            To control dimensional display, use the include_dimensions parameter when calling
            render() or to_dataframe() on the returned Statement object.
        """
        try:
            # Try using the xbrl.find_statement with parenthetical parameter
            if hasattr(self.xbrl, 'find_statement'):
                matching_statements, found_role, _ = self.xbrl.find_statement("IncomeStatement", parenthetical)
                if found_role:
                    return Statement(self.xbrl, found_role, canonical_type="IncomeStatement", 
                                   skip_concept_check=skip_concept_check)

            return self["IncomeStatement"]
        except Exception as e:
            return self._handle_statement_error(e, "IncomeStatement")

    def cashflow_statement(self, parenthetical: bool = False) -> Optional[Statement]:
        """
        Get a cash flow statement.

        Args:
            parenthetical: Whether to get the parenthetical cash flow statement

        Returns:
             The cash flow statement, or None if unable to resolve the statement
        """
        try:
            # Try using the xbrl.find_statement with parenthetical parameter
            if hasattr(self.xbrl, 'find_statement'):
                matching_statements, found_role, _ = self.xbrl.find_statement("CashFlowStatement", parenthetical)
                if found_role:
                    return Statement(self.xbrl, found_role, canonical_type="CashFlowStatement")

            return self["CashFlowStatement"]
        except Exception as e:
            return self._handle_statement_error(e, "CashFlowStatement")

    def statement_of_equity(self, parenthetical: bool = False) -> Optional[Statement]:
        """
        Get a statement of equity.

        Args:
            parenthetical: Whether to get the parenthetical statement of equity

        Returns:
           The statement of equity, or None if unable to resolve the statement
        """
        try:
            # Try using the xbrl.find_statement with parenthetical parameter
            if hasattr(self.xbrl, 'find_statement'):
                matching_statements, found_role, _ = self.xbrl.find_statement("StatementOfEquity", parenthetical)
                if found_role:
                    return Statement(self.xbrl, found_role, canonical_type="StatementOfEquity")

            return self["StatementOfEquity"]
        except Exception as e:
            return self._handle_statement_error(e, "StatementOfEquity")

    def comprehensive_income(self, parenthetical: bool = False) -> Optional[Statement]:
        """
        Get a statement of comprehensive income.

        Comprehensive income includes net income plus other comprehensive income items
        such as foreign currency translation adjustments, unrealized gains/losses on
        investments, and pension adjustments.

        Args:
            parenthetical: Whether to get the parenthetical comprehensive income statement

        Returns:
            The comprehensive income statement, or None if unable to resolve the statement
        """
        try:
            # Try using the xbrl.find_statement with parenthetical parameter
            if hasattr(self.xbrl, 'find_statement'):
                matching_statements, found_role, _ = self.xbrl.find_statement("ComprehensiveIncome", parenthetical)
                if found_role:
                    return Statement(self.xbrl, found_role, canonical_type="ComprehensiveIncome")

            return self["ComprehensiveIncome"]
        except Exception as e:
            return self._handle_statement_error(e, "ComprehensiveIncome")

    def get_period_views(self, statement_type: str) -> List[Dict[str, Any]]:
        """
        Get available period views for a statement type.

        Args:
            statement_type: Type of statement to get period views for

        Returns:
            List of period view options
        """
        return self.xbrl.get_period_views(statement_type)

    def get_by_category(self, category: str) -> List[Statement]:
        """
        Get all statements of a specific category.

        Args:
            category: Category of statement to find ('statement', 'note', 'disclosure', 'document', or 'other')

        Returns:
            List of Statement objects matching the category
        """
        result = []

        # Find all statements with matching category
        for stmt in self.statements:
            if stmt.get('category') == category:
                result.append(Statement(self.xbrl, stmt['role']))

        return result

    def notes(self) -> List[Statement]:
        """
        Get all note sections.

        Returns:
            List of Statement objects for notes
        """
        return self.get_by_category('note')

    def disclosures(self) -> List[Statement]:
        """
        Get all disclosure sections.

        Returns:
            List of Statement objects for disclosures
        """
        return self.get_by_category('disclosure')

    def to_dataframe(self,
                     statement_type: str,
                     period_view: Optional[str] = None,
                     standard: bool = True,
                     include_dimensions: bool = True) -> Optional[pd.DataFrame]:
        """
        Convert a statement to a pandas DataFrame.

        Args:
            statement_type: Type of statement to convert
            period_view: Optional period view name
            standard: Whether to use standardized concept labels (default: True)
            include_dimensions: Whether to include dimensional segment data (default: True)

        Returns:
            pandas DataFrame containing the statement data
        """
        statement = self[statement_type]
        return statement.render(period_view=period_view, standard=standard, include_dimensions=include_dimensions).to_dataframe()


class StitchedStatement:
    """
    A stitched financial statement across multiple time periods.

    This class provides convenient methods for rendering and manipulating a stitched
    financial statement from multiple filings.
    """

    def __init__(self, xbrls, statement_type: str, max_periods: int = 8, standard: bool = True,
                 use_optimal_periods: bool = True, include_dimensions: bool = False):
        """
        Initialize with XBRLS object and statement parameters.

        Args:
            xbrls: XBRLS object containing stitched data
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
            max_periods: Maximum number of periods to include
            standard: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            include_dimensions: Whether to include dimensional segment data (default: False for stitching)
        """
        self.xbrls = xbrls
        self.statement_type = statement_type
        self.max_periods = max_periods
        self.standard = standard
        self.use_optimal_periods = use_optimal_periods
        self.include_dimensions = include_dimensions
        self.show_date_range = False  # Default to not showing date ranges

        # Statement titles
        self.statement_titles = {
            'BalanceSheet': 'CONSOLIDATED BALANCE SHEET',
            'IncomeStatement': 'CONSOLIDATED INCOME STATEMENT',
            'CashFlowStatement': 'CONSOLIDATED STATEMENT OF CASH FLOWS',
            'StatementOfEquity': 'CONSOLIDATED STATEMENT OF STOCKHOLDERS\' EQUITY',
            'ComprehensiveIncome': 'CONSOLIDATED STATEMENT OF COMPREHENSIVE INCOME'
        }
        self.title = self.statement_titles.get(statement_type, statement_type.upper())

        # Cache statement data
        self._statement_data = None

    @property
    def periods(self):
        return [
            period_id[-10:] for period_id, _ in self.statement_data['periods']
        ]

    @property
    def statement_data(self):
        """Get the underlying statement data, loading it if necessary."""
        if self._statement_data is None:
            self._statement_data = self.xbrls.get_statement(
                self.statement_type,
                self.max_periods,
                self.standard,
                self.use_optimal_periods,
                self.include_dimensions
            )
        return self._statement_data

    def render(self, show_date_range: bool = False) -> Table:
        """
        Render the stitched statement as a formatted table.

        Args:
            show_date_range: Whether to show full date ranges for duration periods

        Returns:
            Rich Table containing the rendered statement
        """
        from edgar.xbrl.stitching import render_stitched_statement

        # Update the render_stitched_statement function call to pass the show_date_range parameter
        return render_stitched_statement(
            self.statement_data,
            statement_title=self.title,
            statement_type=self.statement_type,
            entity_info=self.xbrls.entity_info,
            show_date_range=show_date_range
        )

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert the stitched statement to a pandas DataFrame.

        Returns:
            pandas DataFrame with periods as columns and concepts as rows
        """
        from edgar.xbrl.stitching import to_pandas

        return to_pandas(self.statement_data)

    def __rich__(self):
        """
        Rich console representation.

        Returns:
            Rich Table object
        """
        return self.render()

    def __repr__(self):
        return repr_rich(self.__rich__())


class StitchedStatements:
    """
    User-friendly access to stitched financial statements across multiple time periods.

    This class provides a simplified API for accessing and rendering stitched financial
    statements from multiple filings, without requiring detailed knowledge of the
    underlying stitching process.
    """

    def __init__(self, xbrls):
        """
        Initialize with an XBRLS object.

        Args:
            xbrls: The XBRLS object to extract stitched statements from
        """
        self.xbrls = xbrls

    def balance_sheet(self, max_periods: int = 8, standard: bool = True,
                      use_optimal_periods: bool = True, show_date_range: bool = False) -> Optional[StitchedStatement]:
        """
        Get a stitched balance sheet across multiple time periods.

        Args:
            max_periods: Maximum number of periods to include
            standard: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            show_date_range: Whether to show full date ranges for duration periods

        Returns:
            StitchedStatement for the balance sheet
        """
        statement = StitchedStatement(self.xbrls, 'BalanceSheet', max_periods, standard, use_optimal_periods)
        if show_date_range:
            statement.show_date_range = show_date_range
        return statement

    def income_statement(self, max_periods: int = 8, standard: bool = True,
                         use_optimal_periods: bool = True, show_date_range: bool = False) -> Optional[StitchedStatement]:
        """
        Get a stitched income statement across multiple time periods.

        Args:
            max_periods: Maximum number of periods to include
            standard: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            show_date_range: Whether to show full date ranges for duration periods

        Returns:
            StitchedStatement for the income statement
        """
        statement = StitchedStatement(self.xbrls, 'IncomeStatement', max_periods, standard, use_optimal_periods)
        if show_date_range:
            statement.show_date_range = show_date_range
        return statement

    def cashflow_statement(self, max_periods: int = 8, standard: bool = True,
                           use_optimal_periods: bool = True, show_date_range: bool = False) -> Optional[StitchedStatement]:
        """
        Get a stitched cash flow statement across multiple time periods.

        Args:
            max_periods: Maximum number of periods to include
            standard: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            show_date_range: Whether to show full date ranges for duration periods

        Returns:
            StitchedStatement for the cash flow statement
        """
        statement = StitchedStatement(self.xbrls, 'CashFlowStatement', max_periods, standard, use_optimal_periods)
        if show_date_range:
            statement.show_date_range = show_date_range
        return statement

    def statement_of_equity(self, max_periods: int = 8, standard: bool = True,
                            use_optimal_periods: bool = True, show_date_range: bool = False) -> Optional[StitchedStatement]:
        """
        Get a stitched statement of changes in equity across multiple time periods.

        Args:
            max_periods: Maximum number of periods to include
            standard: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            show_date_range: Whether to show full date ranges for duration periods

        Returns:
            StitchedStatement for the statement of equity
        """
        statement = StitchedStatement(self.xbrls, 'StatementOfEquity', max_periods, standard, use_optimal_periods)
        if show_date_range:
            statement.show_date_range = show_date_range
        return statement

    def comprehensive_income(self, max_periods: int = 8, standard: bool = True,
                             use_optimal_periods: bool = True, show_date_range: bool = False) -> Optional[StitchedStatement]:
        """
        Get a stitched statement of comprehensive income across multiple time periods.

        Args:
            max_periods: Maximum number of periods to include
            standard: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            show_date_range: Whether to show full date ranges for duration periods

        Returns:
            StitchedStatement for the comprehensive income statement
        """
        statement = StitchedStatement(self.xbrls, 'ComprehensiveIncome', max_periods, standard, use_optimal_periods)
        if show_date_range:
            statement.show_date_range = show_date_range
        return statement

    def __getitem__(self, statement_type: str) -> StitchedStatement:
        """
        Get a statement by type using dictionary syntax.

        Args:
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)

        Returns:
            StitchedStatement for the requested statement type
        """
        return StitchedStatement(self.xbrls, statement_type, use_optimal_periods=True)

    def __rich__(self):
        """
        Rich console representation.

        Returns:
            Rich Table object
        """
        table = Table(title="Available Stitched Statements", box=box.SIMPLE)
        table.add_column("Statement Type")
        table.add_column("Periods")

        # Get information about available statements
        statement_types = set()
        for xbrl in self.xbrls.xbrl_list:
            statements = xbrl.get_all_statements()
            for stmt in statements:
                if stmt['type']:
                    statement_types.add(stmt['type'])

        # Get periods
        periods = self.xbrls.get_periods()
        period_count = len(periods)

        # Add rows for each statement type
        for stmt_type in sorted(statement_types):
            table.add_row(stmt_type, str(period_count))

        return table

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self) -> str:
        """
        String representation listing available statements.

        Returns:
            String representation
        """
        # Get information about available statements
        statement_types = set()
        for xbrl in self.xbrls.xbrl_list:
            statements = xbrl.get_all_statements()
            for stmt in statements:
                if stmt['type']:
                    statement_types.add(stmt['type'])

        # Get information about periods
        periods = self.xbrls.get_periods()
        period_count = len(periods)

        # Format output
        output = [f"Stitched statements across {period_count} periods:"]
        for stmt_type in sorted(statement_types):
            output.append(f"  - {stmt_type}")

        output.append("\nAvailable methods:")
        output.append("  - balance_sheet()")
        output.append("  - income_statement()")
        output.append("  - cash_flow_statement()")

        return "\n".join(output)
