"""
Financial ratio analysis module for XBRL data.

This module provides a comprehensive set of financial ratio calculations
for analyzing company performance, efficiency, and financial health using
DataFrame operations for handling multiple periods efficiently.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Mapping, Optional, Tuple, Union

import pandas as pd
from pandas import Index
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.richtools import repr_rich
from edgar.xbrl.standardization import MappingStore, StandardConcept


@dataclass
class ConceptEquivalent:
    """Defines an equivalent calculation for a missing concept."""
    target_concept: str
    required_concepts: List[str]
    calculation: Callable[[pd.DataFrame, str], float]
    description: str


@dataclass
class RatioAnalysisGroup:
    """Container for a group of related ratio analyses.
    
    Attributes:
        name: Name of the ratio group (e.g. 'Profitability Ratios')
        description: Description of what these ratios measure
        ratios: Dict mapping ratio names to their RatioAnalysis objects
    """
    name: str
    description: str
    ratios: Dict[str, 'RatioAnalysis']

    def __rich__(self):
        headers = [""] + next(iter(self.ratios.values())).results.columns.tolist()
        table = Table(*headers, box=box.SIMPLE)
        renderables = [table]

        for ratio in self.ratios.values():
            for record in ratio.results.itertuples():
                values = [Text(f"{v:.2f}", justify="right") for v in record[1:]]
                row = [ratio.name] + values
                table.add_row(*row)

        panel = Panel(Group(*renderables),
                      title=self.name,
                      expand=False)
        return panel

    def __repr__(self) -> str:
        return repr_rich(self.__rich__())


@dataclass
class RatioData:
    """Container for financial ratio calculation data.
    
    Attributes:
        calculation_df: DataFrame containing the raw data for calculation
        periods: List of available reporting periods
        equivalents_used: Dictionary mapping concepts to their equivalent descriptions
        required_concepts: List of concepts required for the ratio
        optional_concepts: Dictionary mapping optional concepts to their default values
    """
    calculation_df: pd.DataFrame
    periods: List[str]
    equivalents_used: Dict[str, str]
    required_concepts: List[str]
    optional_concepts: Dict[str, float]
    
    def has_concept(self, concept: str) -> bool:
        """Check if a concept is available in the calculation DataFrame.
        
        Args:
            concept: The concept to check
            
        Returns:
            True if the concept exists and has at least one non-NaN value
        """
        if concept not in self.calculation_df.index:
            return False
        return not self.calculation_df.loc[concept].isna().all()
    
    def get_concept(self, concept: str, default_value: Optional[float] = None) -> pd.Series:
        """Get a concept's values for all periods.
        
        Args:
            concept: The concept to retrieve
            default_value: Default value to use if concept is not found (only for optional concepts)
            
        Returns:
            Series containing the concept values indexed by period
            
        Raises:
            KeyError: If concept is required but not found and no default is provided
        """
        if self.has_concept(concept):
            return self.calculation_df.loc[concept]
            
        # Concept not found or all NaN
        if concept in self.required_concepts and default_value is None:
            raise KeyError(f"Required concept {concept} not found")
            
        # Optional concept with default value or required concept with default override
        if default_value is not None:
            # Create Series of default values for all periods
            return pd.Series(default_value, index=self.periods)
            
        # Check if we have a predefined default for this optional concept
        if concept in self.optional_concepts:
            return pd.Series(self.optional_concepts[concept], index=self.periods)
            
        raise KeyError(f"Concept {concept} not found and no default value provided")
        
    def get_concepts(self, concepts: List[str]) -> Dict[str, pd.Series]:
        """Get multiple concepts at once.
        
        Args:
            concepts: List of concepts to retrieve
            
        Returns:
            Dictionary mapping concepts to their value Series
            
        Raises:
            KeyError: If any required concept is not found
        """
        return {concept: self.get_concept(concept) for concept in concepts}

@dataclass
class RatioAnalysis:
    """Container for ratio calculation results with metadata.
    
    Attributes:
        name: Name of the ratio
        description: Description of what the ratio measures
        calculation_df: DataFrame containing the raw data used in calculation
        results: Series containing the calculated ratio values
        components: Dict mapping component names to their value Series
        equivalents_used: Dict mapping concepts to their equivalent descriptions
    """
    name: str
    description: str
    calculation_df: pd.DataFrame
    results: pd.Series
    components: Dict[str, pd.Series]
    equivalents_used: Mapping[str, str]

    def __rich__(self):
        headers = [""] + self.results.columns.tolist()
        table = Table(*headers, box=box.SIMPLE)
        renderables = [table]
        for record in self.results.itertuples():
            values = [Text(f"{v:.2f}", justify="right") for v in record[1:]]
            row = [self.name] + values
            table.add_row(*row)

        panel = Panel(Group(*renderables),
                      title=self.name,
                      expand=False)
        return panel

    def __repr__(self) -> str:
        return repr_rich(self.__rich__())


class FinancialRatios:
    """Calculate and analyze financial ratios from XBRL data using DataFrame operations."""

    def __init__(self, xbrl):
        """Initialize with an XBRL instance.
        
        Args:
            xbrl: XBRL instance containing financial statements
        """
        self.xbrl = xbrl

        # Initialize concept mappings and equivalents
        self._mapping_store = MappingStore()
        self._concept_equivalents = self._initialize_concept_equivalents()

        # Get rendered statements
        bs = self.xbrl.statements.balance_sheet()
        is_ = self.xbrl.statements.income_statement()
        cf = self.xbrl.statements.cashflow_statement()

        # Convert to DataFrames with consistent periods
        bs_rendered = bs.render()
        is_rendered = is_.render()
        cf_rendered = cf.render()

        self.balance_sheet_df = bs_rendered.to_dataframe()
        self.income_stmt_df = is_rendered.to_dataframe()
        self.cash_flow_df = cf_rendered.to_dataframe()

        # Get all unique periods across statements
        self.periods = sorted(set(
            str(p.end_date) for p in bs_rendered.periods +
            is_rendered.periods + cf_rendered.periods
        ))

    def _prepare_ratio_df(self, required_concepts: List[str], statement_dfs: List[Tuple[pd.DataFrame, str]],
                          optional_concepts: List[str] = []) -> Tuple[pd.DataFrame, Dict[str, str]]:
        """Prepare DataFrame for ratio calculations.
        
        Args:
            required_concepts: List of concepts required for the ratio calculation
            statement_dfs: List of tuples containing statement DataFrames and their types
            optional_concepts: List of concepts that are optional for the calculation
            
        Returns:
            Tuple containing:
                - DataFrame with required concepts as columns
                - Dictionary mapping concepts to their equivalent descriptions (non-None values only)
        """
        """Prepare a DataFrame for ratio calculation.
        
        Args:
            required_concepts: List of concepts required for the ratio
            statement_dfs: List of (DataFrame, statement_type) tuples to search for concepts
            
        Returns:
            Tuple containing:
            - DataFrame with concepts as index and periods as columns
            - Dictionary mapping concepts to their equivalent descriptions if used
        """
        # Get the set of periods available in each statement
        available_periods = set()
        for df, _ in statement_dfs:
            # Get columns that are periods (exclude 'concept', 'label', etc)
            period_cols = [col for col in df.columns if col in self.periods]
            if not available_periods:
                available_periods = set(period_cols)
            else:
                available_periods &= set(period_cols)

        if not available_periods:
            raise ValueError("No common periods found across required statements")

        all_concepts = required_concepts + optional_concepts
        # Create empty DataFrame with only the common periods
        calc_df = pd.DataFrame(index=pd.Index(all_concepts), columns=Index(sorted(available_periods)))

        # Track which concepts used equivalents
        equivalents_used = {}

        # Fill values from each statement
        for concept in all_concepts:
            found = False
            # First try to find matching company concepts from the mapping store
            if concept in self._mapping_store.mappings:
                company_concepts = self._mapping_store.mappings[concept]
                for df, statement_type in statement_dfs:
                    # Check each possible company concept
                    for company_concept in company_concepts:
                        mask = df['concept'] == company_concept
                        if mask.any():
                            matching_row = df[mask].iloc[0]
                            # Only copy values for available periods
                            calc_df.loc[concept] = matching_row[calc_df.columns]
                            found = True
                            break
                    if found:
                        break

            # If not found via mappings, try direct concept match
            if not found:
                for df, statement_type in statement_dfs:
                    mask = df['concept'] == concept
                    if mask.any():
                        matching_row = df[mask].iloc[0]
                        # Only copy values for available periods
                        calc_df.loc[concept] = matching_row[calc_df.columns]
                        found = True
                        break

            # If still not found, try matching by label
            if not found:
                for df, statement_type in statement_dfs:
                    # Get label column if it exists
                    if 'label' in df.columns:
                        mask = df['label'].str.contains(concept, case=False, na=False)
                        if mask.any():
                            matching_row = df[mask].iloc[0]
                            # Only copy values for available periods
                            calc_df.loc[concept] = matching_row[calc_df.columns]
                            found = True
                            break

            # If still not found or all NaN, try concept equivalents
            if not found or calc_df.loc[concept].isna().all():
                if concept in self._concept_equivalents:
                    for equivalent in self._concept_equivalents[concept]:
                        try:
                            # Recursively prepare data for required concepts
                            sub_df, sub_equiv = self._prepare_ratio_df(
                                equivalent.required_concepts, statement_dfs)

                            # Calculate equivalent value for each period
                            for period in calc_df.columns:
                                calc_df.loc[concept, period] = equivalent.calculation(sub_df, period)

                            # Track that we used this equivalent
                            equivalents_used[concept] = equivalent.description
                            # Also include any equivalents used by subconcepts
                            equivalents_used.update(sub_equiv)
                            found = True
                            break
                        except (KeyError, ValueError, ZeroDivisionError):
                            continue

            if not found and concept not in optional_concepts:
                raise KeyError(f"Could not find or calculate required concept: {concept}")

        # Filter out None values from equivalents and ensure all values are strings
        filtered_equivalents = {k: str(v) for k, v in equivalents_used.items() if v is not None}

        # Return the prepared DataFrame and filtered equivalents
        return calc_df, filtered_equivalents

    def _initialize_concept_equivalents(self) -> Dict[str, List[ConceptEquivalent]]:
        """Initialize the concept equivalents mapping.
        
        Returns:
            Dictionary mapping concepts to their possible equivalent calculations.
        """
        return {
            StandardConcept.GROSS_PROFIT: [
                ConceptEquivalent(
                    target_concept=StandardConcept.GROSS_PROFIT,
                    required_concepts=[
                        StandardConcept.REVENUE,
                        StandardConcept.COST_OF_REVENUE
                    ],
                    calculation=lambda df, period: (
                            df.loc[StandardConcept.REVENUE, period] -
                            df.loc[StandardConcept.COST_OF_REVENUE, period]
                    ),
                    description="Revenue - Cost of Revenue"
                )
            ],
            StandardConcept.OPERATING_INCOME: [
                ConceptEquivalent(
                    target_concept=StandardConcept.OPERATING_INCOME,
                    required_concepts=[
                        StandardConcept.GROSS_PROFIT,
                        StandardConcept.OPERATING_EXPENSES
                    ],
                    calculation=lambda df, period: (
                            df.loc[StandardConcept.GROSS_PROFIT, period] -
                            df.loc[StandardConcept.OPERATING_EXPENSES, period]
                    ),
                    description="Gross Profit - Operating Expenses"
                )
            ]
        }

    def _get_concept_value(self, concept: str, calc_df: pd.DataFrame) -> Tuple[pd.Series, Optional[str]]:
        """Get a concept value from the calculation DataFrame.
        
        If the concept is not directly available or is all NaN, try to calculate it using equivalents.
        
        Args:
            concept: The concept to retrieve
            calc_df: DataFrame containing the raw data
            
        Returns:
            Tuple of (value Series, equivalent description if used)
            
        Raises:
            KeyError: If concept is not found and no valid equivalents are available
        """
        # First try to get the direct value
        try:
            value = calc_df.loc[concept]
            # Check if we actually have any non-NaN values
            if not value.isna().all():
                return value, None
        except KeyError:
            pass

        # If we get here, either the concept wasn't found or was all NaN
        # Try to use concept equivalents
        if concept in self._concept_equivalents:
            for equivalent in self._concept_equivalents[concept]:
                try:
                    # Check if all required concepts are available and have values
                    for req in equivalent.required_concepts:
                        if req not in calc_df.index:
                            continue

                    # Calculate equivalent value for each period
                    values = pd.Series(index=calc_df.columns)
                    for period in calc_df.columns:
                        values[period] = equivalent.calculation(calc_df, period)

                    return values, equivalent.description
                except (KeyError, ZeroDivisionError):
                    continue

        # If we get here, no valid concept or equivalent was found
        raise KeyError(f"Concept {concept} not found and no valid equivalents available")

    def get_ratio_data(self, ratio_type: str) -> RatioData:
        """Get the prepared ratio data for a specific ratio calculation.
        
        This allows inspection of the raw data before ratio calculation.
        
        Args:
            ratio_type: Type of ratio to get data for ('current', 'operating_margin', 
                       'return_on_assets', 'gross_margin', 'leverage')
                       
        Returns:
            RatioData object containing calculation data and helper methods for accessing concepts
        """
        # Default values for optional concepts (used when concept is not found)
        default_values = {
            StandardConcept.INVENTORY: 0.0,  # For quick ratio when inventory not found
        }
        
        ratio_configs = {
            'current': {
                'concepts': [
                    StandardConcept.TOTAL_CURRENT_ASSETS,
                    StandardConcept.TOTAL_CURRENT_LIABILITIES,
                    StandardConcept.CASH_AND_EQUIVALENTS  # For cash ratio
                ],
                'optional_concepts': {
                    StandardConcept.INVENTORY: 0.0  # Optional for quick ratio
                },
                'statements': [(self.balance_sheet_df, "BalanceSheet")]
            },
            'operating_margin': {
                'concepts': [
                    StandardConcept.OPERATING_INCOME,
                    StandardConcept.REVENUE
                ],
                'optional_concepts': {},
                'statements': [(self.income_stmt_df, "IncomeStatement")]
            },
            'return_on_assets': {
                'concepts': [
                    StandardConcept.NET_INCOME,
                    StandardConcept.TOTAL_ASSETS
                ],
                'optional_concepts': {},
                'statements': [
                    (self.income_stmt_df, "IncomeStatement"),
                    (self.balance_sheet_df, "BalanceSheet")
                ]
            },
            'gross_margin': {
                'concepts': [
                    StandardConcept.GROSS_PROFIT,
                    StandardConcept.REVENUE
                ],
                'optional_concepts': {},
                'statements': [(self.income_stmt_df, "IncomeStatement")]
            },
            'leverage': {
                'concepts': [
                    StandardConcept.LONG_TERM_DEBT,
                    StandardConcept.TOTAL_EQUITY,
                    StandardConcept.TOTAL_ASSETS,
                    StandardConcept.OPERATING_INCOME,
                    StandardConcept.INTEREST_EXPENSE
                ],
                'optional_concepts': {},
                'statements': [
                    (self.balance_sheet_df, "BalanceSheet"),
                    (self.income_stmt_df, "IncomeStatement")
                ]
            }
        }

        if ratio_type not in ratio_configs:
            raise ValueError(f"Unknown ratio type: {ratio_type}. Valid types are: {list(ratio_configs.keys())}")

        config = ratio_configs[ratio_type]
        # Convert optional_concepts from list to dict if it's still in the old format
        optional_concepts_dict = config.get('optional_concepts', {})
        if isinstance(optional_concepts_dict, list):
            # Convert list to dict using default values
            optional_concepts_dict = {
                concept: default_values.get(concept, 0.0) 
                for concept in optional_concepts_dict
            }
            
        # Get the concepts and equivalents using the old method
        calc_df, equivalents = self._prepare_ratio_df(
            required_concepts=config['concepts'],
            statement_dfs=config['statements'],
            optional_concepts=list(optional_concepts_dict.keys())
        )
        
        # Create and return the RatioData object
        return RatioData(
            calculation_df=calc_df,
            periods=calc_df.columns.tolist(),
            equivalents_used=equivalents,
            required_concepts=config['concepts'],
            optional_concepts=optional_concepts_dict
        )

    def calculate_current_ratio(self) -> RatioAnalysis:
        """Calculate current ratio for all periods.
        
        Current Ratio = Current Assets / Current Liabilities
        """
        ratio_data = self.get_ratio_data('current')

        try:
            # Get required concepts directly from RatioData
            current_assets = ratio_data.get_concept(StandardConcept.TOTAL_CURRENT_ASSETS)
            current_liab = ratio_data.get_concept(StandardConcept.TOTAL_CURRENT_LIABILITIES)

            # Collect equivalent descriptions if any were used
            equivalents_used = {}
            if StandardConcept.TOTAL_CURRENT_ASSETS in ratio_data.equivalents_used:
                equivalents_used['current_assets'] = ratio_data.equivalents_used[StandardConcept.TOTAL_CURRENT_ASSETS]
            if StandardConcept.TOTAL_CURRENT_LIABILITIES in ratio_data.equivalents_used:
                equivalents_used['current_liabilities'] = ratio_data.equivalents_used[StandardConcept.TOTAL_CURRENT_LIABILITIES]

            return RatioAnalysis(
                name="Current Ratio",
                description="Measures ability to pay short-term obligations",
                calculation_df=ratio_data.calculation_df,
                results=(current_assets / current_liab).to_frame().T,
                components={
                    'current_assets': current_assets,
                    'current_liabilities': current_liab
                },
                equivalents_used={k: str(v) for k, v in equivalents_used.items() if v is not None}
            )
        except (KeyError, ZeroDivisionError) as e:
            raise ValueError(f"Failed to calculate current ratio: {str(e)}")

    def calculate_return_on_assets(self) -> RatioAnalysis:
        """Calculate return on assets for all periods.
        
        ROA = Net Income / Average Total Assets
        """
        calc_df, equivalents = self.get_ratio_data('return_on_assets')

        try:
            net_income, income_equiv = self._get_concept_value(
                StandardConcept.NET_INCOME, calc_df)
            total_assets, assets_equiv = self._get_concept_value(
                StandardConcept.TOTAL_ASSETS, calc_df)

            # Calculate average total assets using shift
            prev_assets = total_assets.shift(1)
            avg_assets = (total_assets + prev_assets.fillna(total_assets)) / 2

            equivalents_used = {}
            if income_equiv:
                equivalents_used['net_income'] = income_equiv
            if assets_equiv:
                equivalents_used['total_assets'] = assets_equiv

            return RatioAnalysis(
                name="Return on Assets",
                description="Measures how efficiently company uses its assets to generate earnings",
                calculation_df=calc_df,
                results=(net_income / avg_assets).to_frame().T,
                components={
                    'net_income': net_income,
                    'average_total_assets': avg_assets
                },
                equivalents_used={k: str(v) for k, v in (equivalents_used or {}).items() if v is not None}
            )
        except (KeyError, ZeroDivisionError) as e:
            raise ValueError(f"Failed to calculate return on assets: {str(e)}")

    def calculate_operating_margin(self) -> RatioAnalysis:
        """Calculate operating margin for all periods.
        
        Operating Margin = Operating Income / Revenue
        """
        calc_df, equivalents = self.get_ratio_data('operating_margin')

        try:
            operating_income, income_equiv = self._get_concept_value(
                StandardConcept.OPERATING_INCOME, calc_df)
            revenue, revenue_equiv = self._get_concept_value(
                StandardConcept.REVENUE, calc_df)

            equivalents_used = {}
            if income_equiv:
                equivalents_used['operating_income'] = income_equiv
            if revenue_equiv:
                equivalents_used['revenue'] = revenue_equiv

            return RatioAnalysis(
                name="Operating Margin",
                description="Measures operating efficiency and pricing strategy",
                calculation_df=calc_df,
                results=(operating_income / revenue).to_frame().T,
                components={
                    'operating_income': operating_income,
                    'revenue': revenue
                },
                equivalents_used={k: str(v) for k, v in (equivalents_used or {}).items() if v is not None}
            )
        except (KeyError, ZeroDivisionError) as e:
            raise ValueError(f"Failed to calculate operating margin: {str(e)}")

    def calculate_gross_margin(self) -> RatioAnalysis:
        """Calculate gross margin for all periods.
        
        Gross Margin = Gross Profit / Revenue
        
        Note: If Gross Profit is not directly available, it will be calculated as
        Revenue - Cost of Revenue.
        """
        calc_df, equivalents = self.get_ratio_data('gross_margin')

        try:
            gross_profit, profit_equiv = self._get_concept_value(
                StandardConcept.GROSS_PROFIT, calc_df)
            revenue, revenue_equiv = self._get_concept_value(
                StandardConcept.REVENUE, calc_df)

            equivalents_used = {}
            if profit_equiv:
                equivalents_used['gross_profit'] = profit_equiv
            if revenue_equiv:
                equivalents_used['revenue'] = revenue_equiv

            return RatioAnalysis(
                name="Gross Margin",
                description="Measures basic profitability from core business activities",
                calculation_df=calc_df,
                results=(gross_profit / revenue).to_frame().T,
                components={
                    'gross_profit': gross_profit,
                    'revenue': revenue
                },
                equivalents_used={k: str(v) for k, v in (equivalents_used or {}).items() if v is not None}
            )
        except (KeyError, ZeroDivisionError) as e:
            raise ValueError(f"Failed to calculate gross margin: {str(e)}")

    def calculate_quick_ratio(self) -> RatioAnalysis:
        """Calculate quick ratio for all periods.
        
        Quick Ratio = (Current Assets - Inventory) / Current Liabilities
        Also known as the Acid Test Ratio.
        
        Note:
            If inventory is not found in the financial statements, it will be treated as 0.
            This is appropriate for service companies or companies that do not carry inventory.
            In such cases, the quick ratio will equal the current ratio.
        """
        ratio_data = self.get_ratio_data('current')

        try:
            # Get concepts with defaults handling
            current_assets = ratio_data.get_concept(StandardConcept.TOTAL_CURRENT_ASSETS)
            current_liab = ratio_data.get_concept(StandardConcept.TOTAL_CURRENT_LIABILITIES)
            
            # Get inventory with default 0 - the RatioData class handles missing inventory
            inventory = ratio_data.get_concept(StandardConcept.INVENTORY)
            
            # Calculate quick assets
            quick_assets = current_assets - inventory

            # Collect equivalent descriptions for used concepts
            equivalents_used = {}
            if StandardConcept.TOTAL_CURRENT_ASSETS in ratio_data.equivalents_used:
                equivalents_used['current_assets'] = ratio_data.equivalents_used[StandardConcept.TOTAL_CURRENT_ASSETS]
            if StandardConcept.TOTAL_CURRENT_LIABILITIES in ratio_data.equivalents_used:
                equivalents_used['current_liabilities'] = ratio_data.equivalents_used[StandardConcept.TOTAL_CURRENT_LIABILITIES]
            if StandardConcept.INVENTORY in ratio_data.equivalents_used:
                equivalents_used['inventory'] = ratio_data.equivalents_used[StandardConcept.INVENTORY]
            elif not ratio_data.has_concept(StandardConcept.INVENTORY):
                # If inventory was using the default and wasn't in equivalents
                equivalents_used['inventory'] = "Treated as 0 (not found in statements)"

            return RatioAnalysis(
                name="Quick Ratio",
                description="Measures ability to pay short-term obligations using only highly liquid assets",
                calculation_df=ratio_data.calculation_df,
                results=(quick_assets / current_liab).to_frame().T,
                components={
                    'quick_assets': quick_assets,
                    'current_liabilities': current_liab,
                    'inventory': inventory
                },
                equivalents_used={k: str(v) for k, v in equivalents_used.items() if v is not None}
            )
        except (KeyError, ZeroDivisionError) as e:
            raise ValueError(f"Failed to calculate quick ratio: {str(e)}")

    def calculate_cash_ratio(self) -> RatioAnalysis:
        """Calculate cash ratio for all periods.
        
        Cash Ratio = Cash / Current Liabilities
        Measures ability to pay short-term obligations using only cash.
        """
        calc_df, equivalents = self.get_ratio_data('current')

        try:
            cash, cash_equiv = self._get_concept_value(
                StandardConcept.CASH, calc_df)
            current_liab, liab_equiv = self._get_concept_value(
                StandardConcept.TOTAL_CURRENT_LIABILITIES, calc_df)

            equivalents_used = {}
            if cash_equiv:
                equivalents_used['cash'] = cash_equiv
            if liab_equiv:
                equivalents_used['current_liabilities'] = liab_equiv

            return RatioAnalysis(
                name="Cash Ratio",
                description="Measures ability to pay short-term obligations using only cash",
                calculation_df=calc_df,
                results=(cash / current_liab).to_frame().T,
                components={
                    'cash': cash,
                    'current_liabilities': current_liab
                },
                equivalents_used={k: str(v) for k, v in (equivalents_used or {}).items() if v is not None}
            )
        except (KeyError, ZeroDivisionError) as e:
            raise ValueError(f"Failed to calculate cash ratio: {str(e)}")

    def calculate_working_capital(self) -> RatioAnalysis:
        """Calculate working capital for all periods.
        
        Working Capital = Current Assets - Current Liabilities
        Measures short-term financial health.
        """
        calc_df, equivalents = self.get_ratio_data('current')

        try:
            current_assets, assets_equiv = self._get_concept_value(
                StandardConcept.TOTAL_CURRENT_ASSETS, calc_df)
            current_liab, liab_equiv = self._get_concept_value(
                StandardConcept.TOTAL_CURRENT_LIABILITIES, calc_df)

            equivalents_used = {}
            if assets_equiv:
                equivalents_used['current_assets'] = assets_equiv
            if liab_equiv:
                equivalents_used['current_liabilities'] = liab_equiv

            working_capital = current_assets - current_liab

            return RatioAnalysis(
                name="Working Capital",
                description="Measures short-term financial health",
                calculation_df=calc_df,
                results=working_capital.to_frame().T,
                components={
                    'current_assets': current_assets,
                    'current_liabilities': current_liab
                },
                equivalents_used={k: str(v) for k, v in (equivalents_used or {}).items() if v is not None}
            )
        except (KeyError, ZeroDivisionError) as e:
            raise ValueError(f"Failed to calculate working capital: {str(e)}")

    def calculate_profitability_ratios(self) -> RatioAnalysisGroup:
        """Calculate profitability ratios.
        
        Returns:
            RatioAnalysisGroup containing:
            - gross_margin
            - operating_margin
            - net_margin
            - return_on_assets
            - return_on_equity
        """
        calc_df, equivalents = self.get_ratio_data('profitability')

        try:
            revenue, revenue_equiv = self._get_concept_value(StandardConcept.REVENUE, calc_df)
            gross_profit, profit_equiv = self._get_concept_value(StandardConcept.GROSS_PROFIT, calc_df)
            operating_income, income_equiv = self._get_concept_value(StandardConcept.OPERATING_INCOME, calc_df)
            net_income, net_equiv = self._get_concept_value(StandardConcept.NET_INCOME, calc_df)
            total_assets, assets_equiv = self._get_concept_value(StandardConcept.TOTAL_ASSETS, calc_df)
            total_equity, equity_equiv = self._get_concept_value(StandardConcept.TOTAL_EQUITY, calc_df)

            results = {}

            # Margin Ratios
            if gross_profit is not None:
                results['gross_margin'] = RatioAnalysis(
                    name="Gross Margin",
                    description="Measures basic profitability from core business activities",
                    calculation_df=calc_df,
                    results=(gross_profit / revenue).to_frame().T,
                    components={
                        'gross_profit': gross_profit,
                        'revenue': revenue
                    },
                    equivalents_used={k: str(v) for k, v in {'gross_profit': profit_equiv}.items() if v is not None}
                )

            if operating_income is not None:
                results['operating_margin'] = RatioAnalysis(
                    name="Operating Margin",
                    description="Measures operating efficiency and pricing strategy",
                    calculation_df=calc_df,
                    results=(operating_income / revenue).to_frame().T,
                    components={
                        'operating_income': operating_income,
                        'revenue': revenue
                    },
                    equivalents_used={k: str(v) for k, v in {'operating_income': income_equiv}.items() if v is not None}
                )

            if net_income is not None:
                results['net_margin'] = RatioAnalysis(
                    name="Net Margin",
                    description="Measures overall profitability after all expenses",
                    calculation_df=calc_df,
                    results=(net_income / revenue).to_frame().T,
                    components={
                        'net_income': net_income,
                        'revenue': revenue
                    },
                    equivalents_used={k: str(v) for k, v in {'net_income': net_equiv}.items() if v is not None}
                )

                # Return on Assets
                if total_assets is not None:
                    results['return_on_assets'] = RatioAnalysis(
                        name="Return on Assets",
                        description="Measures how efficiently company uses its assets to generate earnings",
                        calculation_df=calc_df,
                        results=(net_income / total_assets).to_frame().T,
                        components={
                            'net_income': net_income,
                            'total_assets': total_assets
                        },
                        equivalents_used={k: str(v) for k, v in {
                            'net_income': net_equiv,
                            'total_assets': assets_equiv
                        }.items() if v is not None}
                    )

                # Return on Equity
                if total_equity is not None:
                    results['return_on_equity'] = RatioAnalysis(
                        name="Return on Equity",
                        description="Measures return on shareholder investment",
                        calculation_df=calc_df,
                        results=(net_income / total_equity).to_frame().T,
                        components={
                            'net_income': net_income,
                            'total_equity': total_equity
                        },
                        equivalents_used={k: str(v) for k, v in {
                            'net_income': net_equiv,
                            'total_equity': equity_equiv
                        }.items() if v is not None}
                    )

            return RatioAnalysisGroup(
                name="Profitability Ratios",
                description="Measures of company's ability to generate profits and returns",
                ratios=results
            )

        except (KeyError, ZeroDivisionError) as e:
            raise ValueError(f"Failed to calculate profitability ratios: {str(e)}")

    def calculate_efficiency_ratios(self) -> RatioAnalysisGroup:
        """Calculate efficiency ratios.
        
        Returns:
            RatioAnalysisGroup containing:
            - asset_turnover
            - inventory_turnover
            - receivables_turnover
            - days_sales_outstanding
        """
        calc_df, equivalents = self.get_ratio_data('efficiency')

        try:
            revenue, revenue_equiv = self._get_concept_value(StandardConcept.REVENUE, calc_df)
            total_assets, assets_equiv = self._get_concept_value(StandardConcept.TOTAL_ASSETS, calc_df)
            inventory, inventory_equiv = self._get_concept_value(StandardConcept.INVENTORY, calc_df)
            cogs, cogs_equiv = self._get_concept_value(StandardConcept.COST_OF_REVENUE, calc_df)
            receivables, receivables_equiv = self._get_concept_value(StandardConcept.ACCOUNTS_RECEIVABLE, calc_df)

            results = {}

            # Asset Turnover
            if total_assets is not None:
                results['asset_turnover'] = RatioAnalysis(
                    name="Asset Turnover",
                    description="Measures how efficiently company uses its assets to generate revenue",
                    calculation_df=calc_df,
                    results=(revenue / total_assets).to_frame().T,
                    components={
                        'revenue': revenue,
                        'total_assets': total_assets
                    },
                    equivalents_used={k: str(v) for k, v in {
                        'revenue': revenue_equiv,
                        'total_assets': assets_equiv
                    }.items() if v is not None}
                )

            # Inventory Turnover
            if inventory is not None and cogs is not None:
                results['inventory_turnover'] = RatioAnalysis(
                    name="Inventory Turnover",
                    description="Measures how quickly inventory is sold and replaced",
                    calculation_df=calc_df,
                    results=(cogs / inventory).to_frame().T,
                    components={
                        'cogs': cogs,
                        'inventory': inventory
                    },
                    equivalents_used={k: str(v) for k, v in {
                        'cogs': cogs_equiv,
                        'inventory': inventory_equiv
                    }.items() if v is not None}
                )

            # Receivables Turnover
            if receivables is not None:
                turnover = revenue / receivables
                results['receivables_turnover'] = RatioAnalysis(
                    name="Receivables Turnover",
                    description="Measures how quickly company collects receivables",
                    calculation_df=calc_df,
                    results=turnover,
                    components={
                        'revenue': revenue,
                        'receivables': receivables
                    },
                    equivalents_used={k: str(v) for k, v in {
                        'revenue': revenue_equiv,
                        'receivables': receivables_equiv
                    }.items() if v is not None}
                )

                # Days Sales Outstanding
                results['days_sales_outstanding'] = RatioAnalysis(
                    name="Days Sales Outstanding",
                    description="Average number of days to collect payment",
                    calculation_df=calc_df,
                    results=(365 / turnover).to_frame().T,
                    components={
                        'receivables_turnover': turnover
                    },
                    equivalents_used={}
                )

            return RatioAnalysisGroup(
                name="Efficiency Ratios",
                description="Measures of company's operational efficiency",
                ratios=results
            )

        except (KeyError, ZeroDivisionError) as e:
            raise ValueError(f"Failed to calculate efficiency ratios: {str(e)}")

    def calculate_leverage_ratios(self) -> RatioAnalysisGroup:
        """Calculate leverage ratios.
        
        Returns:
            RatioAnalysisGroup containing:
            - debt_to_equity
            - debt_to_assets
            - interest_coverage
            - equity_multiplier
        """
        calc_df, equivalents = self.get_ratio_data('leverage')

        try:
            total_debt, debt_equiv = self._get_concept_value(StandardConcept.LONG_TERM_DEBT, calc_df)
            total_equity, equity_equiv = self._get_concept_value(StandardConcept.TOTAL_EQUITY, calc_df)
            total_assets, assets_equiv = self._get_concept_value(StandardConcept.TOTAL_ASSETS, calc_df)
            operating_income, income_equiv = self._get_concept_value(StandardConcept.OPERATING_INCOME, calc_df)
            interest_expense, interest_equiv = self._get_concept_value(StandardConcept.INTEREST_EXPENSE, calc_df)

            results = {}

            # Debt to Equity
            if total_debt is not None and total_equity is not None:
                results['debt_to_equity'] = RatioAnalysis(
                    name="Debt to Equity",
                    description="Measures financial leverage and long-term solvency",
                    calculation_df=calc_df,
                    results=(total_debt / total_equity).to_frame().T,
                    components={
                        'total_debt': total_debt,
                        'total_equity': total_equity
                    },
                    equivalents_used={k: str(v) for k, v in {
                        'total_debt': debt_equiv,
                        'total_equity': equity_equiv
                    }.items() if v is not None}
                )

            # Debt to Assets
            if total_debt is not None and total_assets is not None:
                results['debt_to_assets'] = RatioAnalysis(
                    name="Debt to Assets",
                    description="Measures what percentage of assets are financed by debt",
                    calculation_df=calc_df,
                    results=(total_debt / total_assets).to_frame().T,
                    components={
                        'total_debt': total_debt,
                        'total_assets': total_assets
                    },
                    equivalents_used={k: str(v) for k, v in {
                        'total_debt': debt_equiv,
                        'total_assets': assets_equiv
                    }.items() if v is not None}
                )

            # Interest Coverage
            if operating_income is not None and interest_expense is not None:
                results['interest_coverage'] = RatioAnalysis(
                    name="Interest Coverage",
                    description="Measures ability to meet interest payments",
                    calculation_df=calc_df,
                    results=(operating_income / interest_expense).to_frame().T,
                    components={
                        'operating_income': operating_income,
                        'interest_expense': interest_expense
                    },
                    equivalents_used={k: str(v) for k, v in {
                        'operating_income': income_equiv,
                        'interest_expense': interest_equiv
                    }.items() if v is not None}
                )

            # Equity Multiplier
            if total_assets is not None and total_equity is not None:
                results['equity_multiplier'] = RatioAnalysis(
                    name="Equity Multiplier",
                    description="Measures financial leverage by assets to equity ratio",
                    calculation_df=calc_df,
                    results=(total_assets / total_equity).to_frame().T,
                    components={
                        'total_assets': total_assets,
                        'total_equity': total_equity
                    },
                    equivalents_used={k: str(v) for k, v in {
                        'total_assets': assets_equiv,
                        'total_equity': equity_equiv
                    }.items() if v is not None}
                )

            return RatioAnalysisGroup(
                name="Leverage Ratios",
                description="Measures of company's financial leverage and solvency",
                ratios=results
            )

        except (KeyError, ZeroDivisionError) as e:
            raise ValueError(f"Failed to calculate leverage ratios: {str(e)}")

    def calculate_liquidity_ratios(self) -> RatioAnalysisGroup:
        """Calculate all liquidity ratios.

        Returns:
            RatioAnalysisGroup containing all liquidity ratios
        """
        try:
            ratios = {}
            ratios['current'] = self.calculate_current_ratio()
            ratios['quick'] = self.calculate_quick_ratio()
            ratios['cash'] = self.calculate_cash_ratio()
            ratios['working_capital'] = self.calculate_working_capital()

            return RatioAnalysisGroup(
                name="Liquidity Ratios",
                description="Measures of a company's ability to pay short-term obligations",
                ratios=ratios
            )
        except ValueError as e:
            raise ValueError(f"Failed to calculate liquidity ratios: {str(e)}")

    def calculate_all(self) -> Dict[str, Union[Dict[str, RatioAnalysis], RatioAnalysisGroup]]:
        """Calculate all available financial ratios."""
        try:
            return {
                'liquidity': self.calculate_liquidity_ratios(),
                'profitability': self.calculate_profitability_ratios(),
                'efficiency': self.calculate_efficiency_ratios(),
                'leverage': self.calculate_leverage_ratios()
            }
        except ValueError as e:
            raise ValueError(f"Failed to calculate all ratios: {str(e)}")
